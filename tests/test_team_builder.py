import json
from playwright.sync_api import Page, expect

def test_team_builder_save(page: Page, server_url: str):
    page.goto(server_url)
    
    # Click Team Builder button
    page.click("button:has-text('👥 Team Builder')")
    
    # Wait for modal
    modal = page.locator("#teamBuilderModal")
    expect(modal).to_have_class("modal-overlay active")
    
    # Fill in a team name
    page.fill("#tbTeamName", "MyTestTeam")
    
    # Select first member
    # Note: the selects are populated. Just pick the first non-empty option
    page.select_option("#tbChar0", index=1)
    # The hero dropdown should populate. Wait a sec and pick the first hero
    page.wait_for_timeout(500) 
    page.select_option("#tbHero0", index=1)
    
    # Hit save
    # Note: 'Save Team' is the text. Let's make sure.
    page.click("button:has-text('Save Team')")
    
    # Wait for page to reload
    page.wait_for_timeout(1000)
    
    # Verify via API
    import urllib.request
    req = urllib.request.urlopen(server_url + "/api/config")
    cfg = json.loads(req.read().decode())
    
    teams = cfg.get("teams", [])
    found = False
    for t in teams:
        if t["name"] == "MyTestTeam":
            found = True
            break
            
    # Cleanup
    cfg["teams"] = [t for t in teams if t["name"] != "MyTestTeam"]
    req = urllib.request.Request(server_url + "/api/config", data=json.dumps(cfg).encode('utf-8'), method='POST')
    urllib.request.urlopen(req)
    
    assert found, "Team was not saved!"
