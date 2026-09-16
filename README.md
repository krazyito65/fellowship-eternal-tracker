# Fellowship Eternal Tracker

A lightweight web dashboard for tracking and comparing Eternal Dungeon progression across your *Fellows.gg* characters and teams.

## Features
- **Team Comparison**: See your push group's bottleneck dungeons and get recommendations on what to run next.
- **Hero-Specific Lookups**: Drill down into specific heroes to check your precise *Fellows.gg* rating and Xul (Pinnacle) progress without leaving the dashboard.
- **Batch Add**: Easily import your whole roster by pasting a list of URLs.

## Project Structure
All core application logic lives in the `app/` directory. Utility scripts have been organized into the `bin/` directory for Windows and Linux/macOS respectively.
This repository strictly enforces `LF` (Line Feed) line endings across all platforms via `.gitattributes`.

## Setup

### Windows
Double-click `bin\windows\run.bat` to automatically install dependencies and start the local server.

### Linux / macOS
Run the setup script from the terminal:
```bash
chmod +x bin/linux/run.sh
./bin/linux/run.sh
```

## Configuration
Upon first run, duplicate `config.example.json` to `config.json` in the root of the directory, and open the UI (http://localhost:8099) to add your characters.

## Development & Testing
You can format your code and run the type checker using:
- **Windows**: `bin\windows\check.bat`
- **Linux/macOS**: `./bin/linux/check.sh`

To view the current code coverage report:
- **Windows**: `bin\windows\coverage.bat`
- **Linux/macOS**: `./bin/linux/coverage.sh`
