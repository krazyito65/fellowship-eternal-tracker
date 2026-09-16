import os
import json
from pathlib import Path

# Allow overriding config file location via environment variable
_env_path = os.environ.get("CONFIG_FILE")
if _env_path:
    CONFIG_PATH = Path(_env_path)
else:
    CONFIG_PATH = Path(__file__).parent.parent / "config.json"


def load_config() -> dict:
    if CONFIG_PATH.exists():
        with open(CONFIG_PATH, encoding="utf-8") as f:
            try:
                return json.load(f)
            except json.JSONDecodeError:
                return {}
    return {}


def save_config(cfg: dict):
    with open(CONFIG_PATH, "w", encoding="utf-8") as f:
        json.dump(cfg, f, indent=4)
