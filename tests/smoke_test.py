#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
tests/smoke_test.py — اختبار الدخان لصفحتَي index.html وprivacy.html

الغرض: كشف الانكسارات في الملف الحالي بسرعة، دون أي تعديل عليه.

طريقة التشغيل:
    python tests/smoke_test.py                 # يفشل (exit 1) عند أي انكسار غير متوقّع
    python tests/smoke_test.py --strict        # يفشل أيضاً عند بنود BACKLOG غير المنفّذة
    python tests/smoke_test.py --headful       # لرؤية المتصفّح

المتطلّبات: Playwright (Python) + متصفّح Chrome مثبّت (channel="chrome").
    python -m pip install playwright

نتائج كل حالة:
    PASS            السلوك مطابق للمطلوب.
    FAIL            انكسار حقيقي — سبب قيمة خروج غير صفرية.
    FAIL (known:#N) انكسار متوقّع معروف، مربوط ببند في docs/BACKLOG.md.
                    لا يؤثّر على قيمة الخروج افتراضياً؛ استخدم --strict ليؤثّر.

سياسة الشبكة: تُحجب كل الطلبات غير file:// في المتصفّح، فلا تصل أي بيانات للخارج.
لا تُعدّل هذه الأداة الملفّ، ولا تكتب أي بيانات.
"""

import argparse
import hashlib
import io
import pathlib
import re
import subprocess
import sys
import tempfile

REPO = pathlib.Path(__file__).resolve().parent.parent
INDEX = REPO / "index.html"
PRIVACY = REPO / "privacy.html"

PASS, FAIL, XFAIL = "PASS", "FAIL", "XFAIL"
results = []  # (status, name, detail, known)


def record(status, name, detail="", known=None):
    detail = " ".join(str(detail).split())[:160]  # سطر واحد قصير
    results.append((status, name, detail, known))
    tag = {PASS: "PASS", FAIL: "FAIL", XFAIL: "FAIL (known)"}[status]
    line = "[%s] %s" % (tag, name)
    if known is not None:
        line += "  (BACKLOG #%s)" % known
    if detail:
        line += "  — " + detail
    print(line, flush=True)


def check(name, cond, detail="", known=None):
    """cond صحيح ⇒ PASS. وإلا FAIL، أو XFAIL إن مُرِّر رقم بند backlog."""
    if cond:
        record(PASS, name, detail)
    elif known is not None:
        record(XFAIL, name, detail, known=known)
    else:
        record(FAIL, name, detail)


# ----------------------------------------------------------------------------
# 1) فحوص ثابتة (بلا متصفّح)
# ----------------------------------------------------------------------------
def static_checks():
    print("\n== فحوص ثابتة ==", flush=True)
    if not INDEX.exists():
        record(FAIL, "index.html موجود", "غير موجود: %s" % INDEX)
        return
    raw = INDEX.read_bytes()
    text = raw.decode("utf-8", errors="replace")

    check("index.html غير فارغ", len(raw) > 150000, "%d بايت" % len(raw))
    check("لا BOM", raw[:3] != b"\xef\xbb\xbf")
    check("ينتهي بـ</html>", text.rstrip().endswith("</html>"))
    check("يحتوي gosiScheme", "gosiScheme" in text)
    check("يحتوي store.set", "store.set" in text)
    check("معرّف GA4 موجود مرة واحدة لكل من src وconfig", text.count("G-HGMS3MZ27P") == 2,
          "المعرّف متوقع في سكربت التحميل وفي التهيئة فقط")
    check("عنوان الصفحة المرسل إلى GA4 يخلو من query وfragment",
          re.search(r"""gtag\(\s*['"]config['"]\s*,\s*['"]G-HGMS3MZ27P['"]\s*,\s*\{\s*page_location\s*:\s*window\.location\.origin\s*\+\s*window\.location\.pathname\s*\}\s*\)\s*;""", text) is not None)
    check("معاملات رابط المشاركة تُحذف بعد استعادة القيم",
          "const shareKeys = ['tool', 's', 'y', 'm', 'd', 'ld', 'lb', 'bs', 'r', 'c', 'b', 'h', 't', 'o']" in text
          and "history.replaceState(null, '', cleanUrl.pathname" in text)
    privacy_text = PRIVACY.read_text(encoding="utf-8") if PRIVACY.exists() else ""
    check("privacy.html موجود", PRIVACY.exists())
    check("سياسة الخصوصية تصرّح باستخدام GA4 باللغتين",
          "نستخدم Google Analytics 4 (GA4)" in privacy_text
          and "We use Google Analytics 4 (GA4)" in privacy_text)
    check("أزيلت عبارة التحليلات القديمة غير المطابقة",
          "لا نستخدم حالياً أدوات تحليل سلوكية خاصة بنا" not in privacy_text
          and "We currently use no behavioral analytics of our own." not in privacy_text)
    check("سكربت Social Bar موجود مرة واحدة",
          text.count("https://bauval.org/14/7cdd0a31b4560a6ce3906a22a43c5ed3") == 1,
          "count=%d" % text.count("https://bauval.org/14/7cdd0a31b4560a6ce3906a22a43c5ed3"))
    check("سكربت Native Banner موجود مرة واحدة",
          text.count("https://bauval.org/21/7af3b8325dba6708da88eed5e517ec89") == 1,
          "count=%d" % text.count("https://bauval.org/21/7af3b8325dba6708da88eed5e517ec89"))
    native_id = re.search(r"bauval\.org/21/([0-9a-f]+)", text)
    container_id = re.search(r'<div id="container-([0-9a-f]+)"></div>', text)
    check("حاوية Native Banner تطابق معرّف الإعلان",
          bool(native_id and container_id and native_id.group(1) == container_id.group(1)),
          "native=%s container=%s" % (native_id.group(1) if native_id else None,
                                      container_id.group(1) if container_id else None))
    check("لا يوجد نطاق الإعلان القديم",
          text.count("pl25967834.profitablecpmrate.com") == 0,
          "count=%d" % text.count("pl25967834.profitablecpmrate.com"))
    check("لا يوجد أثر اختبار ('ad stripped')", "<!--ad stripped-->" not in text)
    check("بصيغة LF فقط", b"\r\n" not in raw and raw.count(b"\r") == 0)

    # فحص الجافاسكربت الرئيسي بـnode --check
    # نختار أكبر سكربت داخلي (بدون src) وهو الجافاسكربت الرئيسي
    scripts = re.findall(r"<script>(.*?)</script>", text, re.S)
    main_js = max(scripts, key=len) if scripts else ""
    if main_js:
        try:
            with tempfile.NamedTemporaryFile("w", suffix=".js", delete=False,
                                             encoding="utf-8") as fh:
                fh.write(main_js)
                js_path = fh.name
            proc = subprocess.run(["node", "--check", js_path],
                                  capture_output=True, text=True)
            check("node --check للجافاسكربت", proc.returncode == 0,
                  (proc.stderr or "").strip()[:200])
        except FileNotFoundError:
            print("[SKIP] node غير متوفّر — تخطّي فحص الصياغة", flush=True)
    else:
        record(FAIL, "العثور على السكربت الرئيسي", "لم يُعثر على <script>…</script>")


# ----------------------------------------------------------------------------
# 2) مساعدات المتصفّح
# ----------------------------------------------------------------------------
def setup_page(ctx, errors):
    pg = ctx.new_page()
    pg.on("console", lambda m: errors.append(m.text) if m.type == "error" else None)
    pg.on("pageerror", lambda e: errors.append("pageerror: %s" % e))
    pg.goto(INDEX.as_uri(), wait_until="load")
    pg.wait_for_timeout(350)
    return pg


def tab(pg, tool):
    pg.evaluate("(t)=>document.getElementById('tab-'+t).click()", tool)
    pg.wait_for_timeout(120)


def setv(pg, el_id, value):
    """إدخال قيمة عبر الأحداث الحقيقية (input + change) دون اعتماد الظهور."""
    pg.evaluate(
        "([s,v])=>{const e=document.getElementById(s); if(!e) throw new Error('no '+s);"
        "e.value=v; e.dispatchEvent(new Event('input',{bubbles:true}));"
        "e.dispatchEvent(new Event('change',{bubbles:true}));}", [el_id, value])


def click(pg, el_id):
    pg.evaluate("(s)=>document.getElementById(s).click()", el_id)


def has_num(text, expected):
    """مقارنة رقمية بعد إزالة رموز العملة والمسافات الخاصة."""
    if text is None:
        return False
    norm = text.replace("\u066b", ".").replace("\u066c", ",")
    norm = re.sub(r"[^\d.]", "", norm)  # يزيل الفواصل ورموز العملة وعلامات الاتجاه
    return expected.replace(",", "").replace(" ", "") in norm


def parse_sar(text):
    """يستخرج أول رقم من نصّ (يزيل رموز العملة والفواصل وعلامات الاتجاه)."""
    if text is None:
        return None
    norm = text.replace("\u066b", ".").replace("\u066c", ",")
    m = re.search(r"\d[\d,]*(?:\.\d+)?", norm)
    return float(m.group(0).replace(",", "")) if m else None


def cv_metric_state(pg, summary):
    """يعيد True إن كان فحص 'المقاييس' ناجحاً (غير موسوم missing)."""
    pg.evaluate(
        "(t)=>{const e=document.getElementById('cv-f-summary'); e.value=t;"
        "e.dispatchEvent(new Event('input',{bubbles:true}));}", summary)
    pg.evaluate("cvAfterInput()")
    items = pg.eval_on_selector_all(
        "#ats-checks li",
        "els=>els.map(e=>({t:e.textContent, miss:e.classList.contains('missing')}))")
    met = [i for i in items if "أرقام" in i["t"] or "Measurable" in i["t"]]
    if not met:
        return None
    return (not met[0]["miss"])


# ----------------------------------------------------------------------------
# 3) فحوص المتصفّح
# ----------------------------------------------------------------------------
# ----------------------------------------------------------------------------
# 2.1) حجب شبكة الإعلانات داخل الاختبار
# ----------------------------------------------------------------------------
SITE_DIR_URI = INDEX.parent.as_uri()   # file:///D:/Business


def stub_third_party(route):
    """تُكمل طلبات الموقع المحلية فقط، وتُعاد استجابة فارغة لأي طلب خارجي.

    كود Adsterra يُحمَّل ببروتوكول نسبي (//host/...)، وهو الصحيح على HTTPS،
    لكنه على file:// يُفسَّر كمسار UNC فيتعلّق حدث load ثلاثين ثانية.
    هنا نُعيد له استجابة فارغة فوراً: لا شبكة، ولا خطأ في الكونسول.
    """
    if route.request.url.startswith(SITE_DIR_URI):
        return route.continue_()
    return route.fulfill(status=200, body="", content_type="application/javascript")


def browser_checks(headless):
    print("\n== فحوص المتصفّح ==", flush=True)
    from playwright.sync_api import sync_playwright

    errors = []
    with sync_playwright() as pw:
        browser = pw.chromium.launch(channel="chrome", headless=headless)
        ctx = browser.new_context(viewport={"width": 1440, "height": 1000})
        ctx.route("**/*", stub_third_party)
        pg = setup_page(ctx, errors)

        # --- روابط المشاركة: استعادة القيم ثم إزالة معاملات الحساب الحساسة من العنوان.
        share_page = ctx.new_page()
        share_page.on("console", lambda m: errors.append(m.text) if m.type == "error" else None)
        share_page.on("pageerror", lambda e: errors.append("pageerror: %s" % e))
        share_page.goto(INDEX.as_uri() +
                        "?tool=eos&s=6500&y=2&m=0&d=0&ld=0&lb=full&r=resignation#eos-tool",
                        wait_until="load")
        share_page.wait_for_timeout(350)
        eos_restored = share_page.evaluate(
            "()=>({salary:document.getElementById('eos-salary').value,"
            "reason:document.getElementById('eos-reason').value,"
            "search:location.search,hash:location.hash})")
        check("رابط EOS يستعيد الراتب وسبب الاستقالة",
              eos_restored["salary"] == "6500" and eos_restored["reason"] == "resignation",
              repr(eos_restored))
        check("رابط EOS يحذف معاملات الحساب بعد الاستعادة",
              eos_restored["search"] == "" and eos_restored["hash"] == "#eos-tool",
              repr(eos_restored))

        share_page.goto(INDEX.as_uri() +
                        "?tool=sal&b=8500&h=1200&t=500&o=80#salary-tool",
                        wait_until="load")
        share_page.wait_for_timeout(350)
        sal_restored = share_page.evaluate(
            "()=>({basic:document.getElementById('sal-basic').value,"
            "housing:document.getElementById('sal-housing').value,"
            "transport:document.getElementById('sal-transport').value,"
            "obligations:document.getElementById('sal-obligations').value,"
            "search:location.search,hash:location.hash})")
        check("رابط الراتب يستعيد قيم الحساب", sal_restored["basic"] == "8500"
              and sal_restored["housing"] == "1200" and sal_restored["transport"] == "500"
              and sal_restored["obligations"] == "80", repr(sal_restored))
        check("رابط الراتب يحذف معاملات الحساب بعد الاستعادة",
              sal_restored["search"] == "" and sal_restored["hash"] == "#salary-tool",
              repr(sal_restored))
        share_page.close()

        # --- بنية
        dups = pg.evaluate(
            "()=>{const s={},d=[];document.querySelectorAll('[id]')"
            ".forEach(e=>{if(s[e.id])d.push(e.id);s[e.id]=1;});return d;}")
        check("لا معرّفات مكرّرة", dups == [], "مكرّر=%r" % dups)

        # --- EOS: الحالة الافتراضية
        tab(pg, "eos")
        check("EOS افتراضي: إجمالي 17,875.00",
              has_num(pg.text_content("#eos-total-val"), "17875.00"),
              repr(pg.text_content("#eos-total-val")))
        check("EOS افتراضي: مكافأة 14,625.00",
              has_num(pg.text_content("#eos-net-gratuity"), "14625.00"))
        check("EOS افتراضي: إجازة 3,250.00",
              has_num(pg.text_content("#eos-leave-out"), "3250.00"))

        # --- EOS: بدل الإجازة على الأساسي
        setv(pg, "eos-reason", "expiry")
        setv(pg, "eos-salary", "8000")
        setv(pg, "eos-years", "0"); setv(pg, "eos-months", "0"); setv(pg, "eos-days", "0")
        setv(pg, "eos-leave-days", "15")
        setv(pg, "eos-leave-basis", "basic"); setv(pg, "eos-basic", "5000")
        click(pg, "eos-calc-btn")
        check("EOS إجازة على الأساسي 5000 = 2,500.00",
              has_num(pg.text_content("#eos-leave-out"), "2500.00"))
        # بعد إزالة افتراض 75%: الأساس الفارغ يطالب بالقيمة الفعلية ولا يقدّرها.
        setv(pg, "eos-basic", ""); click(pg, "eos-calc-btn")
        _lt = pg.text_content("#eos-leave-out")
        check("EOS أساس فارغ: يطالب بالراتب الأساسي ولا يُخمّن 75%",
              ("الأساسي الفعلي" in _lt) and (not has_num(_lt, "3000.00")),
              repr(_lt))
        setv(pg, "eos-basic", "9000"); click(pg, "eos-calc-btn")
        _lt2 = pg.text_content("#eos-leave-out")
        check("EOS أساس أكبر من الأجر: تنبيه لمراجعة القيم",
              "أكبر من آخر أجر" in _lt2, repr(_lt2))

        # --- EOS: حدود المادة 85 (سبب «استقالة») + حالتا المادتين 80 و87
        def _ratio(reason, y, m, d, salary=6500):
            setv(pg, "eos-reason", reason)
            setv(pg, "eos-salary", str(salary))
            setv(pg, "eos-years", str(y))
            setv(pg, "eos-months", str(m))
            setv(pg, "eos-days", str(d))
            click(pg, "eos-calc-btn")
            return pg.text_content("#eos-ratio-out").strip()

        for _lbl, _r, _y, _m, _d, _exp in (
            ("1س11ش → 0%",                    "resignation",  1, 11, 0, "0% (أقل من سنتين)"),
            ("2س بالضبط → الثلث",              "resignation",  2,  0, 0, "33.33% (الثلث)"),
            ("4س11ش → الثلث",                  "resignation",  4, 11, 0, "33.33% (الثلث)"),
            ("5س بالضبط → الثلث لا الثلثان",   "resignation",  5,  0, 0, "33.33% (الثلث)"),
            ("5س + يوم → الثلثان",             "resignation",  5,  0, 1, "66.67% (الثلثان)"),
            ("5س1ش → الثلثان",                 "resignation",  5,  1, 0, "66.67% (الثلثان)"),
            ("9س11ش → الثلثان",                "resignation",  9, 11, 0, "66.67% (الثلثان)"),
            ("10س بالضبط → 100%",              "resignation", 10,  0, 0, "100% (خدمة 10 سنوات فأكثر)"),
            ("مادة 80 → لا مكافأة",            "art80",        3,  0, 0, "0% (بدون استحقاق)"),
            ("قوة قاهرة (87) → 100%",          "force",        3,  0, 0, "100% (استحقاق كامل)"),
            ("العاملة: زواج خلال 6 أشهر (87) → 100%", "marriage", 3, 0, 0, "100% (استحقاق كامل)"),
            ("مادة 81 (3س) → 100% لا استقالة",  "art81",        3,  0, 0, "100% (استحقاق كامل)"),
            ("مادة 81 تحت سنتين → 100% بلا عتبة 85", "art81",    1, 11, 0, "100% (استحقاق كامل)"),
        ):
            _got = _ratio(_r, _y, _m, _d)
            check("EOS حدّ: " + _lbl, _got == _exp, "%r ≠ %r" % (_got, _exp))

        # المادة 81 في المحرك: مكافأة كاملة مساوية لحالة انتهاء عادية، ومخالفة
        # لحالة الاستقالة (صفر) عند المدة نفسها تحت السنتين — لا عتبة ولا نِسَب 85.
        def _net(reason, y, m, d, salary=6500):
            setv(pg, "eos-reason", reason)
            setv(pg, "eos-salary", str(salary))
            setv(pg, "eos-years", str(y))
            setv(pg, "eos-months", str(m))
            setv(pg, "eos-days", str(d))
            click(pg, "eos-calc-btn")
            return pg.text_content("#eos-net-gratuity").strip()

        _n81 = _net("art81", 1, 11, 0)
        _n_exp = _net("expiry", 1, 11, 0)
        _n_res = _net("resignation", 1, 11, 0)
        check("EOS: المادة 81 = استحقاق كامل لا نسب استقالة (1س11ش)",
              (_n81 == _n_exp) and (_n81 != _n_res) and has_num(_n_res, "0.00"),
              "art81=%r expiry=%r resignation=%r" % (_n81, _n_exp, _n_res))

        # تعويض المادة 77: الأداة لا تُدخل ولا تُصدر أي تعويض منفصل، وإجمالي التصفية
        # عند اختيار art81 = صافي المكافأة + بدل الإجازات فقط (بلا قيمة مضافة).
        # نُعيد أساس الإجازة إلى "الأجر الكامل" (الافتراضي) لأن اختبارات سابقة
        # تركت الأساس "basic" بقيمة أكبر من الأجر فلا يحسب المحرّك بدل الإجازة.
        setv(pg, "eos-leave-basis", "full")
        _net("art81", 1, 11, 0)  # يُعيد العرض إلى حالة art81 بأساس إجازة صالح
        _tot81 = parse_sar(pg.text_content("#eos-total-val"))
        _net81 = parse_sar(pg.text_content("#eos-net-gratuity"))
        _lev81 = parse_sar(pg.text_content("#eos-leave-out"))
        _art77_dom = pg.eval_on_selector_all(
            "#eos-tool [id*='77'], #eos-tool [id*='judicial'], "
            "#eos-tool [id*='compensation']",
            "els=>els.length")
        check("EOS: art81 لا يضيف تعويض مادة 77 — الإجمالي = مكافأة + إجازات",
              (_tot81 is not None and _net81 is not None and _lev81 is not None
               and abs(_tot81 - (_net81 + _lev81)) < 0.01) and _art77_dom == 0,
              "total=%r net=%r leave=%r art77_dom=%r"
              % (_tot81, _net81, _lev81, _art77_dom))

        # --- GOSI
        tab(pg, "salary")
        for cat, emp, er, known in (("new2026", "671.88", "796.88", None),
                                    ("legacy", "609.38", "734.38", None),
                                    ("expat", "0.00", "125.00", None)):
            setv(pg, "sal-category", cat)
            setv(pg, "sal-basic", "5000"); setv(pg, "sal-housing", "")
            setv(pg, "sal-transport", "0"); setv(pg, "sal-obligations", "0")
            click(pg, "sal-calc-btn")
            check("GOSI %s: استقطاع الموظف %s" % (cat, emp),
                  has_num(pg.text_content("#sal-gosi-out"), emp),
                  repr(pg.text_content("#sal-gosi-out")), known=known)
            check("GOSI %s: حصة صاحب العمل %s" % (cat, er),
                  has_num(pg.text_content("#sal-gosi-er-out"), er),
                  repr(pg.text_content("#sal-gosi-er-out")), known=known)

        # --- المشاركة
        tab(pg, "eos")
        setv(pg, "eos-reason", "resignation")
        setv(pg, "eos-salary", "6500")
        setv(pg, "eos-leave-basis", "basic"); setv(pg, "eos-basic", "5000")
        click(pg, "eos-calc-btn"); click(pg, "eos-share")
        pg.wait_for_timeout(250)
        preview = pg.text_content("#share-preview") or ""
        pg.keyboard.press("Escape"); pg.wait_for_timeout(120)
        m = re.search(r"file:///\S+", preview)
        link = m.group(0) if m else ""
        check("رابط المشاركة يحمل bs=5000", "bs=5000" in preview)
        check("رابط المشاركة يحمل r=resignation",
              "r=resignation" in preview, link)

        # --- الاستعادة من الرابط في سياق نظيف (بلا localStorage مشترك)
        ctx2 = browser.new_context(viewport={"width": 1280, "height": 900})
        ctx2.route("**/*", stub_third_party)
        if m:
            pg2 = ctx2.new_page()
            pg2.goto(m.group(0), wait_until="load"); pg2.wait_for_timeout(300)
            reason = pg2.eval_on_selector("#eos-reason", "e=>e.value")
            basic = pg2.eval_on_selector("#eos-basic", "e=>e.value")
            salary = pg2.eval_on_selector("#eos-salary", "e=>e.value")
            check("الرابط يعيد سبب الاستقالة", reason == "resignation", repr(reason))
            check("الرابط يعيد eos-basic", basic == "5000", repr(basic))
            check("الرابط يعيد الراتب", salary == "6500", repr(salary))
            pg2.close()
        else:
            record(FAIL, "استخراج رابط المشاركة", "لم يُعثر على رابط file://")
        ctx2.close()

        # --- السيرة: فحص المقاييس (قبل تعبئة المثال، ليكون السياق نظيفاً)
        tab(pg, "cv")
        m2000 = cv_metric_state(pg, "حقّقت وفرة مالية قدرها 2000 ريال خلال العام")
        check("مقاييس السيرة: تُقبل '2000 ريال'", m2000 is True, "state=%r" % m2000)
        m1500 = cv_metric_state(pg, "خفّضت الكلفة بمقدار 1500 ريال خلال الربع")
        check("مقاييس السيرة: تُقبل '1500 ريال'", m1500 is True, "state=%r" % m1500)
        mpct = cv_metric_state(pg, "رفعت الإنتاجية بمقدار 25% خلال العام")
        check("مقاييس السيرة: تُقبل '25%'", mpct is True, "state=%r" % mpct)
        myear = cv_metric_state(pg, "أدرت مشروع تطوير التقنية عام 2019 بنجاح")
        check("مقاييس السيرة: تُرفض السنة المجرّدة '2019'", myear is False, "state=%r" % myear)

        # --- السيرة: علامة الفاصلة ظاهرة في حقول الوسوم الثلاثة
        _hint = pg.evaluate(
            "()=>['cv-f-skills','cv-f-certs','cv-f-langs'].map(f=>{"
            "const i=document.getElementById(f);"
            "const s=i&&i.parentElement?i.parentElement.querySelector('small.field-hint'):null;"
            "const l=document.querySelector('label[for=\"'+f+'\"]');"
            "return {hint:s?s.textContent.trim():'',label:l?l.textContent.trim():''};})")
        check("السيرة: تلميح الفاصلة في الحقول الثلاثة ورمزها داخل التسمية",
              len(_hint) == 3
              and all(h["hint"] for h in _hint)
              and all("،" in h["label"] for h in _hint),
              repr(_hint))

        # --- السيرة: ترويسة بلا تسرّب لوني (بعد تعبئة المثال)
        click(pg, "cv-demo"); pg.wait_for_timeout(250)
        style = pg.evaluate(
            "()=>{const h=document.querySelector('.cv-doc .cvd-head');"
            "const d=document.querySelector('.cv-doc'); if(!h) return null;"
            "const cs=getComputedStyle(h), cd=getComputedStyle(d);"
            "return {tag:h.tagName, bg:cs.backgroundImage, sh:cs.boxShadow, doc:cd.backgroundColor};}")
        check("ترويسة السيرة مولَّدة كـ<header>", bool(style) and style.get("tag") == "HEADER",
              repr(style))
        check("ترويسة السيرة بلا خلفية صورة/ظل",
              bool(style) and style.get("bg") == "none" and style.get("sh") == "none",
              repr(style))
        check("ورقة السيرة بيضاء", bool(style) and style.get("doc") == "rgb(255, 255, 255)",
              repr(style))

        # --- التبويبات: نقر + hash
        tab(pg, "cv")
        check("نقر التبويب يبدّل القسم",
              pg.eval_on_selector(".tool-section.active", "e=>e.id") == "cv-tool")
        check("نقر التبويب يضبط الـhash", pg.evaluate("location.hash") == "#cv-tool")

        # --- التبويبات: لوحة المفاتيح (Home/End + أسهم RTL)
        pg.eval_on_selector("#main-tabs", "e=>e.focus()")
        pg.keyboard.press("Home"); pg.wait_for_timeout(120)
        check("Home يذهب لأول تبويب",
              pg.eval_on_selector(".tool-section.active", "e=>e.id") == "eos-tool")
        pg.keyboard.press("End"); pg.wait_for_timeout(120)
        check("End يذهب لآخر تبويب",
              pg.eval_on_selector(".tool-section.active", "e=>e.id") == "cv-tool")
        pg.keyboard.press("Home"); pg.wait_for_timeout(120)
        pg.keyboard.press("ArrowLeft"); pg.wait_for_timeout(120)  # RTL: التالي
        check("سهم RTL الأيسر = التبويب التالي",
              pg.eval_on_selector(".tool-section.active", "e=>e.id") == "salary-tool")
        pg.keyboard.press("ArrowRight"); pg.wait_for_timeout(120)  # RTL: السابق
        check("سهم RTL الأيمن = التبويب السابق",
              pg.eval_on_selector(".tool-section.active", "e=>e.id") == "eos-tool")

        # --- روابط التذييل (#tool)
        tab(pg, "cv")
        pg.evaluate("document.querySelector('footer a[href=\"#eos-tool\"]').click()")
        pg.wait_for_timeout(250)
        check("رابط التذييل #eos-tool يبدّل التبويب",
              pg.eval_on_selector(".tool-section.active", "e=>e.id") == "eos-tool",
              "hash=%s" % pg.evaluate("location.hash"), known=3)

        # --- الإتاحة/السيو المعلّقة
        pg.evaluate("document.getElementById('lang-btn').click()"); pg.wait_for_timeout(300)
        check("نص إخلاء المسؤولية يحافظ على التنسيق بعد تغيير اللغة",
              pg.evaluate("!!document.querySelector('.disclaimer-banner .inner strong')"))
        aria = pg.eval_on_selector("#theme-btn", "e=>e.getAttribute('aria-label')")
        check("aria-label لزر المظهر مترجم", aria is not None and "للمظهر" not in aria
              and "المظهر" not in aria, "aria=%r" % aria)
        pg.evaluate("document.getElementById('lang-btn').click()"); pg.wait_for_timeout(300)

        check("لا يوجد meta keywords",
              pg.evaluate("document.querySelectorAll('meta[name=keywords]').length") == 0)
        check("theme-color له نسخة ليلية",
              pg.evaluate("document.querySelectorAll('meta[name=theme-color][media]').length") >= 1)
        pg.evaluate("applyTheme('dark')")
        check("theme-color يتبع المظهر الداكن المختار",
              pg.evaluate("document.getElementById('theme-color-dark').media === 'all' && document.getElementById('theme-color-light').media === 'not all'"))
        pg.evaluate("applyTheme('light')")
        check("دعم تقليل الحركة موجود",
              pg.evaluate("document.querySelector('style').textContent.includes('prefers-reduced-motion: reduce')"))
        check("يوجد data-i18n-html لنصوص الإخلاء",
              pg.evaluate("document.querySelectorAll('[data-i18n-html]').length") >= 1)
        check("رابط مشاركة X يستخدم x.com intent",
              pg.evaluate("Array.from(document.scripts).some(s => s.textContent.includes('https://x.com/intent/tweet')) && !Array.from(document.scripts).some(s => s.textContent.includes('https://twitter.com/intent/tweet'))"))
        check("حاوية #ad-top محذوفة",
              pg.evaluate("document.querySelectorAll('#ad-top').length") == 0)
        check("زر .btn-ad محذوف",
              pg.evaluate("document.querySelectorAll('.btn-ad').length") == 0)

        # --- الأرقام الهندية
        tab(pg, "eos")
        setv(pg, "eos-salary", "\u0666\u0665\u0660\u0660")  # ٦٥٠٠
        setv(pg, "eos-years", "0"); setv(pg, "eos-months", "0"); setv(pg, "eos-days", "0")
        setv(pg, "eos-leave-days", "15")
        setv(pg, "eos-leave-basis", "full")
        click(pg, "eos-calc-btn")
        check("مدخل الراتب يقبل الأرقام المحلية",
              pg.eval_on_selector("#eos-salary", "e=>e.type === 'text' && e.inputMode === 'decimal'"))
        check("تقبل الأرقام الهندية (٦٥٠٠ ⇒ 3250 إجازة)",
              has_num(pg.text_content("#eos-leave-out"), "3250.00"),
              repr(pg.text_content("#eos-leave-out")))

        # --- الحفظ المحلي
        keys = pg.evaluate("Object.keys(localStorage)")
        check("مفتاح seh_inputs_v2 موجود", "seh_inputs_v2" in keys, repr(keys))

        # --- خصوصية مشاركة السيرة: لا تُشارَك بيانات شخصية (اسم/جوال/بريد)
        tab(pg, "cv")
        click(pg, "cv-demo"); pg.wait_for_timeout(300)
        person = pg.evaluate(
            "()=>{const g=id=>{const e=document.getElementById(id);return e?(e.value||''):'';};"
            "const o=document.getElementById('cv-output');const s=document.getElementById('ats-score-text');"
            "return {name:g('cv-f-name'),phone:g('cv-f-phone'),email:g('cv-f-email'),"
            "cv:o?(o.textContent||''):'',score:s?(s.textContent||''):''};}")
        click(pg, "cv-share"); pg.wait_for_timeout(250)
        cvprev = pg.text_content("#share-preview") or ""
        pg.keyboard.press("Escape"); pg.wait_for_timeout(150)
        check("السيرة: المخرجات الكاملة تحتوي بيانات شخصية (شرط اختبار ذي معنى)",
              bool(person["name"].strip()) and person["name"].strip() in person["cv"],
              "name=%r" % person["name"])
        _leaked = [k for k in ("name", "phone", "email")
                   if person[k].strip() and person[k].strip() in cvprev]
        check("مشاركة السيرة: لا تسريب للاسم أو الجوال أو البريد", not _leaked,
              "leaked=%r" % _leaked)
        check("مشاركة السيرة: تعرض درجة ATS",
              bool(person["score"].strip()) and person["score"].strip() in cvprev,
              repr(cvprev[:140]))

        # --- قسم الأدلة: موجود، بحالة واضحة، وبلا روابط غير موثوقة
        guides = pg.evaluate(
            "()=>{const box=document.getElementById('guides-list');"
            "return {exists:!!box, text:box?(box.textContent||''):'',"
            " links:document.querySelectorAll('#guides-list a').length};}")
        check("قسم الأدلة موجود أسفل الأدوات", guides["exists"] is True)
        check("قسم الأدلة: رسالة واضحة عند تعذّر التحميل",
              len(guides["text"].strip()) > 10, repr(guides["text"][:80]))
        check("قسم الأدلة: لا روابط غير موثوقة", guides["links"] == 0,
              "links=%d" % guides["links"])

        # --- الأخطاء في الكونسول (يُسمح بأخطاء الشبكة المحجوبة فقط)
        real = [e for e in errors if "ERR_FAILED" not in e and "ERR_BLOCKED" not in e
                and "Failed to load resource" not in e]
        check("لا أخطاء جافاسكربت في الكونسول", not real, repr(real[:3]))

        browser.close()


# ----------------------------------------------------------------------------
def main():
    ap = argparse.ArgumentParser(description="اختبار دخان لمنصة ksatools")
    ap.add_argument("--strict", action="store_true",
                    help="اعتبر بنود BACKLOG غير المنفّذة فشلاً أيضاً")
    ap.add_argument("--headful", action="store_true", help="شغّل المتصفّح بشكل مرئي")
    args = ap.parse_args()

    print("اختبار الدخان — %s" % INDEX)
    if INDEX.exists():
        h = hashlib.sha256(INDEX.read_bytes()).hexdigest().upper()[:16]
        print("الحجم=%d بايت · SHA256[:16]=%s" % (INDEX.stat().st_size, h))

    static_checks()
    try:
        browser_checks(headless=not args.headful)
    except ImportError:
        print("\n[SKIP] Playwright غير مثبّت — تخطّي فحوص المتصفّح "
              "(python -m pip install playwright)", flush=True)
    except Exception as exc:  # noqa: BLE001
        record(FAIL, "تشغيل فحوص المتصفّح", "%s: %s" % (type(exc).__name__, exc))

    n_pass = sum(1 for s, _, _, _ in results if s == PASS)
    n_fail = sum(1 for s, _, _, _ in results if s == FAIL)
    n_xfail = sum(1 for s, _, _, _ in results if s == XFAIL)

    print("\n== الخلاصة ==")
    print("PASS=%d  FAIL=%d  FAIL(known)=%d" % (n_pass, n_fail, n_xfail))
    if n_xfail:
        print("بنود BACKLOG غير المنفّذة: %s" %
              ", ".join("#%s" % k for k in sorted(
                  {k for s, _, _, k in results if s == XFAIL and k is not None},
                  key=lambda x: int(x))))
    bad = n_fail + (n_xfail if args.strict else 0)
    print("الحالة: %s" % ("ناجح" if bad == 0 else "فاشل (%d)" % bad))
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
