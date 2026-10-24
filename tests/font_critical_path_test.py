#!/usr/bin/env python3
"""Synthetic critical-path comparison of inline WOFF2 faces vs remote font CSS.

Compares the actual current page against a reconstructed former blocking
Google Fonts stylesheet (served with controlled 750 ms latency). This measures
DOM readiness, not production Lighthouse LCP. No external network is used.
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
REMOTE_CSS = "https://fonts.googleapis.com/css2?family=Cairo&display=optional"
DELAY_MS = 750


class FixtureHandler(SimpleHTTPRequestHandler):
    def log_message(self, *_args):
        pass

    def do_GET(self):
        parsed = urlsplit(self.path)
        mode = parse_qs(parsed.query).get("font-test", [""])[0]
        if parsed.path in ("/", "/index.html") and mode in ("remote", "local"):
            markup = (ROOT / "index.html").read_text(encoding="utf-8")
            if mode == "remote":
                # A/B control: previous blocking Google CSS fetch, not a
                # candidate production modification.
                markup, count = re.subn(
                    r'<style id="local-web-fonts">[\s\S]*?</style>',
                    f'<link rel="stylesheet" href="{REMOTE_CSS}" />',
                    markup,
                )
                if count != 1:
                    raise AssertionError("Missing current inline web fonts")
            body = markup.encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
        else:
            super().do_GET()


class LocalFontCriticalPathTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        handler = functools.partial(FixtureHandler, directory=str(ROOT))
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

    def test_inline_font_faces_leave_no_external_stylesheet_dependency(self):
        html = (ROOT / "index.html").read_text(encoding="utf-8")
        self.assertEqual(html.count('<style id="local-web-fonts">'), 1)
        self.assertNotIn('fonts.googleapis.com', html)
        self.assertNotIn('fonts.gstatic.com', html)
        self.assertNotIn('media="print" onload=', html)
        self.assertIn('font-display: optional', html)

    def navigate(self, mode, language):
        ctx = self.browser.new_context(
            viewport={"width": 390, "height": 844},
            is_mobile=True, has_touch=True, device_scale_factor=1,
        )
        remote_requests = []

        def isolate(route):
            if route.request.url.startswith(self.origin + "/"):
                return route.continue_()
            if route.request.url.startswith("https://fonts.googleapis.com/"):
                remote_requests.append(route.request.url)
                time.sleep(DELAY_MS / 1000)
                return route.fulfill(
                    status=200,
                    body="/* simulated 750 ms remote stylesheet */",
                    content_type="text/css",
                )
            return route.fulfill(status=200, body="", content_type="text/plain")

        try:
            ctx.route("**/*", isolate)
            page = ctx.new_page()
            page.add_init_script("""{
              window.__fontPathShifts = [];
              new PerformanceObserver(list => {
                for (const item of list.getEntries()) {
                  if (!item.hadRecentInput) window.__fontPathShifts.push(item.value);
                }
              }).observe({type: 'layout-shift', buffered: true});
            }""")
            start = time.perf_counter()
            page.goto(
                self.origin + f"/?font-test={mode}&lang={language}",
                wait_until="domcontentloaded",
                timeout=20000,
            )
            dcl = (time.perf_counter() - start) * 1000
            page.locator("#eos-tool").wait_for(timeout=10000)
            before = page.locator("main").bounding_box()["y"]
            page.wait_for_timeout(400)
            after = page.locator("main").bounding_box()["y"]
            cls = page.evaluate(
                "() => (window.__fontPathShifts || []).reduce((a,b)=>a+b,0)"
            )
            print(
                f"[LOCAL-CSS] mode={mode} lang={language} "
                f"DCL={dcl:.0f}ms CLS={cls:.5f} "
                f"shift={after-before:.2f}px remote={len(remote_requests)}",
                flush=True,
            )
            return dcl, cls, abs(after-before), remote_requests
        finally:
            ctx.close()

    def test_inline_faces_remove_remote_css_wait_without_late_layout_shift(self):
        for language in ("ar", "en"):
            with self.subTest(language=language):
                remote_dcl, _, _, remote = self.navigate("remote", language)
                local_dcl, local_cls, jump, actual_remote = self.navigate(
                    "local", language
                )
                self.assertEqual(len(remote), 1)
                self.assertEqual(actual_remote, [])
                self.assertGreater(
                    remote_dcl - local_dcl, 400,
                    f"remote {remote_dcl:.0f}ms local {local_dcl:.0f}ms",
                )
                self.assertLess(local_cls, 0.10)
                self.assertLessEqual(jump, 2.0)


if __name__ == "__main__":
    unittest.main(verbosity=2)
