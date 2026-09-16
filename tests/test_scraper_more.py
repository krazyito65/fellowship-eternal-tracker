from app import scraper
from app import config
import tempfile
import os
import json
from pathlib import Path
import pytest

@pytest.fixture(autouse=True)
def mock_config():
    fd, path = tempfile.mkstemp(suffix=".json")
    with os.fdopen(fd, 'w') as f:
        json.dump({"characters": [{"id": 1, "name": "Test", "slug": "test"}]}, f)
    
    old_config = config.CONFIG_PATH
    config.CONFIG_PATH = Path(path)
    yield
    config.CONFIG_PATH = old_config
    os.remove(path)

def test_fetch_dungeon_missing_params():
    res = scraper.fetch_dungeon({"id": 1, "slug": "test"}, "")
    assert res["scores"] == []

def test_fetch_dungeon_network_error(requests_mock):
    requests_mock.get("https://fellows.gg/character-contents/1/test-char/ratings?hero=test-hero", status_code=500)
    res = scraper.fetch_dungeon({"id": 1, "slug": "test-char", "name": "Test"}, "test-hero")
    assert res["error"] is not None

def test_fetch_hero_details_html_error(requests_mock):
    requests_mock.get("https://fellows.gg/character/1/test/ratings?hero=test", status_code=404)
    html = scraper.fetch_hero_details_html({"id": 1, "slug": "test"}, "test")
    assert "Unable to fetch" in html

def test_fetch_all_characters_error(requests_mock):
    requests_mock.get("https://fellows.gg/character/1/test/ratings", status_code=500)
    chars = scraper.fetch_all_characters()
    assert chars[0]["error"] is not None

def test_fetch_all_characters_success(requests_mock):
    mock_html = '''
    <script data-page="app" type="application/json">
    {"props": {"pageProps": {"initialState": {"character": {"characters": [{"id":1,"name":"Test","slug":"test"}]}}}}}
    </script>
    '''
    requests_mock.get("https://fellows.gg/character/1/test/ratings", text=mock_html)
    chars = scraper.fetch_all_characters()
    assert chars[0]["name"] == "Test"

def test_fetch_dungeon_success(requests_mock):
    mock_html = '''
    <script data-page="app" type="application/json">
    {"props": {"pageProps": {"initialState": {"character": {"characterHero": {"avatar":"test.png","lastUpdated":123,"levels":[{"difficulty":20}],"season":{"id":1},"pinnacle":{"id":2}}}}}}}
    </script>
    '''
    requests_mock.get("https://fellows.gg/character-contents/1/test/ratings?hero=hero", text=mock_html)
    res = scraper.fetch_dungeon({"id": 1, "slug": "test", "name": "Test"}, "hero")
    assert res["error"] is None
    assert res["avatar"] == "test.png"
    assert res["levels"][0]["difficulty"] == 20
