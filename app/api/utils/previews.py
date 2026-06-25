# ------------------------------------------------------------------------------------------------ #
# Copyright (c) 2026 Carmenda. All rights reserved.                                                #
# This program is distributed under the terms of the GNU General Public License: GPL-3.0-or-later  #
# ------------------------------------------------------------------------------------------------ #

"""Generate row previews (first & last rows) from a job's CSV or Excel input file."""

from __future__ import annotations

import csv
import html
from collections import deque
from pathlib import Path
from typing import TYPE_CHECKING

import polars as pl
from fastexcel import read_excel

from preprocessing.csv_handler import detect_csv_properties, strip_bom

if TYPE_CHECKING:
    from api.models import DeidentificationJob

MAX_FIRST_PREVIEW_ROWS = 3
MAX_LAST_PREVIEW_ROWS = 3


def _csv_preview(file_path: str) -> list[dict]:
    """Read the first & last rows from a CSV file."""
    properties = detect_csv_properties(Path(file_path))
    encoding, delimiter = properties['encoding'], properties['delimiter']

    with Path(file_path).open(encoding=encoding, newline='', errors='ignore') as file:
        csv_reader = csv.reader(file, delimiter=delimiter)

        header_row = next(csv_reader)
        header_row[0] = strip_bom(header_row[0])
        header = [col.strip() for col in header_row]

        first_rows: list[list[str]] = []
        tail: deque = deque(maxlen=MAX_LAST_PREVIEW_ROWS)

        for row in csv_reader:
            if not any(row):
                continue
            if len(first_rows) < MAX_FIRST_PREVIEW_ROWS:
                first_rows.append(row)
            else:
                tail.append(row)

    # If fewer than max data rows, only return the first rows.
    selected = first_rows + list(tail) if len(tail) >= MAX_LAST_PREVIEW_ROWS else first_rows

    preview = []
    for row in selected:
        decoded_values = [html.unescape(value) if value else value for value in row]
        preview.append(dict(zip(header, decoded_values, strict=False)))

    return preview


def _excel_preview(file_path: str) -> list[dict]:
    """Read the first & last rows from an Excel file."""
    excel_reader = read_excel(file_path)
    sheet = excel_reader.load_sheet(0)
    total_rows = sheet.total_height

    def to_dicts(df: pl.DataFrame) -> list[dict]:
        df = df.filter(~pl.all_horizontal(pl.all().is_null()))
        return [{col: html.unescape(str(val)) for col, val in row.items()} for row in df.to_dicts()]

    # Buffer extra rows to compensate for empty rows being filtered out
    head_buffer = MAX_FIRST_PREVIEW_ROWS * 5

    head_df = excel_reader.load_sheet(0, n_rows=min(head_buffer, total_rows)).to_polars()
    first_rows = to_dicts(head_df)[:MAX_FIRST_PREVIEW_ROWS]

    if total_rows < MAX_FIRST_PREVIEW_ROWS + MAX_LAST_PREVIEW_ROWS:
        return first_rows

    tail_buffer = MAX_LAST_PREVIEW_ROWS * 5
    skip = max(0, total_rows - tail_buffer)
    tail_df = excel_reader.load_sheet(0, skip_rows=skip).to_polars()
    tail = to_dicts(tail_df)[-MAX_LAST_PREVIEW_ROWS:]

    return first_rows + tail


def generate_preview(job: DeidentificationJob) -> None:
    """Generate a preview from the input file (1 header + data rows)."""
    file_path = job.input_file.path
    file_extension = Path(file_path).suffix.lower()

    if file_extension == '.csv':
        preview_data = _csv_preview(file_path)
    elif file_extension in {'.xlsx', '.xls'}:
        preview_data = _excel_preview(file_path)

    job.preview = preview_data
    job.save(update_fields=['preview'])
