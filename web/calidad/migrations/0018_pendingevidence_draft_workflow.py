from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    dependencies = [
        ('calidad', '0017_pendingevidence_receipt_batch_key'),
    ]

    operations = [
        migrations.AddField(
            model_name='pendingevidence',
            name='draft_order',
            field=models.PositiveIntegerField(default=0),
        ),
        migrations.AddField(
            model_name='pendingevidence',
            name='is_excluded',
            field=models.BooleanField(default=False),
        ),
        migrations.AddField(
            model_name='pendingevidence',
            name='exclusion_reason',
            field=models.CharField(blank=True, default='', max_length=255),
        ),
        migrations.AddField(
            model_name='pendingevidence',
            name='excluded_at',
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name='pendingevidence',
            name='excluded_by',
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name='excluded_pending_evidences',
                to=settings.AUTH_USER_MODEL,
            ),
        ),
        migrations.AddIndex(
            model_name='pendingevidence',
            index=models.Index(
                fields=['group', 'draft_order'],
                name='pending_ev_draft_order_idx',
            ),
        ),
        migrations.AddIndex(
            model_name='pendingevidence',
            index=models.Index(
                fields=['is_excluded', 'status'],
                name='pending_ev_excluded_idx',
            ),
        ),
    ]
