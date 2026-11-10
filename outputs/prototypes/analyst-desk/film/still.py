"""One still in the film's style: the analyst typing the formula (default), or asking Claude ("chat").

Uses the film's own look and camera. The desk must be running on ERM_DESK_PORT (default 8766). Mode "chat" also needs Claude available.
    uv run --with playwright==1.56.0 --with imageio-ffmpeg python outputs/prototypes/analyst-desk/film/still.py out.jpg
"""

import sys
import tempfile
from pathlib import Path

from playwright.sync_api import sync_playwright

sys.path.insert(0, str(Path(__file__).parent))
import render

QUESTION = "How would I reconcile these companies against the lender filings?"


def main(out, mode="formula"):
    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page(
            viewport={"width": render.W, "height": render.H}, device_scale_factor=1
        )
        page.goto(render.URL)
        page.wait_for_function("document.querySelectorAll('#grid td').length > 100")
        page.add_style_tag(content=render.FILM_CSS)
        page.evaluate(render.FILM_JS)
        page.add_style_tag(content=render.GUIDE_CSS)
        page.evaluate(render.GUIDE_JS)
        page.evaluate("film.cursor(-100, -100)")
        film = render.Film(page, str(Path(tempfile.mkdtemp()) / "unused.mp4"))
        film.cursor_pos = (-200.0, -200.0)  # no pointer in a still
        if mode == "formula":
            page.click('td[data-r="0"][data-c="3"]')
            page.keyboard.type("=RECONCILE(A2:A6)")
            film.cam(film.app_point('td[data-r="2"][data-c="2"]'), 1.75, 0.1)
            film.beat(
                "The analyst calls the tool",
                "They type one formula beside their list. Tested code links each name to the filings.",
                render.FRONT,
                'td[data-r="0"][data-c="3"]',
            )
        else:
            page.click("#use-claude")
            page.fill("#ask-input", QUESTION)
            page.keyboard.press("Enter")
            page.wait_for_selector(".msg.bot .tools-used", timeout=180000)
            render.expect(page, "#chat", "used how_to_reconcile")
            if "couldn't be reached" in page.locator("#chat").inner_text():
                raise SystemExit(
                    "Claude didn't answer; not taking a still that implies it did."
                )
            page.evaluate("document.getElementById('chat').scrollTop = 0")
            film.cam(film.app_point(".msg.bot"), 1.5, 0.1)
            film.beat(
                "The analyst asks Claude",
                "Claude picks the tested tool. The steps and limits come from it, not from memory.",
                render.TOOLS,
                ".msg.bot .tools-used",
            )
        page.evaluate("film.place()")
        page.screenshot(path=out, type="jpeg", quality=92)
        film.ffmpeg.stdin.close()
        film.ffmpeg.wait()
        browser.close()


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2] if len(sys.argv) > 2 else "formula")
