from django.urls import path

from .views import (
    check_username,
    dashboard_view,
    detect_client,
    email_sent,
    landing_view,
    onboarding_view,
    persona_delete_link,
    persona_generate_bio,
    persona_save_bio,
    persona_save_brand_info,
    persona_save_brand_metrics,
    persona_save_link,
    persona_toggle_active,
    persona_toggle_link,
    persona_upload_avatar,
    post_login_redirect,
    pricing_view,
    public_profile,
    save_bio,
    save_profile_view,
    settings_change_password,
    settings_delete_account,
    settings_save_avatar,
    settings_save_profile,
    settings_view,
    submit_feedback,
    stripe_checkout,
    stripe_portal,
    stripe_success,
    stripe_webhook,
    toggle_platform_view,
    update_platform_url_view,
    upgrade_view,
    upload_avatar,
)

urlpatterns = [
    # ── Public ────────────────────────────────────────────────────────────────
    path('', landing_view, name='landing'),

    # ── Auth helpers ──────────────────────────────────────────────────────────
    path('accounts/email-sent/', email_sent, name='email_sent'),

    # ── Onboarding ────────────────────────────────────────────────────────────
    path('onboarding/', onboarding_view, name='onboarding'),
    path('save-profile/', save_profile_view, name='save_profile'),

    # ── Dashboard ─────────────────────────────────────────────────────────────
    path('dashboard/', dashboard_view, name='dashboard'),
    path('redirect/', post_login_redirect, name='post_login_redirect'),

    # ── Pricing / upgrade ─────────────────────────────────────────────────────
    path('pricing/', pricing_view, name='pricing'),
    path('upgrade/', upgrade_view, name='upgrade'),

    # ── Stripe ────────────────────────────────────────────────────────────────
    path('stripe/checkout/', stripe_checkout, name='stripe_checkout'),
    path('stripe/portal/', stripe_portal, name='stripe_portal'),
    path('stripe/success/', stripe_success, name='stripe_success'),
    path('stripe/webhook/', stripe_webhook, name='stripe_webhook'),

    # ── Settings ──────────────────────────────────────────────────────────────
    path('settings/', settings_view, name='settings'),
    path('feedback/', submit_feedback, name='submit_feedback'),
    path('settings/profile/', settings_save_profile, name='settings_save_profile'),
    path('settings/avatar/', settings_save_avatar, name='settings_save_avatar'),
    path('settings/password/', settings_change_password, name='settings_change_password'),
    path('settings/delete/', settings_delete_account, name='settings_delete_account'),

    # ── Detection ─────────────────────────────────────────────────────────────
    path('detect-client/', detect_client, name='detect_client'),
    path('check-username/', check_username, name='check_username'),

    # ── Persona AJAX ──────────────────────────────────────────────────────────
    path('persona/bio/', persona_save_bio, name='persona_save_bio'),
    path('persona/generate-bio/', persona_generate_bio, name='persona_generate_bio'),
    path('persona/brand-info/', persona_save_brand_info, name='persona_save_brand_info'),
    path('persona/brand-metrics/', persona_save_brand_metrics, name='persona_save_brand_metrics'),
    path('persona/avatar/', persona_upload_avatar, name='persona_upload_avatar'),
    path('persona/toggle/', persona_toggle_active, name='persona_toggle_active'),
    path('persona/link/save/', persona_save_link, name='persona_save_link'),
    path('persona/link/delete/', persona_delete_link, name='persona_delete_link'),
    path('persona/link/toggle/', persona_toggle_link, name='persona_toggle_link'),

    # ── Legacy AJAX (kept for backward compat) ────────────────────────────────
    path('toggle-platform/', toggle_platform_view, name='toggle_platform'),
    path('update-platform-url/', update_platform_url_view, name='update_platform_url'),
    path('upload-avatar/', upload_avatar, name='upload_avatar'),
    path('save-bio/', save_bio, name='save_bio'),

    # ── Public profile — MUST be last to avoid shadowing other routes ─────────
    path('<str:username>/', public_profile, name='public_profile'),
]
