#!/usr/bin/env python3
"""Deterministic mobile regression for late-loading web fonts.

Uses a localhost copy of the real home page and a deliberately delayed,
locally installed test font. No network, production, advertisements or secrets.
The fixture font is never committed to this repository.
"""
from __future__ import annotations

import functools
import re
import threading
import time
import unittest
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlsplit

from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parents[1]
FONT_CANDIDATES = (
    Path("/usr/share/fonts/truetype/dejavu/DejaVuSerif.ttf"),
    Path("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"),
    Path("/usr/share/fonts/truetype/liberation2/LiberationSerif-Regular.ttf"),
)
FONT_URL = "https://fonts.gstatic.com/ksa-cls-test.ttf"
WAIT_MS = 1200


class QuietHandler(SimpleHTTPRequestHandler):
    def log_message(self, *_args):
        pass


class MobileFontLayoutTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.font_path = next((p for p in FONT_CANDIDATES if p.is_file()), None)
        if cls.font_path is None:
            raise unittest.SkipTest("No fixture font available on this runner")
        handler = functools.partial(QuietHandler, directory=str(ROOT))
        cls.server = ThreadingHTTPServer(("127.0.0.1", 0), handler)
        cls.thread = threading.Thread(target=cls.server.serve_forever, daemon=True)
        cls.thread.start()
        cls.origin = f"http://127.0.0.1:{cls.server.server_port}"
        cls.pw = sync_playwright().start()
        cls.browser = cls.pw.chromium.launch(headless=True)

    @classmethod
    def tearDownClass(cls):
        cls.browser.close()
        cls.pw.stop()
        cls.server.shutdown()
        cls.server.server_close()
        cls.thread.join(timeout=5)

    def test_font_is_optional_to_prevent_late_swaps(self):
        markup = (ROOT / "index.html").read_text(encoding="utf-8")
        links = re.findall(r'<link\b[^>]*href="([^"]+)"[^>]*>', markup)
        font_links = [v for v in links if v.startswith("https://fonts.googleapis.com/css2?")]
        self.assertEqual(len(font_links), 1, font_links)
        self.assertEqual(parse_qs(urlsplit(font_links[0]).query).get("display"), ["optional"])

    def test_mobile_main_does_not_jump_when_font_finishes_late(self):
        for language in ("ar", "en"):
            with self.subTest(language=language):
                ctx = self.browser.new_context(
                    viewport={"width": 390, "height": 844},
                    is_mobile=True,
                    has_touch=True,
                    device_scale_factor=1,
                )
                font_fetches = []
                stylesheet_fetches = []

                def third_party(route):
                    if route.request.url.startswith(self.origin + "/"):
                        route.continue_()
                    else:
                        route.fulfill(status=200, body="", content_type="text/plain")

                def font_stylesheet(route):
                    # The display parameter must come from the ACTUAL page link.
                    mode = parse_qs(urlsplit(route.request.url).query).get("display", [""])[0]
                    stylesheet_fetches.append(mode)
                    if mode not in ("swap", "optional"):
                        return route.abort()
                    css = (
                        "@font-face { font-family: 'Cairo';"
                        f" src: url('{FONT_URL}') format('truetype');"
                        " font-weight: 400 900; font-style: normal;"
                        f" font-display: {mode}; }}"
                    )
                    route.fulfill(status=200, body=css, content_type="text/css")

                def delayed_font(route):
                    font_fetches.append(route.request.url)
                    time.sleep(WAIT_MS / 1000)
                    route.fulfill(status=200, body=self.font_path.read_bytes(),
                                  content_type="font/ttf")

                try:
                    ctx.route("**/*", third_party)
                    ctx.route("https://fonts.googleapis.com/**", font_stylesheet)
                    ctx.route("https://fonts.gstatic.com/**", delayed_font)
                    page = ctx.new_page()
                    page.add_init_script("""() => {
                      window.__fontTestShifts = [];
                      new PerformanceObserver(list => {
                        for (const x of list.getEntries()) {
                          if (!x.hadRecentInput) window.__fontTestShifts.push(x.value);
                        }
                      }).observe({type:'layout-shift', buffered:true});
                    }""".replace("() => {", "{", 1))
                    page.goto(self.origin + f"/?lang={language}", wait_until="domcontentloaded")
                    page.locator("#eos-tool").wait_for(timeout=10000)
                    before = page.locator("main").bounding_box()
                    page.wait_for_timeout(WAIT_MS + 350)
                    after = page.locator("main").bounding_box()
                    cls = page.evaluate("() => (window.__fontTestShifts || []).reduce((a,b)=>a+b,0)")
                    print(f"[FONT] lang={language} stylesheet={stylesheet_fetches} "
                          f"font_requests={len(font_fetches)} top_before={before['y']:.2f} "
                          f"top_after={after['y']:.2f} CLS={cls:.5f}", flush=True)
                    self.assertEqual(stylesheet_fetches, ["optional"])
                    self.assertLessEqual(abs(after["y"] - before["y"]), 2.0)
                    self.assertLess(cls, 0.03)
                finally:
                    ctx.close()


if __name__ == "__main__":
    unittest.main(verbosity=2)
