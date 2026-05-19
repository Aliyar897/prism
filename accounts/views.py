import json
import re
import uuid

from django.conf import settings
from django.contrib.auth import logout, update_session_auth_hash
from django.contrib.auth.decorators import login_required
from django.contrib.auth.models import User
from django.core.mail import send_mail
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.csrf import csrf_exempt

from .detector import client_context_score, detect
from .models import Feedback, Persona, PersonaLink, Profile, VisitEvent

VALID_MODES = ('fan', 'brand', 'professional')

FREE_LINK_LIMIT    = 3
FREE_PERSONA_LIMIT = 1


def _plan(profile):
    return getattr(profile, 'plan', 'free')


def _is_pro(profile):
    return _plan(profile) == 'pro'


# ── Helpers ───────────────────────────────────────────────────────────────────

def _get_or_create_all_personas(user, profile):
    """Return {mode: Persona} for all 3 modes, auto-migrating legacy data once."""
    personas = {}
    for mode in VALID_MODES:
        persona, created = Persona.objects.get_or_create(user=user, mode=mode)
        if created and mode == 'fan':
            # Migrate legacy profile data into the Fan persona on first use
            if profile.bio:
                persona.bio = profile.bio
            if profile.avatar:
                persona.avatar = profile.avatar
            for i, p in enumerate(profile.platforms or []):
                if isinstance(p, dict) and p.get('url'):
                    PersonaLink.objects.create(
                        persona=persona,
                        label=p.get('name', 'Link'),
                        url=p.get('url', ''),
                        is_enabled=p.get('enabled', True),
                        order=i,
                    )
            if profile.platforms:
                persona.is_active = True
            persona.save()
        personas[mode] = persona
    return personas


COLLAB_TYPE_CHOICES = [
    'Sponsored Post', 'Product Review', 'Unboxing', 'Brand Ambassador',
    'YouTube Integration', 'Instagram Story / Reel', 'TikTok Integration',
    'Event Appearance', 'Gifting / PR', 'Podcast Mention', 'Newsletter Feature',
]

BRAND_METRIC_FIELDS = [
    {'key': 'engagement_rate',  'label': 'Engagement Rate',  'category': 'audience',     'placeholder': 'e.g. 4.2%'},
    {'key': 'follower_count',   'label': 'Total Reach',      'category': 'audience',     'placeholder': 'e.g. 2.5M'},
    {'key': 'audience_age',     'label': 'Audience Age',     'category': 'audience',     'placeholder': 'e.g. 18–28'},
    {'key': 'top_location',     'label': 'Top Location',     'category': 'audience',     'placeholder': 'e.g. US 45%'},
    {'key': 'avg_views',        'label': 'Avg Views',        'category': 'performance',  'placeholder': 'e.g. 850K'},
    {'key': 'avg_likes',        'label': 'Avg Likes',        'category': 'performance',  'placeholder': 'e.g. 45K'},
    {'key': 'story_completion', 'label': 'Story Completion', 'category': 'performance',  'placeholder': 'e.g. 72%'},
    {'key': 'watch_time',       'label': 'Avg Watch Time',   'category': 'performance',  'placeholder': 'e.g. 8.5 min'},
    {'key': 'growth_rate',      'label': 'Growth Rate (30d)','category': 'growth',       'placeholder': 'e.g. +12%'},
    {'key': 'monthly_reach',    'label': 'Monthly Reach',    'category': 'growth',       'placeholder': 'e.g. 1.2M'},
    {'key': 'link_ctr',         'label': 'Link CTR',         'category': 'results',      'placeholder': 'e.g. 3.8%'},
    {'key': 'collab_count',     'label': 'Brand Deals Done', 'category': 'results',      'placeholder': 'e.g. 24+'},
]

_VALID_METRIC_KEYS = {f['key'] for f in BRAND_METRIC_FIELDS}


def _persona_to_dict(persona):
    return {
        'mode': persona.mode,
        'avatar': persona.avatar.url if persona.avatar else '',
        'bio': persona.bio,
        'cta_label': persona.cta_label,
        'is_active': persona.is_active,
        'niche_tags': persona.niche_tags,
        'collab_types': persona.collab_types,
        'past_brands': persona.past_brands,
        'brand_metrics': persona.brand_metrics if isinstance(persona.brand_metrics, dict) else {},
        'links': [
            {
                'id': lnk.id,
                'label': lnk.label,
                'url': lnk.url,
                'icon': lnk.icon,
                'is_cta': lnk.is_cta,
                'order': lnk.order,
                'is_enabled': lnk.is_enabled,
                'stat_value': lnk.stat_value,
                'stat_label': lnk.stat_label,
            }
            for lnk in persona.links.all()
        ],
    }


