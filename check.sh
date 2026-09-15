#!/usr/bin/env bash
echo "Running Ruff Linter and Formatter..."
uv run ruff check . --fix
uv run ruff format .
echo ""
echo "Running Ty Type Checker..."
uv run ty check .
