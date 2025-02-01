import os
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

# Build paths inside the project like this: BASE_DIR / 'subdir'.
BASE_DIR = Path(__file__).resolve().parent.parent

# SECURITY WARNING: keep the secret key used in production secret!
SECRET_KEY = 'T0PS3CR3TSH1T'

# SECURITY WARNING: don't run with debug turned on in production!
DEBUG = True

ALLOWED_HOSTS = ['138.197.95.73', 'gbp.backus.agency', 'localhost', '127.0.0.1']

CSRF_TRUSTED_ORIGINS = [
    'https://gbp.backus.agency',
]

SESSION_ENGINE = 'django.contrib.sessions.backends.db'

AUTHENTICATION_BACKENDS = [
    'django.contrib.auth.backends.ModelBackend',
    'allauth.account.auth_backends.AuthenticationBackend',
]

# Custom adapter for handling multiple social apps
INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    'gbp_django',  # Ensure this is the correct app name
    'gbp_django.templatetags',  # Add templatetags
    'django.contrib.sites',  # Add this if not present
    'django_extensions',
    'allauth',
    'allauth.account',
    'allauth.socialaccount',
    'allauth.socialaccount.providers.google',
]

MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'allauth.account.middleware.AccountMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
]

ROOT_URLCONF = 'gbp_django.urls'

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
                'django.template.context_processors.request',  # Required by allauth
            ],
        },
    },
]

AUTH_USER_MODEL = 'gbp_django.User'

WSGI_APPLICATION = 'gbp_django.wsgi.application'

# Database
# https://docs.djangoproject.com/en/4.0/ref/settings/#databases
DATABASES = {
    'default': {
        'ENGINE': os.getenv('DATABASE_ENGINE'),
        'NAME': os.getenv('DATABASE_NAME'),
        'USER': os.getenv('DATABASE_USER'),
        'PASSWORD': os.getenv('DATABASE_PASSWORD'),
        'HOST': os.getenv('DATABASE_HOST'),
        'PORT': os.getenv('DATABASE_PORT'),
        'OPTIONS': {
            'options': '-c search_path=public'
        },
        'TEST': {
            'OPTIONS': {
                'options': '-c search_path=public -c default_table_access_method=heap',
                'isolation_level': 'repeatable read',
            },
        },
    }
}

# Password validation
# https://docs.djangoproject.com/en/4.0/ref/settings/#auth-password-validators
AUTH_PASSWORD_VALIDATORS = []

# Content Security Policy settings
CSP_DEFAULT_SRC = ["'self'", "https://ui-avatars.com", "data:"]
CSP_STYLE_SRC = ["'self'", "'unsafe-inline'", "https://cdn.tailwindcss.com"]
CSP_SCRIPT_SRC = ["'self'", "'unsafe-inline'", "'unsafe-eval'"]
# CSP_IMG_SRC = ["'self'", "data:", "https://ui-avatars.com"]
# CSP_FONT_SRC = ["'self'", "data:"]

# Internationalization
# https://docs.djangoproject.com/en/4.0/topics/i18n/
LANGUAGE_CODE = 'en-us'

TIME_ZONE = 'EST'

USE_I18N = True

USE_L10N = True

USE_TZ = True

# Email configuration
EMAIL_BACKEND = 'django.core.mail.backends.smtp.EmailBackend'
EMAIL_HOST = 'smtp.gmail.com'
EMAIL_PORT = 587
EMAIL_USE_TLS = True
EMAIL_HOST_USER = 'gbp.automation.pro@gmail.com'
EMAIL_HOST_PASSWORD = os.getenv('EMAIL_HOST_PASSWORD')  # Set this in .env
DEFAULT_FROM_EMAIL = 'GBP Automation Pro <gbp.automation.pro@gmail.com>'
FEEDBACK_EMAIL = 'gbp.automation.pro@gmail.com'
SUPPORT_EMAIL_SUBJECT_PREFIX = '[SUPPORT/FEEDBACK]'

# AI/ML Configuration
GROQ_API_KEY = os.getenv('GROQ_API_KEY')
LLM_MODEL = os.getenv('LLM_MODEL', 'groq')  # 'groq' or 'ollama'

SOCIALACCOUNT_PROVIDERS = {
    'google': {
        'SCOPE': [
            'openid',
            'https://www.googleapis.com/auth/business.manage',
            'https://www.googleapis.com/auth/plus.business.manage',
            'https://www.googleapis.com/auth/userinfo.email',
            'https://www.googleapis.com/auth/userinfo.profile',
            'https://www.googleapis.com/auth/mybusiness.management',
            'https://www.googleapis.com/auth/mybusiness.account',
        ],
        'AUTH_PARAMS': {
            'access_type': 'offline',
            'prompt': 'consent',
        },
        'APP': {
            'client_id': os.getenv('CLIENT_ID'),
            'secret': os.getenv('CLIENT_SECRET'),
            'key': ''
        },
        'REDIRECT_URI': 'https://gbp.backus.agency/google/callback/'
    }
}

ACCOUNT_USER_MODEL_USERNAME_FIELD = None
ACCOUNT_EMAIL_REQUIRED = True
ACCOUNT_USERNAME_REQUIRED = False
ACCOUNT_AUTHENTICATION_METHOD = 'email'
SOCIALACCOUNT_AUTO_SIGNUP = True

SITE_ID = 1  # Or the ID that matches your site in the django_sites table

# Static files (CSS, JavaScript, Images)
# https://docs.djangoproject.com/en/4.0/howto/static-files/
MEDIA_URL = '/media/'
MEDIA_ROOT = BASE_DIR / "media"
STATIC_URL = '/static/'
STATIC_ROOT = BASE_DIR / 'staticfiles'
STATICFILES_DIRS = [
    BASE_DIR / 'static',
]
STATICFILES_FINDERS = [
    'django.contrib.staticfiles.finders.FileSystemFinder',
    'django.contrib.staticfiles.finders.AppDirectoriesFinder',
]

# Site URL for email verification links
SITE_URL = 'https://gbp.backus.agency'

LOGIN_REDIRECT_URL = '/'
ACCOUNT_EMAIL_VERIFICATION = 'none'
ACCOUNT_AUTHENTICATION_METHOD = 'email'
ACCOUNT_EMAIL_REQUIRED = True
DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'
OPENAI_API_KEY = os.getenv('OPENAI_API_KEY')
OLLAMA_ENABLED = True  # Set to False if Ollama is not available
