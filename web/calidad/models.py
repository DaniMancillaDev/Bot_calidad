"""
Modelos Django para el Panel de Calidad - Versión Multiusuario.

Con PostgreSQL, Django gestiona TODAS las tablas (managed = True).
El bot consume el ORM en lugar de sqlite3 directo.
"""
import json
from django.db import models
from django.contrib.auth.models import User
from django.contrib.postgres.fields import ArrayField


# ============================================================
# CHOICES
# ============================================================

class Turno(models.TextChoices):
    A = 'A', 'Turno A'
    B = 'B', 'Turno B'
    C = 'C', 'Turno C'


class Departamento(models.TextChoices):
    IQA  = 'IQA',  'IQA (Inspección de Calidad)'
    SQA  = 'SQA',  'SQA (Aseguramiento de Calidad)'
    PROD = 'PROD', 'Producción'
    ENG  = 'ENG',  'Ingeniería'


class Linea(models.TextChoices):
    T01 = 'T01', 'Línea T01'
    T02 = 'T02', 'Línea T02'
    T03 = 'T03', 'Línea T03'
    T05 = 'T05', 'Línea T05'
    T06 = 'T06', 'Línea T06'
    T07 = 'T07', 'Línea T07'
    T08 = 'T08', 'Línea T08'
    C01 = 'C01', 'CELDA'
    INCOMING = 'INCOMING', 'Incoming Inspection'


class Responsable(models.TextChoices):
    TSCEM = 'TSCEM', 'TSCEM'
    XM = 'XM', 'XM'
    WH = 'WH', 'Warehouse'


class EstadoRevision(models.TextChoices):
    PENDIENTE  = 'pendiente',  'Pendiente'
    REVISADO   = 'revisado',   'Revisado'
    APROBADO   = 'aprobado',   'Aprobado'
    RECHAZADO  = 'rechazado',  'Rechazado'
    DUPLICADO  = 'duplicado',  'Duplicado'
    BORROSO    = 'borroso',    'Borroso'


# ============================================================
# REGISTROS DE DEFECTOS
# ============================================================

class ProteccionBorradoQuerySet(models.QuerySet):
    def delete(self, force_delete=False):
        if not force_delete:
            raise PermissionError("Borrado masivo bloqueado por seguridad. Usa force_delete=True si es intencional.")
        return super().delete()

class ProteccionBorradoManager(models.Manager):
    def get_queryset(self):
        return ProteccionBorradoQuerySet(self.model, using=self._db)

