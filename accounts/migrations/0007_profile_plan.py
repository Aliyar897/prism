from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('accounts', '0006_persona_brand_kit'),
    ]

    operations = [
        migrations.AddField(
            model_name='profile',
            name='plan',
            field=models.CharField(
                choices=[('free', 'Free'), ('pro', 'Pro')],
                default='free',
                max_length=10,
            ),
        ),
    ]
