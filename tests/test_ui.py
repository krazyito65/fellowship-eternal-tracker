import json

from playwright.sync_api import Page, expect


def test_dashboard_loads(page: Page, server_url: str):
    page.goto(server_url)
    # Check title
    expect(page).to_have_title("Fellowship Eternal Tracker")
    # Check that a config button exists
    expect(page.locator("button:has-text('⚙️ Config')")).to_be_visible()


def test_config_modal_opens(page: Page, server_url: str):
    page.goto(server_url)
    # Click config button
    page.click("button:has-text('⚙️ Config')")

    # Wait for modal
    modal = page.locator("#configModal")
    expect(modal).to_have_class("modal-overlay active")

    # Verify the JSON is loaded in the textarea
    textarea = page.locator("#configEditor")
    expect(textarea).not_to_be_empty()

    # Ensure it's valid JSON
    content = textarea.input_value()
    data = json.loads(content)
    assert "characters" in data
