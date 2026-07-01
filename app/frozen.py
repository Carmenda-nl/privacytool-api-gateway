# ------------------------------------------------------------------------------------------------ #
# Copyright (c) 2026 Carmenda. All rights reserved.                                                #
# This program is distributed under the terms of the GNU General Public License: GPL-3.0-or-later  #
# ------------------------------------------------------------------------------------------------ #

"""Entry point for the PyInstaller-frozen build.

Launches uvicorn directly against the ASGI app,
instead of going through Django's manage.py command dispatch.
"""

import os

import uvicorn

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'main.settings')

if __name__ == '__main__':
    from main.settings import HOST, PORT

    uvicorn.run('main.asgi:application', host=HOST, port=PORT, lifespan='off')
