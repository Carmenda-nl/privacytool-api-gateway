# ------------------------------------------------------------------------------------------------ #
# Copyright (c) 2026 Carmenda. All rights reserved.                                                #
# This program is distributed under the terms of the GNU General Public License: GPL-3.0-or-later  #
# ------------------------------------------------------------------------------------------------ #

"""File utilities for handling job uploads in the API gateway."""

from __future__ import annotations

import tempfile
from pathlib import Path
from typing import TYPE_CHECKING

from django.conf import settings

from preprocessing.csv_handler import load_csv

if TYPE_CHECKING:
    from django.core.files.uploadedfile import UploadedFile

    from api.models import DeidentificationJob


def get_file_path(uploaded_file: UploadedFile) -> tuple[str, bool]:
    """Get file path from uploaded file, creating temporary file if needed."""
    if hasattr(uploaded_file, 'temporary_file_path'):
        return uploaded_file.temporary_file_path(), False

    with tempfile.NamedTemporaryFile(delete=False) as temp_file:
        for chunk in uploaded_file.chunks():
            temp_file.write(chunk)

        return temp_file.name, True


def sanitize_uploaded(job: DeidentificationJob, file_metadata: dict) -> None:
    """Convert uploaded CSV input/datakey.

    Reuses the encoding/delimiter/header detected during validation
    (`file_metadata` from the serializer) so the file is read once.
    """
    output_folder = str(Path(settings.MEDIA_ROOT) / 'output')

    for field_name in ('input_file', 'datakey'):
        metadata = file_metadata.get(field_name)
        if not metadata or metadata.get('file_type') != 'csv':
            continue

        field = getattr(job, field_name, None)
        if not field:
            continue

        properties = {
            'header': metadata['header'],
            'encoding': metadata['encoding'],
            'delimiter': metadata['delimiter'],
        }
        load_csv(Path(field.path), output_folder, properties)


def get_metadata(represent: dict, instance: DeidentificationJob, fields: list[str]) -> dict:
    """Populate files with url, filesize and last_modified date."""
    for field in fields:
        file_url = represent.get(field)
        file_field = getattr(instance, field, None)
        relative_path = getattr(file_field, 'name', None) if file_field is not None else None

        if relative_path:
            file_path = Path(settings.MEDIA_ROOT) / relative_path
            if file_path.exists():
                file = file_path.stat()
                file_size = int(file.st_size)
                file_creation = int(getattr(file, 'st_birthtime', file.st_ctime))

                if file_size >= 1 << 30:
                    filesize = f'{file_size / (1 << 30):.2f} Gb'
                elif file_size >= 1 << 20:
                    filesize = f'{file_size / (1 << 20):.2f} Mb'
                else:
                    filesize = f'{file_size / 1024:.2f} Kb'

                represent[field] = {
                    'url': file_url,
                    'filesize': filesize,
                    'build_date': file_creation,
                }
    return represent
