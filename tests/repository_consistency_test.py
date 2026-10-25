#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Static repository consistency checks; no network, browser, API, or file writes."""
from __future__ import annotations

import json
import re
from pathlib import Path
from urllib.parse import urlparse
import xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parent.parent
SITE = "https://ksatools.github.io"
NS = {"sm": "http://www.sitemaps.org/schemas/sitemap/0.9",
      "xhtml": "http://www.w3.org/1999/xhtml"}
SOCIAL_BAR = "https://bauval.org/14/7cdd0a31b4560a6ce3906a22a43c5ed3"
NATIVE_BANNER = "https://bauval.org/21/7af3b8325dba6708da88eed5e517ec89"
AD_CONTAINER = "container-7af3b8325dba6708da88eed5e517ec89"
checks: list[tuple[str, bool, str]] = []


def check(name: str, condition: bool, detail: str = "") -> None:
    checks.append((name, bool(condition), detail))
    status = "PASS" if condition else "FAIL"
    print(f"[{status}] {name}" + (f" — {detail}" if detail else ""), flush=True)


def read_text(relative: str) -> str:
    return (ROOT / relative).read_text(encoding="utf-8")


def is_local_article_url(value: object) -> bool:
    if not isinstance(value, str) or not value.startswith("/articles/"):
        return False
    if value.startswith("//") or chr(92) in value or "?" in value or "#" in value:
        return False
    parsed = urlparse(value)
    return (not parsed.scheme and not parsed.netloc and parsed.path.endswith(".html")
            and ".." not in parsed.path.split("/"))


