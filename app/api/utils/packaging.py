# ------------------------------------------------------------------------------------------------ #
# Copyright (c) 2026 Carmenda. All rights reserved.                                                #
# This program is distributed under the terms of the PolyForm Noncommercial License 1.0.0          #
# ------------------------------------------------------------------------------------------------ #

"""Assemble a job's output: consent file, output collection, and zip packaging."""

from __future__ import annotations

import logging
import os
import zipfile
from pathlib import Path
from typing import TYPE_CHECKING

from django.conf import settings
from django.utils.translation import gettext as _

if TYPE_CHECKING:
    from api.models import DeidentificationJob

logger = logging.getLogger('api-gateway')


def generate_consent(job: DeidentificationJob) -> None:
    """Create consent.txt and store its path on the job when data_permission is set."""
    output_dir = Path(settings.MEDIA_ROOT) / 'output' / str(job.job_id)

    if not output_dir.exists():
        output_dir.mkdir(parents=True, exist_ok=True)

    if not job.data_permission or not job.input_file:
        job.consent_file.delete(save=False)
        job.consent_file = None
        job.save(update_fields=['consent_file'])
        return

    base_name = Path(getattr(job.input_file, 'name', '')).stem
    consent_filename = f'{base_name}_consent.txt'
    consent_path = output_dir / consent_filename

    if not base_name:
        job.consent_file.delete(save=False)
        job.consent_file = None
        job.save(update_fields=['consent_file'])
        return

    if job.consent_file:
        old_name = getattr(job.consent_file, 'name', '')
        old_consent_path = Path(settings.MEDIA_ROOT) / old_name if old_name else None
        if old_consent_path and old_consent_path.exists() and old_consent_path != consent_path:
            old_consent_path.unlink()

    consent_path.write_text(
        _(
            'Yes, Carmenda may contact me with questions about improving the Privacytool.\n'
            'Confirmed during pseudonimisation of the file: {filename}'
        ).format(filename=base_name),
        encoding='utf-8',
    )

    job.consent_file.name = str(Path('output') / str(job.job_id) / consent_filename)
    job.save(update_fields=['consent_file'])


def collect_output_files(job: DeidentificationJob) -> list[str]:
    """Collect all files in the job output directory, excluding the input file."""
    job_output_dir = Path(settings.MEDIA_ROOT) / 'output' / str(job.job_id)
    input_filename = Path(getattr(job.input_file, 'name', '')).name

    if not job_output_dir.exists():
        return []

    return [
        str(path)
        for path in sorted(job_output_dir.iterdir())
        if path.is_file() and (not input_filename or path.name != input_filename) and path.suffix != '.zip'
    ]


def create_zipfile(job: DeidentificationJob, files_to_zip: list[str]) -> None:
    """Create a zip file and store its information in the job model."""
    output_filename = Path(getattr(job.output_file, 'name', '')).name

    if not files_to_zip:
        error_message = f'No output files found to zip for job {job.pk}'
        logger.error(error_message)
        raise RuntimeError(error_message)

    base_name = Path(output_filename).stem
    zip_filename = f'{base_name}.zip'
    zip_path = Path(settings.MEDIA_ROOT) / 'output' / str(job.job_id) / zip_filename

    included_files: list[str] = []

    try:
        # Create the zip file
        with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED) as zipped_file:
            for file_path in files_to_zip:
                file_path_obj = Path(file_path)

                if not file_path_obj.exists():
                    error_message = f'File not found for zipping: {file_path}'
                    logger.error(error_message)
                    raise RuntimeError(error_message)

                basename = file_path_obj.name
                zipped_file.write(file_path, basename)
                included_files.append(basename)

        # Store zip information in job model
        job.zip_file.name = os.path.relpath(zip_path, settings.MEDIA_ROOT)
        job.zip_preview = {
            'zip_file': zip_filename,
            'files': included_files,
        }
        job.save(update_fields=['zip_file', 'zip_preview'])

    except OSError as error:
        error_message = f'Failed to create zip file: {error}'
        logger.exception(error_message)
        raise
