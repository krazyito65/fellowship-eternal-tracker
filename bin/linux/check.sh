#!/bin/bash
cd "$(dirname "$0")/../.."
echo "Running formatters and linters..."
uv run ruff check . --fix
uv run ruff format .
echo "Running type checker..."
uv run ty check .
echo "All checks passed!"
