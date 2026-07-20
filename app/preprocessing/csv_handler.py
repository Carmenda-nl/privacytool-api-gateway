# ------------------------------------------------------------------------------------------------ #
# Copyright (c) 2026 Carmenda. All rights reserved.                                                #
# This program is distributed under the terms of the PolyForm Noncommercial License 1.0.0          #
# ------------------------------------------------------------------------------------------------ #

"""CSV file conversion and sanitization utilities."""

from __future__ import annotations

import contextlib
import csv
import html
import itertools
import logging
import re
import shutil
import tempfile
from pathlib import Path

from charset_normalizer import from_bytes

logger = logging.getLogger('preprocessing')

HTML_TAG = re.compile(r'</?[a-zA-Z][\w-]*(?:\s+[^>]*[=/][^>]*)?\s*/?>', re.IGNORECASE)


def _html_unescape(text: str) -> str:
    """Unescape HTML entities, replacing double-quote entities with a typographic quote.

    This prevents any HTML-encoded double quote (e.g. &quot; &#34; &#x22;) from
    introducing a literal " that would break the CSV structure.
    """
    html_entity = re.compile(r'&(#[0-9]+;?|#[xX][0-9a-fA-F]+;?|[^\t\n\f <&#;]{1,32};?)')

    if '&' not in text:
        return text

    def replace(match: re.Match) -> str:
        unescaped = html.unescape(match.group(0))
        return '\u201c' if unescaped == '"' else unescaped

    return html_entity.sub(replace, text)


def strip_bom(text: str) -> str:
    """Remove BOM (Byte Order Mark) from the header if present in UTF-8 encoding."""
    return text.removeprefix('\ufeff')


def _detect_encoding(data_sample: bytes) -> str:
    """Detect CSV file encoding, defaults to UTF-8."""
    if data_sample.startswith(b'\xef\xbb\xbf'):
        return 'utf-8'  # <- UTF-8 BOM detected

    try:
        results = from_bytes(data_sample)
        best_match = results.best()
        encoding = best_match.encoding if best_match and getattr(best_match, 'encoding', None) else 'utf-8'

        # ascii detection is treated as UTF-8
        if encoding.lower() == 'ascii':
            encoding = 'utf-8'

    except LookupError, ValueError, TypeError, OSError:
        logger.warning('Encoding detection failed, defaults to UTF-8 encoding.')
        encoding = 'utf-8'

    # Normalize encoding name (utf_8 -> utf-8) for consistency
    return encoding.replace('_', '-')


def _detect_delimiter(data_sample: str) -> str:
    """Detect CSV delimiter from sample data."""
    try:
        dialect = csv.Sniffer().sniff(data_sample, delimiters=',;\t|')
    except csv.Error:
        candidates = [',', ';', '\t', '|']
        scores = {delimiter: data_sample.count(delimiter) for delimiter in candidates}
        detected_delimiter = max(scores, key=scores.__getitem__)
        return detected_delimiter if scores[detected_delimiter] > 0 else ','
    else:
        return dialect.delimiter


def detect_csv_properties(file_path: Path) -> dict[str, str]:
    """Detect the CSV encoding, delimiter and header in a CSV file."""
    with file_path.open('rb') as rawdata:
        data_sample = rawdata.read(2 * 1024 * 1024)

    encoding = _detect_encoding(data_sample)

    with file_path.open('r', encoding=encoding, errors='ignore') as file:
        header = strip_bom(next(file).strip())

    delimiter = _detect_delimiter(header)

    logger.info('Detected %s: Encoding=%s, delimiter=%r', file_path.name, encoding, delimiter)
    return {'header': header, 'encoding': encoding, 'delimiter': delimiter}


def _sanitize_csv(file_path: Path, properties: dict[str, str]) -> str:
    """Convert CSV to UTF-8 and sanitize content.

    When the delimiter is `;`, unescape HTML character entities while replacing
    double-quote entities with a typographic quote to preserve CSV structure.
    """
    header, encoding, delimiter = properties['header'], properties['encoding'], properties['delimiter']
    replace_html = delimiter == ';'

    error_temp = None
    error_count = 0

    with (
        contextlib.ExitStack() as stack,
        file_path.open('rb') as file,
        tempfile.NamedTemporaryFile('w', encoding='utf-8', newline='', delete=False) as temp_file,
    ):
        chunk_size = 8 * 1024 * 1024
        buffer = b''

        for chunk in itertools.chain(iter(lambda: file.read(chunk_size), b''), (b'',)):
            buffer += chunk

            try:
                text = buffer.decode(encoding)
            except UnicodeDecodeError, LookupError:
                for raw_line in buffer.split(b'\n'):
                    try:
                        # handle errors line by line if the chunk contains invalid sequences
                        line = raw_line.decode(encoding)
                    except UnicodeDecodeError, LookupError:
                        if not error_temp:
                            # Lazily create the error file only once an actual decode error occurs,
                            # since most uploads have none and never need it.
                            error_temp = stack.enter_context(
                                tempfile.NamedTemporaryFile(
                                    'w', encoding='utf-8', newline='', delete=False, suffix='.csv'
                                ),
                            )
                            error_temp.write(header.replace(delimiter, ',') + '\n')

                        error_line = raw_line.decode(encoding, errors='replace').replace(delimiter, ',')
                        error_temp.write(error_line + '\n')
                        error_count += 1
                        continue

                    if replace_html:
                        line = _html_unescape(HTML_TAG.sub('', line))
                    temp_file.write(line + '\n')
                buffer = b''
                continue

            quote_count = text.count('"') - text.count('\\"')
            if not chunk or quote_count % 2 == 0:
                if replace_html:
                    text = _html_unescape(HTML_TAG.sub('', text))
                temp_file.write(text)
                buffer = b''

    error_csv = file_path.parent / f'{file_path.stem}_skipped_lines.csv'
    if error_temp:
        shutil.move(error_temp.name, error_csv)
        logger.warning('%d errors in rows found.', error_count)
    else:
        error_csv.unlink(missing_ok=True)
        logger.info('No errors in rows found.')

    return temp_file.name


def _normalize_csv(file_path: Path, properties: dict[str, str]) -> str:
    """Convert delimiter to comma and remove empty rows."""
    with (
        file_path.open('r', encoding='utf-8', newline='') as file,
        tempfile.NamedTemporaryFile('w', encoding='utf-8', newline='', delete=False) as csv_temp,
    ):
        delimiter = properties['delimiter']
        reader = csv.reader(file, delimiter=delimiter)
        writer = csv.writer(csv_temp, delimiter=',')

        empty_rows = 0

        for row in reader:
            if any(field.strip() for field in row):
                # Replace newlines within fields with spaces to prevent multiline CSV rows,
                sanitized_row = [field.replace('\n', ' ').replace('\r', ' ') for field in row]
                writer.writerow(sanitized_row)
            else:
                empty_rows += 1

        if empty_rows > 0:
            logger.warning('Found %d empty rows.\n', empty_rows)

    return csv_temp.name


def load_csv(file_path: Path, properties: dict[str, str] | None = None) -> None:
    """Sanitize and normalize a CSV file in place (UTF-8, comma-delimited, no empty rows)."""
    if properties is None:
        properties = detect_csv_properties(file_path)

    sanitized_csv = _sanitize_csv(file_path, properties)
    normalized_csv = _normalize_csv(Path(sanitized_csv), properties)

    Path(sanitized_csv).unlink(missing_ok=True)
    shutil.move(normalized_csv, file_path)
