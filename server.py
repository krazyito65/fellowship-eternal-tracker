"""
Fellowship Eternal Tracker Server

This script runs a lightweight, zero-dependency HTTP server that fetches 
character data from fellows.gg and displays it in a local web dashboard.

Usage:
    python server.py

It serves HTML templates from 'index.html' and uses 'config.json' for settings.
"""

import json
import logging
import re
import string
import sys
import time
import threading
from http.server import HTTPServer, BaseHTTPRequestHandler
from pathlib import Path
from urllib.request import urlopen, Request
from urllib.error import URLError
import ssl
import urllib3

# Suppress InsecureRequestWarning from requests
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

CONFIG_PATH = Path(__file__).parent / "config.json"

# ── Data Fetching ──────────────────────────────────────────────────────────────

# Shared session with bot-check cookie pre-set
_session = None

def _get_session(api_key: str = "") -> "requests.Session":
    """Get or create a requests session with the bot-check cookie."""
    global _session
    if _session is None:
        import requests as req_lib
        _session = req_lib.Session()
        _session.verify = False
        _session.headers.update({
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.5",
        })
        # Pre-set the bot verification cookie
        _session.cookies.set("tomestone_human_verified", "1", domain=".fellows.gg")
    if api_key:
        _session.headers["Authorization"] = f"Bearer {api_key}"
    return _session

def load_config():
    with open(CONFIG_PATH, "r", encoding="utf-8") as f:
        return json.load(f)


def fetch_character_data(char_id: int, slug: str, api_key: str = "") -> dict:
    """Fetch a character page from fellows.gg and parse the embedded JSON."""
    url = f"https://fellows.gg/character/{char_id}/{slug}/ratings"
    session = _get_session(api_key)

    try:
        resp = session.get(url, timeout=15)
        html = resp.text
    except Exception as exc:
        return {"error": str(exc), "name": slug, "id": char_id}

    # The page embeds a big JSON blob in:
    #   <script data-page="app" type="application/json">{...}</script>
    match = re.search(
        r'<script\s+data-page="app"\s+type="application/json">\s*(\{.*?\})\s*</script>',
        html,
        re.DOTALL,
    )
    if not match:
        return {"error": "Could not find embedded JSON data", "name": slug, "id": char_id}

    try:
        page_data = json.loads(match.group(1))
    except json.JSONDecodeError as exc:
        return {"error": f"JSON parse error: {exc}", "name": slug, "id": char_id}

    return parse_page_data(page_data, char_id, slug)


def parse_page_data(page_data: dict, char_id: int, slug: str) -> dict:
    """Extract the relevant fields from the fellows.gg page JSON."""
    props = page_data.get("props", {})
    character = props.get("character", {})
    heroes_data = props.get("heroes", {})

    name = character.get("name", slug)
    avatar = character.get("avatar", "")
    last_updated = character.get("lastUpdated", 0)

    # Hero levels (Eternal progression per hero)
    levels_raw = heroes_data.get("levels", [])
    hero_lookup = {}
    for h in heroes_data.get("heroes", {}).get("heroes", []):
        hero_lookup[h["id"]] = h

    levels = []
    for lv in levels_raw:
        hero_info = hero_lookup.get(lv.get("heroId"), {})
        league = lv.get("league", {})
        levels.append({
            "heroId": lv.get("heroId"),
            "heroName": hero_info.get("localizedName", f"Hero {lv.get('heroId')}"),
            "heroIcon": hero_info.get("icon", ""),
            "heroCss": hero_info.get("cssClassName", ""),
            "difficulty": lv.get("difficulty", 0),
            "difficultyCss": lv.get("difficultyCssClassName", ""),
            "leagueName": league.get("localizedName", ""),
            "leagueCss": league.get("cssClassName", ""),
            "leagueIcon": league.get("icon", ""),
        })

    # Sort by difficulty descending (highest first)
    levels.sort(key=lambda x: x["difficulty"], reverse=True)

    # Season rating
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

    # Pinnacle progression
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


