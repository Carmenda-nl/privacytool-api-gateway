# ------------------------------------------------------------------------------------------------ #
# Copyright (c) 2026 Carmenda. All rights reserved.                                                #
# This program is distributed under the terms of the GNU General Public License: GPL-3.0-or-later  #
# ------------------------------------------------------------------------------------------------ #

"""Background job runner for deidentification jobs.

Delegates the actual pseudonymization to the engine over HTTP. The input file is
not uploaded: the engine reads it directly from the shared MEDIA_ROOT path and
writes its output back into the job's output directory.

Responsible for:
    - Submitting the job to the engine and polling its progress.
    - Updating job status in the database on completion, cancellation, or error.
"""

from __future__ import annotations

import contextlib
import logging
import time
from pathlib import Path

import httpx
from django.conf import settings

from api.models import DeidentificationJob
from api.utils.logger import setup_job_logging
from core.utils.logger import setup_logging
from core.utils.progress_control import JobCancelledError, job_control
from core.utils.progress_tracker import tracker

logger = setup_logging()

_POLL_INTERVAL = 2


def _handle_process_completion(current_job: DeidentificationJob, preview: list | None, file: str) -> None:
    """Save preview, link the engine's output files, and mark the job as completed."""
    current_job.processed_preview = preview
    current_job.save(update_fields=['processed_preview'])

    job_output_dir = Path(settings.MEDIA_ROOT) / 'output' / str(current_job.job_id)
    datakey_output_name = f'{Path(file).stem}_key.csv'

    core_files = [
        ('output_file', job_output_dir / f'{Path(file).stem}_pseudonymised{Path(file).suffix}'),
        ('output_datakey', job_output_dir / datakey_output_name),
        ('skipped_lines', next(job_output_dir.glob('*_skipped_lines.csv'), None)),
    ]

    save_fields = []
    for field_name, path in core_files:
        if path is not None and path.exists():
            getattr(current_job, field_name).name = str(path.relative_to(Path(settings.MEDIA_ROOT)))
            save_fields.append(field_name)
    if save_fields:
        current_job.save(update_fields=save_fields)

    current_job.status = 'completed'
    current_job.save(update_fields=['status'])


def _handle_process_cancellation(job_id: str) -> None:
    """Handle processing cancellation: update database."""
    logger.info('Processing "%s" cancelled by user', job_id)
    cancelled_job = DeidentificationJob.objects.get(pk=job_id)
    cancelled_job.error_message = 'Processing cancelled by user'
    cancelled_job.status = 'cancelled'
    cancelled_job.save()


def _handle_process_error(job_id: str, error: Exception) -> None:
    """Handle processing error: update database."""
    logger.exception('Processing "%s" failed', job_id)
    error_job = DeidentificationJob.objects.get(pk=job_id)
    error_job.error_message = f'Processing error: {error}'
    error_job.status = 'failed'
    error_job.save()


def _sync_progress(client: httpx.Client, engine_url: str) -> None:
    """Pull the engine's progress into the local tracker for SSE consumers."""
    progress_resp = client.get(f'{engine_url}/api/progress')
    if progress_resp.status_code == 200:
        p = progress_resp.json()
        tracker.overall_progress = p.get('percentage', 0)
        tracker.overall_stage = p.get('stage', '')
        tracker.rows_processed = p.get('rows_processed')
        tracker.rows_total = p.get('rows_total')


def run_processing(job_id: str, input_file: str, input_cols: str, output_cols: str, datakey: str | None) -> None:
    """Run processing by delegating to the engine via shared file paths (no upload)."""
    current_job = DeidentificationJob.objects.get(pk=job_id)
    job_handler = setup_job_logging(job_id, input_file, current_job)

    try:
        with job_control.run_job(job_id), contextlib.closing(job_handler):
            engine_url = settings.ENGINE_URL
            input_path = Path(settings.MEDIA_ROOT) / 'input' / input_file
            output_dir = Path(settings.MEDIA_ROOT) / 'output' / job_id
            output_dir.mkdir(parents=True, exist_ok=True)

            payload: dict = {
                'file_path': str(input_path),
                'output_dir': str(output_dir),
                'input_cols': input_cols,
            }
            if datakey:
                payload['datakey_path'] = str(Path(settings.MEDIA_ROOT) / 'input' / datakey)

            with httpx.Client(timeout=None) as client:
                # 1. Submit job to engine (paths only, no file transfer)
                client.post(f'{engine_url}/api/process', json=payload).raise_for_status()

                # 2. Poll until done, cancelled, or failed
                while True:
                    if job_control.is_cancelled(job_id):
                        client.delete(f'{engine_url}/api/process')
                        raise JobCancelledError(job_id)

                    result_resp = client.get(f'{engine_url}/api/process')

                    if result_resp.status_code == 200:
                        break
                    if result_resp.status_code == 500:
                        detail = result_resp.json().get('detail', 'Engine processing failed')
                        raise RuntimeError(detail)

                    # 409 = still running — mirror engine progress for SSE
                    _sync_progress(client, engine_url)
                    time.sleep(_POLL_INTERVAL)

            result = result_resp.json()
            tracker.overall_progress = 100
            tracker.overall_stage = 'done'

            _handle_process_completion(current_job, result.get('preview'), input_file)

    except JobCancelledError:
        _handle_process_cancellation(job_id)
    except Exception as error:
        logger.exception('Unexpected error during run process %s', job_id)
        _handle_process_error(job_id, error)
    finally:
        logging.getLogger('deidentify').removeHandler(job_handler)
        with contextlib.suppress(AttributeError, RuntimeError):
            tracker.clean_progress_bar()
