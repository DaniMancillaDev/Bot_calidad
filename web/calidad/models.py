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


class UsuarioBot(models.Model):
    """
    Mapea la tabla usuarios_bot creada por database.py.
    Almacena los usuarios del bot con su turno y departamento.
    """
    telegram_user_id = models.IntegerField(primary_key=True)
    username         = models.TextField(null=True, blank=True)
    turno            = models.CharField(max_length=1)
    departamento     = models.CharField(max_length=10)
    rol              = models.CharField(max_length=20, default='operador')
    fecha_registro   = models.DateTimeField(null=True, blank=True)

    class Meta:
        managed = False
        db_table = 'usuarios_bot'
        ordering = ['-fecha_registro']
        verbose_name = 'Usuario del Bot'
        verbose_name_plural = 'Usuarios del Bot'

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

    def get_usuario_bot(self):
        """Obtiene el registro de usuarios_bot asociado."""
        if self.telegram_user_id:
            try:
                return UsuarioBot.objects.get(telegram_user_id=self.telegram_user_id)
            except UsuarioBot.DoesNotExist:
                return None
        return None

# ============================================================
# SEÑALES (Sincronización Automática)
# ============================================================
from django.db.models.signals import post_save
from django.dispatch import receiver
from django.utils import timezone

@receiver(post_save, sender=PerfilUsuario)
def sync_usuario_bot(sender, instance, created, **kwargs):
    """
    Sincroniza automáticamente el PerfilUsuario (Web) con la tabla usuarios_bot (Bot).
    Si se registra un ID de Telegram en el panel de Django, el bot le da acceso automáticamente.
    """
    if instance.telegram_user_id:
        try:
            bot_user, is_new = UsuarioBot.objects.get_or_create(
                telegram_user_id=instance.telegram_user_id,
                defaults={
                    'username': instance.usuario.username,
                    'turno': instance.turno,
                    'departamento': instance.departamento,
                    'rol': getattr(instance, "rol", "operador"),
                    'fecha_registro': timezone.now()
                }
            )
            if not is_new:
                # Actualizar si ya existía pero cambió turno o depto
                bot_user.turno = instance.turno
                bot_user.departamento = instance.departamento
                bot_user.rol = getattr(instance, "rol", "operador")
                bot_user.username = instance.usuario.username
                bot_user.save()
        except Exception as e:
            print(f"Error sincronizando con usuarios_bot: {e}")
