env:
	uv venv

rmenv:
	rm -rf .venv

activate:
	source .venv/bin/activate

install:
	uv sync --no-dev

install-dev:
	uv sync --extra dev

install-extras:
	uv sync --all-extras --no-dev

run:
	uv run launcher.py

format:
	ruff check --select I --fix .
	ruff format .

.PHONY: env rmenv activate install install-dev run format
.DEFAULT_GOAL := run