def _stat_label_default(label: str) -> str:
    """Return a sensible stat label for a known platform."""
    l = label.lower()
    if 'youtube'   in l: return 'Subscribers'
    if 'instagram' in l: return 'Followers'
    if 'tiktok'    in l: return 'Followers'
    if 'twitter'   in l or l == 'x': return 'Followers'
    if 'facebook'  in l: return 'Followers'
    if 'spotify'   in l: return 'Monthly Listeners'
    if 'linkedin'  in l: return 'Connections'
    if 'github'    in l: return 'Stars'
    if 'pinterest' in l: return 'Followers'
    return 'Followers'


def _normalize_url(url):
    url = (url or '').strip()
    if url and not url.startswith(('http://', 'https://')):
        url = 'https://' + url
    return url


# ── Public views ──────────────────────────────────────────────────────────────

def landing_view(request):
    return render(request, 'accounts/landing.html')


def pricing_view(request):
    return render(request, 'accounts/pricing.html', {'user': request.user})


@login_required
def upgrade_view(request):
    profile, _ = Profile.objects.get_or_create(user=request.user)
    if request.method == 'POST':
        # Demo upgrade — in production this becomes Stripe webhook
        profile.plan = 'pro'
        profile.save(update_fields=['plan'])
        return redirect('dashboard')
    return render(request, 'accounts/upgrade.html', {'profile': profile})


def email_sent(request):
    return render(request, 'account/email_verification_sent.html')


# ── Client-side context detection endpoint ───────────────────────────────────
# Called by profile.html via fetch() when the server returned 'unknown'.
# Receives device/time signals the browser knows but the server doesn't.

@csrf_exempt
def detect_client(request):
    if request.method != 'POST':
        return JsonResponse({'error': 'POST required'}, status=405)

    try:
        data = json.loads(request.body)
    except json.JSONDecodeError:
        return JsonResponse({'error': 'Invalid JSON'}, status=400)

    hour      = int(data.get('hour', 12))          # local hour 0-23
    is_mobile = bool(data.get('is_mobile', False))
    is_weekend = bool(data.get('is_weekend', False))
    active_modes = data.get('active_modes', [])   # modes the creator has configured

    mode, confidence, source = client_context_score(hour, is_mobile, is_weekend)

    # Only surface a mode that the creator has actually configured
    if mode and mode not in active_modes:
        mode = None

    return JsonResponse({
        'mode':        mode,
        'confidence':  confidence,
        'detected_by': source,
    })


# ── Public profile page ───────────────────────────────────────────────────────

def public_profile(request, username):
    profile_user = get_object_or_404(User, username=username)
    profile = get_object_or_404(Profile, user=profile_user)

    personas_qs = Persona.objects.filter(user=profile_user).prefetch_related('links')
    personas = {p.mode: p for p in personas_qs}

    active_modes = [m for m in VALID_MODES if m in personas and personas[m].is_active]

    # Free plan: only the fan persona is publicly visible, regardless of what's in the DB.
    # (Brand/professional may be stale-active from before a downgrade or paywall addition.)
    if profile.plan == 'free':
        active_modes = [m for m in active_modes if m == 'fan']

    # Server-side detection
    detected_mode, confidence, detected_by = detect(request)

    if detected_mode and detected_mode in personas and personas[detected_mode].is_active:
        mode = detected_mode
    elif active_modes:
        mode = active_modes[0]
    else:
        mode = None

    current_persona = personas.get(mode) if mode else None

    # Log the visit (fire-and-forget; swallow errors so a bad write never breaks the page)
    try:
        visitor_id = request.COOKIES.get('prism_vid') or str(uuid.uuid4())
        ua = request.META.get('HTTP_USER_AGENT', '')
        device = 'mobile' if any(k in ua.lower() for k in ('mobi', 'android', 'iphone')) else 'desktop'
        VisitEvent.objects.create(
            profile=profile_user,
            visitor_id=visitor_id,
            mode_shown=mode or 'none',
            detected_by=detected_by,
            confidence=confidence,
            referrer=request.META.get('HTTP_REFERER', '')[:500],
            device_type=device,
        )
    except Exception:
        pass

    # Derive a clean display name — never show a raw email address to visitors
    display_name = (
        profile_user.first_name
        or profile_user.username.split('@')[0]  # strip domain if username is an email
    ).strip() or profile_user.username

    response = render(request, 'accounts/profile.html', {
        'profile_user': profile_user,
        'profile': profile,
        'personas': personas,
        'current_persona': current_persona,
        'mode': mode or 'fan',
        'detected_by': detected_by,
        'confidence': confidence,
        'active_modes': active_modes,
        'display_name': display_name,
        # Only active personas go to the client — inactive ones simply don't exist in JS
        'personas_json': json.dumps({m: _persona_to_dict(p) for m, p in personas.items() if p.is_active}),
    })

    # Persist visitor ID in cookie (7-day, no sensitive data)
    if 'prism_vid' not in request.COOKIES:
        response.set_cookie('prism_vid', visitor_id, max_age=7 * 24 * 3600, httponly=True, samesite='Lax')
    return response


# ── Onboarding ────────────────────────────────────────────────────────────────

