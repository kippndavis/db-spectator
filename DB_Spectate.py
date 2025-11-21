from playwright.sync_api import sync_playwright, TimeoutError as PlaywrightTimeoutError, expect
import random
import time
from pathlib import Path

DB_USERNAME = "AncientTelescope"
DB_PASSWORD = "DBSpectateBot"
BASE_DIR = Path(__file__).parent
PROFILE_DIR = BASE_DIR / "db-bot-profile"
EXT_DIR     = BASE_DIR / "ublock-origin-lite_2025.1110.1551_0"

def get_spectate_matches(page, format):
    page.locator(f"#{format} .duelbutton.watchbutton").first.wait_for(timeout=5000)

    rows = page.locator(f"#{format} .duelbutton.watchbutton")
    n = rows.count()
    results = []
    for i in range(n):
        row = rows.nth(i)
        try:
            game_type = row.locator(".game_type").inner_text(timeout=1000).strip()
        except:
            continue  # skip malformed rows

        if "MATCH" not in game_type.upper():
            continue

        title = ""
        try:
            title = row.locator(".title_txt").inner_text(timeout=500).strip()
        except:
            pass

        note = ""
        try:
            note = row.locator(".note_txt").inner_text(timeout=500).strip()
        except:
            pass

        results.append({
            "fmt": format,
            "index": i,          # index to click later
            "title": title,      # e.g., "PlayerA (...) | PlayerB (...)"
            "game_type": game_type,  # e.g., "MATCH\n(2 out of 3)"
            "note": note,        # e.g., "(Rated)"
        })
    return results

def login_and_get_to_lobby(page):
    page.goto("https://www.duelingbook.com/")
    page.wait_for_load_state("load")

    page.evaluate("""
        () => {
        const btn = document.getElementById('skip_intro_btn');
        if (btn) btn.click();
        }
                  """)
    # Wait for login form
    if page.is_visible("input.username_txt", timeout=1000):
        page.fill("input.username_txt", DB_USERNAME)
        page.fill("input.password_txt", DB_PASSWORD)
        page.click("input.login_btn")
    page.click("#duel_btn")
    page.click("#room_btn")
    page.click("input.watch_rb")
    page.wait_for_load_state("networkidle")

def click_match_row(page, match):
    scope = f"#{match['fmt']}"
    row = page.locator(f"{scope} .duelbutton.watchbutton").nth(match["index"])
    row.scroll_into_view_if_needed()
    row.click(timeout=1000)

def wait_for_duel_finish(page):

    # Specific locators
    over_body = page.locator("#over .body_txt")                  # Duel finished modal body
    quit_btn  = page.locator("#duel_quit_btn")
    msg_ok    = page.locator("#msg .ok_btn")                     # Lost Connection OK
    room_btn  = page.locator("#room_btn")

    either_event = page.locator("#over .body_txt:visible, #msg .ok_btn:visible")

    while True:
        # Wait until the eventy modal body text is visible
        try:
            either_event.wait_for(state="visible", timeout=1000)
        except PlaywrightTimeoutError:
            continue # Keep polling

        if msg_ok.is_visible(): # Disconnected; keep trying to reconnect
            while True:
                msg_ok.click()
                page.click("#duel_btn")
                try:
                    expect(room_btn).to_be_visible(timeout=10000)
                    if room_btn.is_visible: # Reconnected
                        page.click("#room_btn")
                        page.click("input.watch_rb")
                        return
                except:
                    pass

        if over_body.is_visible():
            page.wait_for_timeout(5000)
            page.click("#duel_quit_btn")
            return

def spectate_loop(page, formats=("gu", "eu")):
    matches = []
    for fmt in formats:
        try:
            matches += get_spectate_matches(page, fmt)
        except:
            pass
    choice = random.choice(matches)
    click_match_row(page, choice)
    wait_for_duel_finish(page)

def maximize_window(page):
    session = page.context.new_cdp_session(page)
    info = session.send("Browser.getWindowForTarget")
    session.send("Browser.setWindowBounds", {
        "windowId": info["windowId"],
        "bounds": {"windowState": "fullscreen"}
    })

def main():
    with sync_playwright() as p:
        context = p.chromium.launch_persistent_context(
            PROFILE_DIR.as_posix(),
            headless=False,
            channel="chromium",
            args=[
                f"--disable-extensions-except={EXT_DIR.as_posix()}",
                f"--load-extension={EXT_DIR.as_posix()}",
                "--start-maximized",
            ],
            ignore_default_args=["--enable-automation"],  # drop the automation info warning
            no_viewport=True # This makes the window scalable/resizable
        )
        
        page = context.new_page()
        maximize_window(page)
        page.evaluate("window.dispatchEvent(new Event('resize'))")
        login_and_get_to_lobby(page)
        while True:
            spectate_loop(page)

if __name__ == "__main__":
    main()