install: install-prod

install-dev:
	uv sync --all-extras

install-prod:
	uv sync --all-extras --no-dev

run:
	uv run launcher.py

lint:
	uv run ruff check --select I --fix .
	uv run ruff format .

clean:
	rm -f logs/*.log

clean-all:
	rm -f logs/*.log
	rm -f logs/errors/*.log
	rm -f logs/tracks/*.log

.PHONY: install install-dev install-prod run lint clean clean-all
.DEFAULT_GOAL := run
