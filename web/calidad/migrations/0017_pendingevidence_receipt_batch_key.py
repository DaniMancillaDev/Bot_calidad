from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ('calidad', '0016_pendingevidence_sender_alt_id'),
    ]

    operations = [
        migrations.AddField(
            model_name='pendingevidence',
            name='receipt_batch_key',
            field=models.CharField(blank=True, default='', max_length=255),
        ),
        migrations.AddIndex(
            model_name='pendingevidence',
            index=models.Index(
                fields=['source_group_id', 'receipt_batch_key', 'status'],
                name='pending_ev_batch_idx',
            ),
        ),
    ]
