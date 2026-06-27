# ------------------------------------------------------------------------------------------------ #
# Copyright (c) 2026 Carmenda. All rights reserved.                                                #
# This program is distributed under the terms of the GNU General Public License: GPL-3.0-or-later  #
# ------------------------------------------------------------------------------------------------ #

"""API service layer for deidentification job processing.

This package forwards deidentification jobs to the engine (job_runner), which
runs them on their job_id, so the HTTP request can return immediately. Progress
and completion are reconciled on demand from the engine and streamed to the
frontend using Server-Sent Events (SSE).
"""
