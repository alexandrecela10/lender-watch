"""Films the real Analyst Desk, frame by frame, into an MP4.

The script drives the running app. Everything inside the window is the app's real output. This file only adds the
camera, the cursor, the captions and the title cards. Waiting time isn't filmed, so waits are shorter than in real use.

Run, with the desk up on ERM_DESK_PORT (default 8766):
    uv run --with playwright==1.56.0 --with imageio-ffmpeg python outputs/prototypes/analyst-desk/film/render.py out.mp4
"""

import math
import os
import subprocess
import sys

import imageio_ffmpeg
from playwright.sync_api import sync_playwright

FPS = 30
W, H = 1920, 1080
STAGE_W, STAGE_H = 1680, 868
STAGE_X, STAGE_Y = (W - STAGE_W) / 2, 34
URL = f"http://127.0.0.1:{os.environ.get('ERM_DESK_PORT', '8766')}"

FILM_CSS = (
    """
html, body { background: #0f1f1a !important; overflow: hidden !important; }
#film-stage { position: fixed; left: @X@px; top: @Y@px; width: @W@px; height: @H@px; overflow: hidden; border-radius: 14px;
  background: #fff; box-shadow: 0 30px 80px rgba(0,0,0,.45), 0 0 0 1px rgba(255,255,255,.08); }
#app { position: absolute; left: 0; top: 0; width: @W@px !important; height: @H@px !important; transform-origin: 0 0; }
#film-cursor { position: fixed; left: 0; top: 0; width: 26px; height: 26px; z-index: 50; pointer-events: none; filter: drop-shadow(0 2px 3px rgba(0,0,0,.4)); }
#film-ring { position: fixed; left: 0; top: 0; width: 40px; height: 40px; margin: -20px 0 0 -20px; border-radius: 50%; border: 3px solid #17594a; z-index: 49; opacity: 0; pointer-events: none; }
#film-caption { position: fixed; left: 120px; right: 120px; top: 918px; color: #f3f1ea; font-family: -apple-system, "Helvetica Neue", sans-serif; }
#film-eyebrow { font-size: 19px; letter-spacing: .09em; text-transform: uppercase; color: #8fd0ba; font-weight: 600; margin-bottom: 8px; }
#film-text { font-size: 37px; line-height: 1.22; font-weight: 500; letter-spacing: -.01em; max-width: 1420px; }
#film-steps { position: fixed; right: 120px; top: 921px; display: flex; gap: 8px; }
#film-steps i { display: block; width: 44px; height: 6px; border-radius: 3px; background: rgba(255,255,255,.2); }
#film-steps i.on { background: #8fd0ba; }
#film-card { position: fixed; inset: 0; z-index: 80; background: #0f1f1a; color: #f3f1ea; display: flex; flex-direction: column; justify-content: center; padding: 0 180px; font-family: -apple-system, "Helvetica Neue", sans-serif; opacity: 0; pointer-events: none; }
#film-card h1 { font-size: 92px; line-height: 1.05; margin: 0 0 30px; font-weight: 600; letter-spacing: -.025em; }
#film-card p { font-size: 39px; line-height: 1.3; margin: 0; max-width: 1380px; color: #c9d6cf; }
#film-card .tag { font-size: 21px; letter-spacing: .09em; text-transform: uppercase; color: #8fd0ba; font-weight: 600; margin-bottom: 26px; }
.film-layers { display: grid; gap: 18px; width: 1400px; }
.film-layer { position: relative; border: 2px solid rgba(255,255,255,.22); border-radius: 14px; padding: 24px 32px; display: grid; grid-template-columns: 370px 1fr; align-items: center; column-gap: 26px; }
.film-layer.base { border-color: #8fd0ba; background: rgba(143,208,186,.13); }
.film-layer b { font-size: 33px; font-weight: 600; letter-spacing: -.01em; }
.film-layer span { font-size: 29px; color: #d4ded8; line-height: 1.28; }
.film-foot { font-size: 25px !important; margin-top: 34px !important; color: #a5b5ad !important; max-width: 1400px; line-height: 1.4 !important; }
""".replace("@X@", str(int(STAGE_X)))
    .replace("@Y@", str(STAGE_Y))
    .replace("@W@", str(STAGE_W))
    .replace("@H@", str(STAGE_H))
)

