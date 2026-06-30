.PHONY: run prod lint format test typecheck check

run:
	uv run manage.py runserver

prod:
	uv run uvicorn main.asgi:application --port 8000

lint:
	uv run ruff check .

format:
	uv run ruff format .

test:
	uv run pytest

typecheck:
	uv run mypy .

check: format lint typecheck test
