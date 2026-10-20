"""Internal, receive-only ingestion endpoint for WhatsApp evidence."""

import hashlib
import logging
import os
import secrets
import uuid
from datetime import timedelta, timezone as dt_timezone
from pathlib import Path

from django.conf import settings
from django.db import IntegrityError, transaction
from django.db.models import F
from django.http import JsonResponse
from django.utils import timezone
from django.utils.dateparse import parse_datetime
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST
from PIL import Image, UnidentifiedImageError

from calidad.models import PendingEvidence, WhatsAppContact

logger = logging.getLogger(__name__)

_IMAGE_FORMATS = {
    'JPEG': ('image/jpeg', '.jpg'),
    'PNG': ('image/png', '.png'),
    'WEBP': ('image/webp', '.webp'),
}


class IngestInputError(ValueError):
    pass


def _error(message, status):
    return JsonResponse({'error': message}, status=status)


def _authenticated(request):
    expected = getattr(settings, 'WHATSAPP_INGEST_API_KEY', None)
    supplied = request.headers.get('X-WhatsApp-Ingest-Key', '')
    return bool(expected and supplied and secrets.compare_digest(supplied, expected))


def _text(request, name, required=False, max_length=None):
    value = (request.POST.get(name) or '').strip()
    if required and not value:
        raise IngestInputError(f'{name} is required')
    if max_length is not None and len(value) > max_length:
        raise IngestInputError(f'{name} is too long')
    return value


def _message_datetime(raw_value):
    if not raw_value:
        return None
    parsed = parse_datetime(raw_value)
    if parsed is None:
        raise IngestInputError('message_at must be a valid ISO-8601 datetime')
    if timezone.is_naive(parsed):
        parsed = parsed.replace(tzinfo=dt_timezone.utc)
    return parsed


def _validate_upload(uploaded_file):
    if uploaded_file is None:
        raise IngestInputError('file is required')

    max_bytes = getattr(settings, 'WHATSAPP_MAX_IMAGE_BYTES', 25 * 1024 * 1024)
    if uploaded_file.size is None or uploaded_file.size <= 0:
        raise IngestInputError('file must not be empty')
    if uploaded_file.size > max_bytes:
        raise IngestInputError('file is too large')

    try:
        uploaded_file.seek(0)
        with Image.open(uploaded_file) as image:
            image.verify()
            image_format = image.format
    except (UnidentifiedImageError, OSError, Image.DecompressionBombError) as exc:
        raise IngestInputError('file is not a valid image') from exc
    finally:
        uploaded_file.seek(0)

    if image_format not in _IMAGE_FORMATS:
        raise IngestInputError('image format is not allowed')
    mime_type, suffix = _IMAGE_FORMATS[image_format]
    return mime_type, suffix


def _upsert_contact(sender_id, sender_name, phone_number, phone_verified):
    if not sender_id:
        return None

    defaults = {
        'display_name': sender_name,
        'phone_number': phone_number if phone_verified else None,
    }
    contact, created = WhatsAppContact.objects.get_or_create(
        whatsapp_id=sender_id,
        defaults=defaults,
    )

    updates = []
    # Never overwrite an operator-assigned name with a later WhatsApp label.
    if not created and not contact.display_name and sender_name:
        contact.display_name = sender_name
        updates.append('display_name')
    # Only attach a number when the source explicitly verified that relation.
    if phone_verified and phone_number and not contact.phone_number:
        contact.phone_number = phone_number
        updates.append('phone_number')
    if updates:
        contact.save(update_fields=[*updates, 'updated_at'])
    return contact


def _claim_evidence(data, contact):
    lookup = {
        'source': PendingEvidence.SOURCE_WHATSAPP,
        'source_group_id': data['group_id'],
        'source_message_id': data['message_id'],
        'media_index': data['media_index'],
    }
    defaults = {
        'source_group_name': data['group_name'],
        'sender': contact,
        'sender_whatsapp_id': data['sender_id'],
        'caption': data['caption'],
        'message_at': data['message_at'],
        'processing_started_at': timezone.now(),
        'status': PendingEvidence.STATUS_PROCESSING,
        'attempts': 1,
    }

    try:
        with transaction.atomic():
            evidence, created = PendingEvidence.objects.get_or_create(
                defaults=defaults,
                **lookup,
            )
    except IntegrityError:
        evidence = PendingEvidence.objects.get(**lookup)
        created = False

    if created:
        return evidence, True

    if evidence.status == PendingEvidence.STATUS_PROCESSING and not evidence.file_path:
        lease_seconds = getattr(settings, 'WHATSAPP_PROCESSING_LEASE_SECONDS', 300)
        stale_before = timezone.now() - timedelta(seconds=lease_seconds)
        claimed = PendingEvidence.objects.filter(
            pk=evidence.pk,
            status=PendingEvidence.STATUS_PROCESSING,
            file_path='',
            attempts=evidence.attempts,
            processing_started_at__lte=stale_before,
        ).update(
            attempts=F('attempts') + 1,
            processing_started_at=timezone.now(),
        )
        if claimed:
            evidence.refresh_from_db()
            return evidence, True
        evidence.refresh_from_db()
        return evidence, False

    if evidence.status != PendingEvidence.STATUS_FAILED:
        return evidence, False

    claimed = PendingEvidence.objects.filter(
        pk=evidence.pk,
        status=PendingEvidence.STATUS_FAILED,
        attempts=evidence.attempts,
    ).update(
        status=PendingEvidence.STATUS_PROCESSING,
        attempts=F('attempts') + 1,
        processing_started_at=timezone.now(),
        error_message='',
    )
    if not claimed:
        evidence.refresh_from_db()
        return evidence, False
    evidence.refresh_from_db()
    return evidence, True


