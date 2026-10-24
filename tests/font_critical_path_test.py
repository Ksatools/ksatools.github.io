#!/usr/bin/env python3
"""Compare critical-path timing with blocking and non-blocking font CSS.

Serves the current index.html from localhost. The only edited response is
the font URL, replaced with a deterministic slow local fixture. No requests
leave the browser test, and the actual site files are not modified.
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
            if mode == "blocking":
                # A/B control: same current markup but use the original
                # render-blocking stylesheet attributes from the prior release.
                markup = markup.replace(
                    ' rel="stylesheet" media="print" onload="this.media=\'all\'"',
                    ' rel="stylesheet"',
                    1,
                )
            markup, replaced = re.subn(FONT_PATTERN, "/__slow_font_css", markup)
            if replaced != 2:
                raise AssertionError(f"Expected active + noscript fonts, found {replaced}")
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

    def test_stylesheet_is_nonblocking_with_noscript_fallback(self):
        html = (ROOT / "index.html").read_text(encoding="utf-8")
        active = re.findall(STYLESHEET_PATTERN, html)
        self.assertEqual(len(active), 2)
        self.assertIn('display=optional', active[0])
        self.assertIn('media="print"', active[0])
        self.assertIn('onload="this.media=\'all\'"', active[0])
        self.assertIn('<noscript>', html)
        self.assertIn(active[1], html.split("<noscript>", 1)[1])
        self.assertNotIn("onload=", active[1])

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

    def test_slow_css_is_removed_from_first_paint_path_without_cls_regression(self):
        before, _, _, _ = self.navigate("blocking", "ar")
        arabic, arabic_cls, arabic_jump, media_ar = self.navigate("nonblocking", "ar")
        english, english_cls, english_jump, media_en = self.navigate("nonblocking", "en")
        self.assertGreater(before - arabic, 850,
                           f"Blocking {before:.0f}ms, nonblocking {arabic:.0f}ms")
        self.assertLess(english, before - 850)
        self.assertEqual((media_ar, media_en), ("all", "all"))
        for language, cls, jump in (
            ("ar", arabic_cls, arabic_jump), ("en", english_cls, english_jump)
        ):
            with self.subTest(language=language):
                self.assertLessEqual(jump, 2.0)
                self.assertLess(cls, 0.03)


if __name__ == "__main__":
    unittest.main(verbosity=2)
