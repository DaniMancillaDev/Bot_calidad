"""
Management command: sync_evidencias

Sincroniza EvidenciaFotografica con las fotos reales en disco.
Para cada RegistroDefecto con fotos_nums, crea o actualiza la
EvidenciaFotografica correspondiente apuntando al archivo real.

Uso:
    uv run python web/manage.py sync_evidencias
    uv run python web/manage.py sync_evidencias --dry-run
"""
import os

from django.core.management.base import BaseCommand
from django.conf import settings
from calidad.models import RegistroDefecto, EvidenciaFotografica
from calidad.utils import get_best_image_path


class Command(BaseCommand):
    help = "Sincroniza EvidenciaFotografica con archivos reales en disco"

    def add_arguments(self, parser):
        parser.add_argument("--dry-run", action="store_true", help="Solo reportar, no modificar DB")

    def handle(self, *args, **options):
        dry_run = options["dry_run"]
        fotos_dir = settings.MEDIA_ROOT / "fotos"

        registros = RegistroDefecto.objects.exclude(fotos_nums__exact=[]).prefetch_related("evidencias_v2")

        creadas = 0
        actualizadas = 0
        sin_archivo = 0
        total_registros = 0

        for reg in registros:
            total_registros += 1
            existentes = {ev.orden: ev for ev in reg.evidencias_v2.all()}

            for idx, num in enumerate(reg.fotos_nums):
                real_path = get_best_image_path(fotos_dir, str(reg.user_id), num)

                if real_path is None:
                    sin_archivo += 1
                    self.stdout.write(
                        self.style.WARNING(f"  FALTA: Registro {reg.id}, foto {num:03d} (user {reg.user_id})")
                    )
                    continue

                # Ruta relativa desde MEDIA_ROOT
                try:
                    ruta_rel = str(real_path.relative_to(settings.MEDIA_ROOT))
                except ValueError:
                    ruta_rel = str(real_path)

                if idx in existentes:
                    ev = existentes[idx]
                    if ev.ruta_archivo != ruta_rel:
                        if not dry_run:
                            ev.ruta_archivo = ruta_rel
                            ev.es_portada = (idx == 0)
                            ev.save(update_fields=["ruta_archivo", "es_portada"])
                        actualizadas += 1
                else:
                    if not dry_run:
                        EvidenciaFotografica.objects.create(
                            registro=reg,
                            ruta_archivo=ruta_rel,
                            orden=idx,
                            es_portada=(idx == 0),
                        )
                    creadas += 1

        prefix = "[DRY-RUN] " if dry_run else ""
        self.stdout.write(self.style.SUCCESS(
            f"{prefix}Done. Registros: {total_registros} | "
            f"Creadas: {creadas} | Actualizadas: {actualizadas} | Sin archivo: {sin_archivo}"
        ))
