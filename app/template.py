import json
import string
import time
from pathlib import Path

from app.config import load_config


def _esc(val) -> str:
    if val is None:
        return ""
    return (
        str(val)
        .replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
    )


def _format_timestamp(ts: int) -> str:
    if not ts:
        return ""
    try:
        t = time.localtime(ts)
        return time.strftime("%Y-%m-%d %H:%M", t)
    except Exception:
        return str(ts)


def build_html(full_roster: list[dict], selected_team=None) -> str:
    characters = list(full_roster)
    cfg = load_config()
    teams = cfg.get("teams", [])

    active_team_members = {}
    if selected_team:
        for t in teams:
            if t.get("name") == selected_team:
                active_team_members = t.get("members", {})
                break

    if selected_team and active_team_members:
        characters = [c for c in characters if c["slug"] in active_team_members]
    else:
        characters = []

    tracked_chars_html = ""
    for char in full_roster:
        cname = _esc(char.get("name", char["slug"]))
        tracked_chars_html += f"""
            <div style="display:flex; justify-content:space-between; align-items:center; font-size:0.9rem;">
                <span>{cname}</span>
                <button class="btn btn-cancel" style="padding:4px 8px; font-size:0.8rem;" onclick="removeCharacter('{_esc(char["slug"])}')">Remove</button>
            </div>"""

    tb_saved_teams_html = ""
    for t in teams:
        tname = _esc(t.get("name"))
        tb_saved_teams_html += f"""
            <div style="display:flex; justify-content:space-between; align-items:center; font-size:0.9rem;">
                <span style="font-weight:600;">{tname}</span>
                <div>
                    <button class="btn" style="padding:4px 8px; font-size:0.8rem;" onclick="tbEditTeam('{tname}')">Edit</button>
                    <button class="btn btn-cancel" style="padding:4px 8px; font-size:0.8rem;" onclick="tbDeleteTeam('{tname}')">Delete</button>
                </div>
            </div>"""

    teams_options_html = ""
    for t in teams:
        tname = _esc(t.get("name"))
        selected_attr = "selected" if tname == selected_team else ""
        teams_options_html += (
            f'<option value="{tname}" {selected_attr}>{tname}</option>\n'
        )

    all_heroes = {}
    for char in full_roster:
        for lv in char.get("levels", []):
            hid = lv.get("heroId")
            if hid and hid not in all_heroes:
                all_heroes[hid] = {
                    "id": hid,
                    "name": lv.get("heroName"),
                    "icon": lv.get("heroIcon"),
                }
    sorted_hero_ids = sorted(all_heroes.keys())

    tb_selectors_html = ""
    for i in range(1, 5):
        char_options = '<option value="">-- Select Character --</option>'
        for c in full_roster:
            if not c.get("error"):
                char_options += f'<option value="{_esc(c["slug"])}">{_esc(c.get("name", c["slug"]))}</option>'

        tb_selectors_html += f"""
        <div style="display:flex; gap:8px; margin-bottom:6px;">
            <select id="tbChar{i}" onchange="tbUpdateHeroes({i})" style="flex:1; padding:6px; background:#16162b; color:var(--text); border:1px solid var(--card-border); border-radius:4px;">
                {char_options}
            </select>
            <select id="tbHero{i}" style="flex:1; padding:6px; background:#16162b; color:var(--text); border:1px solid var(--card-border); border-radius:4px;">
                <option value="">-- Select Hero --</option>
            </select>
        </div>"""

    team_dropdowns_html = ""
    for char in characters:
        if char.get("error"):
            continue
        selected_hero = (
            active_team_members.get(char["slug"]) if active_team_members else ""
        )
        hero_options_html_local = ""
        for hid in sorted_hero_ids:
            hname = all_heroes[hid]["name"]
            selected_attr = "selected" if hname == selected_hero else ""
            hero_options_html_local += f'<option value="{_esc(hname)}" {selected_attr}>{_esc(hname)}</option>\n'

        team_dropdowns_html += f"""
        <div style="display:flex; flex-direction:column; gap:4px;">
            <label style="font-size:0.85rem; color:var(--text-dim);">{_esc(char.get("name", char["slug"]))}</label>
            <select data-slug="{_esc(char["slug"])}" class="team-hero-select" style="padding:6px 10px;background:#0f0f0f;color:var(--text);border:1px solid var(--card-border);border-radius:6px;min-width:120px;">
                <option value="">-- Skip --</option>
                {hero_options_html_local}
            </select>
        </div>"""

    cards_html = ""
    for char in characters:
        if char.get("error"):
            cards_html += f"""
            <div class="card error-card">
                <div class="card-header">
                    <h2>{_esc(char.get("name", char.get("slug", "???")))}</h2>
                    <span class="error-badge">Error</span>
                </div>
                <p class="error-msg">{_esc(char["error"])}</p>
            </div>"""
            continue

        max_eternal = 0
        max_hero_name = ""
        for lv in char.get("levels", []):
            if lv["leagueCss"] == "eternal" and lv["difficulty"] > max_eternal:
                max_eternal = lv["difficulty"]
                max_hero_name = lv["heroName"]

        level_pills = ""
        for lv in char.get("levels", []):
            is_active = ""
            if (
                active_team_members
                and active_team_members.get(char["slug"]) == lv["heroName"]
            ):
                is_active = "box-shadow: 0 0 0 2px var(--paragon); border-radius:14px;"

            level_pills += f"""
                <div class="hero-level level-{_esc(lv["difficultyCss"])}" data-hero-name="{_esc(lv["heroName"])}" 
                     style="cursor:pointer; {is_active}" 
                     onclick="selectHeroForComparison('{_esc(char["slug"])}', '{_esc(lv["heroName"])}', this)"
                     title="Click to select for comparison">
                    <img src="{_esc(lv["heroIcon"])}" alt="{_esc(lv["heroName"])}" class="hero-icon-small"/>
                    <span class="hero-name">{_esc(lv["heroName"])}</span>
                    <span class="league-badge league-{_esc(lv["leagueCss"])}">
                        {_esc(lv["leagueName"])} {lv["difficulty"]}
                    </span>
                </div>"""

        season_html = ""
        if char.get("season"):
            s = char["season"]
            season_html = f"""
                <div class="season-info">
                    <span class="season-label">{_esc(s["seasonName"])}</span>
                    <span class="season-rating">{s["rating"]:.0f} Rating</span>
                    <span class="season-rank rank-{_esc(s["globalCss"])}">
                        Top {100 - s["globalPercent"]:.1f}% (#{s["globalRank"]})
                    </span>
                </div>"""

        pinnacle_html = ""
        if char.get("pinnacle"):
            p = char["pinnacle"]
            cleared_str = ", ".join(p["cleared"]) if p["cleared"] else "None"
            pinnacle_html = f"""
                <div class="pinnacle-info">
                    <span class="pinnacle-label">🏔️ {_esc(p["label"])}</span>
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
                    <span class="eternal-label">Highest Level<br/><small>{_esc(max_hero_name)}</small></span>
                </div>"""

        cards_html += f"""
        <div class="card char-card">
            <div class="card-header">
                <img src="{_esc(char["avatar"])}" alt="" class="avatar"/>
                <div class="card-title">
                    <h2>
                        <a href="https://fellows.gg/character/{char["id"]}/{_esc(char["slug"])}/ratings"
                           target="_blank" rel="noopener">{_esc(char["name"])}</a>
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
                        <div class="bar-fill {"bar-leader" if level == max_val else ""}"
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
        if c.get("error"):
            continue
        h_set = set()
        for lv in c.get("levels", []):
            h_set.add(lv["heroName"])
        char_heroes[c["slug"]] = sorted(h_set)

    try:
        with open(
            Path(__file__).parent / "templates" / "index.html", encoding="utf-8"
        ) as f:
            template_str = f.read()
        template = string.Template(template_str)

        return template.safe_substitute(
            fetch_time=fetch_time,
            bar_chart_html=bar_chart_html,
            teams_options_html=teams_options_html,
            team_dropdowns_html=team_dropdowns_html,
            cards_html=cards_html,
            tracked_chars_html=tracked_chars_html,
            tb_selectors_html=tb_selectors_html,
            tb_saved_teams_html=tb_saved_teams_html,
            char_heroes_json=json.dumps(char_heroes),
            empty_state_html='<div style="text-align:center; margin: 40px; padding:40px; background:rgba(255,255,255,0.05); border-radius:12px;"><h2 style="margin-bottom:10px;">No Team Selected</h2><p style="color:var(--text-dim);">Please select an Active Team from the top menu, or click Team Builder to create one.</p></div>'
            if not characters
            else "",
            display_style="display:none;" if not characters else "",
        )
    except Exception as e:
        return f"<html><body><h1>Template Error</h1><pre>{e!s}</pre></body></html>"
