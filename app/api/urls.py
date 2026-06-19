# ------------------------------------------------------------------------------------------------ #
# Copyright (c) 2026 Carmenda. All rights reserved.                                                #
# This program is distributed under the terms of the GNU General Public License: GPL-3.0-or-later  #
# ------------------------------------------------------------------------------------------------ #

"""URL configuration for the API (Django Rest Framework)."""

from __future__ import annotations

from django.urls import include, path
from rest_framework.routers import DefaultRouter

from api.views import APIRootView, DeidentificationJobViewSet, VersionView
from api.views.root_views import ConfigValuesView
from api.views.sse_views import progress

router = DefaultRouter()
router.register('v1/jobs', DeidentificationJobViewSet, basename='jobs')

urlpatterns = [
    path('', APIRootView.as_view(), name='api-root'),
    path('', include(router.urls)),
    path('v1/version/', VersionView.as_view(), name='version'),
    path('v2/settings/', ConfigValuesView.as_view(), name='settings'),
    path('v2/jobs/<str:job_id>/progress/', progress, name='progress'),
]
