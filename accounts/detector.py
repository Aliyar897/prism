from urllib.parse import urlparse

VALID_MODES = {'fan', 'brand', 'professional'}

# All aliases a creator or brand might use in a ?ref= link
MODE_ALIASES = {
    'fan': 'fan', 'fans': 'fan', 'follow': 'fan', 'social': 'fan',
    'community': 'fan', 'audience': 'fan',
    'brand': 'brand', 'biz': 'brand', 'business': 'brand', 'sponsor': 'brand',
    'partner': 'brand', 'media': 'brand', 'pr': 'brand', 'collab': 'brand',
    'brands': 'brand', 'partnership': 'brand', 'advertise': 'brand',
    'professional': 'professional', 'pro': 'professional', 'work': 'professional',
    'hire': 'professional', 'recruit': 'professional', 'cv': 'professional',
    'portfolio': 'professional', 'resume': 'professional',
}

# HTTP Referer domain → (mode, confidence)
# LinkedIn → brand: brand managers discover creators on LinkedIn, not recruiters
# Email clients → brand: if someone clicked from their inbox, it's almost certainly a pitch
# Influencer platforms → brand: these tools are used exclusively by brands/agencies
REFERRER_MAP = {
    # ── Social / Fan ────────────────────────────────────────────
    'instagram.com':        ('fan', 0.92),
    'www.instagram.com':    ('fan', 0.92),
    'l.instagram.com':      ('fan', 0.92),  # Instagram link proxy
    'tiktok.com':           ('fan', 0.92),
    'www.tiktok.com':       ('fan', 0.92),
    'vm.tiktok.com':        ('fan', 0.92),  # TikTok short links
    'youtube.com':          ('fan', 0.88),
    'www.youtube.com':      ('fan', 0.88),
    'm.youtube.com':        ('fan', 0.88),
    'youtu.be':             ('fan', 0.88),
    't.co':                 ('fan', 0.85),  # Twitter/X link shortener
    'twitter.com':          ('fan', 0.85),
    'x.com':                ('fan', 0.85),
    'facebook.com':         ('fan', 0.82),
    'www.facebook.com':     ('fan', 0.82),
    'fb.me':                ('fan', 0.82),
    'threads.net':          ('fan', 0.88),
    'www.threads.net':      ('fan', 0.88),
    'snapchat.com':         ('fan', 0.88),
    'reddit.com':           ('fan', 0.75),
    'www.reddit.com':       ('fan', 0.75),
    'pinterest.com':        ('fan', 0.78),
    'www.pinterest.com':    ('fan', 0.78),
    'twitch.tv':            ('fan', 0.88),
    'www.twitch.tv':        ('fan', 0.88),
    'spotify.com':          ('fan', 0.75),
    'open.spotify.com':     ('fan', 0.75),
    'discord.com':          ('fan', 0.72),
    'discord.gg':           ('fan', 0.72),
    'bereal.com':           ('fan', 0.82),

    # ── Brand / Collaboration ────────────────────────────────────
    'linkedin.com':         ('brand', 0.88),
    'www.linkedin.com':     ('brand', 0.88),
    'lnkd.in':              ('brand', 0.88),

    # Email clients — clicking from an inbox means they received a pitch
    'mail.google.com':      ('brand', 0.85),
    'outlook.live.com':     ('brand', 0.85),
    'outlook.com':          ('brand', 0.85),
    'mail.yahoo.com':       ('brand', 0.80),
    'mail.yahoo.co.uk':     ('brand', 0.80),

    # Influencer / creator marketing platforms (used exclusively by brands & agencies)
    'modash.io':            ('brand', 0.97),
    'hypeauditor.com':      ('brand', 0.97),
    'creatoriq.com':        ('brand', 0.97),
    'upfluence.com':        ('brand', 0.97),
    'heepsy.com':           ('brand', 0.97),
    'aspireiq.com':         ('brand', 0.97),
    'grin.co':              ('brand', 0.97),
    'influencer.com':       ('brand', 0.97),
    'izea.com':             ('brand', 0.97),
    'klear.com':            ('brand', 0.97),
    'traackr.com':          ('brand', 0.97),
    'taggermedia.com':      ('brand', 0.97),
    'mavrck.co':            ('brand', 0.97),
    'collabstr.com':        ('brand', 0.95),
    'influencerhero.com':   ('brand', 0.95),
    'roster.com':           ('brand', 0.95),
    'later.com':            ('brand', 0.82),
    'sproutsocial.com':     ('brand', 0.80),
    'hootsuite.com':        ('brand', 0.78),

    # ── Professional / Hiring ────────────────────────────────────
    'github.com':           ('professional', 0.85),
    'www.github.com':       ('professional', 0.85),
    'stackoverflow.com':    ('professional', 0.82),
    'producthunt.com':      ('professional', 0.75),
    'wellfound.com':        ('professional', 0.88),  # AngelList
    'angel.co':             ('professional', 0.88),
    'dribbble.com':         ('professional', 0.80),
    'www.dribbble.com':     ('professional', 0.80),
    'behance.net':          ('professional', 0.80),
    'www.behance.net':      ('professional', 0.80),
    'indeed.com':           ('professional', 0.85),
    'glassdoor.com':        ('professional', 0.82),
    'notion.so':            ('professional', 0.65),
}

