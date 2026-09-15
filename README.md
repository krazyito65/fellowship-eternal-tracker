# Fellowship Eternal Tracker

A lightweight web dashboard for tracking and comparing Eternal Dungeon progression across your *Fellows.gg* characters and teams.

## Features
- **Team Comparison**: See your push group's bottleneck dungeons and get recommendations on what to run next.
- **Hero-Specific Lookups**: Drill down into specific heroes to check your precise *Fellows.gg* rating and Xul (Pinnacle) progress without leaving the dashboard.
- **Batch Add**: Easily import your whole roster by pasting a list of URLs.

## Setup

### Windows
Double-click `run.bat` to automatically install dependencies and start the local server.

### Linux / macOS
Run the setup script from the terminal:
```bash
chmod +x run.sh
./run.sh
```

## Configuration
Upon first run, duplicate `config.example.json` to `config.json`, and open the UI (http://localhost:8099) to add your characters.
