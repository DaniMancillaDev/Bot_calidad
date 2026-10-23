"""Web interface for grouping and confirming WhatsApp evidence."""

from io import BytesIO
from pathlib import Path
from uuid import UUID

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.conf import settings
from django.core.exceptions import ObjectDoesNotExist
from django.http import FileResponse, Http404, HttpResponse, HttpResponseForbidden, JsonResponse
from django.core.paginator import Paginator
from django.shortcuts import get_object_or_404, redirect, render
from django.db.models import Q
from django.utils import timezone
from django.views.decorators.http import require_GET, require_http_methods, require_POST
from PIL import Image, ImageOps

from .models import PendingEvidence, PendingEvidenceGroup, WhatsAppContact
from .services.pending_evidence import (
    PendingEvidenceError,
    create_empty_pending_group,
    create_pending_group,
    confirm_pending_group,
    update_pending_group,
)


def _has_pending_access(user):
    if user.is_superuser:
        return True
    try:
        user.perfil
    except ObjectDoesNotExist:
        return False
    return True


def _visible_evidence(user, evidence):
    return _has_pending_access(user) and (
        user.is_superuser
        or evidence.group_id is None
        or evidence.group.operator_id == user.id
    )


def _parse_ids(values):
    ids = []
    for value in values:
        try:
            ids.append(UUID(str(value)))
        except (TypeError, ValueError):
            raise PendingEvidenceError('La selección contiene una evidencia inválida.')
    return list(dict.fromkeys(ids))


def _add_image_urls(evidences):
    for evidence in evidences:
        base = f'/evidencias-pendientes/{evidence.id}/imagen/'
        evidence.thumbnail_url = f'{base}?size=thumb'
        evidence.original_url = base
    return evidences


def _pending_batches(evidences):
    batches = {}
    for evidence in evidences:
        # Legacy rows have no trustworthy album relation; keep each one isolated.
        key = evidence.receipt_batch_key or f'legacy:{evidence.id}'
        batch = batches.setdefault(key, {
            'key': key,
            'evidences': [],
            'source_group_id': evidence.source_group_id,
            'source_group_name': evidence.source_group_name,
            'message_at': evidence.message_at or evidence.received_at,
            'senders': set(),
            'assigned_group_ids': set(),
            'unassigned_count': 0,
        })
        batch['evidences'].append(evidence)
        sender = evidence.sender.display_name if evidence.sender else ''
        batch['senders'].add(sender or evidence.sender_whatsapp_id or 'Remitente desconocido')
        if evidence.group_id:
            batch['assigned_group_ids'].add(str(evidence.group_id))
        else:
            batch['unassigned_count'] += 1

    result = []
    for index, batch in enumerate(batches.values()):
        sender_names = sorted(batch.pop('senders'))
        batch['sender_label'] = sender_names[0] if len(sender_names) == 1 else f'{len(sender_names)} remitentes'
        batch['sender_count'] = len(sender_names)
        batch['assigned_group_ids'] = sorted(batch['assigned_group_ids'])
        batch['label'] = 'Álbum' if batch['key'].startswith('album:') else 'Envío individual'
        batch['dom_id'] = f'pending-batch-{index}'
        _add_image_urls(batch['evidences'])
        result.append(batch)
    return result


def _pending_evidence_payload(evidence):
    timestamp = evidence.message_at or evidence.received_at
    return {
        'id': str(evidence.id),
        'batch_key': evidence.receipt_batch_key or f'legacy:{evidence.id}',
        'thumb_url': evidence.thumbnail_url,
        'original_url': evidence.original_url,
        'sender': evidence.sender.display_name if evidence.sender else '',
        'sender_id': evidence.sender_whatsapp_id or '',
        'caption': evidence.caption or '',
        'meta': timezone.localtime(timestamp).strftime('%Y-%m-%d %H:%M') if timestamp else '',
        'group_id': str(evidence.group_id) if evidence.group_id else '',
        'group_name': evidence.source_group_name or evidence.source_group_id,
        'status': evidence.get_status_display(),
    }


def _pending_group_payload(group):
    evidences = getattr(group, 'pending_evidences', None)
    if evidences is None:
        evidences = list(group.evidences.all())
    return {
        'id': str(group.id),
        'model': group.model,
        'line': group.line,
        'quantity': group.quantity or '',
        'responsible': group.responsible,
        'description': group.description,
        'status': group.get_status_display(),
        'evidence_ids': [str(evidence.id) for evidence in evidences],
    }


