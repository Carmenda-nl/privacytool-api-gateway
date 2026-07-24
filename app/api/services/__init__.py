# ------------------------------------------------------------------------------------------------ #
# Copyright (c) 2026 Carmenda. All rights reserved.                                                #
# This program is distributed under the terms of the PolyForm Noncommercial License 1.0.0          #
# ------------------------------------------------------------------------------------------------ #

"""API service layer for deidentification job processing.

This package forwards deidentification jobs to the engine (job_runner), which
runs them on their job_id, so the HTTP request can return immediately. Progress
and completion are synced on demand from the engine and streamed to the
frontend using Server-Sent Events (SSE).
"""