def _write_pending_file(uploaded_file, evidence_id, suffix):
    root = Path(settings.WHATSAPP_PENDING_ROOT).resolve()
    media_root = Path(settings.MEDIA_ROOT).resolve()
    try:
        root.relative_to(media_root)
    except ValueError:
        pass
    else:
        raise RuntimeError('WhatsApp pending root must not be inside MEDIA_ROOT')

    target_dir = root / str(evidence_id)
    target_dir.mkdir(parents=True, exist_ok=True)
    temporary_path = target_dir / f'.upload-{uuid.uuid4().hex}.tmp'
    final_path = target_dir / f'original{suffix}'
    digest = hashlib.sha256()
    size = 0

    try:
        with temporary_path.open('wb') as destination:
            for chunk in uploaded_file.chunks():
                digest.update(chunk)
                size += len(chunk)
                destination.write(chunk)
            destination.flush()
            os.fsync(destination.fileno())
        os.replace(temporary_path, final_path)
    except Exception:
        temporary_path.unlink(missing_ok=True)
        raise

    return str(final_path.relative_to(root)), digest.hexdigest(), size


@csrf_exempt
@require_POST
def ingest(request):
    """Receive one image. This endpoint never creates RegistroDefecto."""
    if not _authenticated(request):
        return _error('invalid or missing WhatsApp credential', 401)

    try:
        group_id = _text(request, 'group_id', required=True, max_length=255)
        if group_id not in getattr(settings, 'WHATSAPP_ALLOWED_GROUP_IDS', frozenset()):
            return _error('group is not authorized', 403)

        historical = _text(request, 'historical').lower() in {'1', 'true', 'yes'}
        if historical and not getattr(settings, 'WHATSAPP_ALLOW_HISTORICAL', False):
            return _error('historical messages are disabled', 400)

        message_id = _text(request, 'message_id', required=True, max_length=255)
        media_index_raw = _text(request, 'media_index') or '0'
        media_index = int(media_index_raw)
        if media_index < 0 or media_index > 2147483647:
            raise IngestInputError('media_index must be non-negative')

        image = request.FILES.get('file')
        mime_type, suffix = _validate_upload(image)
        data = {
            'group_id': group_id,
            'group_name': _text(request, 'group_name', max_length=255),
            'message_id': message_id,
            'media_index': media_index,
            'sender_id': _text(request, 'sender_id', max_length=255),
            'sender_name': _text(request, 'sender_name', max_length=255),
            'caption': request.POST.get('caption', ''),
            'message_at': _message_datetime(_text(request, 'message_at')),
        }
        phone_number = _text(request, 'phone_number', max_length=40)
        phone_verified = _text(request, 'phone_number_verified').lower() in {'1', 'true', 'yes'}

        with transaction.atomic():
            contact = _upsert_contact(
                data['sender_id'],
                data['sender_name'],
                phone_number,
                phone_verified,
            )
            evidence, should_store = _claim_evidence(data, contact)

        if not should_store:
            return JsonResponse({
                'id': str(evidence.id),
                'status': evidence.status,
                'duplicate': True,
            })

        try:
            file_path, sha256, size_bytes = _write_pending_file(image, evidence.id, suffix)
        except Exception:
            logger.exception('WhatsApp evidence storage failed')
            PendingEvidence.objects.filter(pk=evidence.pk).update(
                status=PendingEvidence.STATUS_FAILED,
                processing_started_at=None,
                error_message='storage failed; resend the same message to retry',
            )
            return _error('temporary storage failure', 503)

        PendingEvidence.objects.filter(pk=evidence.pk).update(
            file_path=file_path,
            sha256=sha256,
            mime_type=mime_type,
            size_bytes=size_bytes,
            status=PendingEvidence.STATUS_READY,
            processing_started_at=None,
            error_message='',
        )
        return JsonResponse({
            'id': str(evidence.id),
            'status': PendingEvidence.STATUS_READY,
            'duplicate': False,
        }, status=201)
    except (IngestInputError, ValueError):
        return _error('invalid ingestion payload', 400)