def main() -> int:
    records = []
    try:
        raw = json.loads(read_text("articles.json"))
        array_ok = isinstance(raw, list)
        check("articles.json is a JSON array", array_ok)
        records = raw if array_ok else []
    except (OSError, json.JSONDecodeError) as exc:
        check("articles.json is a JSON array", False, str(exc))

    try:
        index_html = read_text("index.html")
        check("index.html ends with </html>", index_html.rstrip().endswith("</html>"))
        check("main-page JavaScript retains core entry points",
              all(name in index_html for name in
                  ("gosiScheme", "calculateEOS", "calculateSalary", "loadGuides", "cvSharePayload")))
        check("share values are persisted before URL cleanup",
              "persistInputsNow();" in index_html
              and "history.replaceState(null, '', cleanUrl.pathname" in index_html)
    except OSError as exc:
        check("index.html is readable", False, str(exc))

    seen_urls: set[str] = set()
    by_pair: dict[str, dict[str, dict]] = {}
    records_valid = True
    for i, rec in enumerate(records):
        if not isinstance(rec, dict):
            check(f"article record #{i + 1} is an object", False)
            records_valid = False
            continue
        lang, tid, url, alt = (rec.get("lang"), rec.get("translation_id"),
                               rec.get("url"), rec.get("alternate_url"))
        valid = (lang in ("ar", "en") and isinstance(tid, str) and bool(tid)
                 and rec.get("status") == "published" and is_local_article_url(url)
                 and is_local_article_url(alt) and isinstance(rec.get("title"), str)
                 and bool(rec.get("title", "").strip()))
        check(f"article record #{i + 1} has required fields", valid,
              f"translation_id={tid!r}, lang={lang!r}")
        records_valid = records_valid and valid
        if not valid:
            continue
        unique = url not in seen_urls
        check(f"article URL is unique: {url}", unique)
        records_valid = records_valid and unique
        seen_urls.add(url)
        pair = by_pair.setdefault(tid, {})
        one_per_language = lang not in pair
        check(f"translation pair {tid!r} has one {lang} record", one_per_language)
        records_valid = records_valid and one_per_language
        if one_per_language:
            pair[lang] = rec

        file_path = ROOT / url.lstrip("/")
        exists = file_path.is_file()
        check(f"published article file exists: {url}", exists)
        records_valid = records_valid and exists
        if not exists:
            continue
        try:
            html = file_path.read_text(encoding="utf-8")
            canonical_ok = f'<link rel="canonical" href="{SITE}{url}"' in html
            check(f"canonical matches its record: {url}", canonical_ok)
            records_valid = records_valid and canonical_ok
            social_ok = html.count(SOCIAL_BAR) == 1
            native_ok = html.count(NATIVE_BANNER) == 1
            container_ok = html.count(AD_CONTAINER) == 1
            complete = html.rstrip().endswith("</html>")
            check(f"approved Social Bar occurs once: {url}", social_ok)
            check(f"approved Native Banner occurs once: {url}", native_ok)
            check(f"Native Banner container occurs once: {url}", container_ok)
            check(f"article page is complete: {url}", complete)
            records_valid = records_valid and social_ok and native_ok and container_ok and complete
        except (OSError, UnicodeDecodeError) as exc:
            check(f"published article is readable: {url}", False, str(exc))
            records_valid = False

    for tid, langs in sorted(by_pair.items()):
        pair_ok = set(langs) == {"ar", "en"}
        check(f"translation pair {tid!r} contains ar and en", pair_ok, f"found={sorted(langs)}")
        records_valid = records_valid and pair_ok
        if pair_ok:
            ar_url, en_url = langs["ar"]["url"], langs["en"]["url"]
            reciprocal = (langs["ar"]["alternate_url"] == en_url
                          and langs["en"]["alternate_url"] == ar_url)
            check(f"translation links are reciprocal: {tid}", reciprocal)
            records_valid = records_valid and reciprocal
    check("all article records and language pairs are consistent", records_valid)

    # Every published article must have a crawlable literal HTML link in
    # the library, even before JavaScript fetches articles.json.
    try:
        library = read_text("articles/index.html")
        fallback_match = re.search(
            r'<div id="static-articles" class="grid">(.*?)</div>', library, re.S)
        fallback_html = fallback_match.group(1) if fallback_match else ""
        cards = re.findall(
            r'<article class="card" lang="(ar|en)" dir="(rtl|ltr)"><h2 class="article-title"><a href="([^"]+)">([^<]+)</a></h2>',
            fallback_html)
        published = {r["url"]: r for r in records
                     if isinstance(r, dict) and r.get("status") == "published"
                     and is_local_article_url(r.get("url"))}
        hrefs = [url for _lang, _direction, url, _title in cards]
        check("static library HTML links match all published article URLs",
              len(hrefs) == len(published) and set(hrefs) == set(published),
              f"HTML links={len(hrefs)} published={len(published)}")
        check("static library cards have matching language, direction and title",
              len(cards) == len(published) and all(
                  url in published and lang == published[url]["lang"]
                  and direction == ("rtl" if lang == "ar" else "ltr")
                  and title == published[url]["title"]
                  for lang, direction, url, title in cards))
        check("interactive library fetch and render remain available",
              "function render()" in library
              and "fetch('/articles.json',{cache:'no-store'})" in library
              and 'id="results"' in library)
    except (OSError, UnicodeDecodeError) as exc:
        check("crawlable library HTML is readable", False, str(exc))

    # Keep contextual navigation relevant and matched to the article language.
    article_edges = {
        "articles/ar/labor-art81-ar.html": "/articles/ar/end-of-service-benefit-ar.html",
        "articles/en/labor-art81-en.html": "/articles/en/end-of-service-benefit-en.html",
        "articles/ar/annual-leave-ar.html": "/articles/ar/end-of-service-benefit-ar.html",
        "articles/en/annual-leave-en.html": "/articles/en/end-of-service-benefit-en.html",
        "articles/ar/end-of-service-benefit-ar.html": "/articles/ar/annual-leave-ar.html",
        "articles/en/end-of-service-benefit-en.html": "/articles/en/annual-leave-en.html",
    }
    for src, dst in article_edges.items():
        check(f"contextual guide link {src} -> {dst}",
              (ROOT / dst.lstrip("/")).is_file()
              and f'href="{dst}"' in read_text(src))

    sitemap_ok = False
    try:
        root = ET.fromstring(read_text("sitemap.xml"))
        sitemap_urls = [node.text or "" for node in root.findall("sm:url/sm:loc", NS)]
        unique = len(sitemap_urls) == len(set(sitemap_urls))
        check("sitemap.xml parses and loc URLs are unique", unique, f"loc_count={len(sitemap_urls)}")
        expected = {f"{SITE}{url}" for url in seen_urls}
        missing = sorted(expected - set(sitemap_urls))
        unexpected = sorted(u for u in sitemap_urls if "/articles/" in u and u not in expected
                            and not u.rstrip("/").endswith("/articles"))
        check("all published article URLs appear in sitemap.xml", not missing,
              f"missing={missing[:4]}" if missing else "")
        check("sitemap has no unexpected article-page URLs", not unexpected,
              f"unexpected={unexpected[:4]}" if unexpected else "")
        by_loc = {node.findtext("sm:loc", default="", namespaces=NS): node
                  for node in root.findall("sm:url", NS)}
        alternates_ok = True
        for tid, langs in by_pair.items():
            if set(langs) != {"ar", "en"}:
                alternates_ok = False
                continue
            ar_url, en_url = f"{SITE}{langs['ar']['url']}", f"{SITE}{langs['en']['url']}"
            for loc in (ar_url, en_url):
                node = by_loc.get(loc)
                links = node.findall("xhtml:link", NS) if node is not None else []
                alternates = {link.attrib.get("hreflang"): link.attrib.get("href") for link in links}
                if alternates.get("ar") != ar_url or alternates.get("en") != en_url:
                    alternates_ok = False
        check("sitemap ar/en alternates match the article index", alternates_ok)
        sitemap_ok = unique and not missing and not unexpected and alternates_ok
    except (OSError, ET.ParseError) as exc:
        check("sitemap.xml parses", False, str(exc))
    check("sitemap and article index are consistent", sitemap_ok)

    try:
        marketing = read_text("auto_marketing.py")
        check("Groq is the default provider and Gemini is explicit",
              re.search(r'DEFAULT_PROVIDER\s*=\s*["\']groq["\']', marketing) is not None
              and "AI_PROVIDER" in marketing
              and "groq_generate_json" in marketing and "gemini_generate_json" in marketing)
        check("unsafe auto-publish bypass is rejected",
              "EXIT_UNSAFE_PUBLISH_CONFIG" in marketing
              and 'mode == "auto" and skip_source_check' in marketing)
        check("EOSB examples receive deterministic validation",
              "validate_eosb_calculation_example" in marketing
              and "validate_eosb_translation_pair" in marketing
              and "eosb_reference_amount" in marketing)
    except OSError as exc:
        check("auto_marketing.py is readable", False, str(exc))

    try:
        decisions = read_text("docs/DECISIONS.md")
        if not (ROOT / "opencode.json").is_file():
            check("decision log accurately says opencode.json is absent",
                  "الملف غير موجود" in decisions)
        else:
            check("opencode.json has a decision-log entry", "opencode.json" in decisions)
    except OSError as exc:
        check("docs/DECISIONS.md is readable", False, str(exc))

    failures = sum(not ok for _, ok, _ in checks)
    print(f"\nSUMMARY: PASS={len(checks) - failures} FAIL={failures}")
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
