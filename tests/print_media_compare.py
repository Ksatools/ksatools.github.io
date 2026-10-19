#!/usr/bin/env python3
"""Visual A4-PDF regression for changes to @media print; no site publishing."""
import argparse
import json
import os
import re
import unicodedata
from pathlib import Path
import subprocess
import sys
import tempfile

OUT = Path("print-review")
TOOLS = ("eos-tool", "salary-tool", "letter-tool", "cv-tool")
MAX_DIFF = 0.0005

_DIGIT_TRANSLATION = str.maketrans(
    "٠١٢٣٤٥٦٧٨٩۰۱۲۳۴۵۶۷۸۹", "01234567890123456789"
)


def digits_only(value):
    """Return ASCII digits, ignoring locale-specific separators and bidi marks."""
    value = unicodedata.normalize("NFKC", str(value)).translate(_DIGIT_TRANSLATION)
    return "".join(ch for ch in value if ch.isdigit())


def normalized_text(value):
    """Normalize extracted PDF text enough to compare stable fixture markers."""
    value = unicodedata.normalize("NFKC", str(value)).translate(_DIGIT_TRANSLATION)
    return "".join(ch for ch in value.casefold() if ch.isalnum())


def expected_pdf_markers(page, tool):
    """Capture real rendered output values that must also exist in the generated PDF."""
    if tool == "eos-tool":
        selectors = ("#eos-total-val", "#eos-net-gratuity")
        values = [page.locator(selector).inner_text().strip() for selector in selectors]
        markers = [digits_only(value) for value in values]
        if any(len(marker) < 5 for marker in markers):
            raise RuntimeError(f"EOS calculation output missing before PDF export: {values!r}")
        return {"digits": markers, "text": []}

    if tool == "salary-tool":
        selectors = ("#sal-net-val", "#sal-gross-out")
        values = [page.locator(selector).inner_text().strip() for selector in selectors]
        markers = [digits_only(value) for value in values]
        if any(len(marker) < 5 for marker in markers):
            raise RuntimeError(f"Salary calculation output missing before PDF export: {values!r}")
        return {"digits": markers, "text": []}

    if tool == "letter-tool":
        letter = page.locator("#letter-output").inner_text().strip()
        date_marker = digits_only(page.locator("#let-date").input_value())
        if len(normalized_text(letter)) < 80 or date_marker != "20261020":
            raise RuntimeError("Letter fixture did not generate its expected dated output.")
        # Arabic bidirectional rendering presents this fixture's ISO input as
        # 20-10-2026 in extracted PDF reading order; assert that visible date
        # plus the letter's subject, not the input-field's ISO digit order.
        return {"digits": ["20102026"], "text": [normalized_text("تقديم استقالة")]}

    if tool == "cv-tool":
        resume = page.locator(".cv-doc").inner_text().strip()
        marker = normalized_text("mohammed.otaibi@example.com")
        resume_text = normalized_text(resume)
        if len(resume_text) < 80 or marker not in resume_text:
            raise RuntimeError("CV demo did not generate the expected sample resume content.")
        return {"digits": [], "text": [marker]}

    raise ValueError(f"Unsupported PDF fixture: {tool}")


def inspect_pdf_text(pdf, expected_markers):
    """Validate that the PDF is non-empty and contains the fixture's actual output."""
    pages = []
    for i in range(len(pdf)):
        page = pdf[i]
        text_page = page.get_textpage()
        try:
            pages.append(text_page.get_text_range() or "")
        finally:
            text_page.close()
            page.close()

    raw_text = "\\n".join(pages)
    normalized = normalized_text(raw_text)
    extracted_digits = digits_only(raw_text)
    missing_digits = [
        marker for marker in expected_markers.get("digits", [])
        if not marker or marker not in extracted_digits
    ]
    missing_text = [
        marker for marker in expected_markers.get("text", [])
        if not marker or marker not in normalized
    ]
    return {
        "pages": len(pages),
        "text_chars": len(normalized),
        "markers_present": len(pages) > 0 and len(normalized) >= 80
            and not missing_digits and not missing_text,
        "missing_digits": missing_digits,
        "missing_text": missing_text,
    }


def out_flag(value):
    target = os.environ.get("GITHUB_OUTPUT")
    if target:
        with open(target, "a", encoding="utf-8") as f:
            f.write("generated=" + ("true" if value else "false") + "\n")