class RegistroDefecto(models.Model):
    """Tabla principal del bot: cada defecto fotografiado."""
    objects = ProteccionBorradoManager()
    # ── Campos originales (NO modificar — backward compat) ─────────────────
    fotos          = models.TextField()              # Legacy: "1, 2, 3"
    modelo         = models.TextField()
    numero_parte   = models.CharField(max_length=50, null=True, blank=True)
    linea          = models.TextField()
    cantidad       = models.IntegerField(null=True, blank=True)
    responsable    = models.TextField()
    descripcion    = models.TextField()
    fecha_registro = models.DateTimeField(auto_now_add=True, null=True, blank=True, db_index=True)
    user_id        = models.BigIntegerField(db_index=True)
    turno          = models.CharField(max_length=1, null=True, blank=True)
    departamento   = models.CharField(max_length=10, null=True, blank=True)

    # ── Fase 1: Normalización ──────────────────────────────────────────────
    fotos_nums     = ArrayField(
        models.IntegerField(),
        default=list,
        blank=True,
        help_text='IDs de foto como enteros. Reemplaza fotos (TextField) gradualmente.'
    )

    # ── Fase 1: Estados Operativos ─────────────────────────────────────────
    estado_revision = models.CharField(
        max_length=20,
        choices=EstadoRevision.choices,
        default=EstadoRevision.PENDIENTE,
        db_index=True,
    )
    supervisor      = models.ForeignKey(
        'auth.User',
        null=True, blank=True,
        on_delete=models.SET_NULL,
        related_name='registros_revisados',
        help_text='Supervisor que revisó el registro.'
    )
    comentarios_supervisor = models.TextField(blank=True, default='')
    fecha_revision  = models.DateTimeField(null=True, blank=True)
    is_duplicate    = models.BooleanField(default=False, db_index=True)
    is_blurry       = models.BooleanField(default=False)

    class Meta:
        db_table            = 'registros_defectos'
        ordering            = ['-fecha_registro']
        verbose_name        = 'Registro de Defecto'
        verbose_name_plural = 'Registros de Defectos'
        indexes = [
            models.Index(fields=['turno', 'departamento'], name='idx_turno_depto'),
            models.Index(fields=['fecha_registro'],         name='idx_fecha'),
        ]

    def __str__(self):
        return f"{self.fotos} | {self.modelo} | {self.responsable}"

    @property
    def fotos_rango(self):
        import re
        nums = []
        if self.fotos_nums:
            nums = sorted(list(set(self.fotos_nums)))
        elif self.fotos:
            try:
                nums = sorted(list(set(int(x) for x in re.findall(r'\d+', str(self.fotos)))))
            except Exception:
                pass
        
        if not nums:
            return str(self.fotos)

        rangos = []
        inicio = nums[0]
        anterior = nums[0]

        for n in nums[1:]:
            if n == anterior + 1:
                anterior = n
            else:
                if inicio == anterior:
                    rangos.append(f"{inicio:02d}")
                else:
                    rangos.append(f"{inicio:02d}-{anterior:02d}")
                inicio = n
                anterior = n
        
        if inicio == anterior:
            rangos.append(f"{inicio:02d}")
        else:
            rangos.append(f"{inicio:02d}-{anterior:02d}")

        return ", ".join(rangos)

    def clean_transition(self, nuevo_estado):
        """Valida si la transición de estado es permitida."""
        estados_permitidos = {
            EstadoRevision.PENDIENTE: [EstadoRevision.REVISADO, EstadoRevision.APROBADO, EstadoRevision.RECHAZADO],
            EstadoRevision.REVISADO: [EstadoRevision.APROBADO, EstadoRevision.RECHAZADO],
            EstadoRevision.APROBADO: [EstadoRevision.PENDIENTE, EstadoRevision.RECHAZADO],
            EstadoRevision.RECHAZADO: [EstadoRevision.PENDIENTE, EstadoRevision.REVISADO],
        }
        if self.estado_revision == nuevo_estado:
            return True
        if nuevo_estado not in estados_permitidos.get(self.estado_revision, []):
            raise ValueError(f"Transición inválida de {self.estado_revision} a {nuevo_estado}")
        return True

    def transitar_estado(self, nuevo_estado, supervisor=None, comentarios=''):
        self.clean_transition(nuevo_estado)
        self.estado_revision = nuevo_estado
        if supervisor:
            self.supervisor = supervisor
        if comentarios:
            self.comentarios_supervisor = comentarios
        from django.utils import timezone
        self.fecha_revision = timezone.now()
        self.save(update_fields=['estado_revision', 'supervisor', 'comentarios_supervisor', 'fecha_revision'])

    def save(self, *args, **kwargs):
        from .application.workflows.defecto_workflow import DefectoWorkflow
        super().save(*args, **kwargs)

    def aprobar(self, supervisor=None, comentarios=''):
        self.transitar_estado(EstadoRevision.APROBADO, supervisor, comentarios)

    def rechazar(self, supervisor=None, comentarios=''):
        if not comentarios:
            raise ValueError("Se requiere un motivo/comentario para rechazar.")
        self.transitar_estado(EstadoRevision.RECHAZADO, supervisor, comentarios)

    def delete(self, *args, force_delete=False, **kwargs):
        if not force_delete:
            raise PermissionError("Borrado bloqueado por seguridad. Utiliza force_delete=True desde admin o panel web.")
        return super().delete(*args, **kwargs)


# ============================================================
# CONTADORES DE FOTO POR GRUPO (turno + depto)
# ============================================================


