from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('accounts', '0007_profile_plan'),
    ]

    operations = [
        migrations.AddField(
            model_name='persona',
            name='brand_metrics',
            field=models.JSONField(blank=True, default=dict),
        ),
    ]
