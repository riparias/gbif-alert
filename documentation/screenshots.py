"""Regenerate the user guide screenshots from the demo instance.

Run by hand, not in CI: the demo's data changes with every import, so every run
produces different images. Review the images before committing them.

    uv run python documentation/screenshots.py            # all screenshots
    uv run python documentation/screenshots.py explore-table.png   # just one
    uv run python documentation/screenshots.py --login    # sign in, see below

Screenshots of signed-in pages need a demo session: `--login` opens a browser
window, waits for you to sign in there, and saves the session to AUTH_FILE,
outside the repository. The script never sees the password.
"""

import sys
import time
from collections.abc import Callable
from pathlib import Path

from playwright.sync_api import (
    Browser,
    BrowserContext,
    Locator,
    Page,
    sync_playwright,
)

BASE_URL = "https://demo.gbif-alert.org"
OUT_DIR = Path(__file__).parent / "docs" / "assets" / "img"
# A live session cookie: kept out of the repository so it cannot be committed.
AUTH_FILE = Path.home() / ".cache" / "gbif-alert-docs" / "demo-session.json"
LOGIN_TIMEOUT_S = 600

# The demo throttles anonymous API calls to 60/min and one page load makes
# about 10 of them, so shots are spaced out. A throttled call would otherwise
# leave an error message in the screenshot.
# ponytail: fixed pacing, switch to an authenticated session (600/min) if the
# shot list grows enough for the runtime to matter.
PAUSE_BETWEEN_SHOTS_S = 12


def open_home(page: Page, query: str = "") -> None:
    page.goto(f"{BASE_URL}/{query}")
    settle(page)


def settle(page: Page) -> None:
    page.wait_for_load_state("networkidle")
    page.wait_for_timeout(1_000)  # tab fade-in and map rendering


def show_tab(page: Page, name: str) -> None:
    page.get_by_role("tab", name=name).click()
    settle(page)


# --- Shots: each loads what it needs and returns what to capture ---
#
# Shots showing the map are saved as JPEG: its tiles make PNGs several MB,
# while flat UI stays smaller and sharper as PNG.

# A fixed observation and area, so reruns show the same subject even though
# the demo's data changes. stable_id survives re-imports.
OBSERVATION = "4852f6a7c9cec3762dff74d5699d0975d115909f"
AREA_ID = 274  # BE2500932 - Poldercomplex, near Brugge: many observations around


def tabs(page: Page) -> Locator:
    return page.locator(".p-tabs")


def explore_overview(page: Page) -> Page:
    open_home(page)
    show_tab(page, "Map")
    return page


def explore_date_brush(page: Page) -> Locator:
    open_home(page)
    return page.locator(".histogram-brush")


def explore_species_filter(page: Page) -> Locator:
    open_home(page)
    page.get_by_role("button", name="All species").click()
    settle(page)
    return page.get_by_role("dialog")


def explore_area_filter(page: Page) -> Locator:
    open_home(page)
    page.get_by_role("button", name="Everywhere").click()
    settle(page)
    return page.get_by_role("dialog")


def explore_approaching(page: Page) -> Page:
    open_home(page, f"?areaIds={AREA_ID}&areaFilterMode=both&approachingDistanceKm=2")
    show_tab(page, "Map")
    # The map does not zoom to the selected area by itself: drag the area
    # (found by eye at this offset from the map's top-left) into view, then
    # double-click to zoom in on it.
    # ponytail: hard-coded pixel offset, breaks if the demo's initial map view
    # or AREA_ID changes. Re-measure from a fresh screenshot if so.
    box = page.locator(".ol-viewport").first.bounding_box()
    assert box, "map not visible"
    x, y = box["x"], box["y"]
    page.mouse.move(x + 274, y + 18)
    page.mouse.down()
    page.mouse.move(x + 500, y + 180, steps=10)
    page.mouse.up()
    for _ in range(2):
        page.mouse.dblclick(x + 500, y + 180)
        settle(page)
    return page


def explore_timeline(page: Page) -> Locator:
    open_home(page)
    show_tab(page, "Timeline")
    return tabs(page)


def explore_species_tab(page: Page) -> Locator:
    open_home(page)
    show_tab(page, "Species")
    return tabs(page)


def explore_table(page: Page) -> Locator:
    open_home(page)
    show_tab(page, "Table")
    return tabs(page)


def explore_observation(page: Page) -> Locator:
    open_home(page, f"?obs={OBSERVATION}")
    return page.locator(".p-drawer")


SHOTS: dict[str, Callable[[Page], Page | Locator]] = {
    "explore-overview.jpg": explore_overview,
    "explore-date-brush.png": explore_date_brush,
    "explore-species-filter.png": explore_species_filter,
    "explore-area-filter.png": explore_area_filter,
    "explore-approaching.jpg": explore_approaching,
    "explore-timeline.png": explore_timeline,
    "explore-species-tab.png": explore_species_tab,
    "explore-table.png": explore_table,
    "explore-observation.png": explore_observation,
}


# --- Signed-in shots (need `--login` first) ---
#
# Taken as the demo's operator account, so staff-only controls are hidden and
# personal details swapped for placeholders before each screenshot: what a
# regular user would see, and nothing personal committed to the repository.

GENK_ALERT_ID = 45  # "My study site near Genk", has Not viewed observations
EXAMPLE_ALERT_ID = 43  # "Aquatic plants near protected sites"
GENK_AREA_ID = 326  # user-specific area "My study site near Genk"


def go(page: Page, path: str) -> None:
    page.goto(f"{BASE_URL}{path}")
    settle(page)


