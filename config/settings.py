"""
Django settings for study abroad platform MVP.
Target Audience: 9th-11th grade high school students in Uzbekistan.
"""
import os
from pathlib import Path
from urllib.parse import urlparse
from dotenv import load_dotenv

# Build paths inside the project like this: BASE_DIR / 'subdir'.
BASE_DIR = Path(__file__).resolve().parent.parent

# Load environment variables from .env if present
load_dotenv(BASE_DIR / '.env')

# Quick-start development settings - unsuitable for production
# See https://docs.djangoproject.com/en/6.0/howto/deployment/checklist/

SECRET_KEY = os.getenv('DJANGO_SECRET_KEY', 'django-insecure-study-abroad-platform-mvp-uzbekistan-secret-key')

DEBUG = os.getenv('DJANGO_DEBUG', 'True').lower() in ('true', '1', 'yes', 't')

ALLOWED_HOSTS = [host.strip() for host in os.getenv('DJANGO_ALLOWED_HOSTS', '*').split(',') if host.strip()]

# Application definition
INSTALLED_APPS = [
    'jazzmin',
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',

    # Third-party apps
    'rest_framework',

    # Local application modules
    'apps.core',
    'apps.accounts',
    'apps.onboarding',
    'apps.study_plans',
    'apps.tasks',
    'apps.dashboard',
    'apps.mentor',
    'apps.programs',
    'apps.services',
    'apps.documents',
    'apps.resources',
    'apps.mock_exams',
]

MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'whitenoise.middleware.WhiteNoiseMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
]

CSRF_TRUSTED_ORIGINS = [
    'https://*.railway.app',
    'https://*.up.railway.app',
    'http://localhost:8000',
    'http://127.0.0.1:8000',
    'https://rahimovsuhbatlar.uz',
    'https://*.rahimovsuhbatlar.uz',
]
csrf_env = os.getenv('CSRF_TRUSTED_ORIGINS')
if csrf_env:
    CSRF_TRUSTED_ORIGINS.extend([origin.strip() for origin in csrf_env.split(',') if origin.strip()])

ROOT_URLCONF = 'config.urls'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [BASE_DIR / 'templates'],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.debug',
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
                'apps.core.context_processors.trust_safety_context',
            ],
        },
    },
]

WSGI_APPLICATION = 'config.wsgi.application'
ASGI_APPLICATION = 'config.asgi.application'

# Custom User Model & Auth Backends
AUTH_USER_MODEL = 'accounts.User'

AUTHENTICATION_BACKENDS = [
    'apps.accounts.backends.PhoneAuthBackend',
    'django.contrib.auth.backends.ModelBackend',
]

# Persistent Volume & Media settings (Railway /data volume support)
DATA_DIR_PATH = os.getenv('DATA_DIR', '/data')
DATA_DIR = Path(DATA_DIR_PATH)

if DATA_DIR.exists() and (DATA_DIR.is_dir() or str(DATA_DIR) == '/data'):
    try:
        os.makedirs(DATA_DIR, exist_ok=True)
        sqlite_in_data = DATA_DIR / 'db.sqlite3'
        sqlite_in_base = BASE_DIR / 'db.sqlite3'

        # If /data/db.sqlite3 does not exist yet on initial mount, copy the repository db.sqlite3!
        if not sqlite_in_data.exists() and sqlite_in_base.exists():
            import shutil
            try:
                shutil.copy2(sqlite_in_base, sqlite_in_data)
                print(f"[Railway Volume] Copied base database {sqlite_in_base} to persistent volume {sqlite_in_data}")
            except Exception as copy_err:
                print(f"[Railway Volume] Notice: Could not copy initial db: {copy_err}")

        DEFAULT_SQLITE_PATH = sqlite_in_data
        MEDIA_ROOT = DATA_DIR / 'media'
        os.makedirs(MEDIA_ROOT, exist_ok=True)
    except Exception as e:
        print(f"[Railway Volume] Volume initialization error: {e}")
        DEFAULT_SQLITE_PATH = BASE_DIR / 'db.sqlite3'
        MEDIA_ROOT = BASE_DIR / 'media'
else:
    DEFAULT_SQLITE_PATH = BASE_DIR / 'db.sqlite3'
    MEDIA_ROOT = BASE_DIR / 'media'

MEDIA_URL = '/media/'

# Session Persistence Settings (Stay logged in for 60 days, never force re-registration)
SESSION_ENGINE = 'django.contrib.sessions.backends.db'
SESSION_COOKIE_AGE = 60 * 60 * 24 * 60  # 60 days
SESSION_SAVE_EVERY_REQUEST = True
SESSION_EXPIRE_AT_BROWSER_CLOSE = False
SESSION_COOKIE_HTTPONLY = True
SESSION_COOKIE_SAMESITE = 'Lax'

# Database configuration: Dual-mode with PostgreSQL (Railway) / SQLite fallback
DATABASE_URL = os.getenv('DATABASE_URL')
if DATABASE_URL:
    try:
        import dj_database_url
        DATABASES = {
            'default': dj_database_url.config(
                default=DATABASE_URL,
                conn_max_age=600,
                conn_health_checks=True,
            )
        }
    except Exception:
        parsed_db = urlparse(DATABASE_URL)
        DATABASES = {
            'default': {
                'ENGINE': 'django.db.backends.postgresql',
                'NAME': parsed_db.path.lstrip('/'),
                'USER': parsed_db.username or '',
                'PASSWORD': parsed_db.password or '',
                'HOST': parsed_db.hostname or '',
                'PORT': parsed_db.port or '',
            }
        }
else:
    DATABASES = {
        'default': {
            'ENGINE': 'django.db.backends.sqlite3',
            'NAME': DEFAULT_SQLITE_PATH,
            'OPTIONS': {'timeout': 30},
        }
    }

