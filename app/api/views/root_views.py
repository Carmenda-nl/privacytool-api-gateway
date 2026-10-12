# ------------------------------------------------------------------------------------------------ #
# Copyright (c) 2026 Carmenda. All rights reserved.                                                #
# This program is distributed under the terms of the PolyForm Noncommercial License 1.0.0          #
# ------------------------------------------------------------------------------------------------ #

"""API root view with documentation links, Version control and Settings config values."""

from __future__ import annotations

import time
from pathlib import Path
from typing import TYPE_CHECKING, cast

from django.conf import settings
from django.http import Http404
from django.utils.translation import gettext as _
from rest_framework import generics
from rest_framework.exceptions import ValidationError
from rest_framework.response import Response
from rest_framework.reverse import reverse
from rest_framework.views import APIView

from api.serializers import ConfigValuesSerializer
from api.utils.previews import file_metadata
from preprocessing.encryption import decrypt_bytes
from settings.models import ConfigValues

if TYPE_CHECKING:
    from rest_framework.request import Request


class ApiTags:
    """API tag constants for Swagger/OpenAPI documentation grouping.

    These tags are used to categorize endpoints in the API documentation
    for better organization and discoverability.
    """

    API = 'API'
    JOBS = 'Jobs'
    PROCESSING = 'Processing'
    CANCEL = 'Cancel'


class APIRootView(APIView):
    """Custom API root view that includes documentation links."""

    def get(self, request: Request, format_suffix: str | None = None) -> Response:
        """Return links to all available endpoints."""
        data = {
            'v1/jobs': reverse('jobs-list', request=request, format=format_suffix),
            'v1/version': reverse('version', request=request, format=format_suffix),
            'v2/settings': reverse('settings', request=request, format=format_suffix),
        }
        return Response(data)


class VersionView(APIView):
    """Returns the current application version."""

    def get(self, request: Request) -> Response:
        """Return the application version."""
        return Response({'version': settings.APP_VERSION})


class ConfigValuesView(generics.RetrieveUpdateAPIView):
    """Retrieve and update the application config values."""

    serializer_class = ConfigValuesSerializer
    http_method_names = ('get', 'put', 'patch', 'head', 'options')

    def get_object(self) -> ConfigValues:
        """Return the config values instance, creating it if missing."""
        config_values = ConfigValues.objects.first()

        if config_values is None:
            config_values = ConfigValues.objects.create()

        return config_values


class DatakeyView(generics.GenericAPIView):
    """Retrieve the stored reusable datakey, or validate a new one without storing it."""

    serializer_class = ConfigValuesSerializer

    def get(self, request: Request) -> Response:
        """Return the decrypted reusable datakey content."""
        config_values = ConfigValues.objects.first()
        reusable_datakey = config_values.reusable_datakey if config_values else None

        if not reusable_datakey:
            raise Http404

        with reusable_datakey.open('rb') as source:
            return Response(decrypt_bytes(source.read()).decode('utf-8'))

    def post(self, request: Request) -> Response:
        """Return the metadata the datakey would get, or the validation errors."""
        serializer = self.get_serializer(data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)

        if not serializer.validated_data.get('reusable_datakey'):
            raise ValidationError({'reusable_datakey': [_('No file was submitted.')]})

        file = serializer.validated_data['reusable_datakey']
        return Response(file_metadata(Path(cast('str', file.name)).name, file.size, int(time.time())))
