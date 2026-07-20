# ------------------------------------------------------------------------------------------------ #
# Copyright (c) 2026 Carmenda. All rights reserved.                                                #
# This program is distributed under the terms of the PolyForm Noncommercial License 1.0.0          #
# ------------------------------------------------------------------------------------------------ #

"""Django logging configuration.

The asyncio logger is silenced to reduce noise in production.
"""

from pathlib import Path

from django.conf import settings
from django.core.exceptions import ImproperlyConfigured


def get_log_level() -> str:
    """Get the LOG_LEVEL from Django settings."""
    try:
        return getattr(settings, 'LOG_LEVEL', 'INFO')
    except ImproperlyConfigured:
        return 'INFO'


LOG_LEVEL = get_log_level()
BASE_DIR = Path(__file__).resolve().parent.parent


# Create directory if it doesn't exist
logs_dir = BASE_DIR / 'data' / 'output'
logs_dir.mkdir(parents=True, exist_ok=True)


LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,
    'filters': {
        'ignore_favicon': {
            '()': 'django.utils.log.CallbackFilter',
            'callback': lambda record: '/favicon.ico' not in record.getMessage(),
        },
    },
    'formatters': {
        'verbose': {
            'format': '{levelname} {asctime} {module} {message}',
            'style': '{',
        },
        'console': {
            'format': '{asctime} {name} {levelname} {message}',
            'style': '{',
            'datefmt': '%Y-%m-%d %H:%M:%S',
        },
    },
    'handlers': {
        'console': {
            'level': LOG_LEVEL,
            'class': 'logging.StreamHandler',
            'formatter': 'console',
            'filters': ['ignore_favicon'],
        },
        'debug_file': {
            'level': 'DEBUG',
            'class': 'logging.handlers.RotatingFileHandler',
            'filename': str(logs_dir / 'debug.log'),
            'maxBytes': 2 * 1024 * 1024,
            'backupCount': 3,
            'encoding': 'utf-8',
            'formatter': 'verbose',
        },
    },
    'root': {
        'handlers': ['console', 'debug_file'],
        'level': LOG_LEVEL,
    },
    'loggers': {
        'django': {
            'handlers': ['console', 'debug_file'],
            'level': 'INFO',
            'propagate': False,
        },
        'django.request': {
            'handlers': ['console', 'debug_file'],
            'level': 'ERROR',
            'propagate': False,
        },
        'django.db.backends': {
            'handlers': ['console', 'debug_file'],
            'level': 'INFO',
            'propagate': False,
        },
        'django.channels': {
            'handlers': ['console'],
            'level': 'ERROR',
            'propagate': False,
        },
        'asyncio': {
            'handlers': ['console'],
            'level': 'WARNING',
            'propagate': False,
        },
    },
}
