# ------------------------------------------------------------------------------------------------ #
# Copyright (c) 2026 Carmenda. All rights reserved.                                                #
# This program is distributed under the terms of the PolyForm Noncommercial License 1.0.0          #
# ------------------------------------------------------------------------------------------------ #

"""Assemble a job's output: output collection and zip packaging."""

from __future__ import annotations

import logging
import os
import zipfile
from pathlib import Path
from typing import TYPE_CHECKING

from django.conf import settings

if TYPE_CHECKING:
    from api.models import DeidentificationJob

logger = logging.getLogger('api-gateway')


def collect_output_files(job: DeidentificationJob) -> list[str]:
    """Collect all files in the job output directory, excluding the input file."""
    job_output_dir = Path(settings.MEDIA_ROOT) / 'output' / str(job.job_id)
    input_filename = Path(getattr(job.input_file, 'name', '')).name
    datakey_filename = Path(getattr(job.output_datakey, 'name', '')).name

    if not job_output_dir.exists():
        return []

    return [
        str(path)
        for path in sorted(job_output_dir.iterdir())
        # Exclude the input file and datakey
        if path.is_file() and path.name not in (input_filename, datakey_filename) and path.suffix != '.zip'
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
