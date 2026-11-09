# ------------------------------------------------------------------------------------------------ #
# Copyright (c) 2026 Carmenda. All rights reserved.                                                #
# This program is distributed under the terms of the PolyForm Noncommercial License 1.0.0          #
# ------------------------------------------------------------------------------------------------ #

"""Build a ready-made datakey for an engine to be used."""

from __future__ import annotations

import io
import logging
import secrets
import string
from pathlib import Path
from typing import TYPE_CHECKING, cast

import polars as pl
from django.core.files.base import ContentFile

from api.models import DeidentificationJob
from preprocessing.encryption import decrypt_bytes, encrypt_bytes
from settings.models import ConfigValues

if TYPE_CHECKING:
    from django.db.models.fields.files import FieldFile

logger = logging.getLogger('api-gateway')

DATAKEY_COLUMNS = {'Clientnaam': 'clientname', 'Synoniemen': 'synonyms', 'Code': 'code'}


def load_datakey(datakey_field: FieldFile, *, encrypted: bool = False) -> pl.DataFrame:
    """Load an existing datakey CSV (decrypting it first if encrypted) and return it with internal column names."""
    with datakey_field.open('rb') as source:
        content = decrypt_bytes(source.read()) if encrypted else source.read()

    df = pl.read_csv(io.BytesIO(content), encoding='utf-8', separator=',', eol_char='\n')
    df = df.rename(DATAKEY_COLUMNS)

    return df.with_columns(pl.col('clientname').str.strip_chars()).filter(pl.col('clientname') != '')


def save_datakey(datakey: pl.DataFrame) -> bytes:
    """Serialize a datakey DataFrame to CSV bytes, using the external (Dutch) column names."""
    renamed = datakey.rename({value: key for key, value in DATAKEY_COLUMNS.items()})
    return renamed.write_csv(separator=',').encode('utf-8')


def _check_datakey(datakey_df: pl.DataFrame, missing_names_df: pl.Series | None = None) -> pl.DataFrame:
    """Check existing datakey, add missing names and merge duplicates."""
    if missing_names_df is None or missing_names_df.is_empty():
        logger.debug('No missing names found to add to datakey')
    else:
        missing_df = pl.DataFrame(
            {
                'clientname': missing_names_df,
                'synonyms': [''] * len(missing_names_df),
                'code': [''] * len(missing_names_df),
            }
        )
        datakey_df = pl.concat([datakey_df, missing_df])

    # Merge duplicate client names and combine their synonyms
    return (
        datakey_df.group_by('clientname')
        .agg(
            [
                pl.col('synonyms').filter(pl.col('synonyms') != '').str.join(', ').alias('synonyms'),
                pl.col('code').filter(pl.col('code') != '').first().alias('code'),
            ],
        )
        .with_columns(
            [
                pl.col('synonyms').fill_null('').alias('synonyms'),
                pl.col('code').fill_null('').alias('code'),
            ],
        )
    )


def _add_clientcodes(df: pl.DataFrame) -> pl.DataFrame:
    """Generate missing pseudonym codes for unique names."""
    missing_codes = df.filter(pl.col('code') == '').height
    if missing_codes == 0:
        return df

    existing_codes = df.filter(pl.col('code') != '').get_column('code')

    # Create a large random-code pool to select from.
    pool_size = missing_codes * 15
    code_chars = string.ascii_uppercase + string.digits
    random_pool = pl.Series([''.join(secrets.choice(code_chars) for code in range(14)) for code in range(pool_size)])

    # Filter out existing codes and take unique ones
    available_codes = (
        pl.DataFrame({'temp_code': random_pool})
        .unique()
        .filter(~pl.col('temp_code').is_in(existing_codes.implode()))
        .head(missing_codes)
        .with_row_index('temp_index')
    )

    empty_rows = df.filter(pl.col('code') == '')
    filled_rows = df.filter(pl.col('code') != '')

    apply_codes = (
        empty_rows.with_row_index('temp_index')
        .join(available_codes, on='temp_index', how='left')
        .with_columns(pl.col('temp_code').alias('code'))
        .drop(['temp_index', 'temp_code'])
    )

    return pl.concat([filled_rows, apply_codes])


