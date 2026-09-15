#!/bin/bash
echo "Setting up Fellowship Eternal Tracker..."

if ! command -v uv &> /dev/null; then
    echo "ERROR: 'uv' is not installed or not in your PATH."
    echo "Please install it from https://docs.astral.sh/uv/"
    exit 1
fi

if [ ! -f "config.json" ]; then
    echo "Copying config.example.json to config.json..."
    cp config.example.json config.json
fi

echo "Syncing dependencies..."
uv sync

echo "Starting server..."
uv run server.py