def check_username(request):
    val = request.GET.get('username', '').strip().lower()
    import re
    if not val:
        return JsonResponse({'status': 'empty'})
    if not re.match(r'^[a-z0-9_]{3,30}$', val):
        return JsonResponse({'status': 'invalid'})
    taken = User.objects.filter(username__iexact=val).exists()
    return JsonResponse({'status': 'taken' if taken else 'available'})


@login_required
def onboarding_view(request):
    profile, _ = Profile.objects.get_or_create(user=request.user)
    if profile.onboarding_completed:
        return redirect('dashboard')
    return render(request, 'accounts/onboarding.html')


_PLATFORM_LABELS = {
    'instagram': 'Instagram',
    'whatsapp':  'WhatsApp',
    'tiktok':    'TikTok',
    'youtube':   'YouTube',
    'website':   'Website',
    'spotify':   'Spotify',
    'threads':   'Threads',
    'facebook':  'Facebook',
    'x':         'X (Twitter)',
    'linkedin':  'LinkedIn',
}


@login_required
def save_profile_view(request):
    if request.method != 'POST':
        return redirect('onboarding')

    goal = request.POST.get('goal')
    platforms_raw = request.POST.get('platforms')

    if not goal or not platforms_raw:
        return redirect('onboarding')

    try:
        platforms_list = [p for p in json.loads(platforms_raw) if isinstance(p, str)]
    except (json.JSONDecodeError, TypeError):
        platforms_list = []

    profile, _ = Profile.objects.get_or_create(user=request.user)
    profile.goal = goal
    profile.platforms = [
        {'name': p, 'url': '', 'enabled': True, 'order': i + 1}
        for i, p in enumerate(platforms_list)
    ]
    profile.onboarding_completed = True
    profile.save()

    # Create the fan persona immediately with a placeholder link per platform.
    # Links have empty URLs so the dashboard prompts the user to fill them in.
    fan_persona, _ = Persona.objects.get_or_create(user=request.user, mode='fan')
    if not fan_persona.links.exists():
        for i, p in enumerate(platforms_list):
            PersonaLink.objects.create(
                persona=fan_persona,
                label=_PLATFORM_LABELS.get(p, p.capitalize()),
                url='',
                is_enabled=True,
                order=i,
            )
    fan_persona.is_active = True
    fan_persona.save(update_fields=['is_active'])

    return redirect('dashboard')


# ── Post-login router ─────────────────────────────────────────────────────────

@login_required
def post_login_redirect(request):
    profile, _ = Profile.objects.get_or_create(user=request.user)
    if not profile.onboarding_completed:
        # Auto-complete onboarding for users who already have data (e.g. pre-flag accounts)
        has_persona = Persona.objects.filter(user=request.user).exists()
        if has_persona:
            profile.onboarding_completed = True
            profile.save(update_fields=['onboarding_completed'])
        else:
            return redirect('onboarding')
    return redirect('dashboard')


# ── Dashboard ─────────────────────────────────────────────────────────────────

@login_required
def dashboard_view(request):
    profile, _ = Profile.objects.get_or_create(user=request.user)
    personas = _get_or_create_all_personas(request.user, profile)
    is_pro = _is_pro(profile)

    # Free plan: brand/professional must never appear as active in the dashboard.
    # Override in-memory only — avoids a DB write on every page load.
    if not is_pro:
        for m in ('brand', 'professional'):
            if m in personas and personas[m].is_active:
                personas[m].is_active = False
                Persona.objects.filter(user=request.user, mode=m).update(is_active=False)

    personas_json = json.dumps({m: _persona_to_dict(p) for m, p in personas.items()})

    user = request.user
    display_name = user.get_full_name() or user.username

    return render(request, 'accounts/dashboard.html', {
        'profile': profile,
        'personas': personas,
        'personas_json': personas_json,
        'collab_type_choices': COLLAB_TYPE_CHOICES,
        'brand_metric_fields': [
            {**f, 'value': personas['brand'].brand_metrics.get(f['key'], '')}
            for f in BRAND_METRIC_FIELDS
        ],
        'auto_stat_preview': [
            {'label': 'YouTube',   'icon': 'ti ti-brand-youtube',   'color': '#FF0000', 'hint': 'Subscribers · Avg views · Watch time'},
            {'label': 'Instagram', 'icon': 'ti ti-brand-instagram', 'color': '#E1306C', 'hint': 'Followers · Engagement rate · Story reach'},
            {'label': 'TikTok',   'icon': 'ti ti-brand-tiktok',    'color': '#FAFAFA', 'hint': 'Followers · Avg likes · Video plays'},
            {'label': 'Twitter / X', 'icon': 'ti ti-brand-twitter', 'color': '#1DA1F2', 'hint': 'Followers · Impressions · Engagement'},
            {'label': 'LinkedIn',  'icon': 'ti ti-brand-linkedin',  'color': '#0077B5', 'hint': 'Connections · Post reach · Profile views'},
        ],
        'is_pro': is_pro,
        'display_name': display_name,
    })