# User-Agent substrings → (mode, confidence)
# In-app browsers are the most reliable signal — the app name is literally in the UA
UA_MAP = [
    ('Instagram',     'fan',          0.92),
    ('FBAV',          'fan',          0.88),   # Facebook App
    ('FBAN',          'fan',          0.88),
    ('TikTok',        'fan',          0.92),
    ('Snapchat',      'fan',          0.90),
    ('Twitter',       'fan',          0.85),
    ('Pinterest',     'fan',          0.82),
    ('LinkedInApp',   'brand',        0.92),   # LinkedIn mobile app
    ('linkedin',      'brand',        0.85),
]


def detect(request):
    """
    Detection waterfall. Returns (mode, confidence, detected_by).
    mode is None when all signals miss — caller applies the default.
    """
    ua = request.META.get('HTTP_USER_AGENT', '')

    # ── 1. Explicit URL param (highest priority — creator-controlled) ─────────
    for param in ('ref', 'mode', 'view', 'as'):
        raw = request.GET.get(param, '').lower().strip()
        if raw:
            mode = MODE_ALIASES.get(raw) or (raw if raw in VALID_MODES else None)
            if mode:
                return mode, 1.0, 'url_param'

    # ── 2. UTM parameters ─────────────────────────────────────────────────────
    utm_medium   = request.GET.get('utm_medium',   '').lower()
    utm_source   = request.GET.get('utm_source',   '').lower()
    utm_campaign = request.GET.get('utm_campaign', '').lower()

    # Brand signals from UTM
    if any(k in utm_medium for k in ('pr', 'partnership', 'sponsor', 'brand', 'collab')):
        return 'brand', 0.90, 'utm'
    if any(k in utm_campaign for k in ('collab', 'brand', 'sponsor', 'partnership', 'deal')):
        return 'brand', 0.85, 'utm'
    if utm_source in ('linkedin', 'modash', 'hypeauditor', 'creatoriq', 'upfluence'):
        return 'brand', 0.88, 'utm'
    # Email/newsletter UTM → brand (people emailing you about collabs, not job hunting)
    if any(k in utm_medium for k in ('email', 'newsletter', 'outreach', 'pitch')):
        return 'brand', 0.80, 'utm'

    # Fan signals from UTM
    if utm_source in ('instagram', 'tiktok', 'youtube', 'twitter', 'snapchat', 'facebook'):
        return 'fan', 0.88, 'utm'
    if utm_medium == 'social':
        return 'fan', 0.75, 'utm'

    # Professional signals from UTM
    if utm_source in ('github', 'stackoverflow', 'indeed', 'wellfound'):
        return 'professional', 0.85, 'utm'
    if utm_medium in ('job', 'hiring', 'recruit'):
        return 'professional', 0.85, 'utm'

    # ── 3. HTTP Referer header ────────────────────────────────────────────────
    referer = request.META.get('HTTP_REFERER', '')
    if referer:
        try:
            netloc = urlparse(referer).netloc.lower()
            result = REFERRER_MAP.get(netloc)
            if not result:
                bare = netloc.lstrip('www.')
                result = REFERRER_MAP.get(bare) or REFERRER_MAP.get('www.' + bare)
            if result:
                mode, confidence = result
                return mode, confidence, 'referrer'
        except Exception:
            pass

    # ── 4. User-Agent (in-app browser) ───────────────────────────────────────
    for ua_sub, mode, confidence in UA_MAP:
        if ua_sub.lower() in ua.lower():
            return mode, confidence, 'user_agent'

    # ── 5. Nothing matched — caller will use client-side heuristics ───────────
    return None, 0.0, 'unknown'


def client_context_score(hour: int, is_mobile: bool, is_weekend: bool) -> tuple:
    """
    Low-confidence heuristic from client-side signals (last resort only).
    Returns (mode, confidence, source). Confidence is intentionally low —
    these signals merely break ties, they don't override the user's preference.
    """
    # Weekday business hours on a desktop → lean toward brand (9-to-5 decision makers)
    if not is_weekend and not is_mobile and 9 <= hour <= 18:
        return 'brand', 0.38, 'context'

    # Mobile visit, evening or weekend → lean fan
    if is_mobile and (is_weekend or hour >= 19 or hour <= 9):
        return 'fan', 0.38, 'context'

    # Mobile during business hours — ambiguous
    if is_mobile:
        return 'fan', 0.30, 'context'

    return None, 0.0, 'context'
