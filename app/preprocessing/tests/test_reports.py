# ------------------------------------------------------------------------------------------------ #
# Copyright (c) 2026 Carmenda. All rights reserved.                                                #
# This program is distributed under the terms of the PolyForm Noncommercial License 1.0.0          #
# ------------------------------------------------------------------------------------------------ #

"""Tests for report column preprocessing."""

from __future__ import annotations

from types import SimpleNamespace
from typing import TYPE_CHECKING

import polars as pl

import pytest
from preprocessing.reports import _lowercase_tlds, _number_word_boundaries, _split_icpc, prepare_input

if TYPE_CHECKING:
    from collections.abc import Callable
    from pathlib import Path

    from api.models import DeidentificationJob


def _apply(fn: Callable[[pl.Expr], pl.Expr], text: str | None) -> str | None:
    """Run a single expression function on one value."""
    df = pl.DataFrame({'text': [text]}, schema={'text': pl.String})
    return df.select(fn(pl.col('text'))).item()


def _make_job(input_path: Path, input_cols: str) -> DeidentificationJob:
    """Minimal stand-in for a job, with only the attributes `prepare_input` reads."""
    return SimpleNamespace(  # type: ignore[return-value]
        job_id='test-job',
        input_file=SimpleNamespace(path=str(input_path)),
        input_cols=input_cols,
    )


# ---------------------------- NUMBER WORD BOUNDARY TESTS ---------------------------- #


class TestNumberWordBoundaries:
    """Tests for splitting digits from letters."""

    @pytest.mark.parametrize(
        ('input_text', 'expected'),
        [
            ('3mg', '3 mg'),
            ('2.patient', '2. patient'),
            ('mg5', 'mg 5'),
            ('mg5.', 'mg 5.'),
            ('3mg5', '3 mg 5'),
            ('3Mg', '3 Mg'),
            ('3MGx', '3 MGx'),
            ('3mg 4mg', '3 mg 4 mg'),
            ('mg5 mg6', 'mg 5 mg 6'),
            ('neem 3mg per dag', 'neem 3 mg per dag'),
        ],
    )
    def test_splits(self, input_text: str, expected: str) -> None:
        """Digits are split from an adjacent run of 2+ letters."""
        assert _apply(_number_word_boundaries, input_text) == expected

    @pytest.mark.parametrize(
        'input_text',
        [
            '2x',  # single-letter unit
            'x2',  # single-letter unit
            'COPD2',  # full-caps word
            '3MG',  # full-caps word
            '12345',
            'geen getallen',
            '',
        ],
    )
    def test_untouched(self, input_text: str) -> None:
        """Single-letter units, full-caps words and text without number/word mix stay as-is."""
        assert _apply(_number_word_boundaries, input_text) == input_text


# --------------------------------- SPLIT ICPC TESTS --------------------------------- #


class TestSplitIcpc:
    """Tests for separating leading ICPC codes from the description."""

    @pytest.mark.parametrize(
        ('input_text', 'expected'),
        [
            ('K86Hypertensie', 'K86 | Hypertensie'),
            ('k86Hypertensie', 'k86 | Hypertensie'),
            ('A01.01Koorts', 'A01.01 | Koorts'),
            ('A01.01-hKoorts', 'A01.01-h | Koorts'),
            ('A01.01-h-4wKoorts', 'A01.01-h-4w | Koorts'),
            ('A80-<1UKoorts', 'A80-<1U | Koorts'),
            ('H04-1,5mndKoorts', 'H04-1,5mnd | Koorts'),
            ('L29-1,5wKoorts', 'L29-1,5w | Koorts'),
            ('a01,a02Koorts', 'a01,a02 | Koorts'),
            ('a01, a02Koorts', 'a01, a02 | Koorts'),
            ('A991', 'A99 | 1'),
        ],
    )
    def test_splits(self, input_text: str, expected: str) -> None:
        """A separator is inserted between the leading code(s) and the text."""
        assert _apply(_split_icpc, input_text) == expected

    @pytest.mark.parametrize(
        'input_text',
        [
            'K86 Hypertensie',  # already separated by a space
            'K86|Hypertensie',  # already separated by a pipe
            'K86',  # code only
            'H45 H67',  # codes only
            'K86-9mnd',  # code with month suffix only
            'Hypertensie K86',  # code not leading
            'KK86Hypertensie',
            '',
        ],
    )
    def test_untouched(self, input_text: str) -> None:
        """Text without a leading code, or already separated, stays as-is."""
        assert _apply(_split_icpc, input_text) == input_text


