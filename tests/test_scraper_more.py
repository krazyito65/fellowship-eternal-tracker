import json
import os
import tempfile
from pathlib import Path

import pytest

from app import config, scraper


@pytest.fixture(autouse=True)
def mock_config():
    fd, path = tempfile.mkstemp(suffix=".json")
    with os.fdopen(fd, "w") as f:
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
    requests_mock.get(
        "https://fellows.gg/character-contents/1/test-char/ratings?hero=test-hero",
        status_code=500,
    )
    res = scraper.fetch_dungeon(
        {"id": 1, "slug": "test-char", "name": "Test"}, "test-hero"
    )
    assert res.get("error") is not None


def test_fetch_hero_details_html_error(requests_mock):
    requests_mock.get(
        "https://fellows.gg/character/1/test/ratings?hero=test", status_code=404
    )
    html = scraper.fetch_hero_details_html({"id": 1, "slug": "test"}, "test")
    assert "Error: JSON blob not found" in html


def test_fetch_all_characters_error(requests_mock):
    requests_mock.get("https://fellows.gg/character/1/test/ratings", status_code=500)
    chars = scraper.fetch_all_characters()
    assert chars[0].get("error") is not None


def test_fetch_all_characters_success(requests_mock):
    mock_html = '<script data-page="app" type="application/json">{"props": {"pageProps": {"initialState": {"character": {"characters": [{"id":1,"name":"Test","slug":"test"}]}}}}}</script>'
    requests_mock.get("https://fellows.gg/character/1/test/ratings", text=mock_html)
    chars = scraper.fetch_all_characters()
    assert chars[0]["name"].lower() == "test"


def test_fetch_dungeon_success(requests_mock):
    mock_json = {"ratings": {"scores": [{"dungeon": "test", "score": 100}]}}
    requests_mock.get(
        "https://fellows.gg/character-contents/1/test/ratings?hero=hero", json=mock_json
    )
    res = scraper.fetch_dungeon({"id": 1, "slug": "test", "name": "Test"}, "hero")
    assert res.get("error") is None
    assert res["scores"][0]["score"] == 100
