"""
Django settings for running tests
"""
import os
import sys

# Build paths inside the project like this: BASE_DIR / 'subdir'.
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# Add the project root to Python path
sys.path.insert(0, BASE_DIR)

# SECURITY WARNING: keep the secret key used in production secret!
SECRET_KEY = 'test-secret-key-for-testing-only-do-not-use-in-production'

# SECURITY WARNING: don't run with debug turned on in production!
DEBUG = True

ALLOWED_HOSTS = ['*']

# Application definition
INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    'rest_framework',
    'drf_api_logger',
]

MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
    'drf_api_logger.middleware.api_logger_middleware.APILoggerMiddleware',
]

ROOT_URLCONF = 'tests.urls'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.debug',
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
            ],
        },
    },
]

# Database
DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.sqlite3',
        'NAME': ':memory:',
    }
}

# Password validation
AUTH_PASSWORD_VALIDATORS = [
    {
        'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator',
    },
]

# Internationalization
LANGUAGE_CODE = 'en-us'
TIME_ZONE = 'UTC'
USE_I18N = True
USE_TZ = True

# Static files (CSS, JavaScript, Images)
STATIC_URL = '/static/'
MEDIA_URL = '/media/'

# Default primary key field type
DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

# DRF API Logger settings for testing
DRF_API_LOGGER_DATABASE = False  # Default off, enable in specific tests
DRF_API_LOGGER_SIGNAL = False    # Default off, enable in specific tests
DRF_LOGGER_QUEUE_MAX_SIZE = 50
DRF_LOGGER_INTERVAL = 10
DRF_API_LOGGER_EXCLUDE_KEYS = ['password', 'token', 'access', 'refresh']
DRF_API_LOGGER_PATH_TYPE = 'ABSOLUTE'
DRF_API_LOGGER_TIMEDELTA = 0
DRF_API_LOGGER_CONTENT_TYPES = [
    "application/json",
    "application/vnd.api+json",
    "application/gzip",
    "application/octet-stream",
]
DRF_API_LOGGER_METHODS = []  # Log all methods by default
DRF_API_LOGGER_STATUS_CODES = []  # Log all status codes by default
DRF_API_LOGGER_SKIP_URL_NAME = []
DRF_API_LOGGER_SKIP_NAMESPACE = []
DRF_API_LOGGER_ENABLE_TRACING = False
DRF_API_LOGGER_MAX_REQUEST_BODY_SIZE = -1
DRF_API_LOGGER_MAX_RESPONSE_BODY_SIZE = -1

# REST Framework configuration
REST_FRAMEWORK = {
    'DEFAULT_AUTHENTICATION_CLASSES': [
        'rest_framework.authentication.SessionAuthentication',
    ],
    'DEFAULT_PERMISSION_CLASSES': [
        'rest_framework.permissions.AllowAny',  # Allow anonymous access for tests
    ],
    'TEST_REQUEST_DEFAULT_FORMAT': 'json',
}

# Test runner
TEST_RUNNER = 'django.test.runner.DiscoverRunner'

# Logging configuration for tests
LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,
    'handlers': {
        'console': {
            'class': 'logging.StreamHandler',
        },
    },
    'root': {
        'handlers': ['console'],
        'level': 'WARNING',
    },
}