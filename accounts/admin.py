from django.contrib import admin

from .models import Feedback, Persona, PersonaLink, Profile, VisitEvent


@admin.register(Profile)
class ProfileAdmin(admin.ModelAdmin):
    list_display = ('user', 'goal', 'onboarding_completed')
    search_fields = ('user__username', 'user__email')


@admin.register(Persona)
class PersonaAdmin(admin.ModelAdmin):
    list_display = ('user', 'mode', 'is_active')
    list_filter = ('mode', 'is_active')
    search_fields = ('user__username',)


@admin.register(PersonaLink)
class PersonaLinkAdmin(admin.ModelAdmin):
    list_display = ('persona', 'label', 'url', 'is_cta', 'is_enabled', 'order')
    list_filter = ('is_enabled', 'is_cta', 'persona__mode')
    search_fields = ('persona__user__username', 'label')


@admin.register(Feedback)
class FeedbackAdmin(admin.ModelAdmin):
    list_display = ('user', 'rating', 'short_message', 'created_at')
    list_filter = ('rating',)
    readonly_fields = ('user', 'rating', 'message', 'created_at')
    search_fields = ('user__username', 'message')

    def short_message(self, obj):
        return obj.message[:60] + '…' if len(obj.message) > 60 else obj.message
    short_message.short_description = 'Message'


@admin.register(VisitEvent)
class VisitEventAdmin(admin.ModelAdmin):
    list_display = ('profile', 'mode_shown', 'detected_by', 'confidence', 'device_type', 'created_at')
    list_filter = ('mode_shown', 'detected_by', 'device_type')
    readonly_fields = ('created_at',)
    search_fields = ('profile__username',)
