# ------------------------------------------------------------------------------------------------ #
# Copyright (c) 2026 Carmenda. All rights reserved.                                                #
# This program is distributed under the terms of the PolyForm Noncommercial License 1.0.0          #
# ------------------------------------------------------------------------------------------------ #

"""API models for keeping track of the deidentification process."""

from __future__ import annotations

import uuid
from pathlib import Path

from django.db import models
from django.utils.text import get_valid_filename

from main.storage import OverwriteStorage
from settings.models import ConfigValues
from settings.models import engine_selection as default_engine_id

overwrite_storage = OverwriteStorage()


def default_engine() -> str:
    """Defaults to whichever engine is currently selected in the app settings."""
    config_values = ConfigValues.objects.first()
    return config_values.engine_selection if config_values else default_engine_id()


def filepath(instance: DeidentificationJob, filename: str) -> str:
    """Keep filename, but store it under a UUID folder."""
    safe_name = get_valid_filename(Path(filename).name)
    job_id = getattr(instance, 'job_id', None)
    job_part = str(job_id) if job_id is not None else ''
    return str(Path(job_part) / safe_name)


def input_path(instance: DeidentificationJob, filename: str) -> str:
    """Generate the input file path."""
    base_path = filepath(instance, filename)
    return str(Path('input') / base_path)


def output_path(instance: DeidentificationJob, filename: str) -> str:
    """Generate the output file path."""
    base_path = filepath(instance, filename)
    return str(Path('output') / base_path)


class DeidentificationJob(models.Model):
    """Maintaining state information and file references."""

    class Status(models.TextChoices):
        PENDING = 'pending', 'Pending'
        PROCESSING = 'processing', 'Processing'
        COMPLETED = 'completed', 'Completed'
        CANCELLED = 'cancelled', 'Cancelled'
        FAILED = 'failed', 'Failed'

    ACTIVE_STATUSES = frozenset({Status.PENDING, Status.PROCESSING})

    job_id = models.UUIDField(default=uuid.uuid1, editable=False, primary_key=True)
    engine = models.CharField(default=default_engine)
    input_cols = models.CharField(blank=True)
    input_file = models.FileField(upload_to=input_path, storage=overwrite_storage, max_length=255)
    datakey = models.FileField(upload_to=input_path, storage=overwrite_storage, null=True, blank=True, max_length=255)
    output_file = models.FileField(upload_to=output_path, null=True, blank=True, max_length=255)
    output_datakey = models.FileField(upload_to=output_path, null=True, blank=True, max_length=255)
    data_permission = models.BooleanField(default=False)
    consent_file = models.FileField(upload_to=output_path, null=True, blank=True, max_length=255)
    log_file = models.FileField(upload_to=output_path, null=True, blank=True, max_length=255)
    skipped_lines = models.FileField(upload_to=output_path, null=True, blank=True, max_length=255)
    zip_file = models.FileField(upload_to=output_path, null=True, blank=True, max_length=255)
    zip_preview = models.JSONField(null=True, blank=True)
    preview = models.JSONField(null=True, blank=True)
    processed_preview = models.JSONField(null=True, blank=True)
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.PENDING)
    error_message = models.TextField(default='', blank=True)

    def __str__(self) -> str:
        """Return a string representation of the deidentification job."""
        return f'Job {self.job_id} - {self.status}'

    def reset_zip(self) -> None:
        """Delete the zip file and clear related fields."""
        if self.zip_file:
            self.zip_file.delete(save=False)
            self.zip_file = None

        self.zip_preview = None

    def reset_output(self) -> None:
        """Delete output files and clear related fields."""
        update_fields = []

        for field in self._meta.get_fields():
            if isinstance(field, models.FileField) and getattr(field, 'upload_to', None) == output_path:
                file_instance = getattr(self, field.name)
                if file_instance:
                    file_instance.delete(save=False)
                setattr(self, field.name, None)
                update_fields.append(field.name)

        self.reset_zip()

        # Reset addidtional non-file fields
        self.processed_preview = None
        self.error_message = ''
        self.status = 'pending'

        update_fields += ['processed_preview', 'zip_preview', 'error_message', 'status']
        self.save(update_fields=update_fields)