# ── Persona AJAX: media kit stats ────────────────────────────────────────────

@login_required
def persona_save_brand_metrics(request):
    if request.method != 'POST':
        return JsonResponse({'error': 'Invalid request'}, status=400)
    try:
        data = json.loads(request.body)
    except json.JSONDecodeError:
        return JsonResponse({'error': 'Invalid JSON'}, status=400)

    profile, _ = Profile.objects.get_or_create(user=request.user)
    if not _is_pro(profile):
        return JsonResponse({'error': 'plan_limit', 'feature': 'brand_metrics',
                             'message': 'Media Kit Stats are a Pro feature. Upgrade to showcase your engagement rate, reach, and audience demographics.'}, status=402)

    persona, _ = Persona.objects.get_or_create(user=request.user, mode='brand')
    metrics = {k: str(v).strip()[:30] for k, v in data.items()
               if k in _VALID_METRIC_KEYS and str(v).strip()}
    persona.brand_metrics = metrics
    persona.save(update_fields=['brand_metrics'])
    return JsonResponse({'success': True})


# ── Persona AJAX: brand kit (niche tags, collab types, past brands) ──────────

@login_required
def persona_save_brand_info(request):
    if request.method != 'POST':
        return JsonResponse({'error': 'Invalid request'}, status=400)
    try:
        data = json.loads(request.body)
    except json.JSONDecodeError:
        return JsonResponse({'error': 'Invalid JSON'}, status=400)

    profile, _ = Profile.objects.get_or_create(user=request.user)
    if not _is_pro(profile):
        return JsonResponse({
            'error': 'plan_limit',
            'feature': 'brand_kit',
            'message': 'Brand Kit is a Pro feature. Upgrade to showcase your niche, collaboration formats, and past brand partners.',
        }, status=402)

    persona, _ = Persona.objects.get_or_create(user=request.user, mode='brand')

    raw_niche = (data.get('niche_tags') or '').strip()
    persona.niche_tags = [t.strip() for t in raw_niche.split(',') if t.strip()][:8]

    collab_raw = data.get('collab_types') or []
    persona.collab_types = [ct for ct in collab_raw if isinstance(ct, str) and ct in COLLAB_TYPE_CHOICES]

    raw_brands = (data.get('past_brands') or '').strip()
    persona.past_brands = [b.strip() for b in raw_brands.split(',') if b.strip()][:12]

    persona.save(update_fields=['niche_tags', 'collab_types', 'past_brands'])
    return JsonResponse({'success': True})


# ── Persona AJAX: bio ─────────────────────────────────────────────────────────

@login_required
def persona_save_bio(request):
    if request.method != 'POST':
        return JsonResponse({'error': 'Invalid request'}, status=400)
    try:
        data = json.loads(request.body)
    except json.JSONDecodeError:
        return JsonResponse({'error': 'Invalid JSON'}, status=400)

    mode = data.get('mode')
    if mode not in VALID_MODES:
        return JsonResponse({'error': 'Invalid mode'}, status=400)

    profile, _ = Profile.objects.get_or_create(user=request.user)
    if not _is_pro(profile) and mode != 'fan':
        return JsonResponse({'error': 'plan_limit', 'feature': 'persona_mode',
                             'message': 'Brand and Professional personas require Prism Pro.'}, status=402)

    persona, _ = Persona.objects.get_or_create(user=request.user, mode=mode)
    persona.bio = (data.get('bio') or '').strip()
    persona.cta_label = (data.get('cta_label') or '').strip()
    persona.save(update_fields=['bio', 'cta_label'])
    return JsonResponse({'success': True})


# ── Persona AJAX: avatar ──────────────────────────────────────────────────────

@login_required
def persona_upload_avatar(request):
    if request.method != 'POST':
        return JsonResponse({'error': 'Invalid request'}, status=400)

    mode = request.POST.get('mode')
    if mode not in VALID_MODES:
        return JsonResponse({'error': 'Invalid mode'}, status=400)

    profile, _ = Profile.objects.get_or_create(user=request.user)
    if not _is_pro(profile) and mode != 'fan':
        return JsonResponse({'error': 'plan_limit', 'feature': 'persona_mode',
                             'message': 'Brand and Professional personas require Prism Pro.'}, status=402)

    file = request.FILES.get('avatar')
    if not file:
        return JsonResponse({'error': 'No file'}, status=400)

    persona, _ = Persona.objects.get_or_create(user=request.user, mode=mode)
    persona.avatar = file
    persona.save(update_fields=['avatar'])
    return JsonResponse({'success': True, 'url': persona.avatar.url})


# ── Persona AJAX: toggle active ───────────────────────────────────────────────

