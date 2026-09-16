#!/bin/bash
cd "$(dirname "$0")/../.."
echo "Running pytest with coverage..."
uv run pytest --cov=app --cov-report=term-missing --cov-report=html
echo ""
echo "Coverage report generated! You can view the detailed breakdown by opening htmlcov/index.html in your browser."
