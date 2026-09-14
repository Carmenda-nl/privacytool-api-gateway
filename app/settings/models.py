# ------------------------------------------------------------------------------------------------ #
# Copyright (c) 2026 Carmenda. All rights reserved.                                                #
# This program is distributed under the terms of the PolyForm Noncommercial License 1.0.0          #
# ------------------------------------------------------------------------------------------------ #

"""Settings model for the Django project."""

from pathlib import Path

from django.core.exceptions import ValidationError
from django.db import models

from main.storage import OverwriteStorage

datakey_storage = OverwriteStorage()


def datakey_path(_instance: ConfigValues, filename: str) -> str:
    """Generate the reusable datakey file path."""
    return str(Path('key') / filename)


class ConfigValues(models.Model):
    """Model to store config values for the application."""

    language_selection = models.CharField(max_length=2, default='nl')
    engine_selection = models.CharField(blank=True, default='')
    reusable_datakey = models.FileField(upload_to=datakey_path, storage=datakey_storage, null=True, blank=True)

    def __str__(self) -> str:
        """Return a string representation of the config values."""
        return 'Config values'

    def clean(self) -> None:
        """Ensure only one config values instance exists."""
        super().clean()
        if not self.id and ConfigValues.objects.exists():
            reason = 'Only one instance of config values is allowed.'
            raise ValidationError(reason)
