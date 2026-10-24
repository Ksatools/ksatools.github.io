#!/usr/bin/env python3
"""Read-only checks against the *deployed* KSA Tools site.

Run explicitly: python tests/production_smoke_test.py
Not part of pull-request CI: live availability must not gate code review.
"""
from __future__ import annotations

import json
import urllib.error
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET

ORIGIN = "https://ksatools.github.io"
TIMEOUT = 15
USER_AGENT = "KSA-Tools-Production-Smoke/1.0"


def fetch(path: str, *, content_type: str) -> bytes:
    if not path.startswith("/") or path.startswith("//") or ".." in path:
        raise AssertionError(f"Unsafe site path: {path!r}")
    url = ORIGIN + path
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(req, timeout=TIMEOUT) as response:
        final = urllib.parse.urlsplit(response.geturl())
        assert (final.scheme, final.netloc) == ("https", "ksatools.github.io"), (
            f"Unexpected redirect for {path}: {response.geturl()}"
        )
        assert response.status == 200, f"{path}: HTTP {response.status}"
        mime = response.headers.get_content_type()
        assert mime == content_type, f"{path}: {mime!r} (expected {content_type})"
        data = response.read(3_000_001)
        assert 0 < len(data) <= 3_000_000, f"{path}: empty or oversized response"
        print(f"[PASS] HTTP 200 {path} ({len(data)} bytes, {mime})")
        return data


def main() -> None:
    home = fetch("/", content_type="text/html").decode("utf-8")
    assert "<html" in home.lower() and "gosiScheme" in home
    library = fetch("/articles/", content_type="text/html").decode("utf-8")
    assert "articles.json" in library and 'id="results"' in library
    for path in ("/privacy.html", "/404.html"):
        assert "</html>" in fetch(path, content_type="text/html").decode("utf-8").lower()

    records = json.loads(fetch("/articles.json", content_type="application/json"))
    assert isinstance(records, list) and records, "No article index records"
    published = [r for r in records if r.get("status") == "published"]
    assert published, "No published articles"
    assert {"ar", "en"}.issubset({r.get("lang") for r in published})
    sitemap = ET.fromstring(fetch("/sitemap.xml", content_type="application/xml"))
    ns = {"sm": "http://www.sitemaps.org/schemas/sitemap/0.9"}
    urls = {node.text for node in sitemap.findall(".//sm:loc", ns)}

    for record in published:
        path = record["url"]
        assert path.startswith("/articles/") and path.endswith(".html")
        assert ORIGIN + path in urls, f"Article missing from sitemap: {path}"
        html = fetch(path, content_type="text/html").decode("utf-8")
        assert "<title>" in html and "</html>" in html.lower()
        assert f'href="{ORIGIN + path}"' in html, f"Canonical missing: {path}"

    fetch("/robots.txt", content_type="text/plain")
    print(f"[PASS] Production check complete: {len(published)} published pages and key routes")


if __name__ == "__main__":
    main()
