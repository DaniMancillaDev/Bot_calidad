"""Create definitive records from manually grouped pending evidence."""

import logging
import os
import shutil
import uuid
from pathlib import Path

from django.conf import settings
from django.db import transaction
from django.utils import timezone

from calidad.models import (
    EstadoRevision,
    EvidenciaFotografica,
    PendingEvidence,
    PendingEvidenceGroup,
    RegistroDefecto,
)

logger = logging.getLogger(__name__)


class PendingEvidenceError(ValueError):
    """A user-correctable pending-evidence operation error."""


class PendingEvidenceConflict(PendingEvidenceError):
    """The group or one of its files changed before this request completed."""


def _normalise_group_fields(fields):
    model = str(fields.get('model', '')).strip()
    line = str(fields.get('line', '')).strip()
    responsible = str(fields.get('responsible', '')).strip()
    description = str(fields.get('description', '')).strip()
    quantity_raw = str(fields.get('quantity', '')).strip()

    if not all((model, line, responsible, description, quantity_raw)):
        raise PendingEvidenceError('Completa todos los campos del registro.')
    try:
        quantity = int(quantity_raw)
    except ValueError as exc:
        raise PendingEvidenceError('La cantidad debe ser un número entero.') from exc
    if quantity <= 0:
        raise PendingEvidenceError('La cantidad debe ser mayor que cero.')
    return {
        'modelo': model.upper(),
        'linea': line.upper(),
        'cantidad': quantity,
        'responsable': responsible.upper(),
        'descripcion': description,
    }


def _source_path(evidence):
    root = Path(settings.WHATSAPP_PENDING_ROOT).resolve()
    source = (root / evidence.file_path).resolve()
    try:
        source.relative_to(root)
    except ValueError as exc:
        raise PendingEvidenceError('La ruta de una evidencia no es válida.') from exc
    if not source.is_file():
        raise PendingEvidenceError(
            f'No se encontró el archivo de evidencia {evidence.source_message_id}.'
        )
    return source


def _copy_to_media(source, evidence, user_id):
    target_root = Path(settings.FOTOS_ROOT).resolve()
    target_dir = target_root / str(user_id)
    target_dir.mkdir(parents=True, exist_ok=True)
    suffix = source.suffix.lower() or '.jpg'
    filename = f'wa_{evidence.id}{suffix}'
    target = target_dir / filename
    temporary = target_dir / f'.{filename}.{uuid.uuid4().hex}.tmp'

    try:
        with source.open('rb') as src, temporary.open('wb') as dst:
            shutil.copyfileobj(src, dst, length=1024 * 1024)
            dst.flush()
            os.fsync(dst.fileno())
        os.replace(temporary, target)
    except Exception:
        temporary.unlink(missing_ok=True)
        raise
    return target, f'fotos/{user_id}/{filename}'


def _user_storage_identity(user):
    profile = getattr(user, 'perfil', None)
    return (
        profile.telegram_user_id if profile and profile.telegram_user_id is not None else user.id,
        profile.turno if profile else '',
        profile.departamento if profile else '',
    )


def create_pending_group(user, evidence_ids):
    """Claim ready, unassigned evidence in one transaction."""
    ids = list(dict.fromkeys(evidence_ids))
    if not ids:
        raise PendingEvidenceError('Selecciona al menos una fotografía.')

    with transaction.atomic():
        evidences = list(
            PendingEvidence.objects.select_for_update()
            .filter(id__in=ids)
            .order_by('received_at', 'id')
        )
        if len(evidences) != len(ids):
            raise PendingEvidenceError('Una o más fotografías ya no existen.')
        if any(
            evidence.status != PendingEvidence.STATUS_READY or evidence.group_id
            for evidence in evidences
        ):
            raise PendingEvidenceConflict(
                'Una o más fotografías ya fueron agrupadas o no están disponibles.'
            )

        group = PendingEvidenceGroup.objects.create(
            operator=user,
            created_by=user,
        )
        PendingEvidence.objects.filter(id__in=ids).update(group=group)
    return group


def confirm_pending_group(user, group_id, fields):
    """Copy files and create the definitive record exactly once."""
    values = _normalise_group_fields(fields)
    created_targets = []

    try:
        with transaction.atomic():
            group = (
                PendingEvidenceGroup.objects.select_for_update()
                .get(pk=group_id)
            )
            if not user.is_superuser and group.operator_id != user.id:
                raise PendingEvidenceError('No tienes permiso para confirmar este grupo.')
            if group.status != PendingEvidenceGroup.STATUS_DRAFT:
                raise PendingEvidenceConflict('Este grupo ya fue confirmado o archivado.')

            evidences = list(
                PendingEvidence.objects.select_for_update()
                .filter(group=group)
                .order_by('received_at', 'id')
            )
            if not evidences or any(
                evidence.status != PendingEvidence.STATUS_READY
                for evidence in evidences
            ):
                raise PendingEvidenceConflict(
                    'Todas las fotografías deben estar listas antes de confirmar.'
                )

            user_id, turno, departamento = _user_storage_identity(user)
            evidence_paths = []
            for evidence in evidences:
                source = _source_path(evidence)
                target, relative_path = _copy_to_media(source, evidence, user_id)
                created_targets.append(target)
                evidence_paths.append((evidence, relative_path, target))

            record = RegistroDefecto.objects.create(
                fotos='WEB',
                fotos_nums=[],
                modelo=values['modelo'],
                linea=values['linea'],
                cantidad=values['cantidad'],
                responsable=values['responsable'],
                descripcion=values['descripcion'],
                user_id=user_id,
                turno=turno,
                departamento=departamento,
                estado_revision=EstadoRevision.PENDIENTE,
            )

            for order, (evidence, relative_path, _target) in enumerate(evidence_paths, start=1):
                EvidenciaFotografica.objects.create(
                    registro=record,
                    ruta_archivo=relative_path,
                    orden=order,
                    es_portada=(order == 1),
                    metadatos={
                        'source': PendingEvidence.SOURCE_WHATSAPP,
                        'pending_evidence_id': str(evidence.id),
                        'source_group_id': evidence.source_group_id,
                        'source_message_id': evidence.source_message_id,
                        'sender_whatsapp_id': evidence.sender_whatsapp_id,
                    },
                )

            now = timezone.now()
            group.status = PendingEvidenceGroup.STATUS_CONFIRMED
            group.model = values['modelo']
            group.line = values['linea']
            group.quantity = values['cantidad']
            group.responsible = values['responsable']
            group.description = values['descripcion']
            group.definitive_record = record
            group.confirmed_by = user
            group.confirmed_at = now
            group.save(update_fields=[
                'status', 'model', 'line', 'quantity', 'responsible',
                'description', 'definitive_record', 'confirmed_by',
                'confirmed_at', 'updated_at',
            ])
            PendingEvidence.objects.filter(group=group).update(
                status=PendingEvidence.STATUS_ARCHIVED,
            )

            final_paths = [str(target) for _evidence, _relative, target in evidence_paths]

            def enqueue_thumbnails():
                try:
                    from calidad.tasks import generar_thumbnails_lote_task
                    generar_thumbnails_lote_task.delay(user_id, final_paths)
                except Exception:
                    logger.exception(
                        'Could not enqueue thumbnails for pending group %s', group.id
                    )

            transaction.on_commit(enqueue_thumbnails)
            return group, record
    except Exception:
        # The source remains untouched. Remove only files created by this attempt.
        for target in created_targets:
            try:
                target.unlink(missing_ok=True)
            except OSError:
                logger.exception('Could not clean failed destination %s', target)
        raise
