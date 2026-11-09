# ------------------------------------------------------------------------------------------------ #
# Copyright (c) 2026 Carmenda. All rights reserved.                                                #
# This program is distributed under the terms of the PolyForm Noncommercial License 1.0.0          #
# ------------------------------------------------------------------------------------------------ #

"""Text preprocessing of report columns, applied to the input file before it is sent to an engine."""

from __future__ import annotations

import logging
import shutil
from pathlib import Path
from typing import TYPE_CHECKING

import polars as pl

if TYPE_CHECKING:
    from api.models import DeidentificationJob

logger = logging.getLogger('api-gateway')


def _number_word_boundaries(expr: pl.Expr) -> pl.Expr:
    """Split digits from letters in any word that starts or ends with a number.

    leading digits:   "3mg" -> "3 mg", "2.patient" -> "2. patient"
    trailing digits:  "mg5" -> "mg 5", "mg5." -> "mg 5."
    untouched:        single-letter units ("2x") and full-caps words ("COPD2", "3MG")
    """
    non_upper = r'[\p{L}--\p{Lu}]'
    letters = rf'(?:[A-Za-z]{{2}}\S*{non_upper}|[a-z][A-Za-z]|[A-Za-z][a-z])'
    leading = rf'(^|\s)(\d+\.?)({letters}\S*)'
    trailing = rf'(\S*{non_upper}\S*[A-Za-z]{{2}}|\S*[a-z][A-Za-z]|\S*[A-Za-z][a-z])(\d+\.?)(\s|$)'

    return expr.str.replace_all(leading, '$1$2 $3').str.replace_all(trailing, '$1 $2$3')


def _split_icpc(expr: pl.Expr) -> pl.Expr:
    """Insert " | " between leading ICPC code(s) and the text after it ("K86Hypertension" -> "K86 | Hypertension").

    code unit:     "K86", "A01.01", "A01.01-h-4w", "A80-<1U", "H04-1,5mnd"
    code pattern:  one or more codes separated by commas/spaces, e.g. "a01,a02" or "H45 H67"
    """
    code_unit = r'[A-Za-z]\d{2}(?:\.\d{2})?(?:-(?:[<>]?\d+(?:,\d+)?(?:mnd|[A-Za-z])|[<>]?[A-Za-z]))*'
    code_pattern = rf'^({code_unit}(?:(?:\s*,\s*|\s+){code_unit})*)'

    code = expr.str.extract(code_pattern, 1)
    rest = expr.str.slice(code.str.len_chars())
    needs_separator = (rest != '') & ~rest.str.starts_with(' ') & ~rest.str.starts_with('|')

    return pl.when(needs_separator).then(pl.concat_str(code, pl.lit(' | '), rest)).otherwise(expr)


def _lowercase_tlds(expr: pl.Expr) -> pl.Expr:
    """Lowercase domain TLDs regardless of their input casing."""
    known_tlds = ['com', 'eu', 'nl']
    for tld in known_tlds:
        expr = expr.str.replace_all(rf'(?i)\.{tld}\b', f'.{tld}')
    return expr


def prepare_input(job: DeidentificationJob) -> None:
    """Preprocess the report columns of the input file, ahead of engine submission."""
    input_path = Path(job.input_file.path)
    original_path = input_path.with_name(f'{input_path.stem}_original{input_path.suffix}')

    if not original_path.exists():
        shutil.copy2(input_path, original_path)

    extension = input_path.suffix.lower()
    if extension == '.csv':
        df = pl.read_csv(original_path, encoding='utf-8', separator=',', infer_schema=False)
    else:
        df = pl.read_excel(source=original_path, raise_if_empty=False)

    mapped_cols = [col.partition('=')[2] for col in job.input_cols.split(',') if col.strip().startswith('report')]
    report_cols = [col for col in mapped_cols if col in df.columns]

    # run functions in native polars
    df = df.with_columns(
        pl.col(col)
        .cast(pl.String)
        .pipe(_number_word_boundaries)
        .pipe(_split_icpc)
        .pipe(_lowercase_tlds)
        for col in report_cols
    )

    if extension == '.csv':
        df.write_csv(input_path, separator=',')
    else:
        df.write_excel(input_path)

    logger.debug('Job "%s": preprocessed report columns %s', job.job_id, report_cols)
