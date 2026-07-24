# ------------------------------------------------------------------------------------------------ #
# Copyright (c) 2026 Carmenda. All rights reserved.                                                #
# This program is distributed under the terms of the PolyForm Noncommercial License 1.0.0          #
# ------------------------------------------------------------------------------------------------ #

"""URL configuration for the Django project."""

import sys

from django.conf import settings
from django.conf.urls.static import static
from django.urls import include, path
from django.views.generic import RedirectView

urlpatterns = [
    path('', RedirectView.as_view(url='/api/', permanent=True)),
    path('api/', include('api.urls')),
]

if not getattr(sys, 'frozen', False):
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
    if not settings.DEBUG:
        from django.views.static import serve

        urlpatterns += [
            path(f'{settings.MEDIA_URL.lstrip("/")}<path:path>', serve, {'document_root': settings.MEDIA_ROOT})
        ]
