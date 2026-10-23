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


def create_empty_pending_group(user):
    """Create an editable draft without claiming evidence yet."""
    return PendingEvidenceGroup.objects.create(operator=user, created_by=user)


def _normalise_draft_order(group):
    evidences = list(
        PendingEvidence.objects.select_for_update()
        .filter(
            group=group,
            status=PendingEvidence.STATUS_READY,
            is_excluded=False,
        )
        .order_by('draft_order', 'received_at', 'id')
    )
    for order, evidence in enumerate(evidences, start=1):
        evidence.draft_order = order
    if evidences:
        PendingEvidence.objects.bulk_update(evidences, ['draft_order'])


def _clear_exclusion(evidence):
    evidence.is_excluded = False
    evidence.exclusion_reason = ''
    evidence.excluded_at = None
    evidence.excluded_by = None


def update_pending_group(user, group_id, action, evidence_ids=(), fields=None):
    """Persist draft assignments or fields without creating a definitive record."""
    with transaction.atomic():
        group = PendingEvidenceGroup.objects.select_for_update().get(pk=group_id)
        if not user.is_superuser and group.operator_id != user.id:
            raise PendingEvidenceError('No tienes permiso para editar este borrador.')
        if group.status != PendingEvidenceGroup.STATUS_DRAFT:
            raise PendingEvidenceConflict('Este borrador ya no está disponible.')

        ids = list(dict.fromkeys(evidence_ids))
        if action in {'add', 'remove', 'exclude', 'restore', 'reorder'} and not ids:
            raise PendingEvidenceError('Selecciona al menos una fotografía.')
        if action == 'add':
            evidences = list(PendingEvidence.objects.select_for_update().filter(
                id__in=ids,
                status=PendingEvidence.STATUS_READY,
                group__isnull=True,
                is_excluded=False,
            ))
            if len(evidences) != len(ids):
                raise PendingEvidenceConflict(
                    'Una o más fotografías ya fueron asignadas a otro borrador.'
                )
            next_order = (
                PendingEvidence.objects.filter(group=group, is_excluded=False)
                .order_by('-draft_order')
                .values_list('draft_order', flat=True)
                .first()
                or 0
            )
            for evidence_id in ids:
                next_order += 1
                PendingEvidence.objects.filter(pk=evidence_id).update(
                    group=group,
                    draft_order=next_order,
                )
        elif action == 'remove':
            evidences = list(PendingEvidence.objects.select_for_update().filter(
                id__in=ids,
                group=group,
            ))
            if len(evidences) != len(ids):
                raise PendingEvidenceConflict('Una o más fotografías ya no pertenecen a este borrador.')
            for evidence in evidences:
                _clear_exclusion(evidence)
                evidence.group = None
                evidence.draft_order = 0
            if evidences:
                PendingEvidence.objects.bulk_update(
                    evidences,
                    ['group', 'draft_order', 'is_excluded', 'exclusion_reason', 'excluded_at', 'excluded_by'],
                )
            _normalise_draft_order(group)
        elif action == 'exclude':
            reason = str((fields or {}).get('exclusion_reason', '')).strip()[:255]
            evidences = list(PendingEvidence.objects.select_for_update().filter(
                id__in=ids,
                group=group,
                status=PendingEvidence.STATUS_READY,
                is_excluded=False,
            ))
            if len(evidences) != len(ids):
                raise PendingEvidenceConflict('Una o más fotografías ya no están disponibles para excluir.')
            now = timezone.now()
            for evidence in evidences:
                evidence.is_excluded = True
                evidence.exclusion_reason = reason or 'Excluida por el operador.'
                evidence.excluded_at = now
                evidence.excluded_by = user
            if evidences:
                PendingEvidence.objects.bulk_update(
                    evidences,
                    ['is_excluded', 'exclusion_reason', 'excluded_at', 'excluded_by'],
                )
            _normalise_draft_order(group)
        elif action == 'restore':
            evidences = list(PendingEvidence.objects.select_for_update().filter(
                id__in=ids,
                group=group,
                status=PendingEvidence.STATUS_READY,
                is_excluded=True,
            ))
            if len(evidences) != len(ids):
                raise PendingEvidenceConflict('Una o más fotografías ya no están excluidas de este borrador.')
            for evidence in evidences:
                _clear_exclusion(evidence)
            if evidences:
                PendingEvidence.objects.bulk_update(
                    evidences,
                    ['is_excluded', 'exclusion_reason', 'excluded_at', 'excluded_by'],
                )
            _normalise_draft_order(group)
        elif action == 'reorder':
            current_ids = list(
                PendingEvidence.objects.select_for_update()
                .filter(
                    group=group,
                    status=PendingEvidence.STATUS_READY,
                    is_excluded=False,
                )
                .values_list('id', flat=True)
            )
            if len(ids) != len(current_ids) or set(ids) != set(current_ids):
                raise PendingEvidenceConflict('El orden enviado no coincide con las fotografías del borrador.')
            for order, evidence_id in enumerate(ids, start=1):
                PendingEvidence.objects.filter(pk=evidence_id, group=group).update(draft_order=order)
        elif action == 'save_fields':
            values = fields or {}
            quantity_raw = str(values.get('quantity', '')).strip()
            quantity = None
            if quantity_raw:
                try:
                    quantity = int(quantity_raw)
                except ValueError as exc:
                    raise PendingEvidenceError('La cantidad debe ser un número entero.') from exc
                if quantity <= 0:
                    raise PendingEvidenceError('La cantidad debe ser mayor que cero.')
            group.model = str(values.get('model', '')).strip()[:255]
            group.line = str(values.get('line', '')).strip()[:100]
            group.quantity = quantity
            group.responsible = str(values.get('responsible', '')).strip()[:100]
            group.description = str(values.get('description', '')).strip()
            group.save(update_fields=[
                'model', 'line', 'quantity', 'responsible', 'description', 'updated_at',
            ])
        else:
            raise PendingEvidenceError('Operación de borrador no reconocida.')
    return group


