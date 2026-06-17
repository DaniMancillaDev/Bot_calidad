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

class RegistroDefecto(models.Model):
    """Tabla principal del bot: cada defecto fotografiado."""
    # ── Campos originales (NO modificar — backward compat) ─────────────────
    fotos          = models.TextField()              # Legacy: "1, 2, 3"
    modelo         = models.TextField()
    numero_parte   = models.CharField(max_length=50, null=True, blank=True)
    linea          = models.TextField()
    cantidad       = models.IntegerField(null=True, blank=True)
    responsable    = models.TextField()
    descripcion    = models.TextField()
    fecha_registro = models.DateTimeField(auto_now_add=True, null=True, blank=True)
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


# ============================================================
# CONTADORES DE FOTO POR GRUPO (turno + depto)
# ============================================================

class ContadorUsuario(models.Model):
    """Secuencia de numeración de fotos individual por usuario."""
    telegram_user_id = models.BigIntegerField(unique=True, db_index=True)
    contador_actual = models.IntegerField(default=1)

    class Meta:
        db_table            = 'contadores_usuario'
        verbose_name        = 'Contador de Usuario'
        verbose_name_plural = 'Contadores de Usuario'

    def __str__(self):
        return f"Usuario {self.telegram_user_id} → {self.contador_actual}"


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
