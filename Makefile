env:
	uv venv

rmenv:
	rm -rf .venv

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

.PHONY: env rmenv install install-dev install-extras run format
.DEFAULT_GOAL := run