def restore_unassigned_evidence(user, evidence_ids):
    """Make excluded, unassigned evidence available again without touching its file."""
    ids = list(dict.fromkeys(evidence_ids))
    if not ids:
        raise PendingEvidenceError('Selecciona al menos una fotografía.')
    with transaction.atomic():
        evidences = list(PendingEvidence.objects.select_for_update().filter(
            id__in=ids,
            status=PendingEvidence.STATUS_READY,
            group__isnull=True,
            is_excluded=True,
        ))
        if len(evidences) != len(ids):
            raise PendingEvidenceConflict('Una o más fotografías ya no están disponibles para recuperar.')
        for evidence in evidences:
            _clear_exclusion(evidence)
            evidence.draft_order = 0
        if evidences:
            PendingEvidence.objects.bulk_update(
                evidences,
                ['is_excluded', 'exclusion_reason', 'excluded_at', 'excluded_by', 'draft_order'],
            )
    return evidences


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
            evidence.status != PendingEvidence.STATUS_READY or evidence.group_id or evidence.is_excluded
            for evidence in evidences
        ):
            raise PendingEvidenceConflict(
                'Una o más fotografías ya fueron agrupadas o no están disponibles.'
            )

        group = PendingEvidenceGroup.objects.create(
            operator=user,
            created_by=user,
        )
        for order, evidence_id in enumerate(ids, start=1):
            PendingEvidence.objects.filter(pk=evidence_id).update(
                group=group,
                draft_order=order,
            )
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

            all_evidences = list(
                PendingEvidence.objects.select_for_update()
                .filter(group=group)
                .order_by('is_excluded', 'draft_order', 'received_at', 'id')
            )
            evidences = [evidence for evidence in all_evidences if not evidence.is_excluded]
            if not evidences or any(
                evidence.status != PendingEvidence.STATUS_READY
                for evidence in all_evidences
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
                        'receipt_batch_key': evidence.receipt_batch_key,
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
            PendingEvidence.objects.filter(group=group, is_excluded=False).update(
                status=PendingEvidence.STATUS_ARCHIVED,
                draft_order=0,
            )
            PendingEvidence.objects.filter(group=group, is_excluded=True).update(
                group=None,
                draft_order=0,
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