# ============================================================
# ESTADO DE CONVERSACIONES (antes en SQLite, ahora Postgres)
# ============================================================

class EstadoConversacion(models.Model):
    """Estado de conversación activo de cada usuario del bot."""
    user_id    = models.BigIntegerField(primary_key=True)
    estado_json = models.JSONField(default=dict)

    class Meta:
        db_table            = 'estado_conversaciones'
        verbose_name        = 'Estado de Conversación'
        verbose_name_plural = 'Estados de Conversación'


# ============================================================
# PERFIL DE USUARIO DJANGO
# ============================================================

class PerfilUsuario(models.Model):
    """Extiende User Django con turno, departamento y Telegram ID."""
    usuario          = models.OneToOneField(User, on_delete=models.CASCADE, related_name='perfil')
    turno            = models.CharField(max_length=1, choices=Turno.choices, default=Turno.A)
    departamento     = models.CharField(max_length=10, choices=Departamento.choices, default=Departamento.IQA)
    rol              = models.CharField(max_length=20, default='operador')
    telegram_user_id = models.BigIntegerField(null=True, blank=True, db_index=True,
                                            help_text='ID de Telegram del operador')

    class Meta:
        verbose_name        = 'Perfil de Usuario'
        verbose_name_plural = 'Perfiles de Usuarios'

    def __str__(self):
        return f"{self.usuario.get_full_name() or self.usuario.username} — {self.turno}/{self.departamento}"


# ============================================================
# EVIDENCIAS FOTOGRAFICAS (V2)
# ============================================================

class EvidenciaFotografica(models.Model):
    """Fase 1: Modelo independiente para las fotos."""
    objects = ProteccionBorradoManager()
    registro = models.ForeignKey(RegistroDefecto, on_delete=models.CASCADE, related_name='evidencias_v2')
    ruta_archivo = models.CharField(max_length=500, help_text="Ruta relativa o absoluta al archivo")
    orden = models.IntegerField(default=0)
    es_portada = models.BooleanField(default=False)
    angulo_rotacion = models.IntegerField(default=0)
    
    # Future Proofing
    estado_ia = models.CharField(max_length=20, default='PENDIENTE') 
    metadatos = models.JSONField(default=dict, blank=True)

    class Meta:
        db_table = 'evidencias_fotograficas'
        ordering = ['registro', 'orden']
        verbose_name = 'Evidencia Fotográfica'
        verbose_name_plural = 'Evidencias Fotográficas'

    def __str__(self):
        return f"Evidencia {self.id} (Registro {self.registro_id})"

    def delete(self, *args, force_delete=False, **kwargs):
        if not force_delete:
            raise PermissionError("Borrado bloqueado por seguridad. Utiliza force_delete=True desde admin o panel web.")
        return super().delete(*args, **kwargs)

class GlobalCounter(models.Model):
    """Secuencia de numeración global de fotos en toda la planta."""
    nombre = models.CharField(max_length=50, unique=True, default='fotos')
    valor_actual = models.BigIntegerField(default=1)

    class Meta:
        db_table = 'global_counter'
        verbose_name = 'Contador Global'
        verbose_name_plural = 'Contadores Globales'

    def __str__(self):
        return f"GlobalCounter({self.nombre}) → {self.valor_actual}"

class NumeroReutilizable(models.Model):
    """
    Pool de números fotográficos liberados tras una cancelación.
    Reglas de negocio:
    - Numeración global.
    - Cancelación libera números al pool.
    - Los números liberados se consumen antes de generar nuevos.
    - La reutilización no conserva propiedad histórica del operador.
    Nota: Esta tabla SOLO contiene números liberados. No representa historial fotográfico.
    """
    numero = models.IntegerField(unique=True, db_index=True)
    fecha_liberacion = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'numeros_reutilizables'
        ordering = ['numero']
        verbose_name = 'Número Reutilizable'
        verbose_name_plural = 'Números Reutilizables'

    def __str__(self):
        return f"Hueco fotográfico: {self.numero}"