def print_blocks(html):
    blocks, cursor = [], 0
    while True:
        start = html.find("@media print", cursor)
        if start < 0:
            return blocks
        op = html.find("{", start)
        depth, quote, comment, escaped = 0, None, False, False
        end = None
        i = op
        while i < len(html):
            c = html[i]
            n = html[i + 1] if i + 1 < len(html) else ""
            if comment:
                if c == "*" and n == "/":
                    comment = False
                    i += 2
                    continue
            elif quote:
                if escaped:
                    escaped = False
                elif c == "\\":
                    escaped = True
                elif c == quote:
                    quote = None
            elif c == "/" and n == "*":
                comment = True
                i += 2
                continue
            elif c in ("'", '"'):
                quote = c
            elif c == "{":
                depth += 1
            elif c == "}":
                depth -= 1
                if depth == 0:
                    end = i + 1
                    break
            i += 1
        if end is None:
            raise ValueError("Unbalanced @media print block")
        blocks.append(html[start:end])
        cursor = end


def set_output(page, field, value):
    page.evaluate("""({id, value}) => {
      const el = document.getElementById(id);
      if (!el) return;
      el.value = value;
      el.dispatchEvent(new Event('input', {bubbles: true}));
      el.dispatchEvent(new Event('change', {bubbles: true}));
    }""", {"id": field, "value": value})


def populate(page, tool):
    page.evaluate("id => switchTool(id, false)", tool)
    if tool == "eos-tool":
        for field, value in (
            ("eos-reason", "expiry"), ("eos-salary", "6500"),
            ("eos-years", "7"), ("eos-months", "0"), ("eos-days", "0"),
            ("eos-leave-days", "15"), ("eos-leave-basis", "full"),
        ):
            set_output(page, field, value)
        page.evaluate("calculateEOS()")
    elif tool == "salary-tool":
        for field, value in (
            ("sal-category", "legacy"), ("sal-basic", "5000"),
            ("sal-housing", "1250"), ("sal-transport", "500"),
            ("sal-obligations", "100"),
        ):
            set_output(page, field, value)
        page.evaluate("calculateSalary()")
    elif tool == "letter-tool":
        set_output(page, "let-type", "resign")
        set_output(page, "let-doc-lang", "ar")
        set_output(page, "let-date", "2026-10-20")
        page.evaluate("generateLetter()")
    elif tool == "cv-tool":
        page.locator("#cv-demo").click()
        page.wait_for_timeout(150)


def render(html_path, tool, pdf_path):
    from playwright.sync_api import sync_playwright

    def route_request(route):
        if route.request.url.startswith("file://"):
            route.continue_()
        else:
            route.abort()

    with sync_playwright() as pw:
        browser = pw.chromium.launch(headless=True)
        context = browser.new_context(viewport={"width": 1280, "height": 900})
        context.route("**/*", route_request)
        page = context.new_page()
        page.goto(html_path.resolve().as_uri(), wait_until="load", timeout=30000)
        page.wait_for_timeout(150)
        populate(page, tool)
        markers = expected_pdf_markers(page, tool)
        page.emulate_media(media="print")
        page.pdf(path=str(pdf_path), format="A4", print_background=True,
                 display_header_footer=False, prefer_css_page_size=True)
        context.close()
        browser.close()
        return markers