# Password validation
# https://docs.djangoproject.com/en/6.0/ref/settings/#auth-password-validators
AUTH_PASSWORD_VALIDATORS = [
    {
        'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator',
        'OPTIONS': {'min_length': 6},
    },
]

# Internationalization & Localization
# https://docs.djangoproject.com/en/6.0/topics/i18n/
LANGUAGE_CODE = 'uz'
TIME_ZONE = 'Asia/Tashkent'
USE_I18N = True
USE_TZ = True

# Static files (CSS, JavaScript, Images)
# https://docs.djangoproject.com/en/6.0/howto/static-files/
STATIC_URL = '/static/'
STATICFILES_DIRS = [BASE_DIR / 'static']
STATIC_ROOT = BASE_DIR / 'staticfiles'

STORAGES = {
    "default": {
        "BACKEND": "django.core.files.storage.FileSystemStorage",
    },
    "staticfiles": {
        "BACKEND": "whitenoise.storage.CompressedStaticFilesStorage",
    },
}
WHITENOISE_MANIFEST_STRICT = False
WHITENOISE_USE_FINDERS = True

# Default primary key field type
DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

# Authentication URLs
LOGIN_URL = 'accounts:login'
LOGIN_REDIRECT_URL = 'dashboard:index'
LOGOUT_REDIRECT_URL = 'accounts:login'

# Anthropic Claude / OpenRouter API configuration
ANTHROPIC_API_KEY = os.getenv('ANTHROPIC_API_KEY', '')
ANTHROPIC_MODEL = os.getenv('ANTHROPIC_MODEL', 'claude-sonnet-4-6')

# Jazzmin Admin Configuration
JAZZMIN_SETTINGS = {
    "site_title": "UniMentor Admin",
    "site_header": "UniMentor",
    "site_brand": "UniMentor AI",
    "site_logo_classes": "img-circle",
    "welcome_sign": "UniMentor Boshqaruv Paneliga Xush Kelibsiz",
    "copyright": "UniMentor Platformasi",
    "search_model": ["accounts.User", "programs.Program", "programs.University", "documents.Document"],
    "user_avatar": None,
    "topmenu_links": [
        {"name": "Bosh sahifa", "url": "admin:index", "permissions": ["auth.view_user"]},
        {"name": "Saytga o'tish", "url": "/", "new_window": True},
    ],
    "show_sidebar": True,
    "navigation_expanded": True,
    "hide_apps": [],
    "hide_models": [],
    "order_with_respect_to": ["accounts", "programs", "onboarding", "documents", "resources", "tasks", "study_plans", "mentor"],
    "icons": {
        "auth": "fas fa-users-cog",
        "auth.user": "fas fa-user",
        "auth.Group": "fas fa-users",
        "accounts.User": "fas fa-user-shield",
        "accounts.Student": "fas fa-user-graduate",
        "programs.Program": "fas fa-award",
        "programs.University": "fas fa-university",
        "programs.StudentProgram": "fas fa-bookmark",
        "documents.Document": "fas fa-file-alt",
        "resources.Resource": "fas fa-book-open",
        "tasks.DailyTask": "fas fa-clipboard-check",
        "study_plans.StudyPlan": "fas fa-calendar-check",
        "mentor.MentorMessage": "fas fa-comment-dots",
        "onboarding.TestCertificate": "fas fa-certificate",
        "onboarding.DiagnosticResult": "fas fa-stethoscope",
        "dashboard.ProgressLog": "fas fa-chart-line",
        "mock_exams.MockExam": "fas fa-stopwatch",
        "mock_exams.MockExamSection": "fas fa-tasks",
    },
    "default_icon_parents": "fas fa-chevron-circle-right",
    "default_icon_children": "fas fa-circle",
    "related_modal_active": True,
    "custom_css": None,
    "custom_js": None,
    "use_google_fonts_cdn": True,
    "show_ui_builder": False,
    "changeform_format": "horizontal_tabs",
}

JAZZMIN_UI_TWEAKS = {
    "navbar_small_text": False,
    "footer_small_text": False,
    "body_small_text": False,
    "brand_small_text": False,
    "brand_colour": "navbar-indigo",
    "accent": "accent-indigo",
    "navbar": "navbar-dark navbar-indigo",
    "no_navbar_border": False,
    "navbar_fixed": True,
    "layout_boxed": False,
    "footer_fixed": False,
    "sidebar_fixed": True,
    "sidebar": "sidebar-dark-indigo",
    "sidebar_nav_small_text": False,
    "sidebar_disable_expand": False,
    "sidebar_nav_child_indent": True,
    "sidebar_nav_compact_style": False,
    "sidebar_nav_legacy_style": False,
    "sidebar_nav_flat_style": True,
    "theme": "default",
    "button_classes": {
        "primary": "btn-indigo",
        "secondary": "btn-outline-secondary",
        "info": "btn-info",
        "warning": "btn-warning",
        "danger": "btn-danger",
        "success": "btn-success"
    }
}

# Celery Configuration
CELERY_BROKER_URL = os.environ.get('REDIS_URL', 'redis://localhost:6379/0')
CELERY_RESULT_BACKEND = os.environ.get('REDIS_URL', 'redis://localhost:6379/0')
CELERY_ACCEPT_CONTENT = ['json']
CELERY_TASK_SERIALIZER = 'json'
CELERY_RESULT_SERIALIZER = 'json'
CELERY_TIMEZONE = TIME_ZONE

# Celery Beat Schedule
from celery.schedules import crontab
CELERY_BEAT_SCHEDULE = {
    'decay-scores-every-midnight': {
        'task': 'apps.dashboard.tasks.decay_student_scores_task',
        'schedule': crontab(hour=0, minute=0),
    },
}
