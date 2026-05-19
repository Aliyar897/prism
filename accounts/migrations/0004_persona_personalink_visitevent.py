from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ('accounts', '0003_profile_avatar_profile_bio'),
    ]

    operations = [
        migrations.CreateModel(
            name='Persona',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('mode', models.CharField(choices=[('fan', 'Fan'), ('brand', 'Brand'), ('professional', 'Professional')], max_length=20)),
                ('avatar', models.ImageField(blank=True, null=True, upload_to='persona_avatars/')),
                ('bio', models.TextField(blank=True)),
                ('cta_label', models.CharField(blank=True, max_length=60)),
                ('is_active', models.BooleanField(default=False)),
                ('user', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='personas', to=settings.AUTH_USER_MODEL)),
            ],
            options={
                'ordering': ['mode'],
                'unique_together': {('user', 'mode')},
            },
        ),
        migrations.CreateModel(
            name='PersonaLink',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('label', models.CharField(max_length=100)),
                ('url', models.URLField(max_length=500)),
                ('icon', models.CharField(blank=True, max_length=40)),
                ('is_cta', models.BooleanField(default=False)),
                ('order', models.PositiveIntegerField(default=0)),
                ('is_enabled', models.BooleanField(default=True)),
                ('persona', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='links', to='accounts.persona')),
            ],
            options={
                'ordering': ['order', 'id'],
            },
        ),
        migrations.CreateModel(
            name='VisitEvent',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('visitor_id', models.CharField(max_length=64)),
                ('mode_shown', models.CharField(max_length=20)),
                ('detected_by', models.CharField(max_length=40)),
                ('confidence', models.FloatField(default=0.0)),
                ('referrer', models.URLField(blank=True, max_length=500)),
                ('device_type', models.CharField(blank=True, max_length=20)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('profile', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='visit_events', to=settings.AUTH_USER_MODEL)),
            ],
            options={
                'ordering': ['-created_at'],
            },
        ),
    ]
