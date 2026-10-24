#!/usr/bin/env python3
"""Regression tests for the exact public artifact built by AI Marketing."""
from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
from build_site_artifact import (  # noqa: E402
    PUBLIC_SUFFIXES, REQUIRED_FILES, build_site,
)


class PagesArtifactTests(unittest.TestCase):
    def test_production_artifact_has_all_public_files_and_no_internal_files(self):
        with tempfile.TemporaryDirectory(prefix="ksa-pages-test-") as temp:
            dest = Path(temp) / "_site"
            build_site(dest)
            self.assertTrue(dest.joinpath("articles.json").is_file())
            records = json.loads((dest / "articles.json").read_text(encoding="utf-8"))
            self.assertIsInstance(records, list)
            self.assertTrue(records, "Published article index must not be empty")
            for record in records:
                if record.get("status") == "published":
                    for field in ("url", "alternate_url"):
                        link = record.get(field, "")
                        self.assertTrue(link.startswith("/articles/"), link)
                        self.assertTrue((dest / link.lstrip("/")).is_file(), link)
            for name in REQUIRED_FILES:
                self.assertTrue((dest / name).is_file(), name)
            self.assertTrue((dest / "articles" / "index.html").is_file())
            self.assertEqual(
                {p.name for p in dest.iterdir() if p.is_file()},
                set(REQUIRED_FILES) |
                {p.name for p in ROOT.iterdir()
                 if p.is_file() and p.suffix.lower() in PUBLIC_SUFFIXES},
            )
            for name in ("auto_marketing.py", "marketing_state.json", "latest_social_post.txt",
                         "AGENTS.md", "DEPLOY_NOTES.md", "docs", "tests", "scripts", ".github",
                         ".gitignore", "drafts"):
                self.assertFalse((dest / name).exists(), name)
            self.assertFalse(any(p.is_symlink() for p in dest.rglob("*")))

    def test_nonempty_destination_is_rejected_to_prevent_stale_content(self):
        with tempfile.TemporaryDirectory(prefix="ksa-pages-test-") as temp:
            dest = Path(temp) / "_site"
            dest.mkdir()
            (dest / "stale.html").write_text("old", encoding="utf-8")
            with self.assertRaises(ValueError):
                build_site(dest)

    def test_missing_articles_index_fails_closed(self):
        with tempfile.TemporaryDirectory(prefix="ksa-pages-test-") as temp:
            source = Path(temp) / "source"
            source.mkdir()
            for name in REQUIRED_FILES:
                if name != "articles.json":
                    (source / name).write_text("fixture", encoding="utf-8")
            (source / "articles").mkdir()
            with self.assertRaises(FileNotFoundError):
                build_site(Path(temp) / "output", source=source)

    def test_public_source_directory_cannot_be_overwritten(self):
        with self.assertRaises(ValueError):
            build_site(ROOT / "articles" / "_site")


if __name__ == "__main__":
    unittest.main()
