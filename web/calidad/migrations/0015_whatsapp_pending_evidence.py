# Generated manually for the WhatsApp pending-evidence intake.
import uuid

from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ('calidad', '0014_registrodefecto_wo_alter_registrodefecto_invoice'),
    ]

    operations = [
        migrations.CreateModel(
            name='WhatsAppContact',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('display_name', models.CharField(blank=True, default='', max_length=255)),
                ('phone_number', models.CharField(blank=True, max_length=40, null=True)),
                ('whatsapp_id', models.CharField(max_length=255, unique=True)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
            ],
            options={'db_table': 'whatsapp_contacts', 'ordering': ['display_name', 'id']},
        ),
        migrations.CreateModel(
            name='PendingEvidenceGroup',
            fields=[
                ('id', models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ('status', models.CharField(choices=[('DRAFT', 'Borrador'), ('CONFIRMED', 'Confirmado'), ('ARCHIVED', 'Archivado')], db_index=True, default='DRAFT', max_length=20)),
                ('model', models.CharField(blank=True, default='', max_length=255)),
                ('line', models.CharField(blank=True, default='', max_length=100)),
                ('quantity', models.PositiveIntegerField(blank=True, null=True)),
                ('responsible', models.CharField(blank=True, default='', max_length=100)),
                ('description', models.TextField(blank=True, default='')),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('confirmed_at', models.DateTimeField(blank=True, null=True)),
                ('confirmed_by', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, related_name='confirmed_pending_evidence_groups', to=settings.AUTH_USER_MODEL)),
                ('created_by', models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name='created_pending_evidence_groups', to=settings.AUTH_USER_MODEL)),
                ('definitive_record', models.OneToOneField(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, related_name='pending_evidence_group', to='calidad.registrodefecto')),
                ('operator', models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name='pending_evidence_groups', to=settings.AUTH_USER_MODEL)),
            ],
            options={'db_table': 'pending_evidence_groups', 'ordering': ['-created_at']},
        ),
        migrations.CreateModel(
            name='PendingEvidence',
            fields=[
                ('id', models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ('source', models.CharField(choices=[('WHATSAPP', 'WhatsApp')], default='WHATSAPP', max_length=30)),
                ('source_group_id', models.CharField(max_length=255)),
                ('source_group_name', models.CharField(blank=True, default='', max_length=255)),
                ('source_message_id', models.CharField(max_length=255)),
                ('media_index', models.PositiveIntegerField(default=0)),
                ('sender_whatsapp_id', models.CharField(blank=True, default='', max_length=255)),
                ('caption', models.TextField(blank=True, default='')),
                ('message_at', models.DateTimeField(blank=True, null=True)),
                ('received_at', models.DateTimeField(auto_now_add=True)),
                ('processing_started_at', models.DateTimeField(blank=True, null=True)),
                ('file_path', models.CharField(blank=True, default='', max_length=500)),
                ('sha256', models.CharField(blank=True, default='', max_length=64)),
                ('mime_type', models.CharField(blank=True, default='', max_length=100)),
                ('size_bytes', models.PositiveBigIntegerField(default=0)),
                ('status', models.CharField(choices=[('PROCESSING', 'Procesando'), ('READY', 'Lista'), ('FAILED', 'Error'), ('ARCHIVED', 'Archivada')], db_index=True, default='PROCESSING', max_length=20)),
                ('attempts', models.PositiveIntegerField(default=0)),
                ('error_message', models.TextField(blank=True, default='')),
                ('group', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='evidences', to='calidad.pendingevidencegroup')),
                ('sender', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='pending_evidences', to='calidad.whatsappcontact')),
            ],
            options={'db_table': 'pending_evidences', 'ordering': ['-received_at', 'id']},
        ),
        migrations.AddIndex(model_name='whatsappcontact', index=models.Index(fields=['phone_number'], name='wa_contact_phone_idx')),
        migrations.AddIndex(model_name='whatsappcontact', index=models.Index(fields=['updated_at'], name='wa_contact_updated_idx')),
        migrations.AddIndex(model_name='pendingevidencegroup', index=models.Index(fields=['operator', 'status'], name='pending_group_owner_idx')),
        migrations.AddIndex(model_name='pendingevidencegroup', index=models.Index(fields=['created_at'], name='pending_group_created_idx')),
        migrations.AddIndex(model_name='pendingevidence', index=models.Index(fields=['source_group_id', 'status'], name='pending_evidence_group_idx')),
        migrations.AddIndex(model_name='pendingevidence', index=models.Index(fields=['sender_whatsapp_id'], name='pending_evidence_sender_idx')),
        migrations.AddIndex(model_name='pendingevidence', index=models.Index(fields=['received_at'], name='pending_evidence_received_idx')),
        migrations.AddIndex(model_name='pendingevidence', index=models.Index(fields=['group', 'status'], name='pending_ev_assign_idx')),
        migrations.AddConstraint(
            model_name='pendingevidence',
            constraint=models.UniqueConstraint(fields=('source', 'source_group_id', 'source_message_id', 'media_index'), name='pending_evidence_source_message_uq'),
        ),
    ]
