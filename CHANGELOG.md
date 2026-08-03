# Changelog

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [2.0.2-beta] - 2026-08-03

### Fixed

- Version file not properly promoted to stable

## [2.0.1] - 2026-07-24

### Changed

- Readme & remove bruno files
- Workflows to use shared workflows
- Gpl license to polyform
- Update packages

### Fixed

- Whitenoise not loaded in frozen env

## [2.0.0] - 2026-07-09

### Added

- Import base project files from old core
- Install django framework
- Install extra django based packages
- Import settings app from old core
- Log settings
- Import old language files
- Import bruno collection from older core
- Import pipelines from core-engine repo
- Import core utils from older engine
- Import older core-engine api
- Engine url in gateway settings
- Install httpx & charset-normalizer
- Csv handler unittests
- Makefile, lint & force LF
- Sanitize uploaded csv files
- Job runner refactor to use the new  engine
- Docker compose deployment stack
- Replace daphne with uvicorn
- Dutch translations extended
- Django added to debug_file handler [LVD-316]
- PolyForm noncommercial license

### Changed

- Initialise commit
- Version & storage control
- Rebuild migrations & add packages
- Update packages
- Translations & log files
- Cleanup pyproject
- Update settings
- Remove old core utils
- Code cleanup in serializers
- Update docstrings
- Move old engine log code to django's handler
- Import old core utils from the engine core
- Change old logger refs
- File_handling cleanup
- Split/refactor file_handling.py
- Relocate validators.py
- Refactor csv_handler into preprocessing app
- Code cleanup
- Ruff check
- Validators cleanup & progress bar refactor
- SSE relay the progress from the engine
- Update docstring
- Code refactor improve naming
- Jobs api view to use the engine
- Remove progress bar from gateway
- Update readme
- Update bruno docs
- Cleanup build script
- Remove latest daphne references
- Use uvicorn in dev, prod & frozen
- Update all packages
- Update version
- Refactored csv handler to fix ruff errors
- Update translations
- Remove frontend trigger
- Update pipelines
- Remove GITHUB_REPO 403/panic error
- Rename backend to api-gateway
- Worflows writes version with double quotes
- Pre release v2.0.0

### Fixed

- Fix import files accidentally converted to .txt
- Fix metrics not properly loaded from engine
- Fix lint error in models
- Minor bugs & m2m hash in settings
- Progress bar did not end on 100%
- Uvicorn not loaded in frozen env
- Uvicorn lifespan not supported by django
- Incorrect python version in test pipeline
- Uploaded files got normalised x2 [LVD-318]
- Skipped_lines.csv gets removed when process
- Fix debug.log overwrites logs in debug
- Skipped_lines file not properly deleted
- Downloads streamed synchronously under ASGI
- Fix pipeline artifact location
