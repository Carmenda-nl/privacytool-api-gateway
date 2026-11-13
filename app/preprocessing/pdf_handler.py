# ------------------------------------------------------------------------------------------------ #
# Copyright (c) 2026 Carmenda. All rights reserved.                                                #
# This program is distributed under the terms of the PolyForm Noncommercial License 1.0.0          #
# ------------------------------------------------------------------------------------------------ #

"""PDF file conversion and sanitization utilities."""

from pypdf import PdfReader

reader = PdfReader('report.pdf')
print(len(reader.pages))  # noqa: T201

page = reader.pages[0]

print(page.extract_text())  # noqa: T201
