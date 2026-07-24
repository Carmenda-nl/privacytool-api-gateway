# ------------------------------------------------------------------------------------------------ #
# Copyright (c) 2026 Carmenda. All rights reserved.                                                #
# This program is distributed under the terms of the PolyForm Noncommercial License 1.0.0          #
# ------------------------------------------------------------------------------------------------ #

"""ASGI configuration for the Django project."""

from __future__ import annotations

import os

from django.core.asgi import get_asgi_application

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'main.settings')
application = get_asgi_application()
