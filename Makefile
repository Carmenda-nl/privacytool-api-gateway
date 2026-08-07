# ------------------------------------------------------------------------------------------------ #
# Copyright (c) 2026 Carmenda. All rights reserved.                                                #
# This program is distributed under the terms of the PolyForm Noncommercial License 1.0.0          #
# ------------------------------------------------------------------------------------------------ #

APP_DIR := app
DEPLOY_DIR := deployment

.PHONY: help run prod lint format test typecheck check \
        compose watch-deduce watch-deidentify

help:
	@echo ---------------------------------
	@echo PRIVACYTOOL API GATEWAY COMMANDS:
	@echo ---------------------------------
	@echo   make run              Start the dev server with hot reload
	@echo   make prod             Start the production server
	@echo   make lint             Run ruff lint checks
	@echo   make format           Format code with ruff
	@echo   make test             Run the test suite
	@echo   make typecheck        Run mypy type checks
	@echo   make check            Run all checks
	@echo   make compose          Build and start the docker compose stack

run:
	cd $(APP_DIR) && uv run uvicorn main.asgi:application --reload

prod:
	cd $(APP_DIR) && uv run uvicorn main.asgi:application

lint:
	cd $(APP_DIR) && uv run ruff check .

format:
	cd $(APP_DIR) && uv run ruff format .

test:
	cd $(APP_DIR) && uv run pytest

typecheck:
	cd $(APP_DIR) && uv run mypy .

check: format lint typecheck test

compose:
	cd $(DEPLOY_DIR) && docker compose up -d --build