@login_required
@require_http_methods(['GET', 'POST'])
def pending_evidence(request):
    if not _has_pending_access(request.user):
        return HttpResponseForbidden('No tienes acceso a las evidencias pendientes.')

    if request.method == 'POST':
        action = request.POST.get('action', '')
        try:
            if action == 'new_group':
                group = create_empty_pending_group(request.user)
                messages.success(request, 'Borrador creado. Ahora puedes agregar fotografías.')
                return redirect(f'/evidencias-pendientes/?grupo={group.id}')

            if action == 'create_group':
                group = create_pending_group(
                    request.user,
                    _parse_ids(request.POST.getlist('evidence_ids')),
                )
                messages.success(request, 'Grupo creado. Completa sus datos para confirmarlo.')
                return redirect(f'/evidencias-pendientes/?grupo={group.id}')

            if action == 'confirm_group':
                group_id = UUID(request.POST.get('group_id', ''))
                group, record = confirm_pending_group(request.user, group_id, request.POST)
                messages.success(
                    request,
                    f'Registro {record.id} creado con {group.evidences.count()} fotografías.',
                )
                return redirect('pending_evidence')

            raise PendingEvidenceError('Operación no reconocida.')
        except (PendingEvidenceError, ValueError, PendingEvidenceGroup.DoesNotExist) as exc:
            messages.error(request, str(exc))
            return redirect('pending_evidence')

    source_group_filter = request.GET.get('grupo_origen', '').strip()
    sender_filter = request.GET.get('remitente', '').strip()
    order_filter = request.GET.get('orden', 'recent').strip()
    allowed_groups = getattr(settings, 'WHATSAPP_ALLOWED_GROUP_IDS', frozenset())
    if not source_group_filter and len(allowed_groups) == 1:
        source_group_filter = next(iter(allowed_groups))

    visibility = Q(group__isnull=True) | Q(group__operator=request.user)
    if request.user.is_superuser:
        visibility = Q()
    ready_query = PendingEvidence.objects.filter(
        status=PendingEvidence.STATUS_READY,
    ).filter(visibility)
    available_query = (
        ready_query
        .select_related('sender')
        .order_by(*(
            ['message_at', 'received_at']
            if order_filter == 'oldest'
            else ['-message_at', '-received_at']
        ))
    )
    pending_source_groups = list(
        ready_query.values('source_group_id', 'source_group_name').distinct().order_by('source_group_name', 'source_group_id')
    )
    if source_group_filter:
        available_query = available_query.filter(source_group_id=source_group_filter)
    if sender_filter:
        available_query = available_query.filter(
            Q(sender_whatsapp_id=sender_filter) | Q(sender__whatsapp_id=sender_filter),
        )
    available_batches = _pending_batches(list(available_query))
    available_page = Paginator(available_batches, 30).get_page(request.GET.get('page'))
    available = [evidence for batch in available_page.object_list for evidence in batch['evidences']]
    available_total = sum(len(batch['evidences']) for batch in available_batches)
    groups = list(
        PendingEvidenceGroup.objects.filter(
            status=PendingEvidenceGroup.STATUS_DRAFT,
            **({} if request.user.is_superuser else {'operator': request.user}),
        )
        .prefetch_related('evidences__sender')
        .order_by('-created_at')
    )
    for group in groups:
        group.pending_evidences = list(group.evidences.all())
        _add_image_urls(group.pending_evidences)

    contacts = list(
        WhatsAppContact.objects.filter(
            pending_evidences__in=ready_query,
        ).distinct().order_by('display_name', 'id')
    )
    selected_group = request.GET.get('grupo', '')
    payload_evidences = {evidence.id: _pending_evidence_payload(evidence) for evidence in available}
    for group in groups:
        for evidence in group.pending_evidences:
            payload_evidences[evidence.id] = _pending_evidence_payload(evidence)
    work_payload = {
        'evidences': list(payload_evidences.values()),
        'batches': [
            {
                'key': batch['key'],
                'label': batch['label'],
                'source_group_name': batch['source_group_name'] or batch['source_group_id'],
                'message_at': timezone.localtime(batch['message_at']).strftime('%Y-%m-%d %H:%M') if batch['message_at'] else '',
                'sender_label': batch['sender_label'],
                'evidence_ids': [str(evidence.id) for evidence in batch['evidences']],
            }
            for batch in available_page.object_list
        ],
        'groups': [_pending_group_payload(group) for group in groups],
        'active_group': selected_group,
    }
    return render(request, 'calidad/evidencias_pendientes.html', {
        'available_evidences': _add_image_urls(available),
        'available_total': available_total,
        'available_batch_total': len(available_batches),
        'available_batches': available_page.object_list,
        'pending_source_groups': pending_source_groups,
        'selected_source_group': source_group_filter,
        'selected_sender': sender_filter,
        'selected_order': order_filter,
        'pending_work': work_payload,
        'pending_page': available_page,
        'pending_groups': groups,
        'pending_contacts': contacts,
        'selected_group': selected_group,
        'seccion': 'pending_evidence',
    })


