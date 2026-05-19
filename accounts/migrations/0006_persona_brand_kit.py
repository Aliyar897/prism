from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('accounts', '0005_personalink_stats'),
    ]

    operations = [
        migrations.AddField(
            model_name='persona',
            name='niche_tags',
            field=models.JSONField(blank=True, default=list),
        ),
        migrations.AddField(
            model_name='persona',
            name='collab_types',
            field=models.JSONField(blank=True, default=list),
        ),
        migrations.AddField(
            model_name='persona',
            name='past_brands',
            field=models.JSONField(blank=True, default=list),
        ),
    ]
