# ------------------------------------------------------------------------------------------------ #
# Copyright (c) 2026 Carmenda. All rights reserved.                                                #
# This program is distributed under the terms of the PolyForm Noncommercial License 1.0.0          #
# ------------------------------------------------------------------------------------------------ #

"""Symmetric encryption for data stored at data."""

from __future__ import annotations

from functools import lru_cache

from cryptography.fernet import Fernet
from django.conf import settings


@lru_cache(maxsize=1)
def _fernet() -> Fernet:
    return Fernet(settings.ENCRYPTION_KEY)


def encrypt_bytes(data: bytes) -> bytes:
    """Encrypt bytes for storage."""
    return _fernet().encrypt(data)


def decrypt_bytes(data: bytes) -> bytes:
    """Decrypt bytes previously encrypted."""
    return _fernet().decrypt(data)
