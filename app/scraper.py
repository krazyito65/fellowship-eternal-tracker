import json
import re

from app.config import load_config

_session = None


def _get_session():
    global _session
    if _session is None:
        import requests as req_lib
        import urllib3

        urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
        _session = req_lib.Session()
        _session.verify = False
        _session.headers.update(
            {
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
                "Accept-Language": "en-US,en;q=0.5",
            }
        )
        _session.cookies.set("tomestone_human_verified", "1", domain=".fellows.gg")
    return _session


def parse_page_data(page_data: dict, char_id: int, slug: str) -> dict:
    props = page_data.get("props", {})
    character = props.get("character", {})
    heroes_data = props.get("heroes", {})

    name = character.get("name", slug)
    avatar = character.get("avatar", "")
    last_updated = character.get("lastUpdated", 0)

    levels_raw = heroes_data.get("levels", [])
    hero_lookup = {}
    for h in heroes_data.get("heroes", {}).get("heroes", []):
        hero_lookup[h["id"]] = h

    levels = []
    for lv in levels_raw:
        hero_info = hero_lookup.get(lv.get("heroId"), {})
        league = lv.get("league", {})
        levels.append(
            {
                "heroId": lv.get("heroId"),
                "heroName": hero_info.get("localizedName", f"Hero {lv.get('heroId')}"),
                "heroIcon": hero_info.get("icon", ""),
                "heroCss": hero_info.get("cssClassName", ""),
                "difficulty": lv.get("difficulty", 0),
                "difficultyCss": lv.get("difficultyCssClassName", ""),
                "leagueName": league.get("localizedName", ""),
                "leagueCss": league.get("cssClassName", ""),
                "leagueIcon": league.get("icon", ""),
            }
        )

    levels.sort(key=lambda x: x["difficulty"], reverse=True)

    header = props.get("headerEncounters", {})
    seasons = header.get("fellowshipDungeonSeasons", [])
    season_info = None
    if seasons:
        s = seasons[0]
        ratings = s.get("ratings", {})
        placements = ratings.get("placements", {})
        global_placement = placements.get("global") or {}
        season_info = {
            "seasonName": s.get("caption") or "Unknown Season",
            "rating": ratings.get("rating") or 0,
            "globalRank": global_placement.get("position") or 0,
            "globalPercent": global_placement.get("percent") or 0,
            "globalCss": global_placement.get("cssRankClassName") or "",
        }

    pinnacle = header.get("pinnacleProgression", {})
    pinnacle_info = None
    if pinnacle and pinnacle.get("hasAnyProgress"):
        by_diff = pinnacle.get("byDifficulty", {})
        cleared = []
        for diff_id, diff_data in by_diff.items():
            if diff_data.get("activity"):
                cleared.append(diff_data.get("label", f"Difficulty {diff_id}"))
        pinnacle_info = {
            "label": pinnacle.get("label", ""),
            "cleared": cleared,
        }

    return {
        "id": char_id,
        "slug": slug,
        "name": name,
        "avatar": avatar,
        "lastUpdated": last_updated,
        "levels": levels,
        "season": season_info,
        "pinnacle": pinnacle_info,
        "error": None,
    }


def fetch_character_data(char_id: int, slug: str) -> dict:
    url = f"https://fellows.gg/character/{char_id}/{slug}/ratings"
    session = _get_session()

    try:
        resp = session.get(url, timeout=15)
        html = resp.text
    except Exception as exc:
        return {"error": str(exc), "name": slug, "id": char_id}

    match = re.search(
        r'<script\s+data-page="app"\s+type="application/json">\s*(\{.*?\})\s*</script>',
        html,
        re.DOTALL,
    )
    if not match:
        return {
            "error": "Could not find embedded JSON data",
            "name": slug,
            "id": char_id,
        }

    try:
        page_data = json.loads(match.group(1))
    except json.JSONDecodeError as exc:
        return {"error": f"JSON parse error: {exc}", "name": slug, "id": char_id}

    return parse_page_data(page_data, char_id, slug)


def fetch_all_characters() -> list[dict]:
    config = load_config()
    characters = config.get("characters", [])
    from typing import Any

    results: list[dict[str, Any] | None] = [None] * len(characters)

    import time
    from concurrent.futures import ThreadPoolExecutor

    def worker(args):
        idx, char = args
        # Polite delay to avoid hammering the server
        time.sleep(0.5)
        return idx, fetch_character_data(char.get("id", 0), char["slug"])

    with ThreadPoolExecutor(max_workers=3) as executor:
        futures = executor.map(worker, enumerate(characters))
        for idx, res in futures:
            results[idx] = res

    return [r for r in results if r is not None]


def fetch_dungeon(char, hero):
    if not hero:
        return {"char": char["slug"], "scores": []}
    session = _get_session()
    url = f"https://fellows.gg/character-contents/{char['id']}/{char['slug']}/ratings?hero={hero}"
    try:
        r = session.get(url, timeout=15)
        j = r.json()
        scores = j.get("ratings", {}).get("scores", [])
        return {"char": char["slug"], "hero": hero, "scores": scores}
    except Exception as e:
        return {"char": char["slug"], "hero": hero, "error": str(e)}


def fetch_hero_details_html(char, hero):
    session = _get_session()
    url = (
        f"https://fellows.gg/character/{char['id']}/{char['slug']}/ratings?hero={hero}"
    )
    try:
        r = session.get(url, timeout=15)
        html = r.text
        match = re.search(
            r'<script\s+data-page="app"\s+type="application/json">\s*(\{.*?\})\s*</script>',
            html,
            re.DOTALL,
        )
        if not match:
            raise Exception("JSON blob not found")
        j = json.loads(match.group(1))

        header = j.get("props", {}).get("headerEncounters", {})
        seasons = header.get("fellowshipDungeonSeasons", [])
        season_html = ""
        if seasons:
            s = seasons[0]
            ratings = s.get("ratings", {})
            placements = ratings.get("placements", {})
            global_placement = placements.get("global") or {}
            seasonName = s.get("caption") or "Unknown Season"
            rating = ratings.get("rating") or 0
            globalRank = global_placement.get("position") or 0
            globalPercent = global_placement.get("percent") or 0
            globalCss = global_placement.get("cssRankClassName") or ""

            season_html = f"""
            <div class="season-info">
                <span class="season-label">{seasonName}</span>
                <span class="season-rating">{rating:.0f} Rating</span>
                <span class="season-rank rank-{globalCss}">
                    Top {100 - globalPercent:.1f}% (#{globalRank})
                </span>
            </div>"""

        pinnacle = header.get("pinnacleProgression", {})
        pinnacle_html = ""
        if pinnacle and pinnacle.get("hasAnyProgress"):
            by_diff = pinnacle.get("byDifficulty", {})
            cleared = []
            for diff_id, diff_data in by_diff.items():
                if diff_data.get("activity"):
                    cleared.append(diff_data.get("label", f"Difficulty {diff_id}"))
            cleared_str = ", ".join(cleared) if cleared else "None"
            plabel = pinnacle.get("label", "")
            pinnacle_html = f"""
            <div class="pinnacle-info">
                <span class="pinnacle-label">🏔️ {plabel}</span>
                <span class="pinnacle-cleared">Cleared: {cleared_str}</span>
            </div>"""

        html_out = season_html + pinnacle_html
        if not html_out:
            html_out = f'<p style="color:var(--text-dim);text-align:center;padding:10px;">No Rating or Pinnacle progress yet for {hero}.</p>'
        return html_out
    except Exception as e:
        return f'<p style="color:#ff6b6b;padding:10px;">Error: {e!s}</p>'