@login_required
def persona_toggle_active(request):
    if request.method != 'POST':
        return JsonResponse({'error': 'Invalid request'}, status=400)
    try:
        data = json.loads(request.body)
    except json.JSONDecodeError:
        return JsonResponse({'error': 'Invalid JSON'}, status=400)

    mode = data.get('mode')
    if mode not in VALID_MODES:
        return JsonResponse({'error': 'Invalid mode'}, status=400)

    active = bool(data.get('active', True))
    profile, _ = Profile.objects.get_or_create(user=request.user)

    if not _is_pro(profile):
        if mode != 'fan':
            # Free plan: brand/professional can never be activated
            return JsonResponse({
                'error': 'plan_limit',
                'feature': 'persona_mode',
                'message': 'Brand and Professional personas require Prism Pro. Only the Fan persona is available on the free plan.',
            }, status=402)
        if active:
            # Activating fan: silently clear any stale brand/professional active flags
            # (can happen when plan was downgraded or paywall was added after data existed)
            Persona.objects.filter(user=request.user).exclude(mode='fan').update(is_active=False)

    persona, _ = Persona.objects.get_or_create(user=request.user, mode=mode)
    persona.is_active = active
    persona.save(update_fields=['is_active'])
    return JsonResponse({'success': True, 'is_active': persona.is_active})


# ── Persona AJAX: save link (add or edit) ────────────────────────────────────

@login_required
def persona_save_link(request):
    if request.method != 'POST':
        return JsonResponse({'error': 'Invalid request'}, status=400)
    try:
        data = json.loads(request.body)
    except json.JSONDecodeError:
        return JsonResponse({'error': 'Invalid JSON'}, status=400)

    mode = data.get('mode')
    if mode not in VALID_MODES:
        return JsonResponse({'error': 'Invalid mode'}, status=400)

    label = (data.get('label') or '').strip()
    url = _normalize_url(data.get('url'))
    is_cta = bool(data.get('is_cta', False))
    link_id = data.get('id')
    stat_value = (data.get('stat_value') or '').strip()[:20]
    # Only apply the default label when the user has actually entered a stat value
    raw_stat_label = (data.get('stat_label') or '').strip()
    stat_label = (raw_stat_label or (stat_value and _stat_label_default(label)) or '')[:30]

    if not label or not url:
        return JsonResponse({'error': 'Label and URL required'}, status=400)

    persona, _ = Persona.objects.get_or_create(user=request.user, mode=mode)

    profile, _ = Profile.objects.get_or_create(user=request.user)
    if not _is_pro(profile):
        if mode != 'fan':
            return JsonResponse({'error': 'plan_limit', 'feature': 'persona_mode',
                                 'message': 'Brand and Professional personas require Prism Pro.'}, status=402)
        if stat_value:  # stat_label alone is meaningless without a value
            return JsonResponse({
                'error': 'plan_limit',
                'feature': 'link_stats',
                'message': 'Audience stats are a Pro feature. Upgrade to add subscriber counts and engagement rates to your brand card.',
            }, status=402)
        if not link_id and persona.links.count() >= FREE_LINK_LIMIT:
            return JsonResponse({
                'error': 'plan_limit',
                'feature': 'link_limit',
                'message': f'Free plan supports up to {FREE_LINK_LIMIT} links per persona. Upgrade to Pro for unlimited links.',
            }, status=402)

    if link_id:
        try:
            link = PersonaLink.objects.get(id=link_id, persona=persona)
        except PersonaLink.DoesNotExist:
            return JsonResponse({'error': 'Link not found'}, status=404)
        link.label = label
        link.url = url
        link.is_cta = is_cta
        link.stat_value = stat_value
        link.stat_label = stat_label
        link.save(update_fields=['label', 'url', 'is_cta', 'stat_value', 'stat_label'])
    else:
        max_order = persona.links.count()
        link = PersonaLink.objects.create(
            persona=persona,
            label=label,
            url=url,
            is_cta=is_cta,
            order=max_order,
            stat_value=stat_value,
            stat_label=stat_label,
        )

    return JsonResponse({'success': True, 'id': link.id, 'stat_label_default': _stat_label_default(label)})


# ── Persona AJAX: delete link ─────────────────────────────────────────────────

@login_required
def persona_delete_link(request):
    if request.method != 'POST':
        return JsonResponse({'error': 'Invalid request'}, status=400)
    try:
        data = json.loads(request.body)
    except json.JSONDecodeError:
        return JsonResponse({'error': 'Invalid JSON'}, status=400)

    link_id = data.get('id')
    try:
        link = PersonaLink.objects.get(id=link_id, persona__user=request.user)
        link.delete()
    except PersonaLink.DoesNotExist:
        return JsonResponse({'error': 'Not found'}, status=404)

    return JsonResponse({'success': True})


# ── Persona AJAX: toggle link enabled ────────────────────────────────────────

