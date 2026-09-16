from pathlib import Path
import os
import json
import tempfile
from app import config

def test_load_save_config():
    fd, path = tempfile.mkstemp(suffix=".json")
    with os.fdopen(fd, 'w') as f:
        json.dump({"test": "data"}, f)
    
    # Override CONFIG_FILE
    old_config = config.CONFIG_PATH
    config.CONFIG_PATH = Path(path)
    
    try:
        # Test Load
        data = config.load_config()
        assert data["test"] == "data"
        
        # Test Save
        data["test"] = "new_data"
        config.save_config(data)
        
        data2 = config.load_config()
        assert data2["test"] == "new_data"
    finally:
        config.CONFIG_PATH = old_config
        os.remove(path)

def test_load_config_missing():
    old_config = config.CONFIG_PATH
    config.CONFIG_PATH = Path("does_not_exist_xyz.json")
    try:
        data = config.load_config()
        assert data == {}
    finally:
        config.CONFIG_PATH = old_config
