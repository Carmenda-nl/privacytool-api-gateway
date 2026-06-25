# ------------------------------------------------------------------------------------------------ #
# Copyright (c) 2026 Carmenda. All rights reserved.                                                #
# This program is distributed under the terms of the GNU General Public License: GPL-3.0-or-later  #
# ------------------------------------------------------------------------------------------------ #

"""Preprocessor app for the Django project."""

from django.apps import AppConfig


class PreprocessingConfig(AppConfig):
    """Base configuration for the current app."""

    name = 'preprocessing'
