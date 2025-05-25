ifeq ($(OS),Windows_NT)
    RM = powershell
    RM_FLAGS = -Command "Remove-Item -Path"
    RM_FLAGS_ALL = -Recurse -Force
    SEP = \\
else
    RM = rm
    RM_FLAGS = -f
    RM_FLAGS_ALL =
    SEP = /
endif

env:
	uv venv

install:
	uv sync --all-extras --no-dev

install-dev:
	uv sync --extra dev

run:
	uv run launcher.py

format:
	uv run ruff check --select I --fix .
	uv run ruff format .

clean:
	$(RM) $(RM_FLAGS) logs$(SEP)*.log $(RM_FLAGS_ALL)

clean-all:
	$(RM) $(RM_FLAGS) logs$(SEP)*.log $(RM_FLAGS_ALL)
	$(RM) $(RM_FLAGS) logs$(SEP)errors$(SEP)*.log $(RM_FLAGS_ALL)
	$(RM) $(RM_FLAGS) logs$(SEP)tracks$(SEP)*.log $(RM_FLAGS_ALL)

.PHONY: env install install-dev run format clean clean-all
.DEFAULT_GOAL := run
