from app import template


def test_build_html_empty():
    html = template.build_html([], None)
    assert "Fellowship Eternal Tracker" in html
    assert "Active Team:" in html


def test_build_html_with_data():
    mock_data = [
        {
            "id": 1,
            "name": "TestChar",
            "slug": "testchar",
            "avatar": "",
            "lastUpdated": 0,
            "levels": [
                {
                    "heroId": 1,
                    "heroName": "TestHero",
                    "difficulty": 25,
                    "rating": 1000,
                    "isTimed": True,
                }
            ],
            "season": None,
            "pinnacle": None,
        }
    ]
    html = template.build_html(mock_data, None)
    assert "TestChar" in html
