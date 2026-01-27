"""
Django development settings.
"""
from .base import *  # noqa: F401, F403

DEBUG = True

# Additional development apps
INSTALLED_APPS += [  # noqa: F405
    'django_extensions',
]

# Development-specific middleware
MIDDLEWARE.insert(0, 'debug_toolbar.middleware.DebugToolbarMiddleware')  # noqa: F405
INSTALLED_APPS.insert(0, 'debug_toolbar')  # noqa: F405

# Debug toolbar settings
INTERNAL_IPS = ['127.0.0.1', 'localhost']

# Allow all hosts in development
ALLOWED_HOSTS = ['*']

# CORS allow all in development
CORS_ALLOW_ALL_ORIGINS = True

# Email backend for development
EMAIL_BACKEND = 'django.core.mail.backends.console.EmailBackend'

# Disable caching in development
CACHES = {
    'default': {
        'BACKEND': 'django.core.cache.backends.locmem.LocMemCache',
    }
}

# Show SQL queries in console
LOGGING['loggers']['django.db.backends'] = {  # noqa: F405
    'handlers': ['console'],
    'level': 'DEBUG',
    'propagate': False,
}
