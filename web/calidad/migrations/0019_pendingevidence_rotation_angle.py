from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [('calidad', '0018_pendingevidence_draft_workflow')]

    operations = [
        migrations.AddField(
            model_name='pendingevidence',
            name='rotation_angle',
            field=models.PositiveSmallIntegerField(default=0),
        ),
    ]
