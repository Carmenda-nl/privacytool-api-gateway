# ------------------------------------------------------------------------------------------------ #
# Copyright (c) 2026 Carmenda. All rights reserved.                                                #
# This program is distributed under the terms of the GNU General Public License: GPL-3.0-or-later  #
# ------------------------------------------------------------------------------------------------ #

"""Engine job submission and reconciliation for deidentification jobs."""

from __future__ import annotations

import logging
import shutil
from pathlib import Path

import httpx
from django.conf import settings

from api.models import DeidentificationJob

logger = logging.getLogger('api-gateway')


def engine_header() -> dict[str, str]:
    """Auth header for engine calls: the shared M2M secret."""
    return {'X-M2M-Key': settings.ENGINE_M2M_HASH} if settings.ENGINE_M2M_HASH else {}


def submit_job(job_id: str, input_file: str, input_cols: str, datakey: str | None) -> None:
    """Forward a job to the engine over HTTP (shared paths, no file transfer)."""
    form: dict = {
        'file': str(Path(settings.MEDIA_ROOT) / 'input' / input_file),
        'cols': input_cols,
        'job_id': job_id,
    }

    if datakey:
        form['datakey'] = Path(datakey).name

    httpx.post(f'{settings.ENGINE_URL}/api/process', data=form, headers=engine_header(), timeout=30).raise_for_status()
    logger.debug('Job "%s" submitted to engine', job_id)


def cancel_engine(job_id: str) -> None:
    """Ask the engine to stop the running job."""
    try:
        httpx.delete(f'{settings.ENGINE_URL}/api/process', headers=engine_header(), timeout=10)
        logger.info('Job "%s" cancellation forwarded to engine', job_id)
    except httpx.HTTPError:
        logger.warning('Job "%s": failed to cancel to engine', job_id)


def _engine_get(path: str, job_id: str) -> httpx.Response | None:
    """Engine GET endpoint, or None on any transport error."""
    try:
        return httpx.get(f'{settings.ENGINE_URL}{path}', params={'job_id': job_id}, headers=engine_header(), timeout=10)
    except httpx.HTTPError as exception:
        logger.warning('Job "%s": engine GET %s failed: %s', job_id, path, exception)
        return None


def _engine_progress(job_id: str) -> dict | None:
    """Fetch the engine's live progress for a still-running job, or None on any hiccup."""
    response = _engine_get('/api/progress', job_id)
    if response is None or response.status_code != httpx.codes.OK:
        return None

    return response.json()


def _apply_completion(job: DeidentificationJob, result: dict) -> None:
    """Save preview, link the engine's output files, and mark the job completed."""
    file = Path(getattr(job.input_file, 'name', '')).name

    job.processed_preview = result
    job.save(update_fields=['processed_preview'])

    output_dir = Path(settings.MEDIA_ROOT) / 'output' / str(job.job_id)
    input_dir = Path(settings.MEDIA_ROOT) / 'input' / str(job.job_id)
    datakey = f'{Path(file).stem}_key.csv'

    # skipped lines are produced by the gateway in the input (the engine wipes the output dir at job start)
    skipped_lines = input_dir / f'{Path(file).stem}_skipped_lines.csv'
    skipped_path = None

    if skipped_lines.exists():
        skipped_path = output_dir / skipped_lines.name
        shutil.copy2(skipped_lines, skipped_path)

    core_files = [
        ('output_file', output_dir / f'{Path(file).stem}_pseudonymised{Path(file).suffix}'),
        ('output_datakey', output_dir / datakey),
        ('skipped_lines', skipped_path),
        ('log_file', next(output_dir.glob('*.log'), None)),
    ]

    save_fields = []
    for field_name, path in core_files:
        if path is not None and path.exists():
            getattr(job, field_name).name = str(path.relative_to(Path(settings.MEDIA_ROOT)))
            save_fields.append(field_name)
    if save_fields:
        job.save(update_fields=save_fields)

    if DeidentificationJob.objects.filter(pk=job.pk, status='processing').update(status='completed'):
        job.status = 'completed'
        logger.info('Job "%s" completed', job.job_id)


def _apply_error(job: DeidentificationJob, error: Exception) -> None:
    """Mark the job as failed, when engine fails."""
    message = f'Processing error: {error}'
    logger.error('Job "%s" failed in engine: %s', job.job_id, error)

    if DeidentificationJob.objects.filter(pk=job.pk, status='processing').update(
        status='failed', error_message=message
    ):
        job.status = 'failed'
        job.error_message = message


def sync_status(job: DeidentificationJob) -> dict | None:
    """Sync a processing job against the engine's terminal state."""
    if job.status != 'processing':
        return None

    job_id = str(job.job_id)
    response = _engine_get('/api/process', job_id)

    # engine unreachable -> leave processing, retry next tick
    if response is None:
        return None

    match response.status_code:
        case httpx.codes.CONFLICT:
            return _engine_progress(job_id)
        case httpx.codes.OK:
            _apply_completion(job, response.json())
        case httpx.codes.INTERNAL_SERVER_ERROR:
            detail = 'Engine processing failed'
            if response.content:
                detail = response.json().get('detail', detail)
            _apply_error(job, RuntimeError(detail))

    return None
