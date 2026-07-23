# ------------------------------------------------------------------------------------------------ #
# Copyright (c) 2026 Carmenda. All rights reserved.                                                #
# This program is distributed under the terms of the PolyForm Noncommercial License 1.0.0          #
# ------------------------------------------------------------------------------------------------ #

"""Engine job submission and reconciliation for deidentification jobs."""

from __future__ import annotations

import logging
import shutil
from pathlib import Path

import httpx
from django.conf import settings

from api.models import DeidentificationJob
from api.utils.packaging import generate_consent

logger = logging.getLogger('api-gateway')


def engine_url(engine: str, path: str) -> str:
    """Build a full URL to the given engine's API path."""
    config = settings.ENGINES[engine]
    return f"{config['url']}:{config['port']}{path}"


def engine_header(engine: str) -> dict[str, str]:
    """Auth header for engine calls: the shared M2M secret."""
    m2m_hash = settings.ENGINES[engine].get('m2m_hash')
    return {'X-M2M-Key': m2m_hash} if m2m_hash else {}


def submit_job(job: DeidentificationJob, input_file: str, input_cols: str, datakey: str | None) -> None:
    """Forward a job to the engine over HTTP (shared paths, no file transfer)."""
    job_id = str(job.job_id)
    form: dict = {
        'file': str(Path(settings.MEDIA_ROOT) / 'input' / input_file),
        'cols': input_cols,
        'job_id': job_id,
    }

    if datakey:
        form['datakey'] = Path(datakey).name

    url = engine_url(job.engine, '/api/process')
    httpx.post(url, data=form, headers=engine_header(job.engine), timeout=30).raise_for_status()
    logger.debug('Job "%s" submitted to engine "%s"', job_id, job.engine)


def cancel_engine(job: DeidentificationJob) -> None:
    """Ask the engine to stop the running job."""
    job_id = str(job.job_id)
    try:
        url = engine_url(job.engine, '/api/process')
        httpx.delete(url, headers=engine_header(job.engine), timeout=10)
        logger.info('Job "%s" cancellation forwarded to engine', job_id)
    except httpx.HTTPError:
        logger.warning('Job "%s": failed to cancel to engine', job_id)


def _engine_get(job: DeidentificationJob, path: str) -> httpx.Response | None:
    """Engine GET endpoint, or None on any transport error."""
    job_id = str(job.job_id)
    try:
        url = engine_url(job.engine, path)
        return httpx.get(url, params={'job_id': job_id}, headers=engine_header(job.engine), timeout=10)
    except httpx.HTTPError as exception:
        logger.warning('Job "%s": engine GET %s failed: %s', job_id, path, exception)
        return None


def _engine_progress(job: DeidentificationJob) -> dict | None:
    """Fetch the engine's live progress for a still-running job, or None on any hiccup."""
    response = _engine_get(job, '/api/progress')
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

    if job.data_permission:
        generate_consent(job)

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

    response = _engine_get(job, '/api/process')

    # engine unreachable -> leave processing, retry next tick
    if response is None:
        return None

    match response.status_code:
        case httpx.codes.CONFLICT:
            return _engine_progress(job)
        case httpx.codes.OK:
            _apply_completion(job, response.json())
        case httpx.codes.INTERNAL_SERVER_ERROR:
            detail = 'Engine processing failed'
            if response.content:
                detail = response.json().get('detail', detail)
            _apply_error(job, RuntimeError(detail))

    return None
