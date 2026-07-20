# ------------------------------------------------------------------------------------------------ #
# Copyright (c) 2026 Carmenda. All rights reserved.                                                #
# This program is distributed under the terms of the PolyForm Noncommercial License 1.0.0          #
# ------------------------------------------------------------------------------------------------ #

"""Settings app for the Django project."""

from django.apps import AppConfig


class SettingsConfig(AppConfig):
    """Base configuration for the current app."""

    default_auto_field = 'django.db.models.BigAutoField'
    name = 'settings'