def fetch_all_characters() -> list[dict]:
    """Fetch data for all configured characters in parallel."""
    config = load_config()
    characters = config.get("characters", [])
    api_key = config.get("api_key", "")
    results = [None] * len(characters)

    def worker(idx, char):
        results[idx] = fetch_character_data(char.get("id", 0), char["slug"], api_key)

    threads = []
    for i, char in enumerate(characters):
        t = threading.Thread(target=worker, args=(i, char))
        t.start()
        threads.append(t)

    for t in threads:
        t.join(timeout=20)

    return [r for r in results if r is not None]


# ── HTML Template ──────────────────────────────────────────────────────────────

def build_html(full_roster: list[dict], selected_team=None) -> str:
    characters = list(full_roster)
    """Build a complete HTML dashboard comparing Eternal levels."""

    cfg = load_config()
    teams = cfg.get('teams', [])
    
    active_team_members = {}
    if selected_team:
        for t in teams:
            if t.get('name') == selected_team:
                active_team_members = t.get('members', {})
                break
                
    if selected_team and active_team_members:
        # Filter characters to only those in the team
        characters = [c for c in characters if c['slug'] in active_team_members]
        print(f"Filtered characters down to {len(characters)} members")
    else:
        # If no team is selected, show nothing! (as requested)
        characters = []

    # Collect all unique heroes across all characters for column headers
    all_heroes = {}
    for char in characters:
        if char.get("error"):
            continue
        for lv in char.get("levels", []):
            hid = lv["heroId"]
            if hid not in all_heroes:
                all_heroes[hid] = {
                    "name": lv["heroName"],
                    "icon": lv["heroIcon"],
                    "css": lv["heroCss"],
                }

    # Sort heroes alphabetically
    sorted_hero_ids = sorted(all_heroes.keys(), key=lambda h: all_heroes[h]["name"])
    
    hero_options_html = ""
    for hid in sorted_hero_ids:
        hname = all_heroes[hid]["name"]
        hero_options_html += f'<option value="{_esc(hname)}">{_esc(hname)}</option>\n'

    team_dropdowns_html = ""
    for char in characters:
        if char.get("error"): continue
        
        selected_hero = active_team_members.get(char['slug']) if active_team_members else ""
        
        hero_options_html_local = ""
        for hid in sorted_hero_ids:
            hname = all_heroes[hid]["name"]
            selected_attr = 'selected' if hname == selected_hero else ''
            hero_options_html_local += f'<option value="{_esc(hname)}" {selected_attr}>{_esc(hname)}</option>\n'
            
        team_dropdowns_html += f"""
        <div style="display:flex; flex-direction:column; gap:4px;">
            <label style="font-size:0.85rem; color:var(--text-dim);">{_esc(char.get('name', char['slug']))}</label>
            <select data-slug="{_esc(char['slug'])}" class="team-hero-select" style="padding:6px 10px;background:#0f0f0f;color:var(--text);border:1px solid var(--card-border);border-radius:6px;min-width:120px;">
                <option value="">-- Skip --</option>
                {hero_options_html_local}
            </select>
        </div>"""

    tracked_chars_html = ""
    for char in characters:
        name = _esc(char.get('name', char['slug']))
        slug = _esc(char['slug'])
        tracked_chars_html += f"""
        <div style="display:flex; justify-content:space-between; align-items:center; background:rgba(255,255,255,0.05); padding:6px 12px; border-radius:4px;">
            <span>{name} <small style="color:var(--text-dim);">({slug})</small></span>
            <button class="btn" style="background:#ef4444; padding:4px 8px; font-size:0.75rem;" onclick="removeCharacter('{slug}')">Remove</button>
        </div>"""
        
    if not tracked_chars_html:
        tracked_chars_html = '<span style="color:var(--text-dim);font-size:0.85rem;">No characters tracked yet.</span>'

    cfg = load_config()
    teams = cfg.get('teams', [])
    teams_options_html = ""
    tb_saved_teams_html = ""
    for t in teams:
        tname = _esc(t.get('name', 'Unnamed'))
        teams_options_html += f'<option value="{tname}">{tname}</option>\n'
        tb_saved_teams_html += f"""
        <div style="display:flex; justify-content:space-between; align-items:center; background:rgba(255,255,255,0.05); padding:6px 12px; border-radius:4px;">
            <span>{tname} <small style="color:var(--text-dim);">({len(t.get('members', []))} members)</small></span>
            <button class="btn" style="background:#ef4444; padding:4px 8px; font-size:0.75rem;" onclick="tbDeleteTeam('{tname}')">Delete</button>
        </div>
        """
        
    if not tb_saved_teams_html:
        tb_saved_teams_html = '<span style="color:var(--text-dim);font-size:0.85rem;">No teams created yet.</span>'
        
    tb_selectors_html = ""
    for i in range(4):
        tb_selectors_html += f"""
        <div style="margin-bottom:8px; display:flex; gap:10px;">
            <select id="tbChar{i}" style="flex:1; padding:6px; background:#16162b; color:var(--text); border:1px solid var(--card-border); border-radius:4px;" onchange="tbUpdateHeroes({i})">
                <option value="">-- Select Character --</option>"""
        for char in full_roster:
            cname = _esc(char.get('name', char['slug']))
            cslug = _esc(char['slug'])
            tb_selectors_html += f'<option value="{cslug}">{cname}</option>'
        
        tb_selectors_html += f"""
            </select>
            <select id="tbHero{i}" style="flex:1; padding:6px; background:#16162b; color:var(--text); border:1px solid var(--card-border); border-radius:4px;">
                <option value="">-- Select Hero --</option>
            </select>
        </div>
        """

    # Build character cards
    cards_html = ""
    for char in characters:
        if char.get("error"):
            cards_html += f"""
            <div class="card error-card">
                <div class="card-header">
                    <h2>{_esc(char.get('name', char.get('slug', '???')))}</h2>
                    <span class="error-badge">Error</span>
                </div>
                <p class="error-msg">{_esc(char['error'])}</p>
            </div>"""
            continue

        # Find highest eternal level
        max_eternal = 0
        max_hero_name = ""
        for lv in char.get("levels", []):
            if lv["leagueCss"] == "eternal" and lv["difficulty"] > max_eternal:
                max_eternal = lv["difficulty"]
                max_hero_name = lv["heroName"]

        level_pills = ""
        for lv in char.get("levels", []):
            is_active = ''
            if active_team_members and active_team_members.get(char['slug']) == lv["heroName"]:
                is_active = 'box-shadow: 0 0 0 2px var(--paragon); border-radius:14px;'
            
            level_pills += f"""
                <div class="hero-level level-{_esc(lv['difficultyCss'])}" data-hero-name="{_esc(lv['heroName'])}" 
                     style="cursor:pointer; {is_active}" 
                     onclick="selectHeroForComparison('{_esc(char['slug'])}', '{_esc(lv['heroName'])}', this)"
                     title="Click to select for comparison">
                    <img src="{_esc(lv['heroIcon'])}" alt="{_esc(lv['heroName'])}" class="hero-icon-small"/>
                    <span class="hero-name">{_esc(lv['heroName'])}</span>
                    <span class="league-badge league-{_esc(lv['leagueCss'])}">
                        {_esc(lv['leagueName'])} {lv['difficulty']}
                    </span>
                </div>"""

        season_html = ""
        if char.get("season"):
            s = char["season"]
            season_html = f"""
                <div class="season-info">
                    <span class="season-label">{_esc(s['seasonName'])}</span>
                    <span class="season-rating">{s['rating']:.0f} Rating</span>
                    <span class="season-rank rank-{_esc(s['globalCss'])}">
                        Top {100 - s['globalPercent']:.1f}% (#{s['globalRank']})
                    </span>
                </div>"""

        pinnacle_html = ""
        if char.get("pinnacle"):
            p = char["pinnacle"]
            cleared_str = ", ".join(p["cleared"]) if p["cleared"] else "None"
            pinnacle_html = f"""
                <div class="pinnacle-info">
                    <span class="pinnacle-label">🏔️ {_esc(p['label'])}</span>
                    <span class="pinnacle-cleared">Cleared: {_esc(cleared_str)}</span>
                </div>"""

        updated_str = ""
        if char.get("lastUpdated"):
            updated_str = f'<span class="last-updated">Updated: {_format_timestamp(char["lastUpdated"])}</span>'

        eternal_display = ""
        if max_eternal > 0:
            eternal_display = f"""
                <div class="eternal-highlight">
                    <span class="eternal-number">{max_eternal}</span>
                    <span class="eternal-label">Highest Eternal<br/><small>{_esc(max_hero_name)}</small></span>
                </div>"""

        cards_html += f"""
        <div class="card char-card">
            <div class="card-header">
                <img src="{_esc(char['avatar'])}" alt="" class="avatar"/>
                <div class="card-title">
                    <h2>
                        <a href="https://fellows.gg/character/{char['id']}/{_esc(char['slug'])}/ratings"
                           target="_blank" rel="noopener">{_esc(char['name'])}</a>
                    </h2>
                    {updated_str}
                </div>
                <div style="display:flex; flex-direction:column; align-items:flex-end;">
                    {eternal_display}
                </div>
            </div>
            <div class="hero-specific-details">
                {season_html}
                {pinnacle_html}
            </div>
            <div class="hero-levels">
                {level_pills}
            </div>
        </div>"""

    # Eternal-only comparison bar chart
    bar_chart_html = ""
    eternal_chars = []
    for char in characters:
        if char.get("error"):
            continue
        max_e = 0
        max_h = ""
        for lv in char.get("levels", []):
            if lv["leagueCss"] == "eternal" and lv["difficulty"] > max_e:
                max_e = lv["difficulty"]
                max_h = lv["heroName"]
        eternal_chars.append((char["name"], max_e, max_h, char["avatar"]))

    if eternal_chars:
        max_val = max(e[1] for e in eternal_chars) or 1
        for name, level, hero, avatar in eternal_chars:
            pct = (level / max_val) * 100 if max_val > 0 else 0
            bar_chart_html += f"""
                <div class="bar-row">
                    <div class="bar-label">
                        <img src="{_esc(avatar)}" alt="" class="bar-avatar"/>
                        {_esc(name)}
                    </div>
                    <div class="bar-track">
                        <div class="bar-fill {'bar-leader' if level == max_val else ''}"
                             style="width: {pct}%">
                            <span class="bar-value">Eternal {level}</span>
                        </div>
                    </div>
                    <div class="bar-hero">{_esc(hero)}</div>
                </div>"""

    fetch_time = time.strftime("%Y-%m-%d %H:%M:%S")
    
    if not bar_chart_html:
        bar_chart_html = '<p style="color:var(--text-dim);text-align:center;padding:20px;">No Eternal-level data found</p>'


    char_heroes = {}
    for c in full_roster:
        if c.get("error"): continue
        h_set = set()
        for lv in c.get("levels", []):
            h_set.add(lv["heroName"])
        char_heroes[c["slug"]] = sorted(list(h_set))

    try:
        with open('index.html', 'r', encoding='utf-8') as f:
            template_str = f.read()
        template = string.Template(template_str)
        
        return template.safe_substitute(
            fetch_time=fetch_time,
            bar_chart_html=bar_chart_html,
            teams_options_html=teams_options_html,
            team_dropdowns_html=team_dropdowns_html,
            tb_selectors_html=tb_selectors_html,
            tb_saved_teams_html=tb_saved_teams_html,
            tracked_chars_html=tracked_chars_html,
            cards_html=cards_html,
            all_heroes_json=json.dumps(all_heroes),
            char_heroes_json=json.dumps(char_heroes),
            empty_state_html='<div style="text-align:center; margin: 40px; padding:40px; background:rgba(255,255,255,0.05); border-radius:12px;"><h2 style="margin-bottom:10px;">No Team Selected</h2><p style="color:var(--text-dim);">Please select an Active Team from the top menu, or click Team Builder to create one.</p></div>' if not characters else '',
            display_style='display:none;' if not characters else '',
            api_key_val=_esc(cfg.get('api_key', ''))
        )
    except Exception as e:
        return f"Error loading index.html: {e}"



