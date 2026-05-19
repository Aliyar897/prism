from pathlib import Path
import os
import email.charset

# Load .env file if present (local development)
_env_path = Path(__file__).resolve().parent.parent / '.env'
if _env_path.exists():
    for _line in _env_path.read_text().splitlines():
        _line = _line.strip()
        if _line and not _line.startswith('#') and '=' in _line:
            _k, _v = _line.split('=', 1)
            os.environ.setdefault(_k.strip(), _v.strip())

# Force 8-bit body encoding for outgoing emails.
# Django's default utf-8 charset uses quoted-printable, which wraps lines at
# 76 characters and inserts '=' soft-breaks — breaking verification URLs.
# 8-bit encoding sends the body as-is, keeping every URL intact.
email.charset.add_charset('utf-8', email.charset.SHORTEST, None, 'utf-8')

BASE_DIR = Path(__file__).resolve().parent.parent


# --------------------------------------------------
# SECURITY
# --------------------------------------------------
SECRET_KEY = os.environ.get('SECRET_KEY', 'django-insecure-change-me-in-production')
GROQ_API_KEY = os.environ.get('GROQ_API_KEY', '')

STRIPE_SECRET_KEY      = os.environ.get('STRIPE_SECRET_KEY', '')
STRIPE_PUBLISHABLE_KEY = os.environ.get('STRIPE_PUBLISHABLE_KEY', '')
STRIPE_PRICE_ID        = os.environ.get('STRIPE_PRICE_ID', '')
STRIPE_WEBHOOK_SECRET  = os.environ.get('STRIPE_WEBHOOK_SECRET', '')
DEBUG = True
ALLOWED_HOSTS = ['aliyar116.pythonanywhere.com', '127.0.0.1', '10.42.55.182', 'localhost']


# --------------------------------------------------
# APPS
# --------------------------------------------------
INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    'django.contrib.sites',

    'allauth',
    'allauth.account',
    'allauth.socialaccount',
    'allauth.socialaccount.providers.google',

    'accounts',
]

SITE_ID = 1


# --------------------------------------------------
# MIDDLEWARE
# --------------------------------------------------
MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'allauth.account.middleware.AccountMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
]


# --------------------------------------------------
# URLS / WSGI
# --------------------------------------------------
ROOT_URLCONF = 'prism.urls'
WSGI_APPLICATION = 'prism.wsgi.application'


# --------------------------------------------------
# TEMPLATES
# --------------------------------------------------
TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [os.path.join(BASE_DIR, 'templates')],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
            ],
        },
    },
]


# --------------------------------------------------
# DATABASE
# --------------------------------------------------
DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.sqlite3',
        'NAME': BASE_DIR / 'db.sqlite3',
    }
}


# --------------------------------------------------
# AUTH BACKENDS
# --------------------------------------------------
AUTHENTICATION_BACKENDS = [
    'django.contrib.auth.backends.ModelBackend',
    'allauth.account.auth_backends.AuthenticationBackend',
]


# --------------------------------------------------
# PASSWORD VALIDATION
# --------------------------------------------------
AUTH_PASSWORD_VALIDATORS = [
    {'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator'},
    {'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator'},
    {'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator'},
    {'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator'},
]


# --------------------------------------------------
# ALLAUTH — EMAIL AUTH
# --------------------------------------------------
ACCOUNT_ADAPTER = 'accounts.adapter.AccountAdapter'
SOCIALACCOUNT_ADAPTER = 'accounts.adapter.SocialAccountAdapter'
ACCOUNT_FORMS = {'signup': 'accounts.forms.CustomSignupForm'}

ACCOUNT_LOGIN_METHODS = {'email'}
ACCOUNT_SIGNUP_FIELDS = ['email*', 'username*', 'password1*', 'password2*']

ACCOUNT_EMAIL_VERIFICATION = 'mandatory'
ACCOUNT_EMAIL_CONFIRMATION_HMAC = True
ACCOUNT_CONFIRM_EMAIL_ON_GET = True
ACCOUNT_LOGIN_ON_EMAIL_CONFIRMATION = True

# After clicking the verification link → go to onboarding
ACCOUNT_EMAIL_CONFIRMATION_AUTHENTICATED_REDIRECT_URL = '/onboarding/'
ACCOUNT_EMAIL_CONFIRMATION_ANONYMOUS_REDIRECT_URL = '/accounts/login/'

ACCOUNT_EMAIL_SUBJECT_PREFIX = '[Prism] '
# After signup → allauth shows the "check your inbox" page automatically (no override needed)


# --------------------------------------------------
# ALLAUTH — SOCIAL (GOOGLE)
# --------------------------------------------------
SOCIALACCOUNT_LOGIN_ON_GET = True
SOCIALACCOUNT_AUTO_SIGNUP = True
SOCIALACCOUNT_EMAIL_VERIFICATION = 'none'
SOCIALACCOUNT_EMAIL_AUTHENTICATION = True
SOCIALACCOUNT_EMAIL_AUTHENTICATION_AUTO_CONNECT = True


# --------------------------------------------------
# SESSION — persistent login (30 days, survives browser close)
# --------------------------------------------------
SESSION_COOKIE_AGE = 60 * 60 * 24 * 30   # 30 days in seconds
SESSION_EXPIRE_AT_BROWSER_CLOSE = False
SESSION_SAVE_EVERY_REQUEST = True         # slide the expiry on each request
ACCOUNT_SESSION_REMEMBER = True           # allauth: always persist the session

# --------------------------------------------------
# REDIRECTS
# --------------------------------------------------
LOGIN_REDIRECT_URL = '/redirect/'
LOGOUT_REDIRECT_URL = '/'


# --------------------------------------------------
# EMAIL (DEV — writes .eml files, no line-wrapping issues)
# --------------------------------------------------
EMAIL_BACKEND    = 'django.core.mail.backends.smtp.EmailBackend'
EMAIL_HOST       = 'smtp.gmail.com'
EMAIL_PORT       = 587
EMAIL_USE_TLS    = True
EMAIL_HOST_USER     = os.environ.get('EMAIL_HOST_USER', '')
EMAIL_HOST_PASSWORD = os.environ.get('EMAIL_HOST_PASSWORD', '')
DEFAULT_FROM_EMAIL  = f"Prism <{os.environ.get('EMAIL_HOST_USER', 'noreply@prism.so')}>"
FEEDBACK_EMAIL      = os.environ.get('EMAIL_HOST_USER', '')


# --------------------------------------------------
# INTERNATIONALISATION
# --------------------------------------------------
LANGUAGE_CODE = 'en-us'
TIME_ZONE = 'UTC'
USE_I18N = True
USE_TZ = True
DEFAULT_CHARSET = 'utf-8'


# --------------------------------------------------
# STATIC & MEDIA
# --------------------------------------------------
STATIC_URL = 'static/'
MEDIA_URL = '/media/'
MEDIA_ROOT = BASE_DIR / 'media'
