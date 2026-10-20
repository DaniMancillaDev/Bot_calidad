from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ('calidad', '0015_whatsapp_pending_evidence'),
    ]

    operations = [
        migrations.AddField(
            model_name='pendingevidence',
            name='sender_alt_whatsapp_id',
            field=models.CharField(blank=True, default='', max_length=255),
        ),
        migrations.AddIndex(
            model_name='pendingevidence',
            index=models.Index(fields=['sender_alt_whatsapp_id'], name='pending_ev_alt_sender_idx'),
        ),
    ]
