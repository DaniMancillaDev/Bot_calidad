"""Web interface for grouping and confirming WhatsApp evidence."""

from io import BytesIO
from pathlib import Path
from uuid import UUID

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.conf import settings
from django.core.exceptions import ObjectDoesNotExist
from django.http import FileResponse, Http404, HttpResponse, HttpResponseForbidden
from django.core.paginator import Paginator
from django.shortcuts import get_object_or_404, redirect, render
from django.db.models import Q
from django.views.decorators.http import require_GET, require_http_methods, require_POST
from PIL import Image, ImageOps

from .models import PendingEvidence, PendingEvidenceGroup, WhatsAppContact
from .services.pending_evidence import (
    PendingEvidenceError,
    create_pending_group,
    confirm_pending_group,
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


@login_required
@require_http_methods(['GET', 'POST'])
def pending_evidence(request):
    if not _has_pending_access(request.user):
        return HttpResponseForbidden('No tienes acceso a las evidencias pendientes.')

    if request.method == 'POST':
        action = request.POST.get('action', '')
        try:
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

    available_query = (
        PendingEvidence.objects.filter(
            status=PendingEvidence.STATUS_READY,
            group__isnull=True,
        )
        .select_related('sender')
        .order_by('-message_at', '-received_at')
    )
    available_page = Paginator(available_query, 60).get_page(request.GET.get('page'))
    available = list(available_page.object_list)
    groups = list(
        PendingEvidenceGroup.objects.filter(
            status=PendingEvidenceGroup.STATUS_DRAFT,
            **({} if request.user.is_superuser else {'operator': request.user}),
        )
        .prefetch_related('evidences__sender')
        .order_by('-created_at')
    )
    visible_group_evidences = []
    for group in groups:
        group.pending_evidences = list(group.evidences.all())
        _add_image_urls(group.pending_evidences)
        visible_group_evidences.extend(group.pending_evidences)

    contacts = list(
        WhatsAppContact.objects.filter(
            pending_evidences__in=available + visible_group_evidences,
        ).distinct().order_by('display_name', 'id')
    )
    selected_group = request.GET.get('grupo', '')
    return render(request, 'calidad/evidencias_pendientes.html', {
        'available_evidences': _add_image_urls(available),
        'available_total': available_page.paginator.count,
        'pending_page': available_page,
        'pending_groups': groups,
        'pending_contacts': contacts,
        'selected_group': selected_group,
        'seccion': 'pending_evidence',
    })


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