# ------------------------------- LOWERCASE TLD TESTS -------------------------------- #


class TestLowercaseTlds:
    """Tests for lowercasing known domain TLDs."""

    @pytest.mark.parametrize(
        ('input_text', 'expected'),
        [
            ('EXAMPLE.NL', 'EXAMPLE.nl'),
            ('info@zorg.Com', 'info@zorg.com'),
            ('www.europa.EU/home', 'www.europa.eu/home'),
            ('a.NL en b.COM', 'a.nl en b.com'),
        ],
    )
    def test_lowercases(self, input_text: str, expected: str) -> None:
        """Known TLDs are lowercased regardless of input casing."""
        assert _apply(_lowercase_tlds, input_text) == expected

    @pytest.mark.parametrize('input_text', ['example.DE', 'zorg.NLX', 'NL', ''])
    def test_untouched(self, input_text: str) -> None:
        """Unknown TLDs and partial matches stay as-is."""
        assert _apply(_lowercase_tlds, input_text) == input_text


# ------------------------------- PREPARE INPUT TESTS -------------------------------- #


class TestPrepareInput:
    """Tests for preprocessing the report columns of an input file."""

    def test_csv_report_column_preprocessed(self, tmp_path: Path) -> None:
        """Report columns are preprocessed, other columns are left untouched."""
        input_path = tmp_path / 'input.csv'
        pl.DataFrame({'Client': ['3mg'], 'Report': ['K865mg via INFO.NL']}).write_csv(input_path)

        prepare_input(_make_job(input_path, 'patientName=Client,report=Report'))

        df = pl.read_csv(input_path, infer_schema=False)
        assert df['Client'].to_list() == ['3mg']
        assert df['Report'].to_list() == ['K86 | 5 mg via INFO.nl']

    def test_steps_run_in_order(self, tmp_path: Path) -> None:
        """ICPC split runs before number splitting, so digits exposed by the split are separated too."""
        input_path = tmp_path / 'input.csv'
        pl.DataFrame({'Report': ['K867Bx', 'x399AZ1']}).write_csv(input_path)

        prepare_input(_make_job(input_path, 'report=Report'))

        assert pl.read_csv(input_path, infer_schema=False)['Report'].to_list() == ['K86 | 7 Bx', 'x39 | 9AZ1']

    def test_empty_values_preserved(self, tmp_path: Path) -> None:
        """Empty report values stay empty."""
        input_path = tmp_path / 'input.csv'
        input_path.write_text('Report,Other\n,1\n3mg,2\n', encoding='utf-8')

        prepare_input(_make_job(input_path, 'report=Report'))

        assert pl.read_csv(input_path, infer_schema=False)['Report'].to_list() == [None, '3 mg']

    def test_missing_report_column_ignored(self, tmp_path: Path) -> None:
        """A mapped report column that is not in the file is skipped."""
        input_path = tmp_path / 'input.csv'
        pl.DataFrame({'Report': ['3mg']}).write_csv(input_path)

        prepare_input(_make_job(input_path, 'report=Missing'))

        assert pl.read_csv(input_path, infer_schema=False)['Report'].to_list() == ['3mg']

    def test_original_kept_and_reused(self, tmp_path: Path) -> None:
        """The original is backed up once, and reruns start from it instead of the processed file."""
        input_path = tmp_path / 'input.csv'
        original_path = tmp_path / 'input_original.csv'
        pl.DataFrame({'A': ['3mg'], 'B': ['mg5']}).write_csv(input_path)

        prepare_input(_make_job(input_path, 'report=A'))
        assert original_path.exists()

        # remap the report column: column A must be restored from the original
        prepare_input(_make_job(input_path, 'report=B'))

        df = pl.read_csv(input_path, infer_schema=False)
        assert df['A'].to_list() == ['3mg']
        assert df['B'].to_list() == ['mg 5']
        assert pl.read_csv(original_path, infer_schema=False)['B'].to_list() == ['mg5']

    def test_excel_report_column_preprocessed(self, tmp_path: Path) -> None:
        """Excel input files are read and written back as Excel."""
        input_path = tmp_path / 'input.xlsx'
        pl.DataFrame({'Report': ['K86Hypertensie'], 'Other': ['3mg']}).write_excel(input_path)

        prepare_input(_make_job(input_path, 'report=Report'))

        df = pl.read_excel(input_path)
        assert df['Report'].to_list() == ['K86 | Hypertensie']
        assert df['Other'].to_list() == ['3mg']
        assert (tmp_path / 'input_original.xlsx').exists()