@login_required
def persona_toggle_link(request):
    if request.method != 'POST':
        return JsonResponse({'error': 'Invalid request'}, status=400)
    try:
        data = json.loads(request.body)
    except json.JSONDecodeError:
        return JsonResponse({'error': 'Invalid JSON'}, status=400)

    link_id = data.get('id')
    try:
        link = PersonaLink.objects.get(id=link_id, persona__user=request.user)
        link.is_enabled = bool(data.get('enabled', True))
        link.save(update_fields=['is_enabled'])
    except PersonaLink.DoesNotExist:
        return JsonResponse({'error': 'Not found'}, status=404)

    return JsonResponse({'success': True, 'is_enabled': link.is_enabled})


# ── Legacy AJAX (kept for backward compat) ────────────────────────────────────

@login_required
def toggle_platform_view(request):
    if request.method != 'POST':
        return JsonResponse({'error': 'Invalid request'}, status=400)
    try:
        data = json.loads(request.body)
        index = int(data['index'])
        enabled = bool(data['enabled'])
    except (json.JSONDecodeError, KeyError, TypeError, ValueError):
        return JsonResponse({'error': 'Invalid payload'}, status=400)

    profile = Profile.objects.get(user=request.user)
    platforms = profile.platforms or []
    if 0 <= index < len(platforms):
        platforms[index]['enabled'] = enabled
        profile.platforms = platforms
        profile.save(update_fields=['platforms'])
    return JsonResponse({'success': True})


@login_required
def upload_avatar(request):
    if request.method != 'POST':
        return JsonResponse({'error': 'Invalid request'}, status=400)
    file = request.FILES.get('avatar')
    if not file:
        return JsonResponse({'error': 'No file'}, status=400)
    profile, _ = Profile.objects.get_or_create(user=request.user)
    profile.avatar = file
    profile.save(update_fields=['avatar'])
    return JsonResponse({'success': True, 'url': profile.avatar.url})


@login_required
def save_bio(request):
    if request.method != 'POST':
        return JsonResponse({'error': 'Invalid request'}, status=400)
    try:
        data = json.loads(request.body)
    except json.JSONDecodeError:
        return JsonResponse({'error': 'Invalid JSON'}, status=400)
    profile, _ = Profile.objects.get_or_create(user=request.user)
    profile.bio = (data.get('bio') or '').strip()
    profile.save(update_fields=['bio'])
    return JsonResponse({'success': True})


@login_required
def update_platform_url_view(request):
    if request.method != 'POST':
        return JsonResponse({'error': 'Invalid request'}, status=400)
    try:
        data = json.loads(request.body)
    except json.JSONDecodeError:
        return JsonResponse({'error': 'Invalid JSON'}, status=400)

    index = data.get('index')
    name = (data.get('name') or '').strip()
    url = _normalize_url(data.get('url'))

    if not name or not url:
        return JsonResponse({'error': 'Name and URL required'}, status=400)

    profile = Profile.objects.get(user=request.user)
    platforms = profile.platforms or []

    if index == -1:
        platforms.append({'name': name, 'url': url, 'enabled': True, 'order': len(platforms) + 1})
    else:
        try:
            index = int(index)
        except (TypeError, ValueError):
            return JsonResponse({'error': 'Invalid index'}, status=400)
        if 0 <= index < len(platforms):
            platforms[index]['name'] = name
            platforms[index]['url'] = url

    profile.platforms = platforms
    profile.save(update_fields=['platforms'])
    return JsonResponse({'success': True})


# ── Settings ───────────────────────────────────────────────────────────────────

# ── Stripe ────────────────────────────────────────────────────────────────────

@login_required
def stripe_checkout(request):
    import stripe
    stripe.api_key = settings.STRIPE_SECRET_KEY

    profile = get_object_or_404(Profile, user=request.user)

    # Reuse existing Stripe customer or create one
    if profile.stripe_customer_id:
        customer_id = profile.stripe_customer_id
    else:
        customer = stripe.Customer.create(
            email=request.user.email,
            metadata={'username': request.user.username},
        )
        profile.stripe_customer_id = customer.id
        profile.save(update_fields=['stripe_customer_id'])
        customer_id = customer.id

    session = stripe.checkout.Session.create(
        customer=customer_id,
        payment_method_types=['card'],
        mode='subscription',
        line_items=[{'price': settings.STRIPE_PRICE_ID, 'quantity': 1}],
        success_url=request.build_absolute_uri('/stripe/success/'),
        cancel_url=request.build_absolute_uri('/pricing/'),
    )
    return redirect(session.url, permanent=False)


@login_required
def stripe_portal(request):
    import stripe
    stripe.api_key = settings.STRIPE_SECRET_KEY

    profile = get_object_or_404(Profile, user=request.user)
    if not profile.stripe_customer_id:
        return redirect('pricing')

    portal = stripe.billing_portal.Session.create(
        customer=profile.stripe_customer_id,
        return_url=request.build_absolute_uri('/settings/'),
    )
    return redirect(portal.url, permanent=False)


@login_required
def stripe_success(request):
    return render(request, 'accounts/stripe_success.html')


