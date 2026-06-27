# ------------------------------------------------------------------------------------------------ #
# Copyright (c) 2026 Carmenda. All rights reserved.                                                #
# This program is distributed under the terms of the GNU General Public License: GPL-3.0-or-later  #
# ------------------------------------------------------------------------------------------------ #

"""Server-Sent Events view for real-time job progress updates."""

from __future__ import annotations

import json
from typing import TYPE_CHECKING

import httpx
from asgiref.sync import sync_to_async
from django.conf import settings
from django.http import StreamingHttpResponse
from django.utils import translation
from django.utils.translation import gettext as _

from api.models import DeidentificationJob
from api.services.job_runner import engine_headers, reconcile_job

if TYPE_CHECKING:
    from collections.abc import AsyncGenerator

    from django.http import HttpRequest


def _stage_label(progress_info: dict, fallback: str) -> str:
    """Translate and format a stage label, optionally including row counts."""
    stage = progress_info.get('stage')
    processed = progress_info.get('rows_processed')
    total = progress_info.get('rows_total')

    if not isinstance(stage, str):
        return _(fallback)

    translated_stage = _(stage)

    if processed is not None and total:
        processed_details = _('processed %(processed)s/%(total)s rows') % {'processed': processed, 'total': total}
        return f'{translated_stage} - {processed_details}'

    return translated_stage


async def _relay_engine_stream(client: httpx.AsyncClient, job_id: str) -> AsyncGenerator[tuple[int, str] | None]:
    """Relay the engine's progress stream while it runs."""
    url = f'{settings.ENGINE_URL}/api/progress/stream'

    try:
        async with client.stream('GET', url, params={'job_id': job_id}) as response:
            if response.status_code == httpx.codes.OK:
                async for line in response.aiter_lines():
                    if not line.startswith('data:'):
                        continue

                    info = json.loads(line[len('data:') :].strip())
                    if info.get('done'):
                        yield None
                        return

                    yield int(info.get('percentage') or 0), _stage_label(info, 'processing')

    except httpx.HTTPError:
        return


def _progress_view(status: str, info: dict | None) -> tuple[int, str]:
    """Resolve the (percentage, stage) to report for the current job state."""
    if status not in DeidentificationJob.ACTIVE_STATUSES:
        return (100 if status == DeidentificationJob.Status.COMPLETED else 0), _(status)
    if info is not None:
        return int(info.get('percentage') or 0), _stage_label(info, status)
    return 0, _(status)


def _json_format(**data: object) -> str:
    return f'data: {json.dumps(data)}\n\n'


async def _finalize(job_id: str) -> AsyncGenerator[str]:
    """Reconcile the job against the engine once and report its terminal status.

    Runs after the live stream ends: `reconcile_job` links the engine's output and flips
    the job to its terminal state in the database, which the live stream alone does not do.
    """
    job = await DeidentificationJob.objects.aget(pk=job_id)

    info = None
    if job.status in DeidentificationJob.ACTIVE_STATUSES:
        info = await sync_to_async(reconcile_job)(job)
        job = await DeidentificationJob.objects.aget(pk=job_id)

        if job.status not in DeidentificationJob.ACTIVE_STATUSES:
            info = None

    percentage, stage = _progress_view(job.status, info)
    yield _json_format(percentage=percentage, stage=stage, status=job.status)


async def progress(request: HttpRequest, job_id: str) -> StreamingHttpResponse:
    """Relay job progress as Server-Sent Events from the engine's progress stream."""
    language = getattr(request, 'LANGUAGE_CODE', translation.get_language())

    async def event_stream() -> AsyncGenerator[str]:
        translation.activate(language)

        # Phase 1: relay the engine's live progress.
        async with httpx.AsyncClient(timeout=httpx.Timeout(5.0, read=None), headers=engine_headers()) as client:
            async for live in _relay_engine_stream(client, str(job_id)):
                if live is None:  # engine reached a terminal state
                    break
                yield _json_format(percentage=live[0], stage=live[1], status='processing')

        # Phase 2: report the status (the stream does not finalise the job in the db)
        async for message in _finalize(job_id):
            yield message

    response = StreamingHttpResponse(event_stream(), content_type='text/event-stream')
    response['Cache-Control'] = 'no-cache'
    response['X-Accel-Buffering'] = 'no'

    return response
