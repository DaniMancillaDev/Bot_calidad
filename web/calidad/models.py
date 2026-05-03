"""
Modelos Django para el Panel de Calidad - Versión Multiusuario.

Las tablas del bot usan managed = False → Django las lee pero NO las modifica.
Las tablas gestionadas por Django tienen managed = True (default).
"""
import json
from django.db import models
from django.contrib.auth.models import User


# ============================================================
# TABLAS DEL BOT (managed = False - solo lectura)
# ============================================================

class RegistroDefecto(models.Model):
    """
    Mapea la tabla registros_defectos creada por database.py (versión multiusuario).
    """
    fotos          = models.TextField()
    modelo         = models.TextField()
    linea          = models.TextField()
    cantidad       = models.IntegerField(null=True, blank=True)
    responsable    = models.TextField()
    descripcion    = models.TextField()
    fecha_registro = models.DateTimeField(null=True, blank=True)
    # Campos multiusuario:
    user_id        = models.IntegerField(null=True, blank=True)
    turno          = models.CharField(max_length=1, null=True, blank=True)
    departamento   = models.CharField(max_length=10, null=True, blank=True)

    class Meta:
        managed  = False
        db_table = 'registros_defectos'
        ordering = ['-fecha_registro']
        verbose_name        = 'Registro de Defecto'
        verbose_name_plural = 'Registros de Defectos'

    def __str__(self):
        return f"{self.fotos} | {self.modelo} | {self.responsable}"




    def __str__(self):
        return f"{self.telegram_user_id} - Turno {self.turno} - {self.departamento}"


# ============================================================
# TABLAS DJANGO (managed = True)
# ============================================================

class Turno(models.TextChoices):
    A = 'A', 'Turno A'
    B = 'B', 'Turno B'
    C = 'C', 'Turno C'


class Departamento(models.TextChoices):
    IQA = 'IQA', 'IQA (Inspección de Calidad)'
    SQA = 'SQA', 'SQA (Aseguramiento de Calidad)'
    PROD = 'PROD', 'Producción'
    ENG = 'ENG', 'Ingeniería'


class PerfilUsuario(models.Model):
    """
    Extiende el Usuario de Django con turno y departamento.
    Vinculado con usuarios_bot via telegram_user_id.
    """
    usuario          = models.OneToOneField(User, on_delete=models.CASCADE, related_name='perfil')
    turno            = models.CharField(max_length=1, choices=Turno.choices, default=Turno.A)
    departamento     = models.CharField(max_length=10, choices=Departamento.choices, default=Departamento.IQA)
    rol              = models.CharField(max_length=20, default='operador')
    telegram_user_id = models.IntegerField(null=True, blank=True, help_text='ID de Telegram del operador')

    class Meta:
        verbose_name        = 'Perfil de Usuario'
        verbose_name_plural = 'Perfiles de Usuarios'

    def __str__(self):
        return f"{self.usuario.get_full_name() or self.usuario.username} — {self.turno}/{self.departamento}"


