# ------------------------------------------------------------------------------------------------ #
# Copyright (c) 2026 Carmenda. All rights reserved.                                                #
# This program is distributed under the terms of the PolyForm Noncommercial License 1.0.0          #
# ------------------------------------------------------------------------------------------------ #

"""Convert an uploaded PDF into a single-cell CSV for the generic-label pipeline."""

from typing import TYPE_CHECKING

import polars as pl
from pypdf import PdfReader

if TYPE_CHECKING:
    from pathlib import Path


def _extract_report(pdf_path: Path) -> str:
    """Return the text of all non-empty pages, separated by blank lines."""
    reader = PdfReader(pdf_path)
    pages = ((page.extract_text() or '').strip() for page in reader.pages)

    return '\n\n'.join(page for page in pages if page)


def load_pdf(pdf_path: Path) -> dict[str, str]:
    """Write the PDF text as one row in a .csv with properties."""
    properties = {'header': 'pdf_text', 'encoding': 'utf-8', 'delimiter': ','}

    df = pl.DataFrame({properties['header']: [_extract_report(pdf_path)]})
    df.write_csv(pdf_path.with_suffix('.csv'), separator=properties['delimiter'])

    pdf_path.unlink()

    return properties
