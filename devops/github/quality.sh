#!/usr/bin/env sh
set -eu

cd "$(dirname "$0")/../../backend"

uv sync --all-extras --locked
uv run ruff format --check .
uv run ruff check .
uv run mypy app
uv run pytest -q
