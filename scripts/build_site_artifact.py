#!/usr/bin/env python3
"""Build the public GitHub Pages artifact from an explicit allowlist.

This same builder is used by AI Marketing and tested by CI. Internal files,
drafts, state, and automation code must never enter the Pages artifact.
"""
from __future__ import annotations

import argparse
import shutil
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

REQUIRED_FILES = (
    "index.html",
    "articles.json",
    "privacy.html",
    "404.html",
    "robots.txt",
    "sitemap.xml",
    "ads.txt",
)
PUBLIC_DIRECTORIES = ("articles", "assets", "icons")
PUBLIC_SUFFIXES = frozenset((".png", ".svg", ".ico", ".webmanifest"))


def _reject_symlinks(path: Path) -> None:
    if path.is_symlink() or (path.is_dir() and any(p.is_symlink() for p in path.rglob("*"))):
        raise ValueError(f"Symbolic links are not allowed in the Pages artifact: {path}")


def build_site(output: Path, source: Path = ROOT) -> None:
    """Copy the allowed public files into a fresh, empty output directory."""
    source = source.resolve()
    output = output.resolve()

    if output == source or output in source.parents:
        raise ValueError("Output must not overwrite the repository or its parents.")
    if any(output == source / name or (source / name) in output.parents
           for name in PUBLIC_DIRECTORIES):
        raise ValueError("Output must not be inside a public source directory.")
    if output.exists() and (not output.is_dir() or any(output.iterdir())):
        raise ValueError("Output must be an empty directory to avoid stale files.")

    files = [source / name for name in REQUIRED_FILES]
    for path in files:
        if not path.is_file():
            raise FileNotFoundError(f"Required public file is missing: {path}")
        _reject_symlinks(path)

    directories = []
    for name in PUBLIC_DIRECTORIES:
        path = source / name
        if name == "articles" and not path.is_dir():
            raise FileNotFoundError(f"Required public directory is missing: {path}")
        if path.exists():
            if not path.is_dir():
                raise ValueError(f"Expected a directory: {path}")
            _reject_symlinks(path)
            directories.append(path)

    for path in source.iterdir():
        if path.is_file() and path.suffix.lower() in PUBLIC_SUFFIXES:
            _reject_symlinks(path)
            files.append(path)

    output.mkdir(parents=True, exist_ok=True)
    for path in files:
        shutil.copy2(path, output / path.name)
    for path in directories:
        shutil.copytree(path, output / path.name)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True,
                        help="Empty destination directory for the public Pages artifact")
    args = parser.parse_args()
    build_site(args.output)
    count = sum(p.is_file() for p in args.output.rglob("*"))
    print(f"Public Pages artifact prepared: {count} files in {args.output}")


if __name__ == "__main__":
    main()
