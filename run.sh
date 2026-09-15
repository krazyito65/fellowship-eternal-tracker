#!/bin/bash
echo "Setting up Fellowship Eternal Tracker..."
if [ ! -f "config.json" ]; then
    echo "Copying config.example.json to config.json..."
    cp config.example.json config.json
fi
echo "Syncing dependencies..."
uv sync
echo "Starting server..."
uv run server.py
