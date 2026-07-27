import uuid
from django.db import models
from django.conf import settings

class ImportSession(models.Model):
    STATUS_CHOICES = (
        ('UPLOADING', 'Subiendo archivos'),
        ('PROCESSING', 'Procesando en Celery'),
        ('DRAFT', 'Borrador listo para editar'),
        ('READY', 'Validado y listo para confirmar'),
        ('CONFIRMED', 'Confirmado e insertado'),
        ('EXPIRED', 'Expirado'),
        ('FAILED', 'Error en el procesamiento'),
    )
    
    uuid = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    supervisor = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='UPLOADING', db_index=True)
    
    excel_original_name = models.CharField(max_length=255)
    zip_original_name = models.CharField(max_length=255)
    zip_extract_path = models.CharField(max_length=500)  # Ruta relativa a MEDIA_ROOT
    
    column_mapping = models.JSONField(default=dict, blank=True)
    total_rows = models.PositiveIntegerField(default=0)
    validated_rows = models.PositiveIntegerField(default=0)
    
    error_message = models.TextField(blank=True, null=True)  # Manejo de errores en Celery
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    def __str__(self):
        return f"Session {self.uuid} - {self.status}"


class DraftRegistro(models.Model):
    session = models.ForeignKey(ImportSession, on_delete=models.CASCADE, related_name='drafts')
    row_index = models.PositiveIntegerField(help_text="Número de fila en el Excel (1-indexado)")
    
    raw_data = models.JSONField()  # Datos crudos del Excel
    mapped_data = models.JSONField(default=dict, blank=True)  # Datos mapeados (ej: modelo, cantidad)
    assigned_photos = models.JSONField(default=list, blank=True)  # Nombres de archivo relativos al ZIP
    
    validation_errors = models.JSONField(default=list, blank=True)
    is_valid = models.BooleanField(default=False)
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        unique_together = ('session', 'row_index')
        indexes = [
            models.Index(fields=['session', 'is_valid']),
        ]

    def __str__(self):
        return f"Draft {self.row_index} - Valid: {self.is_valid}"
