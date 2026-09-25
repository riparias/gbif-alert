"""Regenerate the user guide screenshots from the demo instance.

Run by hand, not in CI: the demo's data changes with every import, so every run
produces different images. Review the images before committing them.

    uv run python documentation/screenshots.py            # all screenshots
    uv run python documentation/screenshots.py explore-table.png   # just one
"""

import sys
import time
from collections.abc import Callable
from pathlib import Path

from playwright.sync_api import Locator, Page, sync_playwright

BASE_URL = "https://demo.gbif-alert.org"
OUT_DIR = Path(__file__).parent / "docs" / "assets" / "img"

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


def main(only: list[str]) -> None:
    unknown = set(only) - SHOTS.keys()
    if unknown:
        sys.exit(f"Unknown shot(s): {', '.join(sorted(unknown))}")

    with sync_playwright() as p:
        browser = p.chromium.launch()
        context = browser.new_context(
            viewport={"width": 1440, "height": 900},
            device_scale_factor=2,
            locale="en-US",
        )
        for i, name in enumerate(n for n in SHOTS if not only or n in only):
            if i:
                time.sleep(PAUSE_BETWEEN_SHOTS_S)
            page = context.new_page()
            throttled: list[str] = []
            page.on(
                "response",
                lambda r: throttled.append(r.url) if r.status == 429 else None,
            )
            target = SHOTS[name](page)
            if throttled:
                sys.exit(f"{name}: demo rate limit hit ({throttled[0]}), rerun later")
            path = OUT_DIR / name
            target.screenshot(path=path, quality=85 if path.suffix == ".jpg" else None)
            page.close()
            print(f"wrote {name}")
        browser.close()


if __name__ == "__main__":
    main(sys.argv[1:])
