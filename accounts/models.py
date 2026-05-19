from django.db import models
from django.contrib.auth.models import User


class Profile(models.Model):
    GOAL_CHOICES = [
        ('creator', 'Creator'),
        ('business', 'Business'),
        ('personal', 'Personal'),
    ]
    user = models.OneToOneField(User, on_delete=models.CASCADE)
    goal = models.CharField(max_length=20, choices=GOAL_CHOICES, blank=True)
    platforms = models.JSONField(default=list, blank=True)
    avatar = models.ImageField(upload_to='avatars/', null=True, blank=True)
    bio = models.TextField(blank=True, default='')
    onboarding_completed = models.BooleanField(default=False)
    PLAN_CHOICES = [('free', 'Free'), ('pro', 'Pro')]
    plan = models.CharField(max_length=10, choices=PLAN_CHOICES, default='free')
    stripe_customer_id = models.CharField(max_length=60, blank=True, default='')
    stripe_subscription_id = models.CharField(max_length=60, blank=True, default='')
    plan_cancel_at = models.DateTimeField(null=True, blank=True)

    def __str__(self):
        return f'{self.user.username} — {self.goal}'


class Persona(models.Model):
    MODE_CHOICES = [
        ('fan', 'Fan'),
        ('brand', 'Brand'),
        ('professional', 'Professional'),
    ]

    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='personas')
    mode = models.CharField(max_length=20, choices=MODE_CHOICES)
    avatar = models.ImageField(upload_to='persona_avatars/', null=True, blank=True)
    bio = models.TextField(blank=True)
    cta_label = models.CharField(max_length=60, blank=True)
    is_active = models.BooleanField(default=False)

    niche_tags    = models.JSONField(default=list, blank=True)
    collab_types  = models.JSONField(default=list, blank=True)
    past_brands   = models.JSONField(default=list, blank=True)
    brand_metrics = models.JSONField(default=dict, blank=True)

    class Meta:
        unique_together = ('user', 'mode')
        ordering = ['mode']

    def __str__(self):
        return f'{self.user.username} / {self.mode}'


class PersonaLink(models.Model):
    persona = models.ForeignKey(Persona, related_name='links', on_delete=models.CASCADE)
    label = models.CharField(max_length=100)
    url = models.URLField(max_length=500)
    icon = models.CharField(max_length=40, blank=True)
    is_cta = models.BooleanField(default=False)
    order = models.PositiveIntegerField(default=0)
    is_enabled = models.BooleanField(default=True)
    # Stats shown on the Brand card (e.g. stat_value="48K", stat_label="Subscribers")
    stat_value = models.CharField(max_length=20, blank=True)
    stat_label = models.CharField(max_length=30, blank=True)

    class Meta:
        ordering = ['order', 'id']

    def __str__(self):
        return f'{self.persona} — {self.label}'


class Feedback(models.Model):
    user       = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='feedbacks')
    rating     = models.CharField(max_length=10, blank=True)
    message    = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        name = self.user.username if self.user else 'deleted user'
        return f'{name} {self.rating} — {self.created_at:%Y-%m-%d}'


class VisitEvent(models.Model):
    profile = models.ForeignKey(User, on_delete=models.CASCADE, related_name='visit_events')
    visitor_id = models.CharField(max_length=64)
    mode_shown = models.CharField(max_length=20)
    detected_by = models.CharField(max_length=40)
    confidence = models.FloatField(default=0.0)
    referrer = models.URLField(blank=True, max_length=500)
    device_type = models.CharField(max_length=20, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f'{self.profile.username} — {self.mode_shown} ({self.detected_by})'