def compare_pdfs(before_path, after_path, tool, before_markers, after_markers):
    import pypdfium2 as pdfium
    from PIL import ImageChops

    before = pdfium.PdfDocument(str(before_path))
    after = pdfium.PdfDocument(str(after_path))
    before_count, after_count = len(before), len(after)
    report = {
        "tool": tool, "before_pages": before_count, "after_pages": after_count,
        "page_count_equal": before_count == after_count, "pages": [],
    }
    for i in range(max(before_count, after_count)):
        if i >= before_count or i >= after_count:
            continue
        bi = before[i].render(scale=1.25).to_pil().convert("RGB")
        ai = after[i].render(scale=1.25).to_pil().convert("RGB")
        bi.save(OUT / f"before-{tool}-page-{i + 1}.png")
        ai.save(OUT / f"after-{tool}-page-{i + 1}.png")
        same_size = bi.size == ai.size
        before_ink = sum(1 for pixel in bi.getdata() if pixel != (255, 255, 255))
        after_ink = sum(1 for pixel in ai.getdata() if pixel != (255, 255, 255))
        before_ink_ratio = before_ink / (bi.width * bi.height) if bi.width and bi.height else 0.0
        after_ink_ratio = after_ink / (ai.width * ai.height) if ai.width and ai.height else 0.0
        if same_size:
            diff = ImageChops.difference(bi, ai)
            changed = sum(1 for p in diff.getdata() if p != (0, 0, 0))
            total = bi.width * bi.height
            ratio = changed / total if total else 1.0
            diff.save(OUT / f"diff-{tool}-page-{i + 1}.png")
        else:
            changed, total, ratio = -1, 0, 1.0
        nonblank = before_ink >= 100 and after_ink >= 100
        report["pages"].append({
            "page": i + 1, "same_size": same_size, "changed_pixels": changed,
            "total_pixels": total, "diff_ratio": round(ratio, 8),
            "before_ink_ratio": round(before_ink_ratio, 6),
            "after_ink_ratio": round(after_ink_ratio, 6),
            "nonblank": nonblank,
            "pass": same_size and nonblank and ratio <= MAX_DIFF,
        })
    # Extract text only after raster rendering, because pypdfium2 page handles
    # are tied to their document lifetime.
    before_content = inspect_pdf_text(before, before_markers)
    after_content = inspect_pdf_text(after, after_markers)
    report["content"] = {"before": before_content, "after": after_content}
    report["within_threshold"] = (
        report["page_count_equal"] and before_count > 0 and after_count > 0
        and before_content["markers_present"] and after_content["markers_present"]
        and all(p["pass"] for p in report["pages"])
    )
    before.close()
    after.close()
    return report


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--base-sha", default="")
    args = parser.parse_args()
    if not args.base_sha:
        print("[SKIP] No pull-request base SHA; no PDF render needed.")
        out_flag(False)
        return 0

    try:
        baseline = subprocess.run(
            ["git", "show", f"{args.base_sha}:index.html"],
            check=True, capture_output=True, text=True, encoding="utf-8"
        ).stdout
        candidate = Path("index.html").read_text(encoding="utf-8")
        base_blocks, candidate_blocks = print_blocks(baseline), print_blocks(candidate)
    except (subprocess.CalledProcessError, ValueError) as exc:
        print(f"::error::Could not inspect baseline print CSS: {exc}")
        out_flag(False)
        return 1

    print(f"[INFO] @media print blocks: base={len(base_blocks)} candidate={len(candidate_blocks)}")
    if base_blocks == candidate_blocks:
        print("[SKIP] @media print unchanged; skip PDF dependencies/rendering.")
        out_flag(False)
        return 0

    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "status.txt").write_text("Print comparison started.\n", encoding="utf-8")
    out_flag(True)
    install = subprocess.run(
        [sys.executable, "-m", "pip", "install", "--disable-pip-version-check",
         "pypdfium2", "Pillow"], capture_output=True, text=True
    )
    if install.returncode:
        print(install.stdout, install.stderr)
        print("::error::Could not install PDF comparison dependencies.")
        return 1

    results = []
    with tempfile.TemporaryDirectory(prefix="ksa-print-review-") as temp:
        root = Path(temp)
        bdir, adir = root / "before", root / "after"
        bdir.mkdir()
        adir.mkdir()
        (bdir / "index.html").write_text(baseline, encoding="utf-8")
        (adir / "index.html").write_text(candidate, encoding="utf-8")
        for tool in TOOLS:
            bp, ap = OUT / f"before-{tool}.pdf", OUT / f"after-{tool}.pdf"
            before_markers = render(bdir / "index.html", tool, bp)
            after_markers = render(adir / "index.html", tool, ap)
            result = compare_pdfs(bp, ap, tool, before_markers, after_markers)
            results.append(result)
            print("[PDF] %s: pages %s/%s, diff=%s, content=%s/%s" % (
                tool, result["before_pages"], result["after_pages"],
                [p["diff_ratio"] for p in result["pages"]],
                result["content"]["before"]["markers_present"],
                result["content"]["after"]["markers_present"],
            ))

    (OUT / "summary.json").write_text(
        json.dumps({"base_sha": args.base_sha, "max_diff_ratio": MAX_DIFF,
                    "results": results}, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8"
    )
    fails = [r["tool"] for r in results if not r["within_threshold"]]
    if fails:
        print("::error::PDF comparison failed for: " + ", ".join(fails)
              + ". Check page counts, nonblank output, fixture markers, and visual diffs.")
        return 1
    print("[PASS] Before/after PDFs contain expected output and visually match for all four tools.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