FILM_JS = """
(() => {
  const stage = document.createElement('div'); stage.id = 'film-stage';
  const app = document.getElementById('app'); app.parentNode.insertBefore(stage, app); stage.appendChild(app);
  document.body.insertAdjacentHTML('beforeend', `
    <div id="film-caption"><div id="film-eyebrow"></div><div id="film-text"></div></div>
    <div id="film-steps"><i></i><i></i><i></i></div>
    <div id="film-ring"></div>
    <svg id="film-cursor" viewBox="0 0 24 24"><path d="M4 2l15 12-7 1 4 8-3 1-4-8-5 5z" fill="#111" stroke="#fff" stroke-width="1.6"/></svg>
    <div id="film-card"></div>`);
  window.film = {
    cam(x, y, s) { app.style.transform = `translate(${x}px, ${y}px) scale(${s})`; },
    cursor(x, y) { const c = document.getElementById('film-cursor'); c.style.transform = `translate(${x}px, ${y}px)`; },
    ring(x, y, t) { const r = document.getElementById('film-ring'); r.style.transform = `translate(${x}px, ${y}px) scale(${0.5 + t * 1.4})`; r.style.opacity = t >= 1 ? 0 : 1 - t; },
    caption(eyebrow, text) { document.getElementById('film-eyebrow').textContent = eyebrow; document.getElementById('film-text').textContent = text; },
    capOpacity(o) { document.getElementById('film-caption').style.opacity = o; },
    steps(n) { [...document.querySelectorAll('#film-steps i')].forEach((d, i) => d.classList.toggle('on', i === n)); document.getElementById('film-steps').style.opacity = n < 0 ? 0 : 1; },
    card(html) { document.getElementById('film-card').innerHTML = html; },
    cardOpacity(o) { document.getElementById('film-card').style.opacity = o; },
  };
})();
"""


def ease(t):
    return 0.5 - 0.5 * math.cos(math.pi * max(0, min(1, t)))


class Film:
    def __init__(self, page, out):
        self.page = page
        self.cam_state = (0.0, 0.0, 1.0)
        self.cursor_pos = (W * 0.5, H * 0.55)
        self.last = None
        self.count = 0
        exe = imageio_ffmpeg.get_ffmpeg_exe()
        self.ffmpeg = subprocess.Popen(
            [
                exe,
                "-y",
                "-loglevel",
                "error",
                "-f",
                "image2pipe",
                "-framerate",
                str(FPS),
                "-c:v",
                "mjpeg",
                "-i",
                "-",
                "-c:v",
                "libx264",
                "-preset",
                "medium",
                "-crf",
                "20",
                "-pix_fmt",
                "yuv420p",
                "-movflags",
                "+faststart",
                out,
            ],
            stdin=subprocess.PIPE,
        )

    def js(self, code, *args):
        return self.page.evaluate(code, *args)

    def frame(self):
        self.last = self.page.screenshot(type="jpeg", quality=93)
        self.ffmpeg.stdin.write(self.last)
        self.count += 1

    def hold(self, seconds):
        if self.last is None:
            self.frame()
        for _ in range(int(seconds * FPS)):
            self.ffmpeg.stdin.write(self.last)
            self.count += 1

    def animate(self, seconds, step):
        n = max(1, int(seconds * FPS))
        for i in range(1, n + 1):
            step(ease(i / n))
            self.frame()

    # --- camera ---------------------------------------------------------------------------------
    def cam(self, focus=None, scale=1.0, seconds=0.7):
        """Move the camera so `focus`, a point in the app window, is centred at this zoom. None means the whole window."""
        if focus is None:
            target = (0.0, 0.0, 1.0)
        else:
            fx, fy = focus
            x = min(0.0, max(STAGE_W - STAGE_W * scale, STAGE_W / 2 - fx * scale))
            y = min(0.0, max(STAGE_H - STAGE_H * scale, STAGE_H / 2 - fy * scale))
            target = (x, y, scale)
        x0, y0, s0 = self.cam_state
        x1, y1, s1 = target
        # The cursor stays on the same spot of the app while the camera moves.
        cx, cy = self.cursor_pos
        ax, ay = (cx - STAGE_X - x0) / s0, (cy - STAGE_Y - y0) / s0

        def step(t):
            x, y, s = x0 + (x1 - x0) * t, y0 + (y1 - y0) * t, s0 + (s1 - s0) * t
            self.cursor_pos = (ax * s + x + STAGE_X, ay * s + y + STAGE_Y)
            self.js(
                "a => { film.cam(a[0], a[1], a[2]); film.cursor(a[3], a[4]); }",
                [x, y, s, *self.cursor_pos],
            )

        self.animate(seconds, step)
        self.cam_state = target

    def app_point(self, selector):
        """Centre of an element, in unzoomed app-window coordinates."""
        x0, y0, s = self.cam_state
        box = self.page.locator(selector).first.bounding_box()
        return (
            (box["x"] + box["width"] / 2 - STAGE_X - x0) / s,
            (box["y"] + box["height"] / 2 - STAGE_Y - y0) / s,
        )

    def focus(self, selector, scale, seconds=0.7):
        self.cam(self.app_point(selector), scale, seconds)

    # --- cursor ---------------------------------------------------------------------------------
    def move(self, selector, seconds=0.5):
        box = self.page.locator(selector).first.bounding_box()
        x1, y1 = box["x"] + box["width"] / 2, box["y"] + box["height"] / 2
        x0, y0 = self.cursor_pos
        self.animate(
            seconds,
            lambda t: self.js(
                "a => film.cursor(a[0], a[1])", [x0 + (x1 - x0) * t, y0 + (y1 - y0) * t]
            ),
        )
        self.cursor_pos = (x1, y1)

    def click(self, selector, seconds=0.5):
        self.move(selector, seconds)
        self.page.locator(selector).first.click()
        x, y = self.cursor_pos
        self.animate(
            0.22, lambda t: self.js("a => film.ring(a[0], a[1], a[2])", [x, y, t])
        )

    def type(self, text, per_frame=1):
        for i, ch in enumerate(text):
            self.page.keyboard.type(ch)
            if i % per_frame == 0:
                self.frame()
        self.frame()

    # --- words ---------------------------------------------------------------------------------
    def caption(self, eyebrow, text, step=None):
        self.animate(0.14, lambda t: self.js("o => film.capOpacity(o)", 1 - t))
        self.js("a => film.caption(a[0], a[1])", [eyebrow, text])
        if step is not None:
            self.js("n => film.steps(n)", step)
        self.animate(0.2, lambda t: self.js("o => film.capOpacity(o)", t))

    def card(self, html, seconds):
        self.js("h => film.card(h)", html)
        self.animate(0.3, lambda t: self.js("o => film.cardOpacity(o)", t))
        self.hold(seconds)

    def card_out(self):
        self.animate(0.3, lambda t: self.js("o => film.cardOpacity(o)", 1 - t))


