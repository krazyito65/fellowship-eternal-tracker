#!/bin/bash
echo "Setting up Fellowship Eternal Tracker..."
if [ ! -f "config.json" ]; then
    echo "Copying config.example.json to config.json..."
    cp config.example.json config.json
fi
echo "Installing dependencies using uv..."
uv venv
source .venv/bin/activate
uv pip install -r pyproject.toml
echo "Starting server..."
python3 server.py
