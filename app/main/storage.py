# ------------------------------------------------------------------------------------------------ #
# Copyright (c) 2026 Carmenda. All rights reserved.                                                #
# This program is distributed under the terms of the PolyForm Noncommercial License 1.0.0          #
# ------------------------------------------------------------------------------------------------ #

"""Custom storage functionality for the application."""

from django.core.files.storage import FileSystemStorage


class OverwriteStorage(FileSystemStorage):
    """FileSystemStorage that overwrites existing files."""

    def get_available_name(self, name: str, max_length: int | None = None) -> str:
        """Return the given filename, deleting any existing file first."""
        if self.exists(name):
            self.delete(name)
        return name
