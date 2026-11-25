# ------------------------------------------------------------------------------------------------ #
# Copyright (c) 2026 Carmenda. All rights reserved.                                                #
# This program is distributed under the terms of the PolyForm Noncommercial License 1.0.0          #
# ------------------------------------------------------------------------------------------------ #

"""Convert an uploaded document into a single-cell CSV for the process pipeline."""

from typing import TYPE_CHECKING

import docx2txt
import polars as pl
from pypdf import PdfReader

if TYPE_CHECKING:
    from pathlib import Path


def _extract_docx_text(docx_path: Path) -> str:
    """Return the extracted text of a DOCX document."""
    return (docx2txt.process(str(docx_path)) or '').strip()


def _extract_pdf_text(pdf_path: Path) -> str:
    """Return the text of all non-empty pages, separated by blank lines."""
    reader = PdfReader(pdf_path)
    pages = ((page.extract_text() or '').strip() for page in reader.pages)

    return '\n\n'.join(page for page in pages if page)


def _load_document(doc_path: Path, file_type: str | None = None) -> tuple[str, str]:
    """Load document based file & extract text."""
    file_type = file_type or doc_path.suffix.lower().lstrip('.')

    if file_type == '.docx':
        return _extract_docx_text(doc_path), 'docx_text'
    if file_type == '.pdf':
        return _extract_pdf_text(doc_path), 'pdf_text'

    error_message = f'Unsupported document format: {file_type}'
    raise ValueError(error_message)


def convert_document(doc_path: Path, file_type: str | None = None) -> dict[str, str]:
    """Write the document text as one row in a .csv with properties."""
    text, header = _load_document(doc_path, file_type=file_type)
    properties = {'header': header, 'encoding': 'utf-8', 'delimiter': ','}

    df = pl.DataFrame({properties['header']: [text]})
    df.write_csv(doc_path.with_suffix('.csv'), separator=properties['delimiter'])

    doc_path.unlink()

    return properties