@csrf_exempt
def stripe_webhook(request):
    import stripe
    stripe.api_key = settings.STRIPE_SECRET_KEY

    payload = request.body
    sig_header = request.META.get('HTTP_STRIPE_SIGNATURE', '')

    try:
        event = stripe.Webhook.construct_event(
            payload, sig_header, settings.STRIPE_WEBHOOK_SECRET
        )
    except (ValueError, stripe.error.SignatureVerificationError):
        return JsonResponse({'error': 'invalid signature'}, status=400)

    if event['type'] == 'checkout.session.completed':
        session = event['data']['object']
        customer_id = getattr(session, 'customer', None)
        sub_id = getattr(session, 'subscription', None)
        if customer_id:
            Profile.objects.filter(stripe_customer_id=customer_id).update(
                plan='pro',
                stripe_subscription_id=sub_id or '',
                plan_cancel_at=None,
            )

    elif event['type'] == 'customer.subscription.updated':
        import datetime
        sub = event['data']['object']

        def _s(key, default=None):
            try:
                return sub[key]
            except (KeyError, AttributeError):
                return default

        customer_id = _s('customer')
        status      = _s('status', '')
        # API 2026-04-22.dahlia: cancel_at_period_end is always False;
        # cancellation is signalled by cancel_at being a future timestamp.
        cancel_at   = _s('cancel_at')   # unix timestamp or None

        new_plan = 'pro' if status in ('active', 'trialing') else 'free'
        cancel_dt = (
            datetime.datetime.fromtimestamp(cancel_at, tz=datetime.timezone.utc)
            if cancel_at else None
        )
        Profile.objects.filter(stripe_customer_id=customer_id).update(
            plan=new_plan,
            plan_cancel_at=cancel_dt,
        )

    elif event['type'] in ('customer.subscription.deleted', 'customer.subscription.paused'):
        sub = event['data']['object']
        customer_id = getattr(sub, 'customer', None)
        if customer_id:
            Profile.objects.filter(stripe_customer_id=customer_id).update(
                plan='free',
                plan_cancel_at=None,
                stripe_subscription_id='',
            )

    return JsonResponse({'ok': True})


@login_required
def settings_view(request):
    profile = get_object_or_404(Profile, user=request.user)
    return render(request, 'accounts/settings.html', {
        'profile': profile,
        'is_pro': _is_pro(profile),
        'plan_cancel_at': profile.plan_cancel_at,
    })


@login_required
def submit_feedback(request):
    if request.method != 'POST':
        return JsonResponse({'error': 'method'}, status=405)
    try:
        data    = json.loads(request.body)
        rating  = data.get('rating', '').strip()
        message = data.get('message', '').strip()
    except (json.JSONDecodeError, AttributeError):
        return JsonResponse({'error': 'invalid'}, status=400)

    if not rating and not message:
        return JsonResponse({'error': 'empty'}, status=400)

    user = request.user
    subject = f"Prism feedback {rating} — {user.username}"
    body = (
        f"From: {user.get_full_name() or user.username} ({user.email})\n"
        f"Rating: {rating or '(not selected)'}\n\n"
        f"{message or '(no message)'}"
    )
    Feedback.objects.create(user=user, rating=rating, message=message)

    try:
        send_mail(subject, body, settings.DEFAULT_FROM_EMAIL, [settings.FEEDBACK_EMAIL])
    except Exception as e:
        print(f"[feedback] email failed: {e}")

    return JsonResponse({'ok': True})


@login_required
def settings_save_profile(request):
    if request.method != 'POST':
        return JsonResponse({'error': 'method'}, status=405)
    try:
        data = json.loads(request.body)
    except json.JSONDecodeError:
        return JsonResponse({'error': 'invalid_json'}, status=400)

    user = request.user
    profile = get_object_or_404(Profile, user=user)

    # Display name
    display_name = (data.get('display_name') or '').strip()[:80]
    if display_name:
        parts = display_name.split(' ', 1)
        user.first_name = parts[0][:30]
        user.last_name = (parts[1] if len(parts) > 1 else '')[:150]

    # Username
    new_username = re.sub(r'\s+', '', (data.get('username') or '').strip().lower())
    if new_username and new_username != user.username:
        if not re.match(r'^[a-z0-9_]{3,30}$', new_username):
            return JsonResponse({'error': 'invalid_username', 'message': 'Username must be 3–30 chars: a–z, 0–9, or _'}, status=400)
        if User.objects.filter(username=new_username).exclude(pk=user.pk).exists():
            return JsonResponse({'error': 'username_taken', 'message': 'That username is already taken'}, status=400)
        user.username = new_username

    user.save(update_fields=['first_name', 'last_name', 'username'])

    # Goal
    goal = (data.get('goal') or '').strip()
    if goal in dict(Profile.GOAL_CHOICES):
        profile.goal = goal
        profile.save(update_fields=['goal'])

    return JsonResponse({'ok': True, 'username': user.username})