def alerts_profile(page: Page) -> Locator:
    go(page, "/profile")
    return page.locator(".page-content--narrow")


def alerts_not_viewed(page: Page) -> Page:
    go(page, f"/alert/{GENK_ALERT_ID}")
    show_tab(page, "Table")
    return page


def alerts_area_editor(page: Page) -> Page:
    go(page, f"/my-custom-areas/{GENK_AREA_ID}/edit")
    return page


def alerts_templates(page: Page) -> Page:
    go(page, "/new-alert")
    return page


def alerts_form(page: Page) -> Page:
    go(page, f"/edit-alert/{EXAMPLE_ALERT_ID}")
    return page


def alerts_my_alerts(page: Page) -> Page:
    go(page, "/my-alerts")
    return page


def alerts_comments(page: Page) -> Locator:
    go(page, f"/?obs={OBSERVATION}")
    return page.locator(".comments-card")


def advanced_api_tokens(page: Page) -> Locator:
    go(page, "/api-tokens")
    return page.locator(".page-content--wide")


SIGNED_IN_SHOTS: dict[str, Callable[[Page], Page | Locator]] = {
    "alerts-profile.png": alerts_profile,
    "alerts-not-viewed.png": alerts_not_viewed,
    "alerts-area-editor.jpg": alerts_area_editor,
    "alerts-templates.png": alerts_templates,
    "alerts-form.png": alerts_form,
    "alerts-my-alerts.png": alerts_my_alerts,
    "alerts-comments.png": alerts_comments,
    "advanced-api-tokens.png": advanced_api_tokens,
}

PLACEHOLDERS = {
    "username": "jdoe",
    "firstName": "Jane",
    "lastName": "Doe",
    "email": "jane.doe@example.org",
}
# Replaces text on the page (not in the database) with the placeholders.
SWAP_TEXT_JS = """(pairs) => {
    const swap = (s) => pairs.reduce((acc, [from, to]) => acc.split(from).join(to), s);
    const walker = document.createTreeWalker(document.body, NodeFilter.SHOW_TEXT);
    while (walker.nextNode()) walker.currentNode.nodeValue = swap(walker.currentNode.nodeValue);
    document.querySelectorAll("input").forEach((i) => { i.value = swap(i.value); });
}"""


def as_regular_user(page: Page) -> None:
    page.add_style_tag(content='a[href*="/admin/"] { display: none !important; }')
    page.get_by_role("button", name="Publish as template").evaluate_all(
        "buttons => buttons.forEach((b) => { b.style.display = 'none'; })"
    )
    profile = page.request.get(f"{BASE_URL}/api/v2/profile/").json()
    pairs = [[profile[k], v] for k, v in PLACEHOLDERS.items() if profile[k]]
    page.evaluate(SWAP_TEXT_JS, pairs)


def login() -> None:
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=False)
        context = browser.new_context(locale="en-US")
        context.new_page().goto(f"{BASE_URL}/accounts/signin/")
        print("Sign in to the demo in the browser window that just opened.")
        deadline = time.monotonic() + LOGIN_TIMEOUT_S
        # The page shell reports the login state in its nav config.
        while '"isAuthenticated": true' not in context.request.get(BASE_URL).text():
            if time.monotonic() > deadline:
                sys.exit("Timed out waiting for sign-in.")
            time.sleep(2)
        AUTH_FILE.parent.mkdir(parents=True, exist_ok=True)
        context.storage_state(path=AUTH_FILE)
        AUTH_FILE.chmod(0o600)
        print(f"Signed in. Session saved to {AUTH_FILE}")
        browser.close()


def new_context(browser: Browser, session: Path | None = None) -> BrowserContext:
    return browser.new_context(
        viewport={"width": 1440, "height": 900},
        device_scale_factor=2,
        locale="en-US",
        storage_state=session,
    )


def main(only: list[str]) -> None:
    all_shots = SHOTS | SIGNED_IN_SHOTS
    unknown = set(only) - all_shots.keys()
    if unknown:
        sys.exit(f"Unknown shot(s): {', '.join(sorted(unknown))}")
    selected = [n for n in all_shots if not only or n in only]
    if any(n in SIGNED_IN_SHOTS for n in selected) and not AUTH_FILE.exists():
        sys.exit("Signed-in shots need a session: run with --login first.")

    with sync_playwright() as p:
        browser = p.chromium.launch()
        anonymous = new_context(browser)
        # Without a session file this is just another anonymous context, never
        # used: main() already refused to run signed-in shots.
        signed_in = new_context(browser, AUTH_FILE if AUTH_FILE.exists() else None)
        for i, name in enumerate(selected):
            if i:
                time.sleep(PAUSE_BETWEEN_SHOTS_S)
            is_signed_in = name in SIGNED_IN_SHOTS
            page = (signed_in if is_signed_in else anonymous).new_page()
            throttled: list[str] = []
            page.on(
                "response",
                lambda r: throttled.append(r.url) if r.status == 429 else None,
            )
            target = all_shots[name](page)
            if throttled:
                sys.exit(f"{name}: demo rate limit hit ({throttled[0]}), rerun later")
            if is_signed_in:
                as_regular_user(page)
            path = OUT_DIR / name
            target.screenshot(path=path, quality=85 if path.suffix == ".jpg" else None)
            page.close()
            print(f"wrote {name}")
        browser.close()


if __name__ == "__main__":
    if sys.argv[1:] == ["--login"]:
        login()
    else:
        main(sys.argv[1:])