def _load_clientnames(job: DeidentificationJob) -> pl.Series | None:
    """Read the stripped clientname column from the job's input file, or None if not mapped."""
    input_cols_dict = {}
    for column in job.input_cols.split(','):
        partitioned = column.partition('=')
        input_cols_dict[partitioned[0].strip()] = partitioned[2]

    clientname_col = input_cols_dict.get('clientname')
    if not clientname_col:
        return None

    input_extension = Path(job.input_file.path).suffix.lower()
    if input_extension == '.csv':
        input_df = pl.read_csv(job.input_file.path, encoding='utf-8', separator=',')
    else:
        input_df = pl.read_excel(source=job.input_file.path)

    return input_df.get_column(clientname_col).str.strip_chars()


def prepare_datakey(job: DeidentificationJob) -> str | None:
    """Build or refresh the job's datakey ahead of engine submission."""
    clientnames = _load_clientnames(job)
    if clientnames is None:
        return None

    config_values = ConfigValues.objects.first()
    reusable_datakey = config_values.reusable_datakey if config_values else None

    existing = pl.DataFrame(schema={'clientname': pl.Utf8, 'synonyms': pl.Utf8, 'code': pl.Utf8})
    if reusable_datakey:
        existing = load_datakey(reusable_datakey, encrypted=True)
    elif job.datakey:
        existing = load_datakey(job.datakey)

    unique_names = clientnames.drop_nulls().unique()
    existing_names = existing.get_column('clientname').drop_nulls().unique()
    missing_names_df = unique_names.filter(~unique_names.is_in(existing_names.implode()))

    merged = _check_datakey(existing, missing_names_df)
    datakey_df = _add_clientcodes(merged).sort('clientname')

    old_datakey = job.datakey.name if job.datakey else None
    filename = f'{Path(cast("str", job.input_file.name)).stem}_key.csv'
    job.datakey.save(filename, ContentFile(save_datakey(datakey_df)), save=True)

    if old_datakey and old_datakey != job.datakey.name:
        job.datakey.storage.delete(old_datakey)

    logger.debug('Job "%s": datakey built/refreshed as "%s"', job.job_id, job.datakey.name)
    return Path(cast('str', job.datakey.name)).name


def find_new_clientnames(job: DeidentificationJob) -> list[str]:
    """List clientnames in the job's input file that aren't yet in the reusable datakey."""
    config_values = ConfigValues.objects.first()
    reusable_datakey = config_values.reusable_datakey if config_values else None

    if not reusable_datakey:
        return []

    clientnames = _load_clientnames(job)
    if clientnames is None:
        return []

    existing_names = load_datakey(reusable_datakey, encrypted=True).get_column('clientname').drop_nulls().unique()
    unique_names = clientnames.drop_nulls().unique()
    missing = unique_names.filter(~unique_names.is_in(existing_names.implode()))

    return sorted(missing.to_list())


def sync_datakey(reusable_datakey: FieldFile) -> None:
    """Copy the (encrypted) reusable datakey into every pending job's own datakey."""
    filename = Path(cast('str', reusable_datakey.name)).with_suffix('.csv').name

    for job in DeidentificationJob.objects.filter(status=DeidentificationJob.Status.PENDING):
        if job.datakey:
            job.datakey.storage.delete(cast('str', job.datakey.name))

        with reusable_datakey.open('rb') as source:
            job.datakey.save(filename, ContentFile(decrypt_bytes(source.read())), save=True)


def append_new_clientnames(job: DeidentificationJob) -> list[str]:
    """Add the job's new clientnames, with freshly generated codes, to the reusable datakey."""
    config_values = ConfigValues.objects.first()
    reusable_datakey = config_values.reusable_datakey if config_values else None

    if not reusable_datakey:
        return []

    new_names = find_new_clientnames(job)
    if not new_names:
        return []

    existing = load_datakey(reusable_datakey, encrypted=True)
    merged = _check_datakey(existing, pl.Series(new_names))
    datakey_df = _add_clientcodes(merged).sort('clientname')

    old_name = cast('str', reusable_datakey.name)
    filename = Path(old_name).name
    reusable_datakey.storage.delete(old_name)
    reusable_datakey.save(filename, ContentFile(encrypt_bytes(save_datakey(datakey_df))), save=True)

    sync_datakey(reusable_datakey)

    return new_names
