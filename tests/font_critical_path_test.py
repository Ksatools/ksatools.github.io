#!/usr/bin/env python3
"""Protect the CLS-safe critical path from deferred font CSS regressions.

Locally serves the production markup with a simulated slow Google Fonts CSS
response. Compares the stable blocking link to an injected deferred version
representing the published PR #52 regression. No external requests or edits.
The synthetic fixture does not replace production PageSpeed measurement.
"""
from __future__ import annotations

import functools
import re
import threading
import time
import unittest
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlsplit

from playwright.sync_api import sync_playwright


ROOT = Path(__file__).resolve().parents[1]
SLOW_CSS = 1.8
FONT_FILE = Path("/usr/share/fonts/truetype/dejavu/DejaVuSerif.ttf")
FONT_PATTERN = r"https://fonts\.googleapis\.com/css2\?[^\"<]+"
STYLESHEET_PATTERN = r'<link\b[^>]*href="https://fonts\.googleapis\.com/css2\?[^"]+"[^>]*>'


class FixtureHandler(SimpleHTTPRequestHandler):
    def log_message(self, *_args):
        pass

    def do_GET(self):
        path = urlsplit(self.path).path
        if path in ("/", "/index.html") and "font-test" in self.path:
            markup = (ROOT / "index.html").read_text(encoding="utf-8")
            mode = "blocking" if "font-test=blocking" in self.path else "nonblocking"
            if mode == "nonblocking":
                # Regression control: PR #52 deferred the font CSS and
                # allowed it to change font metrics after first paint.
                old = ' rel="stylesheet" />'
                deferred = ' rel="stylesheet" media="print" onload="this.media=\'all\'" />'
                if markup.count(old) != 1:
                    raise AssertionError("Expected exactly one font stylesheet")
                markup = markup.replace(old, deferred, 1)
            markup, replaced = re.subn(FONT_PATTERN, "/__slow_font_css", markup)
            if replaced != 1:
                raise AssertionError(f"Expected one font stylesheet, found {replaced}")
            body = markup.encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
        elif path == "/__slow_font_css":
            time.sleep(SLOW_CSS)
            css = (
                '@font-face{font-family:"Cairo";'
                'src:url("/__fixture_font.ttf") format("truetype");'
                'font-weight:400 900;font-display:optional;}'
            ).encode()
            self.send_response(200)
            self.send_header("Content-Type", "text/css")
            self.send_header("Content-Length", str(len(css)))
            self.end_headers()
            self.wfile.write(css)
        elif path == "/__fixture_font.ttf":
            body = FONT_FILE.read_bytes()
            self.send_response(200)
            self.send_header("Content-Type", "font/ttf")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
        else:
            super().do_GET()


class FontCriticalPathTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if not FONT_FILE.is_file():
            raise RuntimeError(f"Runner missing deterministic font fixture: {FONT_FILE}")
        cls.http = ThreadingHTTPServer(
            ("127.0.0.1", 0),
            functools.partial(FixtureHandler, directory=str(ROOT)),
        )
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

    def create_context(self):
        ctx = self.browser.new_context(
            viewport={"width": 390, "height": 844},
            is_mobile=True,
            has_touch=True,
            device_scale_factor=1,
        )

        def block_external(route):
            if route.request.url.startswith(self.origin + "/"):
                route.continue_()
            else:
                route.fulfill(status=200, body="", content_type="text/plain")

        ctx.route("**/*", block_external)
        return ctx

    def test_stylesheet_is_blocking_with_optional_font_display(self):
        html = (ROOT / "index.html").read_text(encoding="utf-8")
        tags = re.findall(STYLESHEET_PATTERN, html)
        self.assertEqual(len(tags), 1, tags)
        self.assertIn("display=optional", tags[0])
        self.assertIn('rel="stylesheet"', tags[0])
        self.assertNotIn('media="print"', tags[0])
        self.assertNotIn("onload=", tags[0])
        self.assertNotIn("<noscript><link href=\"https://fonts.googleapis.com", html)

    def navigate(self, mode, language):
        ctx = self.create_context()
        page = ctx.new_page()
        page.add_init_script("""{
          window.__fontCriticalShifts = [];
          new PerformanceObserver(entries => {
            for (const entry of entries.getEntries()) {
              if (!entry.hadRecentInput) window.__fontCriticalShifts.push(entry.value);
            }
          }).observe({type: 'layout-shift', buffered: true});
        }""")
        start = time.perf_counter()
        page.goto(
            self.origin + f"/?font-test={mode}&lang={language}",
            wait_until="domcontentloaded",
            timeout=15000,
        )
        dcl = (time.perf_counter() - start) * 1000
        page.locator("#eos-tool").wait_for(timeout=10000)
        before = page.locator("main").bounding_box()["y"]
        # Leave enough time for the slow CSS and fixture font to finish.
        page.wait_for_timeout(int(SLOW_CSS * 1000 + 350))
        after = page.locator("main").bounding_box()["y"]
        cls = page.evaluate(
            "() => (window.__fontCriticalShifts || []).reduce((a,b)=>a+b,0)"
        )
        media = page.locator('link[href="/__slow_font_css"]').first.get_attribute("media")
        print(f"[FONT-PATH] {mode} lang={language} DCL={dcl:.0f}ms "
              f"main_shift={after-before:.2f}px CLS={cls:.5f} media={media}",
              flush=True)
        ctx.close()
        return dcl, cls, abs(after - before), media

    def test_delayed_stylesheet_finishes_before_main_is_visible(self):
        # Reproduce the network dependency that PR #52 moved after the
        # first paint. Stable CSS deliberately delays DCL, so any font
        # metrics are known by the time the page is first displayed.
        for lang in ("ar", "en"):
            with self.subTest(language=lang):
                blocking_dcl, blocking_cls, blocking_jump, media = self.navigate(
                    "blocking", lang
                )
                deferred_dcl, _, _, deferred_media = self.navigate(
                    "nonblocking", lang
                )
                self.assertGreater(
                    blocking_dcl - deferred_dcl, 850,
                    f"Blocking {blocking_dcl:.0f}ms, deferred {deferred_dcl:.0f}ms",
                )
                self.assertIsNone(media)
                self.assertEqual(deferred_media, "all")
                self.assertLessEqual(blocking_jump, 2.0)
                self.assertLess(blocking_cls, 0.03)


if __name__ == "__main__":
    unittest.main(verbosity=2)
