#!/usr/bin/env python3
"""Regression coverage for real, self-hosted variable WOFF2 fonts.

Loads the page offline with intentionally delayed font responses. Both Arabic
and English mobile layouts must remain stable, and downloaded fonts must be
real WOFF2 files covered by the bundled Open Font Licenses.
"""
from __future__ import annotations

import functools
import re
import threading
import time
import unittest
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parents[1]
FONT_DIR = ROOT / "assets" / "fonts"
EXPECTED_FONTS = {
    "cairo-arabic-wght-normal.woff2",
    "cairo-latin-wght-normal.woff2",
    "cairo-latin-ext-wght-normal.woff2",
    "inter-latin-wght-normal.woff2",
}
WAIT_MS = 1200


class QuietHandler(SimpleHTTPRequestHandler):
    def log_message(self, *_args):
        pass


class LocalFontLayoutTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        handler = functools.partial(QuietHandler, directory=str(ROOT))
        cls.http = ThreadingHTTPServer(("127.0.0.1", 0), handler)
        cls.thread = threading.Thread(target=cls.http.serve_forever, daemon=True)
        cls.thread.start()
        cls.origin = f"http://127.0.0.1:{cls.http.server_port}"
        cls.pw = sync_playwright().start()
        cls.browser = cls.pw.chromium.launch(headless=True)

    @classmethod
    def tearDownClass(cls):
        cls.browser.close()
        cls.pw.stop()
        cls.http.shutdown()
        cls.http.server_close()
        cls.thread.join(timeout=5)

    def test_inlined_local_font_faces_are_licensed_and_valid(self):
        markup = (ROOT / "index.html").read_text(encoding="utf-8")
        self.assertNotIn("fonts.googleapis.com", markup)
        self.assertNotIn("fonts.gstatic.com", markup)
        block = re.search(
            r'<style id="local-web-fonts">([\s\S]*?)</style>', markup
        )
        self.assertIsNotNone(block, "Inline font definitions missing")
        css = block.group(1)
        self.assertEqual(css.count("@font-face"), 4)
        self.assertEqual(css.count("font-display: optional"), 4)
        self.assertIn("font-family: 'Cairo'", css)
        self.assertIn("font-family: 'Inter'", css)
        paths = set(re.findall(r"/assets/fonts/([\w-]+\.woff2)", css))
        self.assertEqual(paths, EXPECTED_FONTS)
        for name in paths:
            with self.subTest(font=name):
                data = (FONT_DIR / name).read_bytes()
                self.assertEqual(data[:4], b"wOF2")
                self.assertGreater(len(data), 8000)
                self.assertLess(len(data), 100000)
        for family in ("CAIRO", "INTER"):
            license_text = (FONT_DIR / f"LICENSE-{family}.txt").read_text(
                encoding="utf-8"
            )
            self.assertIn("SIL OPEN FONT LICENSE Version 1.1", license_text)

    def test_delayed_real_fonts_do_not_shift_mobile_layout(self):
        for width, language in ((375, "ar"), (390, "ar"), (390, "en")):
            with self.subTest(width=width, language=language):
                ctx = self.browser.new_context(
                    viewport={"width": width, "height": 844},
                    is_mobile=True,
                    has_touch=True,
                    device_scale_factor=1,
                )
                requests = []
                decode_errors = []

                def isolate(route):
                    if route.request.url.startswith(self.origin + "/"):
                        if "/assets/fonts/" in route.request.url:
                            requests.append(route.request.url)
                            time.sleep(WAIT_MS / 1000)
                        return route.continue_()
                    return route.fulfill(
                        status=200, body="", content_type="text/plain"
                    )

                try:
                    ctx.route("**/*", isolate)
                    page = ctx.new_page()
                    page.on("console", lambda msg: decode_errors.append(msg.text)
                            if msg.type == "error" and "font" in msg.text.lower()
                            else None)
                    page.add_init_script("""{
                      window.__fontShifts = [];
                      new PerformanceObserver(list => {
                        for (const e of list.getEntries()) {
                          if (!e.hadRecentInput) window.__fontShifts.push(e.value);
                        }
                      }).observe({type: 'layout-shift', buffered: true});
                    }""")
                    page.goto(
                        self.origin + f"/?lang={language}",
                        wait_until="domcontentloaded", timeout=20000,
                    )
                    page.locator("#eos-tool").wait_for(timeout=10000)
                    before = page.locator("main").bounding_box()
                    page.wait_for_timeout(WAIT_MS + 450)
                    after = page.locator("main").bounding_box()
                    cls = page.evaluate(
                        "() => (window.__fontShifts || []).reduce((a,b)=>a+b,0)"
                    )
                    print(
                        f"[LOCAL-WOFF2] width={width} lang={language} "
                        f"requests={len(requests)} main_delta={after['y']-before['y']:.2f} "
                        f"CLS={cls:.5f} font_errors={len(decode_errors)}",
                        flush=True,
                    )
                    self.assertTrue(requests, "No actual self-hosted font requested")
                    self.assertEqual(decode_errors, [])
                    self.assertLessEqual(abs(after["y"] - before["y"]), 2.0)
                    self.assertLess(cls, 0.10)
                finally:
                    ctx.close()


if __name__ == "__main__":
    unittest.main(verbosity=2)
