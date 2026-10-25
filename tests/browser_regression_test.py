#!/usr/bin/env python3
"""Offline browser regressions for mobile layouts and successful article loading.

Serves the repository on 127.0.0.1 and blocks third-party requests; no
production traffic, remote services, secrets, or content changes are needed.
"""
from __future__ import annotations

import functools
import json
import threading
import unittest
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parents[1]


class QuietHandler(SimpleHTTPRequestHandler):
    def log_message(self, *_args):
        pass


class BrowserRegressionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        handler = functools.partial(QuietHandler, directory=str(ROOT))
        cls.server = ThreadingHTTPServer(("127.0.0.1", 0), handler)
        cls.thread = threading.Thread(target=cls.server.serve_forever, daemon=True)
        cls.thread.start()
        cls.base = f"http://127.0.0.1:{cls.server.server_port}"
        cls.data = json.loads((ROOT / "articles.json").read_text(encoding="utf-8"))
        cls.playwright = sync_playwright().start()
        cls.browser = cls.playwright.chromium.launch(headless=True)

    @classmethod
    def tearDownClass(cls):
        cls.browser.close()
        cls.playwright.stop()
        cls.server.shutdown()
        cls.server.server_close()
        cls.thread.join(timeout=5)

    def context(self, **kwargs):
        ctx = self.browser.new_context(**kwargs)
        local = self.base + "/"

        def isolate(route):
            if route.request.url.startswith(local):
                return route.continue_()
            return route.fulfill(status=200, body="", content_type="text/plain")

        ctx.route("**/*", isolate)
        return ctx

    def count_for(self, lang):
        return sum(1 for r in self.data if r.get("status") == "published" and r.get("lang") == lang)

    def test_article_library_loads_filters_searches_and_switches_language(self):
        ctx = self.context()
        try:
            page = ctx.new_page()
            for lang in ("ar", "en"):
                page.goto(self.base + f"/articles/?lang={lang}", wait_until="domcontentloaded")
                page.locator("#results .card").first.wait_for(timeout=10000)
                # Once JavaScript initializes, the static fallback is replaced.
                self.assertEqual(page.locator("#static-articles").count(), 0)
                records = [
                    r for r in self.data
                    if r.get("status") == "published" and r.get("lang") == lang
                ]
                self.assertEqual(page.locator("#results .card").count(), len(records))
                self.assertEqual(page.locator("html").get_attribute("dir"), "rtl" if lang == "ar" else "ltr")
                expected = {r["url"] for r in records}
                actual = set(page.locator("#results .article-title a").evaluate_all(
                    "(els) => els.map(el => el.getAttribute('href'))"
                ))
                self.assertEqual(actual, expected)

                title = records[0]["title"]
                page.locator("#search").fill(title)
                self.assertEqual(page.locator("#results .card").count(), 1)
                self.assertEqual(page.locator("#results .article-title").inner_text(), title)
                page.locator("#search").fill("__no_such_article_ksa__")
                self.assertEqual(page.locator("#results .card").count(), 0)
                self.assertTrue(page.locator("#results .empty").is_visible())
                page.locator("#search").fill("")

                # Filter by a real category, then restore all articles.
                category = next((r["category"] for r in records if r.get("category")), None)
                self.assertIsNotNone(category)
                selected_label = page.locator(
                    f'#category option[value="{category}"]'
                ).inner_text()
                page.locator("#category").select_option(category)
                # The UI also infers a category when the raw field is absent
                # or unrecognized; assert actual filter behavior, not raw counts.
                filtered_count = page.locator("#results .card").count()
                self.assertGreater(filtered_count, 0)
                self.assertLessEqual(filtered_count, len(records))
                self.assertEqual(
                    page.locator("#results .card .pill").all_inner_texts(),
                    [selected_label] * filtered_count,
                )
                page.locator("#category").select_option("all")
                self.assertEqual(page.locator("#results .card").count(), self.count_for(lang))

                # A real article URL must serve its HTML page from the local site.
                article_path = records[0]["url"]
                response = page.request.get(self.base + article_path)
                self.assertEqual(response.status, 200)
                self.assertIn("<title>", response.text())
        finally:
            ctx.close()

    def test_library_links_exist_without_javascript_on_mobile(self):
        published = {r["url"]: r for r in self.data if r.get("status") == "published"}
        for width in (375, 390):
            with self.subTest(viewport=width):
                ctx = self.context(java_script_enabled=False,
                                   viewport={"width": width, "height": 844},
                                   is_mobile=True, has_touch=True)
                try:
                    page = ctx.new_page()
                    response = page.goto(self.base + "/articles/", wait_until="domcontentloaded")
                    self.assertEqual(response.status, 200)
                    anchors = page.locator("#static-articles .article-title a")
                    self.assertEqual(anchors.count(), len(published))
                    urls = [anchors.nth(i).get_attribute("href")
                            for i in range(anchors.count())]
                    self.assertEqual(set(urls), set(published))
                    self.assertEqual(len(urls), len(set(urls)))
                    self.assertTrue(anchors.first.is_visible())
                    # HTML fallback provides usable navigation without scripts.
                    anchors.first.click()
                    self.assertTrue(page.url.endswith(urls[0]))
                finally:
                    ctx.close()

    def test_home_guides_fetch_real_article_index(self):
        ctx = self.context()
        try:
            page = ctx.new_page()
            page.goto(self.base + "/?lang=ar", wait_until="domcontentloaded")
            page.locator("#guides-list a").first.wait_for(timeout=10000)
            urls = page.locator("#guides-list a").evaluate_all(
                "(els) => els.map(e => e.getAttribute('href'))"
            )
            self.assertTrue(urls)
            self.assertTrue(all(u.startswith("/articles/") for u in urls))
            page.locator("#lang-btn").click()
            self.assertEqual(page.locator("html").get_attribute("lang"), "en")
            page.locator("#guides-list a").first.wait_for(timeout=10000)
            self.assertTrue(page.locator("#guides-list a").count() > 0)
        finally:
            ctx.close()

    def test_mobile_tools_and_share_panel_have_no_horizontal_overflow(self):
        for width, height in ((375, 812), (390, 844), (768, 1024)):
            with self.subTest(viewport=width):
                ctx = self.context(
                    viewport={"width": width, "height": height},
                    is_mobile=True,
                    has_touch=True,
                    device_scale_factor=1,
                )
                try:
                    page = ctx.new_page()
                    page.goto(self.base + "/?lang=ar", wait_until="domcontentloaded")
                    page.locator("#eos-total-val").wait_for(timeout=10000)
                    for tool in ("eos", "salary", "letter", "cv"):
                        page.locator(f"#tab-{tool}").click()
                        self.assertEqual(
                            page.locator(f"#tab-{tool}").get_attribute("aria-selected"), "true",
                            (width, tool),
                        )
                        self.assertTrue(page.locator(
                            f"#{'eos-tool' if tool == 'eos' else tool + '-tool'}"
                        ).is_visible(), (width, tool))
                        overflow = page.evaluate(
                            "() => document.documentElement.scrollWidth - document.documentElement.clientWidth"
                        )
                        self.assertLessEqual(overflow, 2, (width, tool, overflow))

                    page.locator("#tab-eos").click()
                    page.locator("#eos-share").click()
                    self.assertFalse(page.locator("#share-modal").evaluate("(el) => el.hidden"))
                    modal_overflow = page.evaluate(
                        "() => document.documentElement.scrollWidth - document.documentElement.clientWidth"
                    )
                    self.assertLessEqual(modal_overflow, 2, (width, "share", modal_overflow))
                    page.locator("#share-close").click()
                    self.assertTrue(page.locator("#share-modal").evaluate("(el) => el.hidden"))
                finally:
                    ctx.close()


if __name__ == "__main__":
    unittest.main(verbosity=2)