ONE = "The analyst knows the tool"
TWO = "The analyst knows the problem"
THREE = "The analyst doesn't know it exists"


def start_over(f):
    f.page.click("#reset-btn")
    f.page.wait_for_function(
        "document.querySelectorAll('#grid td').length > 100 && document.getElementById('chat').children.length === 0"
    )


def expect(page, selector, text):
    found = page.locator(selector).first.inner_text()
    if text not in found:
        raise SystemExit(
            f"Film stopped: expected {text!r} in {selector}, found {found[:300]!r}"
        )


def scene_invoke(f):
    f.caption(ONE, "They call it from the sheet, like any Excel function.", 0)
    f.click('td[data-r="0"][data-c="3"]')
    f.focus('td[data-r="2"][data-c="4"]', 1.35)
    f.type("=RECONCILE(A2:A6)")
    f.hold(0.4)
    f.page.keyboard.press("Enter")
    f.page.wait_for_selector("td.flagged", timeout=60000)
    f.page.wait_for_function("document.querySelector('.confirm-card')")
    f.frame()
    f.hold(0.5)
    expect(f.page, 'td[data-r="1"][data-c="5"]', "78.0%")
    expect(f.page, 'td[data-r="4"][data-c="4"]', "LogRhythm")
    f.focus('td[data-r="1"][data-c="5"]', 1.75)
    f.caption(
        ONE,
        "KnowBe4 is flagged: lenders value its debt at 78% of what they're owed, down 11 points in a quarter.",
    )
    f.hold(2.4)
    f.focus('td[data-r="4"][data-c="4"]', 1.75, 0.5)
    f.caption(
        ONE,
        "Exabeam has no loans under its own name. Lenders list it as LogRhythm, which no lookup would find.",
    )
    f.hold(2.6)
    f.cam(None, 1.0, 0.5)


def scene_ask(f):
    start_over(f)
    f.frame()
    f.caption(TWO, "They ask Claude in plain words, from the same workbook.", 1)
    f.click("#use-claude")
    f.focus(".panel", 2.05)
    f.click("#ask-input", 0.4)
    f.type(
        "How would I reconcile these companies against the lender filings?", per_frame=2
    )
    f.hold(0.3)
    f.page.keyboard.press("Enter")
    f.frame()
    f.hold(0.5)
    f.page.wait_for_selector(".msg.bot .tools-used", timeout=180000)
    f.page.evaluate(
        "document.querySelector('.msg.bot .tools-used').scrollIntoView({block: 'start'})"
    )
    f.frame()
    expect(f.page, "#chat", "used how_to_reconcile")
    f.caption(
        TWO,
        "Claude picks the tool and explains it. The steps and limits come from the tool, not from memory.",
    )
    f.hold(3.6)
    f.cam(None, 1.0, 0.5)
    f.click("#use-claude", 0.3)