def _esc(text) -> str:
    """HTML-escape a string."""
    if not isinstance(text, str):
        text = str(text)
    return (text
            .replace("&", "&amp;")
            .replace("<", "&lt;")
            .replace(">", "&gt;")
            .replace('"', "&quot;"))


def _format_timestamp(ts):
    """Format a Unix timestamp (seconds) to a readable string."""
    try:
        return time.strftime("%Y-%m-%d %H:%M", time.localtime(ts))
    except (ValueError, OSError):
        return "Unknown"


# ── HTTP Server ────────────────────────────────────────────────────────────────

class TrackerHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        from urllib.parse import urlparse, parse_qs
        parsed_path = urlparse(self.path)
        if parsed_path.path == "/" or parsed_path.path == "/index.html":
            qs = parse_qs(parsed_path.query)
            selected_team = qs.get('team', [None])[0]
            print(f"[*] Fetching character data for team: {selected_team}...")
            characters = fetch_all_characters()
            html = build_html(characters, selected_team)
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.end_headers()
            self.wfile.write(html.encode("utf-8"))

        elif self.path == "/api/hero-details":
            length = int(self.headers.get("Content-Length", 0))
            body = self.rfile.read(length).decode("utf-8")
            try:
                data = json.loads(body)
            except Exception:
                data = {}
                
            slug = data.get("slug")
            hero = data.get("hero")
            
            config = load_config()
            chars = config.get("characters", [])
            char = next((c for c in chars if c["slug"] == slug), None)
            
            html_out = ""
            if char and hero:
                api_key = config.get("api_key", "")
                session = _get_session(api_key)
                url = f"https://fellows.gg/character/{char['id']}/{char['slug']}/ratings?hero={hero}"
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
                    j = __import__('json').loads(match.group(1))
                    
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
                            <span class="season-label">{_esc(seasonName)}</span>
                            <span class="season-rating">{rating:.0f} Rating</span>
                            <span class="season-rank rank-{_esc(globalCss)}">
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
                            <span class="pinnacle-label">🏔️ {_esc(plabel)}</span>
                            <span class="pinnacle-cleared">Cleared: {_esc(cleared_str)}</span>
                        </div>"""
                        
                    html_out = season_html + pinnacle_html
                    if not html_out:
                        html_out = f'<p style="color:var(--text-dim);text-align:center;padding:10px;">No Rating or Pinnacle progress yet for {_esc(hero)}.</p>'
                except Exception as e:
                    html_out = f'<p style="color:#ff6b6b;padding:10px;">Error: {str(e)}</p>'
                    
            self.send_response(200)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.end_headers()
            self.wfile.write(json.dumps({"html": html_out}).encode("utf-8"))

        elif self.path == "/api/config":
            try:
                with open(CONFIG_PATH, "r", encoding="utf-8") as f:
                    content = f.read()
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.end_headers()
                self.wfile.write(content.encode("utf-8"))
            except FileNotFoundError:
                self.send_response(404)
                self.end_headers()
                self.wfile.write(b"Config not found")

        else:
            self.send_response(404)
            self.end_headers()
            self.wfile.write(b"Not Found")

    def do_POST(self):
        if self.path == "/api/team-dungeons":
            length = int(self.headers.get("Content-Length", 0))
            body = self.rfile.read(length).decode("utf-8")
            try:
                selections = json.loads(body)
            except Exception:
                selections = {}

            config = load_config()
            characters = config.get("characters", [])
            api_key = config.get("api_key", "")
            
            results = []
            def fetch_dungeon(char):
                hero = selections.get(char["slug"])
                if not hero:
                    return {"char": char["slug"], "scores": []}
                    
                session = _get_session(api_key)
                url = f"https://fellows.gg/character-contents/{char['id']}/{char['slug']}/ratings?hero={hero}"
                try:
                    r = session.get(url, timeout=15)
                    j = r.json()
                    scores = j.get("ratings", {}).get("scores", [])
                    return {"char": char["slug"], "hero": hero, "scores": scores}
                except Exception as e:
                    return {"char": char["slug"], "hero": hero, "error": str(e)}
                    
            import concurrent.futures
            selected_chars = [c for c in characters if selections.get(c["slug"])]
            with concurrent.futures.ThreadPoolExecutor() as executor:
                futures = [executor.submit(fetch_dungeon, c) for c in selected_chars]
                results = [f.result() for f in futures]
                
            self.send_response(200)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.end_headers()
            self.wfile.write(json.dumps(results).encode("utf-8"))

        elif self.path == "/api/hero-details":
            length = int(self.headers.get("Content-Length", 0))
            body = self.rfile.read(length).decode("utf-8")
            try:
                data = json.loads(body)
            except Exception:
                data = {}
                
            slug = data.get("slug")
            hero = data.get("hero")
            
            config = load_config()
            chars = config.get("characters", [])
            char = next((c for c in chars if c["slug"] == slug), None)
            
            html_out = ""
            if char and hero:
                api_key = config.get("api_key", "")
                session = _get_session(api_key)
                url = f"https://fellows.gg/character/{char['id']}/{char['slug']}/ratings?hero={hero}"
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
                    j = __import__('json').loads(match.group(1))
                    
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
                            <span class="season-label">{_esc(seasonName)}</span>
                            <span class="season-rating">{rating:.0f} Rating</span>
                            <span class="season-rank rank-{_esc(globalCss)}">
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
                            <span class="pinnacle-label">🏔️ {_esc(plabel)}</span>
                            <span class="pinnacle-cleared">Cleared: {_esc(cleared_str)}</span>
                        </div>"""
                        
                    html_out = season_html + pinnacle_html
                    if not html_out:
                        html_out = '<p style="color:var(--text-dim);text-align:center;padding:10px;">No hero-specific data.</p>'
                except Exception as e:
                    html_out = f'<p style="color:#ff6b6b;padding:10px;">Error: {str(e)}</p>'
                    
            self.send_response(200)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.end_headers()
            self.wfile.write(json.dumps({"html": html_out}).encode("utf-8"))

        elif self.path == "/api/config":
            length = int(self.headers.get("Content-Length", 0))
            body = self.rfile.read(length).decode("utf-8")

            try:
                parsed = json.loads(body)
                # Validate structure
                if "characters" not in parsed:
                    raise ValueError("Missing 'characters' array")
                for ch in parsed["characters"]:
                    if "id" not in ch or "slug" not in ch:
                        raise ValueError("Each character needs 'id' and 'slug'")
            except (json.JSONDecodeError, ValueError) as exc:
                self.send_response(400)
                self.end_headers()
                self.wfile.write(str(exc).encode("utf-8"))
                return

            with open(CONFIG_PATH, "w", encoding="utf-8") as f:
                json.dump(parsed, f, indent=2)

            self.send_response(200)
            self.end_headers()
            self.wfile.write(b"OK")
        else:
            self.send_response(404)
            self.end_headers()

    def log_message(self, fmt, *args):
        # Cleaner logging
        print(f"[{time.strftime('%H:%M:%S')}] {args[0]}")


def main():
    config = load_config()
    port = config.get("port", 8080)

    server = HTTPServer(("0.0.0.0", port), TrackerHandler)
    banner = f"""
===================================================
   Fellowship Eternal Tracker
===================================================

  Server running at:  http://localhost:{port}
  Config file:        config.json

  Press Ctrl+C to stop
===================================================
"""
    print(banner)

    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\n[*] Shutting down...")
        server.server_close()


if __name__ == "__main__":
    main()