@login_required
@require_POST
def create_pending_group_draft(request):
    if not _has_pending_access(request.user):
        return JsonResponse({'error': 'No tienes acceso a las evidencias pendientes.'}, status=403)
    group = create_empty_pending_group(request.user)
    return JsonResponse({'group': _pending_group_payload(group)}, status=201)


@login_required
@require_POST
def update_pending_group_view(request, group_id):
    if not _has_pending_access(request.user):
        return JsonResponse({'error': 'No tienes acceso a las evidencias pendientes.'}, status=403)
    try:
        action = request.POST.get('action', '')
        evidence_ids = _parse_ids(request.POST.getlist('evidence_ids'))
        group = update_pending_group(
            request.user,
            UUID(str(group_id)),
            action,
            evidence_ids=evidence_ids,
            fields=request.POST,
        )
        group.pending_evidences = list(group.evidences.all())
        return JsonResponse({'group': _pending_group_payload(group)})
    except (PendingEvidenceError, ValueError, PendingEvidenceGroup.DoesNotExist) as exc:
        return JsonResponse({'error': str(exc)}, status=409)


@login_required
@require_POST
def rename_pending_contact(request, contact_id):
    if not _has_pending_access(request.user):
        return HttpResponseForbidden('No tienes acceso a los contactos de WhatsApp.')
    contact = get_object_or_404(WhatsAppContact, pk=contact_id)
    if not request.user.is_superuser and not PendingEvidence.objects.filter(
        sender=contact,
    ).filter(
        Q(group__isnull=True) | Q(group__operator=request.user),
    ).exists():
        return HttpResponseForbidden('No tienes acceso a este contacto.')
    name = (request.POST.get('display_name') or '').strip()
    if len(name) > 255:
        messages.error(request, 'El nombre del contacto es demasiado largo.')
    else:
        contact.display_name = name
        contact.save(update_fields=['display_name', 'updated_at'])
        messages.success(request, 'Nombre de contacto actualizado.')
    return redirect('pending_evidence')


def _pending_file(evidence):
    root = Path(settings.WHATSAPP_PENDING_ROOT).resolve()
    path = (root / evidence.file_path).resolve()
    try:
        path.relative_to(root)
    except ValueError as exc:
        raise Http404('Archivo no permitido') from exc
    if not path.is_file():
        raise Http404('Archivo no encontrado')
    return path


@login_required
@require_GET
def pending_evidence_image(request, evidence_id):
    evidence = get_object_or_404(
        PendingEvidence.objects.select_related('group'),
        pk=evidence_id,
    )
    if not _visible_evidence(request.user, evidence):
        raise Http404('Evidencia no encontrada')
    path = _pending_file(evidence)

    if request.GET.get('size') == 'thumb':
        try:
            with Image.open(path) as original:
                image = ImageOps.exif_transpose(original)
                image.thumbnail((360, 360), Image.Resampling.LANCZOS)
                if image.mode not in ('RGB', 'L'):
                    image = image.convert('RGB')
                output = BytesIO()
                image.save(output, format='JPEG', quality=78, optimize=True)
        except (OSError, Image.UnidentifiedImageError) as exc:
            raise Http404('Imagen no válida') from exc
        response = HttpResponse(output.getvalue(), content_type='image/jpeg')
    else:
        response = FileResponse(
            path.open('rb'),
            content_type=evidence.mime_type or 'application/octet-stream',
        )
        response['Content-Disposition'] = f'inline; filename="{path.name}"'

    response['Cache-Control'] = 'private, no-store'
    response['X-Content-Type-Options'] = 'nosniff'
    return response