def scene_notice(f):
    start_over(f)
    f.frame()
    f.caption(THREE, "They write their usual lookup between two tabs.", 2)
    f.click('td[data-r="1"][data-c="3"]')
    f.focus('td[data-r="3"][data-c="3"]', 1.3)
    f.type("=XLOOKUP(A2:A6,'Lender tape'!B:B,'Lender tape'!D:D)", per_frame=2)
    f.hold(0.3)
    f.page.keyboard.press("Enter")
    f.page.wait_for_selector(".card [data-act=link]")
    f.frame()
    expect(f.page, 'td[data-r="1"][data-c="3"]', "#N/A")
    f.caption(
        THREE, "All five come back #N/A. The tabs write the same companies differently."
    )
    f.hold(1.8)
    f.focus(".card", 1.75)
    f.caption(
        THREE, "The assistant spots why, and offers the fix, without being asked."
    )
    f.hold(3.2)
    f.click(".card [data-act=link]")
    f.page.wait_for_selector("td.flagged", timeout=60000)
    f.page.wait_for_function("document.querySelector('.confirm-card')")
    f.page.evaluate("document.getElementById('chat').scrollTop = 0")
    f.frame()
    f.cam(None, 1.0, 0.6)
    f.caption(
        "One result, whichever way in",
        "Two companies flagged. Three matches wait for a person.",
        -1,
    )
    f.hold(2.2)


def scene_trust(f):
    eyebrow = "Every number has a source"
    f.click('td[data-r="1"][data-c="3"]')
    f.page.wait_for_selector("#source .loan")
    f.frame()
    f.focus("#source", 1.65)
    expect(f.page, "#source", "Lenders call it KnowBe4 Inc.")
    f.caption(
        eyebrow,
        "Click a result and see the lender, the filing row and a link to the SEC filing.",
    )
    f.hold(3)
    f.page.click("#source .close")
    f.frame()
    f.page.evaluate(
        "document.querySelector('.confirm-card').scrollIntoView({block: 'center'})"
    )
    f.frame()
    expect(f.page, ".confirm-card .q", "Apex Bidco")
    f.focus(".confirm-card", 1.8, 0.5)
    f.caption(
        "A person decides what's unclear",
        "Is Apex Bidco your Apex Group? The filing doesn't say, so the analyst decides.",
    )
    f.hold(2.8)
    f.click('.confirm-card button[data-same="0"]')
    f.page.wait_for_function(
        "document.getElementById('chat').innerText.includes('Saved.')"
    )
    f.page.evaluate(
        "[...document.querySelectorAll('.msg.bot .note')].pop().scrollIntoView({block: 'center'})"
    )
    f.frame()
    f.caption(
        "A person decides what's unclear",
        "The answer is saved and overrides the AI. They won't be asked again.",
    )
    f.hold(2.4)
    f.cam(None, 1.0, 0.5)
    f.move("#export-btn", 0.5)
    f.focus("#export-btn", 1.6, 0.5)
    f.caption(
        "The Excel stays the record",
        "They download a real workbook: their columns, the lender columns, one row per loan with its filing.",
    )
    f.hold(2.8)


LAYERS = """
<div class="tag">How it fits together</div>
<div class="film-layers">
  <div class="film-layer"><b>Where people work</b><span>A formula, a question, or the assistant noticing a failed lookup</span></div>
  <div class="film-layer"><b>Tested tools</b><span>One connector. Code links the names and does the maths. Claude only picks the tool</span></div>
  <div class="film-layer base"><b>Organised data</b><span>One company across every name lenders use, with a filing behind each value</span></div>
</div>
<p class="film-foot">Real app, real SEC filings, 5 sample companies. Waits shortened. No investor has tested it yet. Values are lenders' own estimates, and banks don't publish loans.</p>
"""


def main(out):
    with sync_playwright() as p:
        browser = p.chromium.launch()
        context = browser.new_context(
            viewport={"width": W, "height": H},
            device_scale_factor=1,
            accept_downloads=True,
        )
        page = context.new_page()
        page.goto(URL)
        page.wait_for_function("document.querySelectorAll('#grid td').length > 100")
        page.add_style_tag(content=FILM_CSS)
        page.evaluate(FILM_JS)
        page.evaluate("film.steps(-1)")
        f = Film(page, out)
        f.js("a => film.cursor(a[0], a[1])", list(f.cursor_pos))

        f.card(
            '<div class="tag">Lender Watch, inside the workbook</div><h1>One company.<br>Many names.</h1>'
            "<p>A lookup needs identical text, and lenders write company names their own way. Three ways to reach the fix, without leaving the workbook.</p>",
            3.4,
        )
        f.card_out()
        scene_invoke(f)
        scene_ask(f)
        scene_notice(f)
        scene_trust(f)
        f.card(LAYERS, 5.2)

        f.ffmpeg.stdin.close()
        f.ffmpeg.wait()
        print(f"{f.count} frames, {f.count / FPS:.1f} seconds")
        browser.close()


if __name__ == "__main__":
    main(sys.argv[1])
