import json
from playwright.sync_api import Page, expect

def test_team_builder_ui(page: Page, server_url: str):
    page.goto(server_url)
    
    # Click Team Builder button
    page.click("button:has-text('Team Builder')")
    
    # Wait for modal
    modal = page.locator("#teamModal")
    expect(modal).to_have_class("modal-overlay active")
    
    # Fill in a team name
    page.fill("#tbTeamName", "MyTestTeam")
    
    # Select first member
    page.select_option("#tbChar1", index=1)
    
    # We will NOT click save to avoid overwriting live user config.
    # Instead, we just verify the Close button works.
    page.click("button:has-text('Close')")
    expect(modal).not_to_have_class("modal-overlay active")