@login_required
def settings_save_avatar(request):
    if request.method != 'POST':
        return JsonResponse({'error': 'method'}, status=405)
    file = request.FILES.get('avatar')
    if not file:
        return JsonResponse({'error': 'no_file'}, status=400)
    profile = get_object_or_404(Profile, user=request.user)
    profile.avatar = file
    profile.save(update_fields=['avatar'])
    return JsonResponse({'ok': True, 'url': profile.avatar.url})


@login_required
def settings_change_password(request):
    if request.method != 'POST':
        return JsonResponse({'error': 'method'}, status=405)
    try:
        data = json.loads(request.body)
    except json.JSONDecodeError:
        return JsonResponse({'error': 'invalid_json'}, status=400)

    old_pw = data.get('old_password', '')
    new_pw = data.get('new_password', '')
    confirm_pw = data.get('confirm_password', '')

    if not request.user.has_usable_password():
        return JsonResponse({'error': 'no_password', 'message': 'Your account uses Google sign-in — no password to change'}, status=400)
    if not request.user.check_password(old_pw):
        return JsonResponse({'error': 'wrong_password', 'message': 'Current password is incorrect'}, status=400)
    if len(new_pw) < 8:
        return JsonResponse({'error': 'weak_password', 'message': 'New password must be at least 8 characters'}, status=400)
    if new_pw != confirm_pw:
        return JsonResponse({'error': 'mismatch', 'message': 'New passwords do not match'}, status=400)

    request.user.set_password(new_pw)
    request.user.save()
    update_session_auth_hash(request, request.user)
    return JsonResponse({'ok': True})


@login_required
def persona_generate_bio(request):
    if request.method != 'POST':
        return JsonResponse({'error': 'method'}, status=405)
    try:
        data = json.loads(request.body)
    except json.JSONDecodeError:
        return JsonResponse({'error': 'invalid_json'}, status=400)

    mode = data.get('mode', 'fan')
    if mode not in VALID_MODES:
        return JsonResponse({'error': 'invalid_mode'}, status=400)

    # Optional freeform description from the user
    description = (data.get('description') or '').strip()[:400]

    profile = get_object_or_404(Profile, user=request.user)
    persona = Persona.objects.filter(user=request.user, mode=mode).first()

    name = (request.user.first_name or request.user.username).strip()
    goal = profile.goal or 'creator'
    platforms = [p.get('name', '') for p in (profile.platforms or []) if isinstance(p, dict)]
    niche_tags = (persona.niche_tags if persona else []) or []
    past_brands = (persona.past_brands if persona else []) or []

    persona_instructions = {
        'fan': (
            "Write a short, warm and engaging bio for a creator's Fan page. "
            "Tone: casual, friendly, community-focused. "
            "It should feel like the creator is talking directly to their fans. "
            "Max 2 sentences."
        ),
        'brand': (
            "Write a concise, professional bio for a creator's Brand collaboration page. "
            "Tone: confident, data-aware, business-oriented. "
            "It should speak to brand managers and marketers, highlighting reach and credibility. "
            "Max 2 sentences."
        ),
        'professional': (
            "Write a sharp professional bio for a creator's Professional / recruiter page. "
            "Tone: formal, achievement-focused. "
            "It should appeal to employers, clients, or collaborators looking at skills and experience. "
            "Max 2 sentences."
        ),
    }

    context_parts = [f"Name: {name}", f"Goal: {goal}"]
    if platforms:
        context_parts.append(f"Active platforms: {', '.join(platforms)}")
    if niche_tags:
        context_parts.append(f"Content niche: {', '.join(niche_tags)}")
    if past_brands:
        context_parts.append(f"Past brand partners: {', '.join(past_brands)}")
    if description:
        context_parts.append(f"Creator's own description: {description}")

    prompt = (
        f"{persona_instructions[mode]}\n\n"
        f"Creator context:\n" + "\n".join(context_parts) + "\n\n"
        + ("Use the creator's own description as the primary source of truth. " if description else "")
        + "Return only the bio text — no quotes, no labels, no explanation."
    )

    try:
        from groq import Groq
        client = Groq(api_key=settings.GROQ_API_KEY)
        response = client.chat.completions.create(
            model='llama-3.1-8b-instant',
            messages=[{'role': 'user', 'content': prompt}],
            max_tokens=120,
            temperature=0.8,
        )
        bio = response.choices[0].message.content.strip().strip('"').strip("'")
        return JsonResponse({'ok': True, 'bio': bio})
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)


@login_required
def settings_delete_account(request):
    if request.method != 'POST':
        return JsonResponse({'error': 'method'}, status=405)
    try:
        data = json.loads(request.body)
    except json.JSONDecodeError:
        return JsonResponse({'error': 'invalid_json'}, status=400)

    confirm = (data.get('confirm') or '').strip()
    if confirm != request.user.username:
        return JsonResponse({'error': 'wrong_confirm', 'message': 'Type your exact username to confirm'}, status=400)

    user = request.user
    logout(request)
    user.delete()
    return JsonResponse({'ok': True})
