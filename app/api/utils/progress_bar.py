# ------------------------------------------------------------------------------------------------ #
# Copyright (c) 2026 Carmenda. All rights reserved.                                                #
# This program is distributed under the terms of the GNU General Public License: GPL-3.0-or-later  #
# ------------------------------------------------------------------------------------------------ #

"""Terminal progress bar for data processing.

Renders the engine's row-based progress to the gateway's terminal with Rich.
This is purely cosmetic developer feedback: the engine owns the real job state
(see api.services.job_runner), so nothing here affects job correctness. A single
shared terminal renders a single bar, hence the module-level `progress_bar`
singleton; in frozen builds there is no console and it is never driven.
"""

from __future__ import annotations

import sys

from rich.progress import (
    BarColumn,
    MofNCompleteColumn,
    Progress,
    SpinnerColumn,
    TaskID,
    TaskProgressColumn,
    TextColumn,
    TimeElapsedColumn,
    TimeRemainingColumn,
)


class ProgressBar:
    """Render the engine's row-based progress to the terminal using Rich."""

    def __init__(self) -> None:
        """Start with no active bar; one is created lazily on the first update."""
        self._default_state()

    def _default_state(self) -> None:
        """Reset to the idle state so the next job starts a fresh bar."""
        self.task_id: TaskID | None = None
        self.rich_progress: Progress | None = None
        self.rows_progress = 0
        self.rows_processed: int | None = None
        self.rows_total: int | None = None

    def _progress_bar(self) -> Progress:
        """Build the Rich progress bar: spinner, description, bar, %, M/N and timings."""
        spinner = SpinnerColumn()
        text = TextColumn('[bold blue]{task.description}', justify='left')
        bar = BarColumn(bar_width=40)
        task_progress = TaskProgressColumn()
        mofn = MofNCompleteColumn()
        time_elapsed = TimeElapsedColumn()
        time_remaining = TimeRemainingColumn()

        return Progress(spinner, text, bar, task_progress, mofn, time_elapsed, time_remaining)

    def clean_progress_bar(self) -> None:
        """Stop the live bar and clear it, so the next job lazily builds a fresh one."""
        if self.rich_progress is not None:
            self.rich_progress.stop()
            sys.stdout.write('\n')

        self.rich_progress = None
        self.task_id = None

    def set_row_progress(self, stage: str, processed: int, total: int, progress: int) -> None:
        """Render one row-based progress tick, building the bar on the first call."""
        if self.rich_progress is None:
            self.rows_progress = 0
            self.rich_progress = self._progress_bar()

        self.rows_processed = processed
        self.rows_total = total

        progress_percentage = max(self.rows_progress, min(int(progress), 100))

        self.rows_progress = progress_percentage
        self.rich_progress.start()

        if self.task_id is None:
            self.task_id = self.rich_progress.add_task(stage, total=total, completed=0)

        self.rich_progress.update(
            self.task_id,
            completed=processed,
            description=f'{stage} ({progress_percentage}%)',
        )


# Singleton instance: one shared terminal renders one bar at a time.
progress_bar = ProgressBar()
