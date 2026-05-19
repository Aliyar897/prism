from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('accounts', '0004_persona_personalink_visitevent'),
    ]

    operations = [
        migrations.AddField(
            model_name='personalink',
            name='stat_value',
            field=models.CharField(blank=True, max_length=20),
        ),
        migrations.AddField(
            model_name='personalink',
            name='stat_label',
            field=models.CharField(blank=True, max_length=30),
        ),
    ]
