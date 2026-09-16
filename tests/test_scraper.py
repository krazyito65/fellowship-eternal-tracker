from app.scraper import parse_page_data


def test_parse_page_data_valid():
    # Mock some basic expected JSON structure
    mock_json = {
        "props": {
            "character": {"name": "TestChar", "avatar": "url"},
            "heroes": {
                "levels": [
                    {"heroId": 1, "difficulty": 5},
                    {"heroId": 2, "difficulty": 10},
                ]
            },
        }
    }

    result = parse_page_data(mock_json, 123, "testchar")
    assert result["id"] == 123
    assert result["slug"] == "testchar"
    assert result["name"] == "TestChar"
    assert result["avatar"] == "url"
    assert len(result["levels"]) == 2
    # Difficulty should sort descending
    assert result["levels"][0]["difficulty"] == 10


def test_parse_page_data_invalid():
    result = parse_page_data({}, 123, "testchar")
    assert result["error"] is None
    assert result["id"] == 123
    assert result["name"] == "testchar"
    assert len(result["levels"]) == 0
