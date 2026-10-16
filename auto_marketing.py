#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
auto_marketing.py — KSA Tools | مولّد ومُدير مقالات ثنائية اللغة + أرشفة + منشورات تسويقية.

مكتبات Python القياسية فقط (بلا حزم خارجية)، والاتصال بمزوّد المحتوى عبر HTTP مباشرة
(Groq هو الافتراضي — خطة مجانية — وGemini اختياري بتحديد صريح).

التشغيل:
    python auto_marketing.py --selftest          # اختبارات داخلية بلا شبكة ولا API
    python auto_marketing.py --dry-run           # دورة كاملة بمحتوى تجريبي بلا كتابة
    python auto_marketing.py --verify            # فحص ملفات الموقع/الأرشفة فقط
    python auto_marketing.py                     # دورة واحدة (الافتراضي: draft + groq)
    python auto_marketing.py --provider gemini   # اختيار صريح للمزوّد (بلا انتقال تلقائي)
    PUBLISH_MODE=auto python auto_marketing.py   # نشر تلقائي بعد اجتياز كل البوابات

متغيّرات البيئة (لا تُطبع قيمها في السجل أبداً):
    AI_PROVIDER (groq|gemini، الافتراضي groq),
    GROQ_API_KEY, GROQ_MODEL (افتراضي: openai/gpt-oss-20b),
    GEMINI_API_KEY, GEMINI_MODEL (افتراضي: gemini-3.8-flash، اختياري — يُستعمل مع AI_PROVIDER=gemini فقط),
    TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID,
    PUBLISH_MODE (draft|auto، الافتراضي draft),
    SOCIAL_LANGUAGE (ar|en|both، الافتراضي both),
    DRAFT_DIR (مسار المسودات، الافتراضي drafts/)

مزوّدو المحتوى:
    Groq هو الافتراضي (‎/v1/chat/completions مع response_format=json_object)، وGemini خيار
    صريح. لا يوجد انتقال تلقائي بين المزوّدين: فشل المزوّد المحدَّد يُنهي الدورة بفشل واضح
    ولا يُرسل أي طلب إلى المزوّد الآخر. مخرجات المزوّد تمرّ على البوابات نفسها بلا استثناء
    (validate_article + duplicate_check + فحص المصادر الرسمية قبل النشر).

حالة التسويق (marketing_state.json):
    ملف محلي (مُتجاهَل في Git) يحفظ تقدّم المواضيع. في GitHub Actions يُحفظ عبر Cache،
    والـCache غير دائم وقد يُحذف (إخلاء بعد فترة عدم استخدام، أو تجاوز سعة التخزين،
    أو فشل التنزيل)، لذا يتعامل النظام مع غياب الملف أو تلفه بأمان: من دون الأسرار،
    ويعود إلى الحالة الافتراضية. ولأن اختيار الموضوع يعتمد على سجل النشر الدائم
    (articles.json) لا على الحالة وحدها، ففقدان الحالة لا يكرّر موضوعاً مكتمل النشر،
    وتُصلَح الحالة تلقائياً من السجل في بداية كل دورة (مع الإبقاء على المحاولات).

النشر الآمن (وضع auto):
    تُجهَّز صفحات المقالات في مجلد مؤقت، ثم تُفحص HTML وarticles.json وsitemap.xml،
    ولا يُنقل شيء إلى الملفات العامة ولا يُدفع إلا بعد نجاح كل الفحوص.

رموز الخروج:
    0 = نجاح، أو حالة متوقّعة أُديرت بأمان (لا مواضيع متاحة، النسختان منشورتان سابقاً،
        فشل جزئي تُكتب فيه مسودة واحدة بلا نشر، وأخطاء تُدار دون كتابة).
    1 = خطأ داخلي غير متوقّع، أو فشل في --selftest / --verify.
    2 = فشل توليد المحتوى: لم تنتج الدورة أي نسخة صالحة (EXIT_GENERATION_FAILED)
        — لا مسودات ولا نشر، ويُحفظ `attempts` فقط.
    3 = فشل الإعداد: مفتاح المزوّد المحدَّد غير مضبوط (EXIT_CONFIG_FAILED)
        — GROQ_API_KEY لمزوّد groq أو GEMINI_API_KEY لمزوّد gemini.
        لا محاولة تُستهلك، ولا ملف يُكتب، ولا نداء شبكة.

الإعادة عند أخطاء المزوّد المؤقّتة:
    يُعاد الطلب عند 408/425/500/502/503/504 وعند 429 المؤقّت (تجاوز معدّل) بحدّ أقصى
    GEMINI_MAX_TRIES = 4 محاولات لكل نسخة لغوية، بتراجع تصاعدي 2/4/8s (سقف 30s) وباحترام
    Retry-After كرقم ثوانٍ فقط. ولا يُعاد إطلاقاً عند 401/403 (مصادقة)، أو نموذج غير متاح،
    أو 429 يشير إلى حصة يومية/فوترة (تكراره بلا فائدة). الإعادة ليست محاولة موضوع
    جديدة ولا تزيد MAX_ATTEMPTS.
"""

from __future__ import annotations

import argparse
import hashlib
import html
import json
import os
import re
import shutil
import sys
import tempfile
import time
import urllib.error
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from pathlib import Path
from string import Template

try:  # لتفادي مشاكل ترميز الطرفية على ويندوز
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:  # noqa: BLE001
    pass


# =====================================================================================
# 1) ثوابت المشروع
# =====================================================================================

BASE_DIR = Path(__file__).resolve().parent
SITE_BASE = "https://ksatools.github.io"

ARTICLES_JSON = BASE_DIR / "articles.json"
SITEMAP_XML = BASE_DIR / "sitemap.xml"
STATE_JSON = BASE_DIR / "marketing_state.json"
SOCIAL_TXT = BASE_DIR / "latest_social_post.txt"
ARTICLES_DIR = BASE_DIR / "articles"
DRAFTS_DIR = Path(os.environ.get("DRAFT_DIR") or (BASE_DIR / "drafts"))

LOG_PREFIX = "[auto_marketing]"

SITEMAP_NS = "http://www.sitemaps.org/schemas/sitemap/0.9"
XHTML_NS = "http://www.w3.org/1999/xhtml"

# أكواد الإعلان المعتمدة (تُدرج مرة واحدة في كل صفحة).
# نطاق المالك المعتمد: bauval.org — مطابق لما في index.html. لا تغيّره منفرداً.
AD_SOCIAL_BAR = (
    '<script data-cfasync="false" '
    'src="https://bauval.org/14/7cdd0a31b4560a6ce3906a22a43c5ed3"></script>'
)
AD_NATIVE_BANNER = (
    '<script async="async" data-cfasync="false" '
    'src="https://bauval.org/21/7af3b8325dba6708da88eed5e517ec89"></script>\n'
    '<div id="container-7af3b8325dba6708da88eed5e517ec89"></div>'
)
AD_SOCIAL_BAR_SRC = "https://bauval.org/14/7cdd0a31b4560a6ce3906a22a43c5ed3"
AD_NATIVE_BANNER_SRC = "https://bauval.org/21/7af3b8325dba6708da88eed5e517ec89"
AD_CONTAINER_ID = "container-7af3b8325dba6708da88eed5e517ec89"
LEGACY_AD_HOST = "pl25967834.profitablecpmrate.com"

TOOL_ANCHOR = {"eos": "eos-tool", "salary": "salary-tool", "letter": "letter-tool", "cv": "cv-tool"}
TOOL_LABEL = {
    "eos": ("حاسبة مكافأة نهاية الخدمة", "End-of-Service Benefits Calculator"),
    "salary": ("حاسبة صافي الراتب والتأمينات", "Net Salary & GOSI Calculator"),
    "letter": ("مولّد الخطابات الرسمية", "Official Letter Generator"),
    "cv": ("منسّق السيرة الذاتية وفاحص ATS", "Resume Builder & ATS Checker"),
}

# النطاقات المسموح بها للمصادر الرسمية
ALLOWED_SOURCE_SUFFIXES = (".gov.sa",)
ALLOWED_SOURCE_HOSTS = {"qiwa.sa", "www.qiwa.sa"}

MIN_WORDS = {"ar": 250, "en": 250}
MIN_SECTIONS = 3
MAX_SECTIONS = 12
MIN_TOTAL_CHARS = 1200
MAX_ATTEMPTS = 3

# سياسة إعادة المحاولة عند استدعاء مزوّد المحتوى (Groq/Gemini): أخطاء مؤقّتة فقط.
#   408/425 = انتهاء مهلة أو طلب مبكّر، 429 = تجاوز المعدّل، 5xx = خلل مؤقّت عند المزوّد.
#   503 (UNAVAILABLE) هو الأكثر وقوعاً: «النموذج يواجه طلباً مرتفعاً حالياً».
RETRYABLE_STATUS = frozenset({408, 425, 429, 500, 502, 503, 504})
# حدّ أعلى صريح: المحاولة الأولى + 3 إعادات = 4 محاولات كحدّ أقصى لكل نسخة لغوية.
# الإعادة الداخلية ليست محاولة موضوع جديدة ولا دورة تسويق جديدة: عدّاد `attempts`
# يُزاد مرة واحدة لكل دورة في run_once، لا لكل نداء شبكة.
GEMINI_MAX_TRIES = 4
GEMINI_BACKOFF_BASE = 2.0   # ثانية — الانتظار يتضاعف: 2s, 4s, 8s …
GEMINI_BACKOFF_MAX = 30.0   # سقف الانتظار بين محاولتين
# رمز خروج مميّز لفشل توليد المحتوى (لا نجاح مضلّل)، ويوقف كل خطوات النشر بعده.
EXIT_GENERATION_FAILED = 2
# رمز خروج مميّز لفشل الإعداد (غياب مفتاح المزوّد): لا توليد ولا نشر ولا استهلاك محاولات.
EXIT_CONFIG_FAILED = 3

# ---------------------------------------------------------------------------------
# مزوّدو المحتوى: Groq هو الافتراضي (خطة مجانية)، وGemini خيار صريح.
# لا انتقال تلقائي بين المزوّدين عند الفشل (منعاً لطلبات غير مقصودة للمزوّد الآخر).
AI_PROVIDERS = ("groq", "gemini")
DEFAULT_PROVIDER = "groq"

GROQ_URL = "https://api.groq.com/openai/v1/chat/completions"
DEFAULT_GROQ_MODEL = "openai/gpt-oss-20b"
DEFAULT_MODEL = "gemini-3.8-flash"        # افتراضي Gemini (توافق خلفي مع الاسم القديم)

PROVIDER_KEY_ENV = {"groq": "GROQ_API_KEY", "gemini": "GEMINI_API_KEY"}
PROVIDER_MODEL_ENV = {"groq": "GROQ_MODEL", "gemini": "GEMINI_MODEL"}
PROVIDER_DEFAULT_MODEL = {"groq": DEFAULT_GROQ_MODEL, "gemini": DEFAULT_MODEL}

# رسائل تدلّ على أن النموذج غير متاح: العِلاج تغيير النموذج لا إعادة الطلب.
MODEL_STOP_HINTS = (
    "model_not_found", "model does not exist", "model not found",
    "decommissioned", "no longer supported", "unknown model", "invalid model",
)
# رسائل تدلّ على حصة يومية أو مشكلة فوترة: تكرار الطلب بلا فائدة (خلاف تجاوز المعدّل اللحظي).
QUOTA_STOP_HINTS = (
    "requests per day", "per day", "daily limit", "daily quota",
    "insufficient_quota", "exceeded your current quota", "check your plan",
    "billing", "payment required",
)

# نقطة استبدال للاختبارات: نصمت الانتظار الحقيقي في الاختبار الذاتي.
SLEEP = time.sleep

UA = "KSA-Tools-Bot/1.0 (+https://ksatools.github.io/)"

DISCLAIMER_AR = (
    "هذا المحتوى إرشادي وتعليمي عام، ولا يُعدّ استشارة قانونية. "
    "قد تتغيّر الأنظمة واللوائح، وقد تختلف النتائج بحسب تفاصيل كل حالة. "
    "للاستفسارات الرسمية راجع الجهات المختصّة أو مستشاراً قانونياً."
)
DISCLAIMER_EN = (
    "This content is general guidance for information only and is not legal advice. "
    "Regulations may change and outcomes depend on the facts of each case. "
    "For official matters, consult the competent authority or a qualified legal professional."
)


# =====================================================================================
# 2) أدوات مساعدة
# =====================================================================================

def log(msg) -> None:
    print(f"{LOG_PREFIX} {msg}", flush=True)


def redact(text) -> str:
    """إخفاء أي سرّ قد يظهر داخل رسالة خطأ (مفاتيح كل المزوّدين + تلغرام)."""
    if not text:
        return ""
    out = str(text)
    for var in ("GEMINI_API_KEY", "GROQ_API_KEY", "TELEGRAM_BOT_TOKEN", "TELEGRAM_CHAT_ID"):
        val = os.environ.get(var, "")
        if val and len(val) >= 6:
            out = out.replace(val, "***")
    out = re.sub(r"(?i)(key|token|api[_-]?key)=[^&\s\"']+", r"\1=***", out)
    out = re.sub(r"/bot\d+:[A-Za-z0-9_\-]+", "/bot***", out)
    return out


def today_iso() -> str:
    return datetime.now(timezone.utc).date().isoformat()


def esc(value) -> str:
    return html.escape("" if value is None else str(value), quote=True)


def load_json(path: Path, default):
    if not path.exists():
        return default
    try:
        with path.open("r", encoding="utf-8") as fh:
            return json.load(fh)
    except (OSError, ValueError) as exc:
        log(f"[WARN] تعذّر قراءة {path.name}: {redact(exc)} — سيُستخدم الافتراضي.")
        return default


def atomic_write_text(path: Path, text: str) -> None:
    """كتابة ذرّية: ملف مؤقت ثم استبدال، حتى لا يُفقد ملف قائم عند الفشل."""
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + ".tmp")
    with tmp.open("w", encoding="utf-8", newline="\n") as fh:
        fh.write(text)
    os.replace(tmp, path)


def atomic_write_json(path: Path, data) -> None:
    atomic_write_text(path, json.dumps(data, ensure_ascii=False, indent=2) + "\n")


def slug_ok(slug: str) -> bool:
    return bool(re.fullmatch(r"[a-z0-9]+(?:-[a-z0-9]+)*", slug or "")) and len(slug) <= 80


def strip_ws(value) -> str:
    return re.sub(r"[ \t]+", " ", "" if value is None else str(value)).strip()


def word_count(text) -> int:
    return len([w for w in re.split(r"\s+", strip_ws(text)) if w])


def has_arabic(text) -> bool:
    return bool(re.search(r"[\u0600-\u06FF]", text or ""))


def latin_ratio(text) -> float:
    letters = [c for c in (text or "") if c.isalpha()]
    if not letters:
        return 0.0
    return sum(1 for c in letters if ord(c) < 128) / len(letters)


def looks_like_html(value) -> bool:
    return bool(re.search(r"<\s*/?\s*[a-zA-Z!][^>]*>", value or ""))


def has_dangerous_scheme(value) -> bool:
    return bool(re.search(r"(javascript|vbscript|data|file)\s*:", value or "", re.I))


def collapse_paragraphs(body: str) -> list:
    parts = re.split(r"\n\s*\n", body or "")
    return [re.sub(r"\s*\n\s*", " ", p).strip() for p in parts if p.strip()]


def sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


# =====================================================================================
# 2) قائمة المواضيع (30 موضوعاً — نقطة بداية قابلة للتوسيع)
# =====================================================================================

def _t(tid, ar, en, tool):
    return {"id": tid, "title_ar": ar, "title_en": en, "tool": tool}


TOPICS = [
    _t("eosb-basics", "حساب مكافأة نهاية الخدمة في السعودية", "Saudi End-of-Service Benefits: How They Are Calculated", "eos"),
    _t("eosb-resignation", "حساب مكافأة نهاية الخدمة عند الاستقالة", "End-of-Service Benefits on Resignation in Saudi Arabia", "eos"),
    _t("labor-art84", "شرح المادة 84 من نظام العمل السعودي", "Article 84 of the Saudi Labour Law Explained", "eos"),
    _t("labor-art85", "شرح المادة 85 من نظام العمل السعودي", "Article 85 of the Saudi Labour Law Explained", "eos"),
    _t("eosb-full-entitlement", "حالات الاستحقاق الكامل لمكافأة نهاية الخدمة", "When End-of-Service Benefits Are Payable in Full", "eos"),
    _t("rights-contract-end", "حقوق الموظف عند انتهاء العقد", "Employee Rights When a Contract Ends", "eos"),
    _t("rights-employer-termination", "حقوق العامل عند إنهاء العقد من صاحب العمل", "Rights When the Employer Terminates the Contract", "eos"),
    _t("labor-art81", "حالات ترك العمل وفق المادة 81", "Leaving Work Under Article 81 of the Saudi Labour Law", "eos"),
    _t("labor-art80", "الحرمان من مكافأة نهاية الخدمة وفق المادة 80", "Forfeiting End-of-Service Benefits Under Article 80", "eos"),
    _t("annual-leave-balance", "حساب رصيد الإجازات السنوية غير المستخدمة", "Calculating Your Unused Annual Leave Balance", "eos"),
    _t("daily-monthly-wage", "كيفية حساب الأجر اليومي والشهري", "How Daily and Monthly Wages Are Calculated", "salary"),
    _t("wage-definition", "تعريف الراتب والأجر في نظام العمل", "Defining Wage and Salary Under the Saudi Labour Law", "salary"),
    _t("letter-leave-request", "طريقة صياغة خطاب طلب إجازة", "How to Write a Leave Request Letter", "letter"),
    _t("letter-resignation", "طريقة كتابة خطاب استقالة احترافي", "How to Write a Professional Resignation Letter", "letter"),
    _t("letter-work-start", "طريقة إعداد خطاب مباشرة عمل", "How to Prepare a Work Commencement Letter", "letter"),
    _t("cv-saudi-market", "كيفية كتابة سيرة ذاتية للسوق السعودي", "Writing a Resume for the Saudi Job Market", "cv"),
    _t("cv-ats-optimization", "تحسين السيرة الذاتية لأنظمة ATS", "Optimising Your Resume for ATS Screening", "cv"),
    _t("cv-common-mistakes", "الأخطاء الشائعة في السيرة الذاتية", "Common Resume Mistakes to Avoid", "cv"),
    _t("letter-cover-letter", "كيفية كتابة خطاب تغطية وظيفي", "How to Write a Job Cover Letter", "letter"),
    _t("gosi-overview", "التأمينات الاجتماعية للسعوديين والمقيمين", "GOSI Social Insurance for Saudis and Expats", "salary"),
    _t("basic-vs-actual-wage", "الفرق بين الأساسي والأجر الفعلي في حساب الحقوق", "Basic Wage vs Actual Wage in Entitlement Calculations", "salary"),
    _t("payslip-reading", "كيفية قراءة مسير الراتب", "How to Read Your Payslip", "salary"),
    _t("gosi-deduction-basis", "احتساب استقطاعات التأمينات وفق النظام المطبق", "How GOSI Deductions Are Calculated", "salary"),
    _t("gosi-new-registrant", "التأمينات للعامل المسجّل حديثاً", "Social Insurance for Newly Registered Employees", "salary"),
    _t("contract-end-vs-resignation", "الفرق بين إنهاء العقد والاستقالة", "Contract Termination vs Resignation", "eos"),
    _t("notice-period", "فترة الإشعار عند إنهاء عقد العمل", "Notice Period When Ending an Employment Contract", "letter"),
    _t("final-settlement", "تنظيم مستحقات العامل عند انتهاء الخدمة", "Organising Final Settlement Entitlements", "eos"),
    _t("net-salary-calculation", "كيفية حساب الراتب الصافي", "How to Calculate Your Net Salary", "salary"),
    _t("letter-salary-certificate-en", "إعداد خطاب تعريف بالراتب بالإنجليزية", "Writing a Salary Certificate Letter in English", "letter"),
    _t("employee-exit-checklist", "قائمة تحقق للموظف قبل مغادرة العمل", "An Employee Checklist Before Leaving a Job", "eos"),
]


def topic_by_id(tid: str):
    for t in TOPICS:
        if t["id"] == tid:
            return t
    return None


def pick_topic(state, published_pairs=None):
    """أول موضوع متاح للمعالجة.

    المرجع الأساسي لمنع التكرار هو **سجل المقالات المنشورة** (articles.json)، لا
    marketing_state.json وحده: الأخير يُخزَّن في GitHub Actions عبر Cache قد يُحذف
    أو يتلف. فإذا اكتملت النسختان (ar/en) في السجل المنشور فلا يُعاد اختيار الموضوع
    حتى لو ضاعت الحالة تماماً.

    يُستثنى كذلك: (1) ما نُشرت نسختاه، (2) ما أُنتجت مسودتاه وينتظران مراجعة بشرية،
    (3) ما تجاوز حدّ المحاولات بعد تكرار الفشل. حالات المحاولات/الأخطاء تبقى محفوظة.
    """
    if published_pairs is None:
        published_pairs = existing_published_pairs()
    produced = {"draft", "draft_unverified", "published"}
    for t in TOPICS:
        tid = t["id"]
        # (1) مكتمل في سجل النشر الفعلي — مرجع دائم لا يعتمد على ملف الحالة.
        if (tid, "ar") in published_pairs and (tid, "en") in published_pairs:
            continue
        rec = state.get("topics", {}).get(tid, {})
        if not isinstance(rec, dict):
            rec = {}
        if rec.get("ar") == "published" and rec.get("en") == "published":
            continue
        if rec.get("ar") in produced and rec.get("en") in produced:
            continue
        try:
            attempts = int(rec.get("attempts", 0) or 0)
        except (TypeError, ValueError):
            attempts = 0
        if attempts >= MAX_ATTEMPTS:
            continue
        return t
    return None


# =====================================================================================
# 3) محتوى تجريبي للاختبار بلا API
# =====================================================================================

_AR_BODY = (
    "هذا نصّ اختباري داخلي لا يُنشر على الموقع إطلاقاً، ووُجد فقط لتمرين بوابات الجودة. "
    "يوضّح أنه يجب تحديد أجر العامل أولاً، ثم حساب مدة الخدمة بالسنوات والأشهر والأيام، "
    "ثم تطبيق القاعدة النظامية على كل جزء من المدة، مع توضيح أن النتيجة تقديرية استرشادية. "
    "ولا يُغني هذا المحتوى عن مراجعة الجهة المختصة في الحالات الفعلية. "
    "تكرار مقصود لجعل النص يتجاوز الحد الأدنى لعدد الكلمات في الفحوص الآلية."
)
_EN_BODY = (
    "This is internal test content that is never published; it exists only to exercise the "
    "quality gates of the pipeline. " * 6
) + (
    "It restates the same idea several times on purpose so that word-count thresholds are met "
    "during automated self-tests. "
) * 3


def fixture_data(lang: str) -> dict:
    if lang == "ar":
        return {
            "title": "مقال اختباري عن حساب مكافأة نهاية الخدمة",
            "meta_description": "وصف اختباري قصير يوضّح حساب مكافأة نهاية الخدمة للأغراض الداخلية فقط دون نشر.",
            "excerpt": "ملخص اختباري لصفحة توضيحية عن حساب المكافأة وشروط الاستحقاق الأساسية في الاختبار.",
            "sections": [
                {"heading": "أساس الحساب", "body": _AR_BODY + " " + _AR_BODY, "bullets": ["نقطة أولى", "نقطة ثانية"]},
                {"heading": "أجزاء السنة", "body": _AR_BODY + " " + _AR_BODY, "bullets": []},
                {"heading": "الاستقالة", "body": _AR_BODY + " " + _AR_BODY, "bullets": ["نقطة ثالثة"]},
                {"heading": "مثال توضيحي", "body": _AR_BODY + " " + _AR_BODY, "bullets": []},
            ],
            "faq": [
                {"q": "هل هذا المقال حقيقي؟", "a": "لا، هذا محتوى اختباري داخلي يُستخدم في فحوص الجودة الآلية فقط ولا يُنشر."},
                {"q": "متى يُستخدم؟", "a": "يُستخدم عند تشغيل السكربت في وضع الاختبار الذاتي أو المحاكاة بدون مفتاح API."},
            ],
            "official_sources": [
                {"title": "المؤسسة العامة للتأمينات الاجتماعية", "url": "https://www.gosi.gov.sa/"},
                {"title": "وزارة الموارد البشرية والتنمية الاجتماعية", "url": "https://www.hrsd.gov.sa/"},
            ],
        }
    return {
        "title": "Sample Article About Entitlement Calculations",
        "meta_description": "A short sample description used only for internal testing of the publishing pipeline.",
        "excerpt": "A sample excerpt for an internal test page about entitlement calculation and eligibility rules.",
        "sections": [
            {"heading": "Calculation Basis", "body": _EN_BODY + " " + _EN_BODY, "bullets": ["First point", "Second point"]},
            {"heading": "Partial Years", "body": _EN_BODY + " " + _EN_BODY, "bullets": []},
            {"heading": "Resignation", "body": _EN_BODY + " " + _EN_BODY, "bullets": ["Third point"]},
            {"heading": "Worked Example", "body": _EN_BODY + " " + _EN_BODY, "bullets": []},
        ],
        "faq": [
            {"q": "Is this a real article?", "a": "No. It is internal test content used only by the automated quality checks and is never published."},
            {"q": "When is it used?", "a": "It is used when the script runs in self-test or simulation mode without an API key."},
        ],
        "official_sources": [
            {"title": "General Organization for Social Insurance", "url": "https://www.gosi.gov.sa/"},
            {"title": "Ministry of Human Resources and Social Development", "url": "https://www.hrsd.gov.sa/"},
        ],
    }


# =====================================================================================
# 4) حالة النظام
# =====================================================================================

def default_state():
    return {"version": 1, "topics": {}, "last_run": None}


def load_state():
    """يقرأ حالة التسويق من marketing_state.json بأمان.

    الملف قد يكون غائباً أو تالفاً: في GitHub Actions يُخزَّن عبر Cache، والـCache
    قد يُحذف (إخلاء بعد فترة عدم استخدام، أو تجاوز سعة التخزين، أو فقد التنزيل).
    لذلك نتحقّق من صحة JSON ومن بنيته، وعند أي خلل نعود إلى الحالة الافتراضية بهدوء،
    دون طباعة أي محتوى من الملف ودون كشف أي أسرار.
    """
    raw = load_json(STATE_JSON, default_state())
    if not isinstance(raw, dict):
        log("[WARN] ملف الحالة ليس كائناً JSON — سيُستخدم الافتراضي.")
        raw = default_state()

    state = {"version": 1, "topics": {}, "last_run": None}
    try:
        state["version"] = int(raw.get("version") or 1)
    except (TypeError, ValueError):
        state["version"] = 1

    topics = raw.get("topics")
    if isinstance(topics, dict):
        for tid, rec in topics.items():
            if isinstance(tid, str) and isinstance(rec, dict):
                state["topics"][tid] = dict(rec)

    last_run = raw.get("last_run")
    state["last_run"] = last_run if isinstance(last_run, str) else None

    for t in TOPICS:
        rec = state["topics"].setdefault(t["id"], {"ar": "pending", "en": "pending", "published_at": None})
        for lang in ("ar", "en"):
            if not isinstance(rec.get(lang), str):
                rec[lang] = "pending"
        try:
            rec["attempts"] = max(0, int(rec.get("attempts", 0) or 0))
        except (TypeError, ValueError):
            rec["attempts"] = 0
        if not isinstance(rec.get("published_at"), str):
            rec["published_at"] = None
    return state


def save_state(state) -> None:
    state["last_run"] = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    atomic_write_text(STATE_JSON, json.dumps(state, ensure_ascii=False, indent=2) + "\n")


# =====================================================================================
# 5) HTTP
# =====================================================================================

def http_request_full(url, *, method="GET", data=None, headers=None, timeout=25, retries=2):
    """يرجع (status, headers, bytes, final_url). يرفع آخر استثناء عند فشل الشبكة كاملاً.

    `retries=0` يعني محاولة واحدة فقط، ويُستعمل حين تتولّى الدالة المستدعية سياسة
    إعادة المحاولة بنفسها (كما في Gemini) حتى لا تتضاعف المحاولات.
    """
    hdrs = {"User-Agent": UA, "Accept": "*/*"}
    if headers:
        hdrs.update(headers)
    last_exc = None
    for attempt in range(retries + 1):
        try:
            req = urllib.request.Request(url, data=data, headers=hdrs, method=method)
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                return resp.status, resp.headers, resp.read(), resp.geturl()
        except urllib.error.HTTPError as exc:
            if exc.code in RETRYABLE_STATUS and attempt < retries:
                last_exc = exc
                time.sleep(1.5 * (attempt + 1))
                continue
            try:
                payload = exc.read()
            except Exception:  # noqa: BLE001
                payload = b""
            return exc.code, getattr(exc, "headers", None), payload, url
        except (urllib.error.URLError, TimeoutError, OSError) as exc:
            last_exc = exc
            if attempt < retries:
                time.sleep(1.5 * (attempt + 1))
                continue
    raise last_exc if last_exc else RuntimeError("http_request failed")


def http_request(url, *, method="GET", data=None, headers=None, timeout=25, retries=2):
    """يرجع (status, bytes, final_url) — نسخة مختصرة من http_request_full."""
    status, _headers, body, final_url = http_request_full(
        url, method=method, data=data, headers=headers, timeout=timeout, retries=retries)
    return status, body, final_url


def header_get(headers, name):
    """قراءة ترويسة استجابة بلا حساسية لحالة الأحرف، مع تجاهل القيم غير النصّية."""
    try:
        value = headers.get(name) if headers is not None else None
    except AttributeError:
        return None
    return value if isinstance(value, str) else None


def backoff_delay(attempt, *, retry_after=None, base=GEMINI_BACKOFF_BASE,
                  cap=GEMINI_BACKOFF_MAX) -> float:
    """انتظار تصاعدي `base × 2^attempt` بحدّ أعلى `cap`، مع احترام Retry-After إن وُجد."""
    delay = min(base * (2 ** max(0, int(attempt))), cap)
    if retry_after:
        try:
            asked = float(str(retry_after).strip())
        except ValueError:
            asked = 0.0   # تاريخ HTTP أو قيمة غير صالحة ⇒ نكتفي بالانتظار التصاعدي
        if asked > 0:
            delay = min(max(delay, asked), cap)
    return float(delay)


def classify_failure(status, raw) -> tuple:
    """يصنّف استجابة فشل من مزوّد المحتوى إلى (retryable, code, note).

    - auth  : 401/403 (مفتاح ناقص/غير صالح/بلا صلاحية) — لا يُعاد.
    - model : 404 أو رسالة تدلّ على نموذج غير متاح — لا يُعاد (العِلاج تغيير النموذج).
    - quota : 429 مع دلالة حصة يومية أو فوترة — لا يُعاد (تكراره بلا فائدة).
    - rate_limit : 429 مؤقّت — يُعاد مع احترام Retry-After.
    - transient  : 408/425/5xx — يُعاد بتراجع تصاعدي.
    - other : أي رمز آخر — لا يُعاد.
    """
    text = raw.decode("utf-8", "replace") if isinstance(raw, (bytes, bytearray)) else (
        "" if raw is None else str(raw))
    low = text.lower()
    if status in (401, 403):
        return False, "auth", "خطأ مصادقة/صلاحية — لا يُعاد الطلب"
    if status == 404 or any(h in low for h in MODEL_STOP_HINTS):
        return False, "model", "النموذج غير متاح — لا يُعاد الطلب"
    if status == 429:
        if any(h in low for h in QUOTA_STOP_HINTS):
            return False, "quota", "حصة/فوترة — تكرار الطلب بلا فائدة"
        return True, "rate_limit", "تجاوز معدّل مؤقّت"
    if status in RETRYABLE_STATUS:
        return True, "transient", "خطأ مؤقّت"
    return False, "other", "خطأ غير قابل لإعادة المحاولة"


def format_failure(status, raw, tries_used, tries) -> str:
    """رسالة فشل موحّدة (بلا أسرار): الرمز + مقتطف الاستجابة + التصنيف وعدد المحاولات."""
    retryable, _code, note = classify_failure(status, raw)
    if retryable and tries_used >= tries:
        note = "خطأ مؤقّت — استُنفدت المحاولات"
    snippet = redact(raw.decode("utf-8", "replace")[:300]) if isinstance(raw, (bytes, bytearray)) else ""
    return f"http_{status}: {snippet} [{note} — محاولات {tries_used}/{tries}]"


def provider_request(url, body, headers, *, provider, timeout=90, tries=GEMINI_MAX_TRIES,
                     sleep=None):
    """يرسل طلب POST إلى مزوّد المحتوى ويعيد (status, raw, tries_used).

    إعادة المحاولة محدودة للأخطاء المؤقّتة فقط (خطأ شبكة أو رمز يُصنَّف مؤقّتاً)،
    ولا تحدث إطلاقاً عند 401/403 أو نموذج غير متاح أو حصة يومية/فوترة، ويُحترم
    Retry-After عند 429. `retries=0` في http_request_full يمنع تضاعف المحاولات.
    """
    sleep = SLEEP if sleep is None else sleep
    tries = max(1, int(tries))
    last_exc = None
    for attempt in range(tries):
        try:
            status, resp_headers, raw, _ = http_request_full(
                url,
                method="POST",
                data=body,
                headers=headers,
                timeout=timeout,
                retries=0,
            )
        except (urllib.error.URLError, TimeoutError, OSError) as exc:
            last_exc = exc
            if attempt + 1 >= tries:
                break
            delay = backoff_delay(attempt)
            log(f"[RETRY] {provider}: خطأ شبكة مؤقّت ({type(exc).__name__}) — "
                f"المحاولة {attempt + 2}/{tries} بعد {delay:.1f}s")
            sleep(delay)
            continue

        retryable, _code, _note = classify_failure(status, raw)
        if retryable and attempt + 1 < tries:
            delay = backoff_delay(attempt, retry_after=header_get(resp_headers, "Retry-After"))
            log(f"[RETRY] {provider}: استجابة مؤقّتة http_{status} — "
                f"المحاولة {attempt + 2}/{tries} بعد {delay:.1f}s")
            sleep(delay)
            continue
        return status, raw, attempt + 1

    raise last_exc if last_exc else RuntimeError("provider_request failed")


def gemini_request(url, body, api_key, *, timeout=90, tries=GEMINI_MAX_TRIES, sleep=None):
    """طلب Gemini (نفس سلوك provider_request) — يبقى للتوافق ولاختبارات مسار Gemini."""
    return provider_request(
        url, body, {"Content-Type": "application/json; charset=utf-8",
                    "x-goog-api-key": api_key},
        provider="Gemini", timeout=timeout, tries=tries, sleep=sleep)


def groq_request(url, body, api_key, *, timeout=90, tries=GEMINI_MAX_TRIES, sleep=None):
    """طلب Groq (OpenAI-compatible) — المفتاح في ترويسة Authorization، ولا يُطبع أبداً."""
    return provider_request(
        url, body, {"Content-Type": "application/json; charset=utf-8",
                    "Accept": "application/json",
                    "Authorization": f"Bearer {api_key}"},
        provider="Groq", timeout=timeout, tries=tries, sleep=sleep)


# =====================================================================================
# 6) مزوّدو المحتوى (Groq افتراضياً، Gemini اختياري)
# =====================================================================================

def build_prompt(topic, lang: str) -> str:
    title = topic["title_ar"] if lang == "ar" else topic["title_en"]
    lang_name = "العربية" if lang == "ar" else "English"
    if lang == "ar":
        guidance = (
            "اكتب بالعربية الفصحى المبسّطة لجمهور سعودي (موظفون ومقيمون). "
            "استخدم المصطلحات النظامية السعودية بدقة، وأشر إلى النظام باسمه لا بنصّ منسوخ. "
            "اجعل الشرح عملياً بخطوات، وأضف مثالاً رقمياً واحداً مبيّناً صراحةً أنه مثال توضيحي."
        )
    else:
        guidance = (
            "Write in clear professional English for employees and expats in Saudi Arabia. "
            "Explain Saudi statutory terms in plain language instead of mistranslating them. "
            "Cover the same statutory constraints as the Arabic version, and label any numeric example clearly as illustrative."
        )
    return (
        "أنت محرّر محتوى إرشادي-عملي لمنصة أدوات سعودية. ما تكتبه إرشاد عام وليس استشارة قانونية.\n"
        f"الموضوع: {title}\n"
        f"لغة المخرجات: {lang_name}\n"
        f"{guidance}\n\n"
        "قواعد إلزامية:\n"
        "1) أعد كائن JSON واحداً فقط، بلا نص خارجه وبلا أسوار markdown.\n"
        "2) لا تُدرج أي HTML أو وسوم أو سكربتات داخل النصوص؛ نصّ عادي فقط.\n"
        "3) لا تخترع أرقام مواد أو نِسَباً أو مُدداً أو جهات. إن لم تكن واثقاً فاذكر القاعدة العامة بتحفّظ.\n"
        "4) official_sources: من 2 إلى 4 مصادر رسمية سعودية فقط، ونطاقاتها ضمن *.gov.sa أو qiwa.sa.\n"
        "5) لا أسلوب دعائياً، ولا وعوداً بنتائج توظيف مضمونة، ولا ادّعاء بأن المحتوى مُراجَع قانونياً.\n"
        "6) لا تذكر أنك نموذج ذكاء اصطناعي.\n\n"
        "بنية JSON المطلوبة بالحرف:\n"
        "{\n"
        '  "title": "عنوان المقال",\n'
        '  "meta_description": "وصف من 50 إلى 160 حرفاً",\n'
        '  "excerpt": "ملخص من 40 إلى 240 حرفاً",\n'
        '  "sections": [{"heading": "عنوان فرعي", "body": "فقرة أو فقرات مفصولة بسطر فارغ", "bullets": ["نقطة"]}],\n'
        '  "faq": [{"q": "سؤال", "a": "جواب"}],\n'
        '  "official_sources": [{"title": "اسم الجهة", "url": "https://....gov.sa/..."}]\n'
        "}\n\n"
        f"- sections: من {MIN_SECTIONS} إلى {MAX_SECTIONS} عناصر، و bullets اختيارية (اتركها [] عند عدم الحاجة).\n"
        "- faq: من سؤالين إلى أربعة أسئلة.\n"
        "- إجمالي المحتوى لا يقل عن 350 كلمة.\n"
        "- لا تُضِف حقولاً خارج البنية أعلاه.\n"
    )


def _extract_json_text(text):
    """يحوّل نصّ مخرجات المزوّد إلى JSON: مباشرةً، أو بعد استخراج أول كائن {…} عند الحاجة."""
    text = (text or "").strip()
    if not text:
        return False, None, "empty_text"
    try:
        return True, json.loads(text), "ok"
    except ValueError:
        match = re.search(r"\{.*\}", text, re.S)
        if match:
            try:
                return True, json.loads(match.group(0)), "ok_extracted"
            except ValueError:
                pass
        return False, None, "invalid_content_json"


def gemini_generate_json(prompt, *, api_key, model, timeout=90, tries=GEMINI_MAX_TRIES,
                        sleep=None):
    """يرجع (ok, data|None, message) من Gemini. لا يطبع المفتاح أبداً.

    إعادة المحاولة تحدث داخل gemini_request: أخطاء مؤقّتة فقط وبحدّ أعلى صريح،
    ولا تزيد عدّاد `attempts` (العدّ مرة واحدة لكل دورة في run_once).
    """
    if not api_key:
        return False, None, "no_api_key"
    url = (
        "https://generativelanguage.googleapis.com/v1beta/models/"
        + urllib.parse.quote(model or DEFAULT_MODEL, safe="")
        + ":generateContent"
    )
    payload = {
        "contents": [{"role": "user", "parts": [{"text": prompt}]}],
        "generationConfig": {
            "temperature": 0.35,
            "topP": 0.95,
            "maxOutputTokens": 12000,
            "responseMimeType": "application/json",
        },
    }
    body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    try:
        status, raw, tries_used = gemini_request(
            url, body, api_key, timeout=timeout, tries=tries, sleep=sleep)
    except Exception as exc:  # noqa: BLE001
        return False, None, f"network_error: {redact(exc)}"

    if status != 200:
        return False, None, format_failure(status, raw, tries_used, tries)

    try:
        envelope = json.loads(raw.decode("utf-8"))
    except ValueError:
        return False, None, "invalid_envelope_json"

    feedback = (envelope.get("promptFeedback") or {}) if isinstance(envelope, dict) else {}
    if feedback.get("blockReason"):
        return False, None, "blocked: " + str(feedback.get("blockReason"))

    try:
        parts = envelope["candidates"][0]["content"]["parts"]
        text = "".join(p.get("text", "") for p in parts if isinstance(p, dict))
    except (KeyError, IndexError, TypeError):
        return False, None, "no_candidate_text"

    return _extract_json_text(text)


# تعليمات نظام لـGroq: مخرجات JSON صالحة فقط، بلا نص أو أسوار markdown حولها.
GROQ_SYSTEM_PROMPT = (
    "أنت مساعد إنتاج محتوى آلي. أعد كائن JSON واحداً صالحاً فقط بالحقول المطلوبة في "
    "تعليمات المستخدم، دون أي نص إضافي ودون أسوار markdown. لا تذكر أنك نموذج ذكاء اصطناعي."
)


def groq_generate_json(prompt, *, api_key, model, timeout=90, tries=GEMINI_MAX_TRIES,
                       sleep=None):
    """يرجع (ok, data|None, message) من Groq عبر مخطط OpenAI-compatible.

    المفتاح يُرسل في ترويسة Authorization ولا يُطبع أبداً، ولا يظهر في أي رسالة خطأ.
    المخرجات تُمرَّر كما هي إلى بوابات التحقّق الحالية (لا استثناءات ولا تجاوز).
    """
    if not api_key:
        return False, None, "no_api_key"
    payload = {
        "model": model or DEFAULT_GROQ_MODEL,
        "messages": [
            {"role": "system", "content": GROQ_SYSTEM_PROMPT},
            {"role": "user", "content": prompt},
        ],
        "temperature": 0.35,
        "max_tokens": 12000,
        "response_format": {"type": "json_object"},
    }
    body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    try:
        status, raw, tries_used = groq_request(
            GROQ_URL, body, api_key, timeout=timeout, tries=tries, sleep=sleep)
    except Exception as exc:  # noqa: BLE001
        return False, None, f"network_error: {redact(exc)}"

    if status != 200:
        return False, None, format_failure(status, raw, tries_used, tries)

    try:
        envelope = json.loads(raw.decode("utf-8"))
    except ValueError:
        return False, None, "invalid_envelope_json"
    if not isinstance(envelope, dict):
        return False, None, "invalid_envelope_shape"
    if envelope.get("error"):
        # خطأ أُعلن داخل جسم الاستجابة (بعض الأخطاء تصل بترميز 200) — بلا كشف أسرار.
        return False, None, "provider_error: " + redact(json.dumps(envelope.get("error"), ensure_ascii=False)[:200])

    choices = envelope.get("choices")
    if not isinstance(choices, list) or not choices or not isinstance(choices[0], dict):
        return False, None, "no_choices"
    choice = choices[0]
    message = choice.get("message") if isinstance(choice.get("message"), dict) else {}
    text = message.get("content")
    if not isinstance(text, str) or not text.strip():
        if choice.get("finish_reason") == "length":
            return False, None, "truncated_output"
        return False, None, "empty_text"
    if choice.get("finish_reason") == "length":
        return False, None, "truncated_output"
    return _extract_json_text(text)


def generate_json(provider, prompt, *, api_key, model, timeout=90, tries=GEMINI_MAX_TRIES,
                  sleep=None):
    """يوجّه التوليد إلى المزوّد المطلوب فقط — بلا انتقال تلقائي عند الفشل."""
    if provider == "groq":
        return groq_generate_json(prompt, api_key=api_key, model=model,
                                  timeout=timeout, tries=tries, sleep=sleep)
    if provider == "gemini":
        return gemini_generate_json(prompt, api_key=api_key, model=model,
                                    timeout=timeout, tries=tries, sleep=sleep)
    return False, None, f"unknown_provider: {provider}"


# =====================================================================================
# 7) التحقّق
# =====================================================================================

class Reject(Exception):
    """رفض محتوى لم يجتز بوابة الجودة."""


def _text(value, field, *, lo, hi):
    if not isinstance(value, str):
        raise Reject(f"{field}: ليس نصاً")
    text = strip_ws(value)
    if not text:
        raise Reject(f"{field}: فارغ")
    if looks_like_html(text):
        raise Reject(f"{field}: يحتوي HTML")
    if has_dangerous_scheme(text):
        raise Reject(f"{field}: بروتوكول ممنوع")
    if not (lo <= len(text) <= hi):
        raise Reject(f"{field}: الطول {len(text)} خارج المدى {lo}-{hi}")
    return text


def is_allowed_source_url(url: str) -> bool:
    try:
        parts = urllib.parse.urlsplit(url or "")
    except ValueError:
        return False
    if parts.scheme != "https" or not parts.netloc:
        return False
    host = parts.netloc.lower().split(":")[0]
    if host in ALLOWED_SOURCE_HOSTS:
        return True
    return any(host.endswith(sfx) for sfx in ALLOWED_SOURCE_SUFFIXES)


def normalize_sources(raw) -> list:
    if not isinstance(raw, list) or not raw:
        raise Reject("official_sources: مطلوب مصدران على الأقل")
    if len(raw) > 4:
        raise Reject("official_sources: أكثر من أربعة مصادر")
    out, seen = [], set()
    for i, item in enumerate(raw):
        if not isinstance(item, dict):
            raise Reject(f"official_sources[{i}]: ليس كائناً")
        extra = set(item) - {"title", "url"}
        if extra:
            raise Reject(f"official_sources[{i}]: حقول غير متوقّعة")
        title = _text(item.get("title"), f"official_sources[{i}].title", lo=3, hi=160)
        url = strip_ws(item.get("url"))
        if not is_allowed_source_url(url):
            raise Reject(f"official_sources[{i}]: رابط غير مسموح ({url[:70]})")
        if url in seen:
            continue
        seen.add(url)
        out.append({"title": title, "url": url})
    if len(out) < 2:
        raise Reject("official_sources: أقل من مصدرين فريدين")
    return out


def normalize_sections(raw) -> list:
    if not isinstance(raw, list):
        raise Reject("sections: ليس قائمة")
    if not (MIN_SECTIONS <= len(raw) <= MAX_SECTIONS):
        raise Reject(f"sections: العدد {len(raw)} خارج المدى {MIN_SECTIONS}-{MAX_SECTIONS}")
    out = []
    for i, item in enumerate(raw):
        if not isinstance(item, dict):
            raise Reject(f"sections[{i}]: ليس كائناً")
        extra = set(item) - {"heading", "body", "bullets"}
        if extra:
            raise Reject(f"sections[{i}]: حقول غير متوقّعة")
        heading = _text(item.get("heading"), f"sections[{i}].heading", lo=3, hi=120)
        body = _text(item.get("body"), f"sections[{i}].body", lo=120, hi=8000)
        bullets = item.get("bullets") or []
        if not isinstance(bullets, list):
            raise Reject(f"sections[{i}].bullets: ليست قائمة")
        if len(bullets) > 8:
            raise Reject(f"sections[{i}].bullets: أكثر من 8 عناصر")
        bl = [_text(b, f"sections[{i}].bullets[{j}]", lo=3, hi=300) for j, b in enumerate(bullets)]
        out.append({"heading": heading, "body": body, "bullets": bl})
    return out


def normalize_faq(raw) -> list:
    if raw is None:
        return []
    if not isinstance(raw, list):
        raise Reject("faq: ليست قائمة")
    if len(raw) > 6:
        raise Reject("faq: أكثر من ستة أسئلة")
    out = []
    for i, item in enumerate(raw):
        if not isinstance(item, dict):
            raise Reject(f"faq[{i}]: ليس كائناً")
        extra = set(item) - {"q", "a"}
        if extra:
            raise Reject(f"faq[{i}]: حقول غير متوقّعة")
        q = _text(item.get("q"), f"faq[{i}].q", lo=5, hi=200)
        a = _text(item.get("a"), f"faq[{i}].a", lo=20, hi=1500)
        out.append({"q": q, "a": a})
    return out


def validate_article(data, *, topic, lang, published_at) -> dict:
    """يرفع Reject عند فشل أي بوابة، ويرجع قاموس المقال النهائي عند النجاح."""
    if not isinstance(data, dict):
        raise Reject("المخرجات ليست كائن JSON")

    allowed = {"title", "meta_description", "excerpt", "sections", "faq", "official_sources"}
    extra = set(data) - allowed
    if extra:
        raise Reject("حقول غير متوقّعة: " + ", ".join(sorted(extra)))

    title = _text(data.get("title"), "title", lo=8, hi=120)
    meta_description = _text(data.get("meta_description"), "meta_description", lo=50, hi=200)
    excerpt = _text(data.get("excerpt"), "excerpt", lo=40, hi=300)

    if lang == "ar":
        if not has_arabic(title) or latin_ratio(title) > 0.5:
            raise Reject("title: لا يبدو عربياً")
    else:
        if latin_ratio(title) < 0.6 or has_arabic(title):
            raise Reject("title: لا يبدو إنجليزياً")

    sections = normalize_sections(data.get("sections"))
    faq = normalize_faq(data.get("faq"))
    sources = normalize_sources(data.get("official_sources"))

    body_text = " ".join(s["body"] + " " + " ".join(s["bullets"]) for s in sections)
    faq_text = " ".join(f"{f['q']} {f['a']}" for f in faq)
    total_chars = len(body_text) + len(faq_text) + len(title) + len(excerpt)
    if total_chars < MIN_TOTAL_CHARS:
        raise Reject(f"المحتوى قصير: {total_chars} حرفاً (الحد {MIN_TOTAL_CHARS})")
    words = word_count(body_text) + word_count(faq_text) + word_count(title)
    if words < MIN_WORDS[lang]:
        raise Reject(f"المحتوى قصير: {words} كلمة (الحد {MIN_WORDS[lang]})")

    slug = f"{topic['id']}-{lang}"
    if not slug_ok(slug):
        raise Reject("slug: غير صالح")
    return {
        "translation_id": topic["id"],
        "lang": lang,
        "slug": slug,
        "title": title,
        "meta_description": meta_description,
        "excerpt": excerpt,
        "sections": sections,
        "faq": faq,
        "official_sources": sources,
        "tool": topic["tool"],
        "published_at": published_at,
        "updated_at": published_at,
        "url": f"/articles/{lang}/{slug}.html",
        "word_count": words,
    }


def duplicate_check(article, existing_records) -> list:
    problems = []
    norm = re.sub(r"\s+", " ", article["title"].strip().lower())
    for rec in existing_records or []:
        if not isinstance(rec, dict) or rec.get("lang") != article["lang"]:
            continue
        if rec.get("url") == article["url"]:
            problems.append(f"رابط مكرر: {article['url']}")
        other = re.sub(r"\s+", " ", str(rec.get("title", "")).strip().lower())
        if other and other == norm:
            problems.append(f"عنوان مطابق لعنصر قائم: {rec.get('url')}")
    return problems


def check_sources(sources, *, timeout=20) -> list:
    """يتحقّق من إمكانية الوصول للمصادر الرسمية. يرجع قائمة مشاكل (فارغة = نجاح)."""
    problems = []
    for src in sources:
        try:
            status, body, _ = http_request(src["url"], method="GET", timeout=timeout, retries=1)
        except Exception as exc:  # noqa: BLE001
            problems.append(f"{src['url']} غير قابل للوصول ({redact(exc)})")
            continue
        if status != 200:
            problems.append(f"{src['url']} أعاد الحالة {status}")
        elif not (body and len(body) > 200):
            problems.append(f"{src['url']} استجابة فارغة أو قصيرة جداً")
    return problems


# =====================================================================================
# 8) عرض HTML
# =====================================================================================

ARTICLE_TEMPLATE = Template(
    """<!DOCTYPE html>
<html lang="$lang" dir="$dir">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>$title_tag</title>
  <meta name="description" content="$meta_description" />
  <meta name="robots" content="$robots_meta" />
  <link rel="canonical" href="$canonical" />
  <link rel="alternate" hreflang="ar" href="$alt_ar" />
  <link rel="alternate" hreflang="en" href="$alt_en" />
  <link rel="alternate" hreflang="x-default" href="$alt_ar" />
  <meta property="og:type" content="article" />
  <meta property="og:site_name" content="$site_name" />
  <meta property="og:title" content="$title" />
  <meta property="og:description" content="$meta_description" />
  <meta property="og:url" content="$canonical" />
  <link rel="icon" href="/favicon.svg" type="image/svg+xml" />
  <style>
    :root { --ink:#12211b; --muted:#5b6b64; --brand:#0a6847; --bg:#f6f8f7; --card:#ffffff; --line:#dde5e1; }
    * { box-sizing: border-box; }
    body { margin:0; background:var(--bg); color:var(--ink); line-height:1.85;
           font-family: "Tajawal", "Segoe UI", system-ui, -apple-system, Tahoma, sans-serif; }
    header.site { background:var(--brand); color:#fff; padding:14px 18px; }
    header.site a { color:#fff; text-decoration:none; font-weight:700; }
    main { max-width:820px; margin:0 auto; padding:22px 18px 56px; background:var(--card); }
    h1 { font-size:1.7rem; line-height:1.4; margin:0 0 10px; }
    h2 { font-size:1.2rem; margin:26px 0 8px; color:var(--brand); }
    p { margin:0 0 12px; }
    .meta { color:var(--muted); font-size:.86rem; margin-bottom:18px; }
    ul { padding-inline-start:22px; }
    .cta { margin:26px 0; padding:14px 16px; background:#eef6f2; border:1px solid var(--line); border-radius:10px; }
    .cta a { color:var(--brand); font-weight:700; }
    details { border:1px solid var(--line); border-radius:8px; padding:10px 12px; margin:8px 0; }
    summary { cursor:pointer; font-weight:700; }
    .sources a { color:var(--brand); }
    .note { font-size:.88rem; color:var(--muted); border-top:1px solid var(--line); margin-top:24px; padding-top:14px; }
    .ad-slot { max-width:820px; margin:18px auto; padding:0 18px; text-align:center; }
    footer.site { max-width:820px; margin:0 auto; padding:18px; color:var(--muted); font-size:.85rem; text-align:center; }
    footer.site a { color:var(--brand); }
    @media (max-width:600px) { main { padding:16px 14px 42px; } h1 { font-size:1.35rem; } }
  </style>
  <script type="application/ld+json">$json_ld</script>
  $ad_social_bar
</head>
<body>
  <header class="site"><a href="/">$site_name</a></header>
  <main>
    <h1>$title</h1>
    <p class="meta">$meta_line</p>
    $sections_html
    $faq_html
    <div class="cta">
      <p>$cta_text</p>
      <p><a href="$tool_url">$tool_label</a> &middot; <a href="/">$home_label</a> &middot; <a href="/privacy.html">$privacy_label</a></p>
    </div>
    <div class="sources">
      <h2>$sources_heading</h2>
      <ul>$sources_html</ul>
    </div>
    <div class="ad-slot">
$ad_native_banner
    </div>
    <p class="note">$disclaimer</p>
    <p class="note">$alt_lang_html</p>
  </main>
  <footer class="site">
    <p>$footer_text</p>
  </footer>
</body>
</html>
"""
)


def render_article_html(article, *, published: bool) -> str:
    lang = article["lang"]
    ar = lang == "ar"
    tid = article["translation_id"]
    canonical = f"{SITE_BASE}/articles/{lang}/{article['slug']}.html"
    alt_ar = f"{SITE_BASE}/articles/ar/{tid}-ar.html"
    alt_en = f"{SITE_BASE}/articles/en/{tid}-en.html"

    section_blocks = []
    for sec in article["sections"]:
        parts = [f"<h2>{esc(sec['heading'])}</h2>"]
        for para in collapse_paragraphs(sec["body"]):
            parts.append(f"<p>{esc(para)}</p>")
        if sec["bullets"]:
            parts.append("<ul>" + "".join(f"<li>{esc(b)}</li>" for b in sec["bullets"]) + "</ul>")
        section_blocks.append("\n      ".join(parts))
    sections_html = "\n      ".join(section_blocks)

    faq_html = ""
    if article["faq"]:
        items = "".join(
            f"<details><summary>{esc(f['q'])}</summary><p>{esc(f['a'])}</p></details>\n      "
            for f in article["faq"]
        )
        faq_html = f"<h2>{esc('الأسئلة الشائعة' if ar else 'Frequently asked questions')}</h2>\n      {items}"

    sources_html = "".join(
        f'<li><a href="{esc(s["url"])}" rel="noopener noreferrer" target="_blank">{esc(s["title"])}</a></li>'
        for s in article["official_sources"]
    )

    tool = article.get("tool", "eos")
    meta_line = (
        f"نُشر: {article['published_at']} &middot; آخر تحديث: {article['updated_at']}"
        if ar else
        f"Published: {article['published_at']} &middot; Last updated: {article['updated_at']}"
    )
    json_ld = json.dumps(
        {
            "@context": "https://schema.org",
            "@type": "Article",
            "headline": article["title"],
            "inLanguage": lang,
            "datePublished": article["published_at"],
            "dateModified": article["updated_at"],
            "description": article["meta_description"],
            "mainEntityOfPage": canonical,
            "author": {"@type": "Organization", "name": "KSA Tools"},
            "publisher": {"@type": "Organization", "name": "KSA Tools"},
        },
        ensure_ascii=False,
    ).replace("</", "<\\/")

    alt_lang_html = (
        f'<a href="{esc(alt_en)}">Read this guide in English</a>'
        if ar
        else f'<a href="{esc(alt_ar)}">اقرأ هذا الدليل بالعربية</a>'
    )

    return ARTICLE_TEMPLATE.substitute(
        lang=lang,
        dir="rtl" if ar else "ltr",
        title_tag=esc(article["title"] + " | KSA Tools"),
        title=esc(article["title"]),
        meta_description=esc(article["meta_description"]),
        robots_meta="index,follow" if published else "noindex,nofollow",
        canonical=esc(canonical),
        alt_ar=esc(alt_ar),
        alt_en=esc(alt_en),
        site_name=esc("KSA Tools — خدمات الموظف والمقيم" if ar else "KSA Tools"),
        meta_line=esc(meta_line).replace("&amp;middot;", "&middot;"),
        sections_html="\n    ".join(section_blocks),
        faq_html=faq_html,
        sources_heading=esc("المصادر الرسمية" if ar else "Official sources"),
        sources_html=sources_html,
        cta_text=esc("استخدم الأداة المجانية على الموقع لحساب نتيجتك بنفسك."
                     if ar else
                     "Use the free tool on the site to calculate your own result."),
        tool_label=esc(TOOL_LABEL.get(article["tool"], TOOL_LABEL["eos"])[0 if ar else 1]),
        tool_url=esc(f"{SITE_BASE}/#{TOOL_ANCHOR.get(article['tool'], 'eos-tool')}"),
        home_label=esc("الصفحة الرئيسية" if ar else "Home"),
        privacy_label=esc("سياسة الخصوصية" if ar else "Privacy policy"),
        disclaimer=esc(DISCLAIMER_AR if ar else DISCLAIMER_EN),
        alt_lang_html=alt_lang_html,
        footer_text=esc("© 2026 KSA Tools — محتوى إرشادي عام." if ar else "© 2026 KSA Tools — General guidance only."),
        json_ld=json_ld,
        ad_social_bar=AD_SOCIAL_BAR,
        ad_native_banner=AD_NATIVE_BANNER,
    )


def validate_generated_page(html_text: str, article) -> list:
    """يتحقّق من صفحة مقال مولَّدة قبل نشرها؛ يعيد قائمة مشاكل (فارغة = سليمة).

    يضمن: HTML مكتمل، canonical مطابق، robots مناسب للنشر، وجود أكواد الإعلان
    المعتمدة (bauval.org) مرة واحدة لكل كود، وغياب أي نطاق إعلان قديم.
    """
    problems = []
    if not html_text.rstrip().endswith("</html>"):
        problems.append("الصفحة لا تنتهي بـ</html>")
    canonical = f"{SITE_BASE}/articles/{article['lang']}/{article['slug']}.html"
    if f'hreflang="x-default"' not in html_text:
        problems.append("وسم hreflang x-default غير موجود")
    if canonical not in html_text:
        problems.append("رابط canonical غير موجود في الصفحة")
    if '<meta name="robots" content="index,follow"' not in html_text:
        problems.append("صفحة النشر غير قابلة للفهرسة (robots)")
    if html_text.count(AD_SOCIAL_BAR) != 1:
        problems.append("كود Social Bar المعتمد ليس مرة واحدة")
    if html_text.count(AD_NATIVE_BANNER) != 1:
        problems.append("كود Native Banner المعتمد ليس مرة واحدة")
    if AD_CONTAINER_ID not in html_text:
        problems.append("معرّف حاوية الإعلان المعتمد غير موجود")
    if LEGACY_AD_HOST in html_text:
        problems.append("نطاق إعلان قديم " + LEGACY_AD_HOST)
    return problems


# =====================================================================================
# 9) الأرشفة
# =====================================================================================

def merge_articles(existing, new_records) -> list:
    """يدمج بلا حذف أي سجل قائم، ويعيد قائمة مرتبة من الأحدث."""
    if not isinstance(existing, list):
        existing = []
    by_url = {}
    order = []
    for rec in existing:
        if not isinstance(rec, dict):
            continue
        url = rec.get("url")
        if not url or url in by_url:
            continue
        by_url[url] = rec
        order.append(url)
    for rec in new_records:
        url = rec["url"]
        if url in by_url:
            merged = dict(by_url[url])
            merged.update(rec)
            merged["published_at"] = by_url[url].get("published_at") or rec["published_at"]
            by_url[url] = merged
        else:
            by_url[url] = rec
            order.append(url)
    out = [by_url[u] for u in order if u in by_url]
    out.sort(key=lambda r: (str(r.get("published_at", "")), str(r.get("url", ""))), reverse=True)
    return out


def validate_articles_json(records) -> list:
    problems = []
    if not isinstance(records, list):
        return ["articles.json ليس قائمة"]
    seen = set()
    for i, rec in enumerate(records):
        if not isinstance(rec, dict):
            problems.append(f"articles.json[{i}]: ليس كائناً")
            continue
        for key in ("translation_id", "lang", "title", "url", "published_at", "status"):
            if not rec.get(key):
                problems.append(f"articles.json[{i}]: الحقل {key} مفقود")
        if rec.get("lang") not in ("ar", "en"):
            problems.append(f"articles.json[{i}]: lang غير صالح")
        url = rec.get("url", "")
        if url in seen:
            problems.append(f"articles.json[{i}]: رابط مكرر {url}")
        seen.add(url)
        if rec.get("status") != "published":
            problems.append(f"articles.json[{i}]: حالة غير منشورة داخل الملف العام")
    return problems


def existing_published_pairs(records=None) -> set:
    """أزواج (translation_id, lang) المنشورة فعلاً في articles.json.

    هذا هو المرجع الدائم للنشر: لا يعتمد إطلاقاً على ملف الحالة (الـCache) ولا على
    متغيّرات البيئة، فيصمد أمام فقدان الحالة أو تلفها.
    """
    if records is None:
        records = load_json(ARTICLES_JSON, [])
    pairs = set()
    if isinstance(records, list):
        for rec in records:
            if isinstance(rec, dict) and rec.get("status") == "published":
                tid = rec.get("translation_id")
                lang = rec.get("lang")
                if isinstance(tid, str) and lang in ("ar", "en"):
                    pairs.add((tid, lang))
    return pairs


def reconcile_state_with_records(state, published_pairs) -> int:
    """يُصلح الحالة وفق السجل المنشور (مثلاً بعد فقدان الـCache أو تلفه).

    يعلّم النسخ المنشورة فعلاً في articles.json كـ"published"، دون مسح حالة
    المحاولات ولا حالات اللغات الأخرى (error/rejected/draft_unverified). يعيد عدد
    السجلات التي أُصلحت.
    """
    topics = state.get("topics") if isinstance(state, dict) else None
    if not isinstance(topics, dict):
        return 0
    fixed = 0
    for tid, lang in published_pairs:
        rec = topics.get(tid)
        if isinstance(rec, dict) and rec.get(lang) != "published":
            rec[lang] = "published"
            fixed += 1
    return fixed


def article_record(art) -> dict:
    tid = art["translation_id"]
    other = "en" if art["lang"] == "ar" else "ar"
    return {
        "translation_id": tid,
        "lang": art["lang"],
        "title": art["title"],
        "excerpt": art["excerpt"],
        "url": art["url"],
        "alternate_url": f"/articles/{other}/{tid}-{other}.html",
        "published_at": art["published_at"],
        "updated_at": art["updated_at"],
        "status": "published",
    }


def sitemap_url_block(loc, lastmod, alternates, changefreq="monthly", priority="0.7") -> str:
    lines = ["  <url>", f"    <loc>{esc(loc)}</loc>", f"    <lastmod>{esc(lastmod)}</lastmod>",
             f"    <changefreq>{changefreq}</changefreq>", f"    <priority>{priority}</priority>"]
    for hreflang, href in alternates:
        lines.append(f'    <xhtml:link rel="alternate" hreflang="{esc(hreflang)}" href="{esc(href)}" />')
    lines.append("  </url>")
    return "\n".join(lines)


def add_sitemap_entries(xml_text: str, entries: list) -> str:
    """إدراج عناصر جديدة قبل </urlset> دون لمس أي محتوى قائم."""
    if "</urlset>" not in xml_text:
        raise ValueError("sitemap.xml غير صالح: لا يحتوي </urlset>")
    # لا تكرار على الإطلاق: لا مع المحتوى القائم، ولا داخل قائمة العناصر الواردة نفسها
    # (article_sitemap_entries يُرجع زوج اللغتين لكل مقال، فقد يُستدعى مرتين لنفس المقال).
    existing = set(re.findall(r"<loc>\s*([^<]+?)\s*</loc>", xml_text))
    blocks = []
    seen = set(existing)
    for b in entries:
        loc = b["loc"]
        if loc in seen:
            continue
        seen.add(loc)
        blocks.append(b)
    if not blocks:
        return xml_text
    payload = "\n".join(
        sitemap_url_block(b["loc"], b["lastmod"], b.get("alternates", []),
                          b.get("changefreq", "monthly"), b.get("priority", "0.7"))
        for b in blocks
    )
    return xml_text.replace("</urlset>", payload + "\n\n</urlset>")


def validate_sitemap(xml_text: str) -> list:
    problems = []
    try:
        root = ET.fromstring(xml_text)
    except ET.ParseError as exc:
        return [f"sitemap.xml غير صالح: {exc}"]
    if not root.tag.endswith("urlset"):
        problems.append("العنصر الجذر ليس urlset")
    locs = [el.text or "" for el in root.iter(f"{{{SITEMAP_NS}}}loc")]
    if len(locs) != len(set(locs)):
        problems.append("sitemap.xml يحتوي روابط مكررة")
    for loc in locs:
        if not loc.startswith(SITE_BASE):
            problems.append(f"رابط خارج النطاق الرسمي: {loc}")
    return problems


def article_sitemap_entries(article) -> list:
    tid = article["translation_id"]
    ar = f"{SITE_BASE}/articles/ar/{tid}-ar.html"
    en = f"{SITE_BASE}/articles/en/{tid}-en.html"
    alts = [("ar", ar), ("en", en), ("x-default", ar)]
    return [
        {"loc": ar, "lastmod": article["updated_at"], "alternates": alts},
        {"loc": en, "lastmod": article["updated_at"], "alternates": alts},
    ]


SITEMAP_EMPTY = (
    '<?xml version="1.0" encoding="UTF-8"?>\n'
    f'<urlset xmlns="{SITEMAP_NS}"\n        xmlns:xhtml="{XHTML_NS}">\n\n</urlset>\n'
)


# =====================================================================================
# 10) المنشور التسويقي + Telegram
# =====================================================================================

def build_social_text(article) -> str:
    ar = article["lang"] == "ar"
    url = SITE_BASE + article["url"]
    if ar:
        return (
            f"📄 {article['title']}\n\n"
            f"{article['excerpt']}\n\n"
            f"اقرأ الدليل كاملاً: {url}\n\n"
            "جرّب الأدوات المجانية على KSA Tools: https://ksatools.github.io/\n"
            "#نظام_العمل #السعودية"
        )
    return (
        f"📄 {article['title']}\n\n"
        f"{article['excerpt']}\n\n"
        f"Read the full guide: {url}\n\n"
        "Try the free tools on KSA Tools: https://ksatools.github.io/\n"
        "#SaudiArabia #LabourLaw"
    )


def write_social_file(articles, social_lang: str) -> None:
    parts = ["# KSA Tools — منشورات تسويقية جاهزة (لم تُنشر تلقائياً على أي منصة)", ""]
    wanted = {"ar", "en"} if social_lang == "both" else {social_lang}
    for art in articles:
        if art["lang"] not in wanted:
            continue
        label = "العربية" if art["lang"] == "ar" else "English"
        parts += [f"## {label}", "```", build_social_text(art), "```", ""]
    parts.append("ملاحظة: هذه النصوص جاهزة للنسخ اليدوي. لا يُنشر أي منها تلقائياً إلا عبر تلغرام عند ضبط الرموز.")
    atomic_write_text(SOCIAL_TXT, "\n".join(parts) + "\n")


def send_telegram(articles, social_lang: str, token: str, chat_id: str) -> str:
    if not token or not chat_id:
        return "skipped (لا توجد رموز تلغرام)"
    wanted = {"ar", "en"} if social_lang == "both" else {social_lang}
    sent = 0
    for art in articles:
        if art["lang"] not in wanted:
            continue
        payload = urllib.parse.urlencode({
            "chat_id": chat_id,
            "text": build_social_text(art),
        }).encode("utf-8")
        try:
            status, raw, _ = http_request(
                f"https://api.telegram.org/bot{token}/sendMessage",
                method="POST",
                data=payload,
                headers={"Content-Type": "application/x-www-form-urlencoded"},
                timeout=25,
                retries=1,
            )
        except Exception as exc:  # noqa: BLE001
            return f"telegram_network_error: {redact(exc)}"
        if status != 200:
            return f"telegram_http_{status}: {redact(raw.decode('utf-8', 'replace')[:200])}"
        sent += 1
    return f"sent ({sent})"


# =====================================================================================
# 11) الدورة الكاملة
# =====================================================================================

def write_article_files(article, *, published: bool) -> Path:
    root = ARTICLES_DIR if published else DRAFTS_DIR
    path = root / article["lang"] / f"{article['slug']}.html"
    atomic_write_text(path, render_article_html(article, published=published))
    return path


def resolve_provider(value=None) -> str:
    """يحسم المزوّد: الوسيط الصريح، ثم AI_PROVIDER، ثم الافتراضي. غير المعروف ⇒ الافتراضي."""
    name = (value if value is not None else os.environ.get("AI_PROVIDER", "")) or ""
    name = str(name).strip().lower()
    if name in AI_PROVIDERS:
        return name
    if name:
        log(f"[WARN] مزوّد غير معروف ({redact(name)}) — سيُستخدم {DEFAULT_PROVIDER}.")
    return DEFAULT_PROVIDER


def run_once(*, mode, topic_id=None, social_lang="both", dry_run=False,
             skip_source_check=False, provider=None, api_key=None, model=None) -> int:
    provider = resolve_provider(provider)
    key_env = PROVIDER_KEY_ENV[provider]
    model_env = PROVIDER_MODEL_ENV[provider]
    api_key = os.environ.get(key_env, "") if api_key is None else api_key
    model = model or os.environ.get(model_env) or PROVIDER_DEFAULT_MODEL[provider]

    # فشل الإعداد يُكتشف قبل أي قراءة/كتابة: لا محاولة تُستهلك، ولا ملف مقال أو مسودة،
    # ولا نداء شبكة، ولا انتقال إلى مزوّد آخر. (dry-run مستثنى: يعمل بمصادر وهمية بلا مفتاح.)
    if not api_key and not dry_run:
        log(f"[FAIL] فشل الإعداد: مفتاح المزوّد ({provider}) غير مضبوط — "
            f"المتغيّر الناقص: {key_env}، ولم يُجرَ توليد أو نشر.")
        log(f"[FAIL] النتيجة: فشل الإعداد (رمز خروج {EXIT_CONFIG_FAILED}) — "
            "لم تُستهلك أي محاولة موضوع، ولم يُكتب أي ملف، ولم يُرسل أي طلب شبكة.")
        return EXIT_CONFIG_FAILED

    log(f"مزوّد المحتوى: {provider} — النموذج: {model} (لا انتقال تلقائي بين المزوّدين).")

    state = load_state()
    records = load_json(ARTICLES_JSON, [])
    if not isinstance(records, list):
        records = []
    # مرجع النشر الدائم هو articles.json (لا الحالة/الـCache). نُصلح الحالة وفقه
    # كي لا يعيد اختيار موضوع مكتمل حتى بعد فقدان الحالة، مع الإبقاء على المحاولات.
    published_pairs = existing_published_pairs(records)
    healed = reconcile_state_with_records(state, published_pairs)
    if healed:
        log(f"[INFO] أُصلحت حالة {healed} نسخة منشورة من articles.json (فقدان/تلف الحالة).")

    if topic_id:
        topic = topic_by_id(topic_id)
        if topic is None:
            log(f"[SKIP] معرّف الموضوع غير معروف: {topic_id}")
            return 0
    else:
        topic = pick_topic(state, published_pairs)
        if topic is None:
            log("[SKIP] لا يوجد موضوع متاح: الكل إما منشور، أو مسوّد وينتظر مراجعة بشرية، "
                "أو موقوف بعد تكرار الفشل. راجع المسودات أو أضِف مواضيع جديدة إلى TOPICS.")
            return 0

    log(f"الموضوع المختار: {topic['id']} — {topic['title_ar']}")

    state["topics"][topic["id"]]["attempts"] = int(state["topics"][topic["id"]].get("attempts", 0)) + 1

    results = {}
    attempted = False
    for lang in ("ar", "en"):
        if (topic["id"], lang) in published_pairs:
            log(f"[SKIP] النسخة {lang} منشورة سابقاً — لا إعادة إنشاء.")
            continue
        attempted = True
        log(f"توليد النسخة {lang}…")
        if dry_run:
            ok, data, msg = True, fixture_data(lang), "fixture"
        else:
            ok, data, msg = generate_json(
                provider, build_prompt(topic, lang), api_key=api_key, model=model)
        if not ok:
            log(f"[FAIL] تعذّر توليد النسخة {lang}: {redact(msg)}")
            state["topics"][topic["id"]][lang] = "error"
            continue
        try:
            article = validate_article(data, topic=topic, lang=lang, published_at=today_iso())
        except Reject as exc:
            log(f"[REJECT] النسخة {lang} لم تجتز بوابة الجودة: {redact(exc)}")
            state["topics"][topic["id"]][lang] = "rejected"
            continue
        problems = duplicate_check(article, records)
        if problems:
            log(f"[REJECT] النسخة {lang}: " + "; ".join(problems))
            state["topics"][topic["id"]][lang] = "rejected"
            continue
        article["content_hash"] = sha256_text(json.dumps(article["sections"], ensure_ascii=False))
        results[lang] = article
        log(f"[OK] النسخة {lang} اجتازت بوابة الجودة ({article['word_count']} كلمة).")

    ready = [results[l] for l in ("ar", "en") if results.get(l)]
    if not ready:
        if not attempted:
            log("[SKIP] النسختان (ar/en) منشورتان سابقاً — لا شيء لتوليده في هذه الدورة.")
            return 0
        statuses = ", ".join(
            f"{lang}={state['topics'][topic['id']].get(lang)}" for lang in ("ar", "en"))
        log("[FAIL] فشل توليد المحتوى: لم تنتج هذه الدورة أي نسخة صالحة "
            f"({statuses}). لم يُكتب أي ملف، ولم تُنشأ مسودة، ولم يُنشر شيء.")
        log("[FAIL] النتيجة: فشل توليد المحتوى (رمز خروج "
            f"{EXIT_GENERATION_FAILED}) — وليس اكتمال دورة تسويق.")
        if not dry_run:
            save_state(state)
        return EXIT_GENERATION_FAILED

    if dry_run:
        log(f"[DRY-RUN] لا كتابة. النسخ الصالحة: {', '.join(a['lang'] for a in ready)} — لم يُلمس أي ملف.")
        return 0

    if len(ready) == 2 and not skip_source_check:
        problems = check_sources(ready[0]["official_sources"])
        if problems:
            log("[REJECT] تعذّر التحقّق من المصادر الرسمية — تبقى النسختان مسودتين غير منشورتين:")
            for p in problems:
                log("   - " + redact(p))
            for art in ready:
                write_article_files(art, published=False)
                state["topics"][topic["id"]][art["lang"]] = "draft_unverified"
            save_state(state)
            return 0
    elif skip_source_check:
        log("[WARN] تم تخطّي التحقّق الشبكي من المصادر بأمر صريح (استخدام يدوي فقط).")

    if len(ready) != 2:
        missing = [l for l in ("ar", "en") if l not in results]
        log(f"[WARN] نسخة واحدة فقط اجتازت هذه الدورة (الناقص: {', '.join(missing)}) — "
            "لا نشر مع نسخة واحدة، ولن يُعاد إنشاء النسخة المنشورة سابقاً.")

    if mode != "auto" or len(ready) != 2:
        for art in ready:
            write_article_files(art, published=False)
            state["topics"][topic["id"]][art["lang"]] = "draft"
        save_state(state)
        log(f"[DRAFT] حفظ {len(ready)} مسودة في {DRAFTS_DIR} — لم تُضف إلى articles.json ولا إلى sitemap.xml.")
        log("[DONE] اكتملت دورة التسويق (بلا نشر).")
        return 0

    # --- النشر الآمن: نجهّز الصفحات في مجلد مؤقت، ونتحقّق من HTML وarticles.json
    # و sitemap.xml بالكامل قبل نقل أي شيء إلى الملفات العامة. فشل أي فحص ⇒
    # لا تُكتب صفحات ولا يُحدَّث articles.json/sitemap.xml (فلا صفحات يتيمة تُدفع).
    staging_root = Path(tempfile.mkdtemp(prefix="ksa-articles-"))
    try:
        staged_pages = []
        for art in ready:
            rel = Path(art["lang"]) / f"{art['slug']}.html"
            html_text = render_article_html(art, published=True)
            problems = validate_generated_page(html_text, art)
            if problems:
                log("[REJECT] صفحة المقال لم تجتز الفحص — لم يُنشر شيء: " + "; ".join(problems[:5]))
                save_state(state)
                return 0
            staged_path = staging_root / rel
            atomic_write_text(staged_path, html_text)
            staged_pages.append((staged_path, ARTICLES_DIR / rel))

        new_records = [article_record(art) for art in ready]
        records = merge_articles(records, new_records)
        problems = validate_articles_json(records)
        if problems:
            log("[REJECT] articles.json غير صالح — لم يُنشر شيء: " + "; ".join(problems[:5]))
            save_state(state)
            return 0

        try:
            xml_text = SITEMAP_XML.read_text(encoding="utf-8") if SITEMAP_XML.exists() else SITEMAP_EMPTY
            entries = []
            seen_tids = set()
            for art in ready:
                # زوج اللغتين يُضاف مرة واحدة لكل مقال (لا مرة لكل نسخة لغوية)
                if art["translation_id"] in seen_tids:
                    continue
                seen_tids.add(art["translation_id"])
                entries.extend(article_sitemap_entries(art))
            new_xml = add_sitemap_entries(xml_text, entries)
        except (OSError, ValueError) as exc:
            log("[REJECT] تعذّر تحديث sitemap.xml — لم يُنشر شيء: " + redact(exc))
            save_state(state)
            return 0
        problems = validate_sitemap(new_xml)
        if problems:
            log("[REJECT] sitemap.xml غير صالح — لم يُنشر شيء: " + "; ".join(problems))
            save_state(state)
            return 0

        # كل الفحوص ناجحة: انقل الصفحات إلى مجلد المقالات، ثم اكتب الفهارس العامة.
        for staged_path, dest in staged_pages:
            dest.parent.mkdir(parents=True, exist_ok=True)
            shutil.move(str(staged_path), str(dest))
            log(f"[OK] نُشرت الصفحة: {dest.relative_to(BASE_DIR).as_posix()}")
        atomic_write_json(ARTICLES_JSON, records)
        log("[OK] تحديث articles.json.")
        atomic_write_text(SITEMAP_XML, new_xml)
        log("[OK] تحديث sitemap.xml.")
    finally:
        shutil.rmtree(staging_root, ignore_errors=True)

    for art in ready:
        state["topics"][topic["id"]][art["lang"]] = "published"
    state["topics"][topic["id"]]["published_at"] = today_iso()
    save_state(state)

    write_social_file(ready, social_lang)
    log("[OK] تحديث latest_social_post.txt.")
    tg = send_telegram(ready, social_lang,
                       os.environ.get("TELEGRAM_BOT_TOKEN", ""),
                       os.environ.get("TELEGRAM_CHAT_ID", ""))
    log(f"Telegram: {tg}")
    log(f"[DONE] اكتملت دورة التسويق — الوضع=auto — نُشرت {len(ready)} نسخة لمقال واحد.")

    return 0


# =====================================================================================
# 12) اختبارات داخلية (بلا شبكة وبلا API)
# =====================================================================================

_PUBLISHED_SAMPLE = [{
    "translation_id": "zz-existing", "lang": "ar", "title": "سجل قائم",
    "url": "/articles/ar/zz-existing-ar.html", "published_at": "2026-01-01",
    "updated_at": "2026-01-01", "status": "published",
}]


def selftest() -> int:
    problems = []

    def check(label, ok):
        print(f"{LOG_PREFIX} [selftest] {'PASS' if ok else 'FAIL'} {label}", flush=True)
        if not ok:
            problems.append(label)

    topic = topic_by_id("eosb-basics")

    # 1) نموذج عربي سليم
    art_ar = None
    try:
        art_ar = validate_article(fixture_data("ar"), topic=topic, lang="ar", published_at="2026-01-01")
        check("validate_article: نموذج عربي سليم", art_ar["lang"] == "ar" and art_ar["url"].endswith("-ar.html"))
    except Reject as exc:
        check(f"validate_article: نموذج عربي سليم (رُفض: {redact(exc)})", False)

    # 2) نموذج إنجليزي سليم
    try:
        art_en = validate_article(fixture_data("en"), topic=topic, lang="en", published_at="2026-01-01")
        check("validate_article: نموذج إنجليزي سليم", art_en["lang"] == "en")
    except Reject as exc:
        check(f"validate_article: نموذج إنجليزي سليم (رُفض: {redact(exc)})", False)

    # 3) رفض HTML
    bad = fixture_data("ar")
    bad["sections"][0]["body"] = "<script>alert(1)</script>" + bad["sections"][0]["body"]
    check("رفض HTML داخل النص", _rejects(lambda: validate_article(bad, topic=topic, lang="ar", published_at="2026-01-01")))

    # 4) رفض مصدر غير مسموح / غير https
    bad = fixture_data("ar")
    bad["official_sources"] = [
        {"title": "مصدر خارجي", "url": "https://evil.example.com/x"},
        {"title": "مصدر غير آمن", "url": "http://gosi.gov.sa/"},
    ]
    check("رفض مصدر خارج النطاقات المسموحة", _rejects(lambda: validate_article(bad, topic=topic, lang="ar", published_at="2026-01-01")))

    # 5) رفض حقل زائد
    bad = fixture_data("ar")
    bad["extra_field"] = "x"
    check("رفض الحقول الزائدة", _rejects(lambda: validate_article(bad, topic=topic, lang="ar", published_at="2026-01-01")))

    # 6) رفض بروتوكول javascript
    bad = fixture_data("ar")
    bad["excerpt"] = "javascript:alert(1) " + bad["excerpt"]
    check("رفض بروتوكول javascript في النص", _rejects(lambda: validate_article(bad, topic=topic, lang="ar", published_at="2026-01-01")))

    # 7) العرض والهروب
    art = dict(art_ar) if art_ar else validate_article(fixture_data("ar"), topic=topic, lang="ar", published_at="2026-01-01")
    art["sections"] = [dict(art["sections"][0])] + art["sections"][1:]
    art["sections"][0]["heading"] = "A & B <i>"
    html_out = render_article_html(art, published=True)
    draft_out = render_article_html(art, published=False)
    check("الهروب من الوسوم في العرض", "<i>" not in html_out)
    check("canonical صحيح", f"{SITE_BASE}/articles/ar/{art['slug']}.html" in html_out)
    check("hreflang متبادل (ar/en)", 'hreflang="ar"' in html_out and 'hreflang="en"' in html_out and "-en.html" in html_out)
    check("كود Social Bar مرة واحدة", html_out.count(AD_SOCIAL_BAR) == 1)
    check("حاوية الإعلان مرة واحدة", html_out.count("container-7af3b8325dba6708da88eed5e517ec89") == 1)
    check("صفحة منشورة قابلة للفهرسة", "noindex" not in html_out)
    check("صفحة مسودة غير قابلة للفهرسة", "noindex" in draft_out)
    check("JSON-LD صالح", '"@type": "Article"' in html_out)

    # 7-أ) أكواد الإعلان المعتمدة في القالب المولَّد (bauval.org) وغياب النطاق القديم
    check("قالب المقال يستخدم كود Social Bar المعتمد (bauval.org)",
          AD_SOCIAL_BAR_SRC in html_out and html_out.count(AD_SOCIAL_BAR_SRC) == 1)
    check("قالب المقال يستخدم كود Native Banner المعتمد (bauval.org)",
          html_out.count(AD_NATIVE_BANNER_SRC) == 1)
    _native_id = re.search(r"bauval\.org/21/([0-9a-f]+)", html_out)
    _container_id = re.search(r'id="(container-[0-9a-f]+)"', html_out)
    check("معرّف حاوية الإعلان مطابق لمعرّف Native Banner",
          bool(_native_id and _container_id and _container_id.group(1) == "container-" + _native_id.group(1)))
    check("قالب المقال بلا نطاق إعلان قديم",
          LEGACY_AD_HOST not in ARTICLE_TEMPLATE.template
          and LEGACY_AD_HOST not in AD_SOCIAL_BAR
          and LEGACY_AD_HOST not in AD_NATIVE_BANNER)
    check("صفحة مولَّدة جديدة بلا نطاق إعلان قديم", LEGACY_AD_HOST not in html_out)
    check("validate_generated_page يقبل صفحة سليمة", validate_generated_page(html_out, art) == [])
    _legacy_probe = validate_generated_page(
        html_out.replace(AD_SOCIAL_BAR, '<script src="https://' + LEGACY_AD_HOST + '/x.js"></script>'),
        art)
    check("validate_generated_page يرفض صفحة تحمل نطاقاً قديماً",
          any(LEGACY_AD_HOST in p for p in _legacy_probe))

    # 8) دمج articles.json بلا حذف
    rec = {"translation_id": "x", "lang": "ar", "title": "t", "url": "/articles/ar/x-ar.html",
           "published_at": "2026-01-01", "updated_at": "2026-01-01", "status": "published"}
    merged = merge_articles([rec], [dict(rec, title="t2")])
    check("الدمج لا يكرّر الرابط ويحفظ تاريخ النشر", len(merged) == 1 and merged[0]["published_at"] == "2026-01-01")
    merged2 = merge_articles([rec], [dict(rec, url="/articles/en/x-en.html")])
    check("الدمج يحفظ السجل القديم", len(merged2) == 2)
    check("validate_articles_json يقبل سجلاً سليماً", validate_articles_json([rec]) == [])
    check("validate_articles_json يرفض مسودة في الملف العام", validate_articles_json([dict(rec, status="draft")]) != [])

    # 9) sitemap
    new_xml = add_sitemap_entries(SITEMAP_EMPTY, [{
        "loc": f"{SITE_BASE}/articles/ar/x-ar.html", "lastmod": "2026-01-01",
        "alternates": [("ar", f"{SITE_BASE}/articles/ar/x-ar.html")],
    }])
    check("sitemap: XML صالح", validate_sitemap(new_xml) == [])
    check("sitemap: لا تكرار عند الإضافة مرة أخرى",
          add_sitemap_entries(new_xml, [{"loc": f"{SITE_BASE}/articles/ar/x-ar.html", "lastmod": "2026-01-02"}]) == new_xml)


    # حماية من الانحدار: article_sitemap_entries يُرجع زوج اللغتين لكل مقال،
    # وقد يُمرَّر نفس العنصر مرتين (مرة لكل نسخة لغوية). يجب ألا يُنتج تكراراً.
    _pair = [
        {"loc": f"{SITE_BASE}/articles/ar/y-ar.html", "lastmod": "2026-01-03"},
        {"loc": f"{SITE_BASE}/articles/en/y-en.html", "lastmod": "2026-01-03"},
        {"loc": f"{SITE_BASE}/articles/ar/x-ar.html", "lastmod": "2026-01-04"},
    ]
    _dup_fixed = add_sitemap_entries(new_xml, _pair + _pair)
    check("sitemap: لا تكرار داخل قائمة العناصر الواردة نفسها",
          validate_sitemap(_dup_fixed) == []
          and _dup_fixed.count("x-ar.html</loc>") == 1
          and _dup_fixed.count("y-ar.html</loc>") == 1)

    # 10) أدوات مساعدة
    check("slug_ok", slug_ok("eosb-resignation-ar") and not slug_ok("سيء") and not slug_ok("A B"))
    check("redact يحجب القيم الحسّاسة", redact("key=SECRETVALUE123") == "key=***")
    check("is_allowed_source_url",
          is_allowed_source_url("https://www.hrsd.gov.sa/x")
          and is_allowed_source_url("https://qiwa.sa/y")
          and not is_allowed_source_url("https://example.com")
          and not is_allowed_source_url("http://www.hrsd.gov.sa/x"))

    # 11) قائمة المواضيع
    ids = [t["id"] for t in TOPICS]
    check("عدد المواضيع >= 30", len(TOPICS) >= 30)
    check("معرّفات المواضيع فريدة وصالحة", len(ids) == len(set(ids)) and all(slug_ok(i) for i in ids))

    # 12) اختيار الموضوعات: سجل النشر (articles.json) مرجع دائم لا يعتمد على الحالة
    t_first, t_second = TOPICS[0]["id"], TOPICS[1]["id"]
    pub_records = [
        {"translation_id": t_first, "lang": "ar", "status": "published"},
        {"translation_id": t_first, "lang": "en", "status": "published"},
    ]
    pairs_pub = existing_published_pairs(pub_records)
    check("existing_published_pairs: يقرأ المنشور فقط ويتجاهل غير المنشور",
          pairs_pub == {(t_first, "ar"), (t_first, "en")}
          and existing_published_pairs(
              [{"translation_id": t_first, "lang": "ar", "status": "draft"}]) == set()
          and existing_published_pairs(
              [{"translation_id": 5, "lang": "xx", "status": "published"}]) == set())
    check("pick_topic: لا يعيد موضوعاً اكتملت نسختاه في السجل المنشور",
          pick_topic(default_state(), pairs_pub)["id"] != t_first)
    check("pick_topic: يختار الموضوع التالي غير المنشور",
          pick_topic(default_state(), pairs_pub)["id"] == t_second)
    check("pick_topic: بلا سجل منشور يختار أول موضوع",
          pick_topic(default_state(), set())["id"] == t_first)
    check("pick_topic: نسخة منشورة واحدة لا تُكمل الموضوع",
          pick_topic(default_state(), {(t_first, "ar")})["id"] == t_first)
    check("pick_topic: فقدان الحالة تماماً لا يكرّر موضوعاً مكتملاً في السجل",
          pick_topic(default_state(), existing_published_pairs(pub_records))["id"] == t_second)
    check("pick_topic: حالة تالفة (بلا topics) لا تُسقط الاختيار",
          pick_topic({}, pairs_pub)["id"] == t_second)
    stopped = {"version": 1, "last_run": None,
               "topics": {t_first: {"ar": "pending", "en": "pending", "attempts": MAX_ATTEMPTS}}}
    check("pick_topic: يوقف الموضوع المتجاوز حدّ المحاولات (ويُبقي المحاولات محفوظة)",
          pick_topic(stopped, set())["id"] == t_second
          and stopped["topics"][t_first]["attempts"] == MAX_ATTEMPTS)
    healed_state = {"version": 1, "last_run": None,
                    "topics": {t_first: {"ar": "pending", "en": "error", "attempts": 2}}}
    _fixed = reconcile_state_with_records(healed_state, pairs_pub)
    check("reconcile: يُعلّم النسخ المنشورة ويُبقي المحاولات وحالة اللغة الأخرى",
          _fixed == 2 and healed_state["topics"][t_first]["ar"] == "published"
          and healed_state["topics"][t_first]["en"] == "published"
          and healed_state["topics"][t_first]["attempts"] == 2)
    check("reconcile: يحترم حالة languages غير المنشورة",
          reconcile_state_with_records(
              {"topics": {t_second: {"ar": "draft", "en": "pending", "attempts": 1}}}, pairs_pub) == 0)

    # 13) مزوّدو المحتوى (Groq افتراضياً، Gemini اختياري): إعادة المحاولة، بوابات
    #     الجودة، ومنع النشر — كلها باستجابات وهمية فقط (بلا شبكة وبلا انتظار حقيقي).
    _real_http_full = globals()["http_request_full"]
    _real_sleep = globals()["SLEEP"]
    _real_paths = {name: globals()[name] for name in (
        "ARTICLES_JSON", "SITEMAP_XML", "STATE_JSON", "SOCIAL_TXT",
        "ARTICLES_DIR", "DRAFTS_DIR")}
    _sandboxes = []
    _sleeps = []

    def _fake_http(responses):
        """يستبدل http_request_full باستجابات متتابعة؛ آخر استجابة تتكرّر."""
        calls = []

        def _fn(url, **kwargs):
            calls.append(kwargs)
            status, headers, body = responses[min(len(calls) - 1, len(responses) - 1)]
            return status, headers, body, url

        return _fn, calls

    _FAKE_GROQ_KEY = "gsk_FAKE_1234567890_SELFTEST"

    def _envelope(lang):
        text = json.dumps(fixture_data(lang), ensure_ascii=False)
        blob = {"candidates": [{"content": {"parts": [{"text": text}]}}]}
        return 200, {}, json.dumps(blob, ensure_ascii=False).encode("utf-8")

    def _groq_envelope(content=None, lang=None, finish="stop"):
        """ظرف Groq (OpenAI-compatible) بنصّ JSON داخل message.content."""
        if content is None:
            content = json.dumps(fixture_data(lang), ensure_ascii=False)
        blob = {
            "id": "chatcmpl-selftest",
            "object": "chat.completion",
            "model": DEFAULT_GROQ_MODEL,
            "choices": [{"index": 0, "finish_reason": finish,
                         "message": {"role": "assistant", "content": content}}],
            "usage": {"prompt_tokens": 10, "completion_tokens": 20, "total_tokens": 30},
        }
        return 200, {}, json.dumps(blob, ensure_ascii=False).encode("utf-8")

    def _request_prompt(kwargs):
        """يستخرج نصّ التعليمات من جسم الطلب أياً كان شكل المزوّد (Gemini أو Groq)."""
        body = json.loads(kwargs["data"].decode("utf-8"))
        if "messages" in body:
            return body["messages"][-1]["content"]
        return body["contents"][0]["parts"][0]["text"]

    def _provider_of(url):
        return "groq" if "api.groq.com" in url else "gemini"

    def _fake_by_lang(en_ok):
        """503 للنسخة العربية دائماً، و(503 أو نجاح) للنسخة الإنجليزية — بحسب شكل الطلب."""
        calls = {"ar": 0, "en": 0}
        urls = []

        def _fn(url, **kwargs):
            urls.append(url)
            prompt = _request_prompt(kwargs)
            lang = "en" if "لغة المخرجات: English" in prompt else "ar"
            calls[lang] += 1
            if lang == "en" and en_ok:
                ok_env = _groq_envelope(lang=lang) if _provider_of(url) == "groq" else _envelope(lang)
                return ok_env + (url,)
            return (503, {}, b'{"error":{"status":"UNAVAILABLE","message":"high demand"}}', url)

        return _fn, calls, urls

    def _sandbox():
        """مجلد مؤقّت بدل ملفات الموقع الحقيقية: الدورة الفاشلة لا تلمس المستودع."""
        root = Path(tempfile.mkdtemp(prefix="ksa-selftest-"))
        _sandboxes.append(root)
        globals()["ARTICLES_JSON"] = root / "articles.json"
        globals()["SITEMAP_XML"] = root / "sitemap.xml"
        globals()["STATE_JSON"] = root / "marketing_state.json"
        globals()["SOCIAL_TXT"] = root / "latest_social_post.txt"
        globals()["ARTICLES_DIR"] = root / "articles"
        globals()["DRAFTS_DIR"] = root / "drafts"
        atomic_write_json(ARTICLES_JSON, _PUBLISHED_SAMPLE)
        atomic_write_text(SITEMAP_XML, SITEMAP_EMPTY)
        return root

    try:
        globals()["SLEEP"] = _sleeps.append

        # (أ) نجاح بعد خطأ 503 مؤقّت واحد
        fake, calls = _fake_http([
            (503, {}, b'{"error":{"status":"UNAVAILABLE"}}'), _envelope("ar")])
        globals()["http_request_full"] = fake
        ok, data, msg = gemini_generate_json("p", api_key="k", model="m")
        check("إعادة المحاولة: نجاح بعد 503 مؤقّت",
              bool(ok) and isinstance(data, dict) and msg == "ok"
              and len(calls) == 2 and _sleeps == [backoff_delay(0)])

        # (ب) استمرار 503 حتى استنفاد الحدّ الأعلى
        _sleeps.clear()
        fake, calls = _fake_http([(503, {}, b'{"error":{"status":"UNAVAILABLE"}}')])
        globals()["http_request_full"] = fake
        ok, data, msg = gemini_generate_json("p", api_key="k", model="m")
        _delays = [backoff_delay(i) for i in range(GEMINI_MAX_TRIES - 1)]
        check("إعادة المحاولة: 503 متكرّر يستنفد الحدّ الأعلى بانتظار تصاعدي",
              not ok and data is None and msg.startswith("http_503")
              and len(calls) == GEMINI_MAX_TRIES
              and _sleeps == _delays and len(_sleeps) == GEMINI_MAX_TRIES - 1
              and all(_delays[i] < _delays[i + 1] for i in range(len(_delays) - 1))
              and "استُنفدت المحاولات" in msg)

        check("إعادة المحاولة: حدّ أعلى صريح وسقف انتظار معلَنان",
              2 <= GEMINI_MAX_TRIES <= 6
              and backoff_delay(50) == GEMINI_BACKOFF_MAX
              and backoff_delay(0) == GEMINI_BACKOFF_BASE
              and backoff_delay(0, retry_after="12") == 12.0
              and backoff_delay(0, retry_after="600") == GEMINI_BACKOFF_MAX
              and backoff_delay(0, retry_after="غير رقمي") == GEMINI_BACKOFF_BASE
              and {503, 429, 500, 502, 504} <= RETRYABLE_STATUS
              and not ({400, 401, 403, 404, 422} & RETRYABLE_STATUS))

        # (ج) خطأ غير مؤقّت (مفتاح غير صالح / طلب غير صحيح) ⇒ بلا أي إعادة
        _sleeps.clear()
        fake, calls = _fake_http([
            (400, {}, b'{"error":{"message":"API key not valid. Please pass a valid API key."}}')])
        globals()["http_request_full"] = fake
        ok, data, msg = gemini_generate_json("p", api_key="bad", model="m")
        check("إعادة المحاولة: الخطأ غير المؤقّت لا يُعاد إطلاقاً",
              not ok and len(calls) == 1 and _sleeps == []
              and msg.startswith("http_400") and "not valid" in msg
              and "غير قابل لإعادة المحاولة" in msg)

        # (د) فشل النسختين: لا مسودات، ولا صفحات، ولا تعديل على الفهارس، ومحاولة واحدة للموضوع
        _sandbox()
        before = (ARTICLES_JSON.read_bytes(), SITEMAP_XML.read_bytes())
        _sleeps.clear()
        fake, _calls, _urls = _fake_by_lang(en_ok=False)
        globals()["http_request_full"] = fake
        rc = run_once(mode="draft", provider="gemini", api_key="k", model="m")
        rec = load_state()["topics"][TOPICS[0]["id"]]
        check("Gemini دورة فاشلة: رمز خروج غير صفري (لا نجاح مضلّل)",
              rc == EXIT_GENERATION_FAILED and rc != 0)
        check("Gemini دورة فاشلة: لا صفحة منشورة ولا مسودة ولا ملف يتيم",
              not ARTICLES_DIR.exists() and not DRAFTS_DIR.exists()
              and not SOCIAL_TXT.exists()
              and (ARTICLES_JSON.read_bytes(), SITEMAP_XML.read_bytes()) == before)
        check("Gemini دورة فاشلة: الإعادات الداخلية لا تُحتسب محاولات ولا دورات",
              rec.get("attempts") == 1 and rec.get("ar") == "error"
              and rec.get("en") == "error" and _calls == {"ar": GEMINI_MAX_TRIES,
                                                          "en": GEMINI_MAX_TRIES})
        check("دورة فاشلة: الحالة تُحفظ كي يعمل حدّ المحاولات لاحقاً",
              load_state().get("last_run") and not (ARTICLES_DIR / "ar").exists())

        # (هـ) فشل نسخة واحدة في وضع auto: مسودة فقط، ولا نشر إطلاقاً
        good = list(ARTICLES_DIR.glob("**/*.html")) + list(DRAFTS_DIR.glob("**/*.html"))
        before = (ARTICLES_JSON.read_bytes(), SITEMAP_XML.read_bytes())
        fake, _calls, _urls = _fake_by_lang(en_ok=True)
        globals()["http_request_full"] = fake
        rc = run_once(mode="auto", provider="gemini", api_key="k", model="m")
        drafts = list(DRAFTS_DIR.glob("**/*.html"))
        check("فشل جزئي في وضع auto: لا نشر ولا سجل مقال (مسودة واحدة فقط)",
              rc == 0 and good == [] and len(drafts) == 1
              and "/en/" in drafts[0].as_posix()
              and not ARTICLES_DIR.exists()
              and (ARTICLES_JSON.read_bytes(), SITEMAP_XML.read_bytes()) == before
              and load_state()["topics"][TOPICS[0]["id"]]["en"] == "draft")

        # (و) غياب مفتاح المزوّد المحدَّد: فشل إعداد صريح بلا محاولات وبلا ملفات وبلا نداء شبكة
        _sandbox()
        before = (ARTICLES_JSON.read_bytes(), SITEMAP_XML.read_bytes())
        _net_calls = []

        def _no_network(url, **kwargs):
            _net_calls.append(url)
            return 503, {}, b'{"error":{"status":"UNAVAILABLE"}}', url

        globals()["http_request_full"] = _no_network

        def _capture_run(**kwargs):
            """يشغّل دورة مع التقاط stdout (بلا طباعة) ويرجع (rc, out)."""
            saved = sys.stdout
            cap = tempfile.TemporaryFile(mode="w+", encoding="utf-8")
            try:
                sys.stdout = cap
                rc_v = run_once(**kwargs)
                sys.stdout = saved
                cap.seek(0)
                out_v = cap.read()
                return rc_v, out_v
            finally:
                sys.stdout = saved
                cap.close()

        _saved_keys = {var: os.environ.pop(var, None) for var in PROVIDER_KEY_ENV.values()}
        try:
            rc, _out = _capture_run(mode="draft", provider="groq")
            rc_gem, _out_gem = _capture_run(mode="draft", provider="gemini")
            rc_dry, _out_dry = _capture_run(mode="draft", provider="groq", dry_run=True)
        finally:
            for var, val in _saved_keys.items():
                if val is not None:
                    os.environ[var] = val

        _state = load_state()
        check("غياب المفتاح (Groq): رمز خروج 3 ورسالة تسمّي GROQ_API_KEY بلا كشف سرّ",
              rc == EXIT_CONFIG_FAILED and rc != 0 and "GROQ_API_KEY" in _out
              and "groq" in _out and "لم يُجرَ توليد أو نشر" in _out)
        check("غياب المفتاح (Gemini): رمز خروج 3 ورسالة تسمّي GEMINI_API_KEY",
              rc_gem == EXIT_CONFIG_FAILED and "GEMINI_API_KEY" in _out_gem)
        check("غياب المفتاح: بلا محاولات وبلا ملفات وبلا نداء شبكة",
              _net_calls == []
              and _state["topics"][TOPICS[0]["id"]].get("attempts", 0) == 0
              and not STATE_JSON.exists() and not ARTICLES_DIR.exists()
              and not DRAFTS_DIR.exists() and not SOCIAL_TXT.exists()
              and (ARTICLES_JSON.read_bytes(), SITEMAP_XML.read_bytes()) == before)
        check("غياب المفتاح + dry-run: نجاح بلا كتابة (لا ينكسر CI/الاختبار الذاتي)",
              rc_dry == 0 and not STATE_JSON.exists() and not ARTICLES_DIR.exists()
              and not DRAFTS_DIR.exists()
              and (ARTICLES_JSON.read_bytes(), SITEMAP_XML.read_bytes()) == before)

        # (ز) مسار Groq الكامل: ظرف chat.completions صالح ⇒ JSON صالح ⇒ مسودتان
        _sandbox()
        before = (ARTICLES_JSON.read_bytes(), SITEMAP_XML.read_bytes())
        _groq_reqs = []

        def _fake_groq_ok(url, **kwargs):
            _groq_reqs.append({"url": url, "headers": dict(kwargs.get("headers") or {}),
                               "body": json.loads(kwargs["data"].decode("utf-8"))})
            prompt = _request_prompt(kwargs)
            lang = "en" if "لغة المخرجات: English" in prompt else "ar"
            return _groq_envelope(lang=lang) + (url,)

        globals()["http_request_full"] = _fake_groq_ok
        rc = run_once(mode="draft", provider="groq", api_key=_FAKE_GROQ_KEY,
                      skip_source_check=True)
        drafts = sorted(DRAFTS_DIR.glob("**/*.html"))
        check("Groq: ظرف JSON صالح يمرّ إلى بوابات التحقّق ويُحفظ مسودتين",
              rc == 0 and len(drafts) == 2 and len(_groq_reqs) == 2
              and all(r["url"] == GROQ_URL for r in _groq_reqs)
              and (ARTICLES_JSON.read_bytes(), SITEMAP_XML.read_bytes()) == before
              and load_state()["topics"][TOPICS[0]["id"]]["ar"] == "draft")
        check("Groq: الطلب يطلب JSON صالحاً (response_format) ويمرّر التعليمات",
              all(r["body"].get("response_format") == {"type": "json_object"}
                  for r in _groq_reqs)
              and all(r["body"].get("model") == DEFAULT_GROQ_MODEL for r in _groq_reqs)
              and all(r["body"]["messages"][-1]["role"] == "user"
                      and r["body"]["messages"][-1]["content"] for r in _groq_reqs))
        check("Groq: المفتاح في ترويسة Authorization فقط ولا يظهر في الجسم",
              all(r["headers"].get("Authorization") == f"Bearer {_FAKE_GROQ_KEY}"
                  for r in _groq_reqs)
              and all(_FAKE_GROQ_KEY not in json.dumps(r["body"], ensure_ascii=False)
                      for r in _groq_reqs))

        # (ح) نموذج Groq قابل للضبط عبر GROQ_MODEL
        _groq_reqs.clear()
        _saved_model = os.environ.get("GROQ_MODEL")
        os.environ["GROQ_MODEL"] = "openai/gpt-oss-120b"
        try:
            rc = run_once(mode="draft", provider="groq", api_key=_FAKE_GROQ_KEY,
                          skip_source_check=True)
        finally:
            if _saved_model is None:
                os.environ.pop("GROQ_MODEL", None)
            else:
                os.environ["GROQ_MODEL"] = _saved_model
        check("Groq: النموذج يُقرأ من GROQ_MODEL ويسود على الافتراضي",
              rc == 0 and _groq_reqs
              and all(r["body"].get("model") == "openai/gpt-oss-120b" for r in _groq_reqs))

        # (ط) JSON ناقص أو نصّ غير JSON: ترفضه البوابات الحالية، ولا ملف يُكتب
        _sandbox()
        before = (ARTICLES_JSON.read_bytes(), SITEMAP_XML.read_bytes())

        def _fake_content(text):
            def _fn(url, **kwargs):
                return _groq_envelope(content=text) + (url,)
            return _fn

        globals()["http_request_full"] = _fake_content('{"title": "ناقص", "slug": "x"}')
        rc = run_once(mode="draft", provider="groq", api_key=_FAKE_GROQ_KEY)
        st = load_state()["topics"][TOPICS[0]["id"]]
        check("Groq: JSON ناقص الحقول يُرفض ببوابات الجودة الحالية (بلا استثناء)",
              rc == EXIT_GENERATION_FAILED and st.get("ar") == "rejected"
              and st.get("en") == "rejected" and not DRAFTS_DIR.exists()
              and (ARTICLES_JSON.read_bytes(), SITEMAP_XML.read_bytes()) == before)

        _sandbox()
        before = (ARTICLES_JSON.read_bytes(), SITEMAP_XML.read_bytes())
        globals()["http_request_full"] = _fake_content("هذا ليس JSON على الإطلاق")
        rc = run_once(mode="draft", provider="groq", api_key=_FAKE_GROQ_KEY)
        st = load_state()["topics"][TOPICS[0]["id"]]
        check("Groq: نصّ غير JSON يُرفض ولا يُكتب أي ملف ولا فهرس",
              rc == EXIT_GENERATION_FAILED and st.get("ar") == "error"
              and not DRAFTS_DIR.exists()
              and (ARTICLES_JSON.read_bytes(), SITEMAP_XML.read_bytes()) == before)

        # (ي) إعادة المحاولة عند Groq: 429 مؤقّت مع Retry-After ثم نجاح
        _sleeps.clear()
        fake, calls = _fake_http([
            (429, {"Retry-After": "7"}, b'{"error":{"message":"rate limit reached"}}'),
            _groq_envelope(lang="ar"),
        ])
        globals()["http_request_full"] = fake
        ok, data, msg = groq_generate_json("p", api_key=_FAKE_GROQ_KEY, model=DEFAULT_GROQ_MODEL)
        check("Groq: 429 مؤقّت يُعاد ويحترم Retry-After (ثوانٍ) ثم ينجح",
              bool(ok) and isinstance(data, dict) and msg == "ok"
              and len(calls) == 2 and _sleeps == [7.0])

        _sleeps.clear()
        fake, calls = _fake_http([(503, {}, b'{"error":{"message":"overloaded"}}')])
        globals()["http_request_full"] = fake
        ok, data, msg = groq_generate_json("p", api_key=_FAKE_GROQ_KEY, model=DEFAULT_GROQ_MODEL)
        check("Groq: خطأ مؤقّت مستمرّ يستنفد الحدّ الأعلى (4 محاولات) ثم يفشل بوضوح",
              not ok and data is None and len(calls) == GEMINI_MAX_TRIES
              and msg.startswith("http_503") and "استُنفدت المحاولات" in msg
              and len(_sleeps) == GEMINI_MAX_TRIES - 1)

        # (ي) 401/403 ونموذج غير متاح: لا إعادة إطلاقاً، وتصنيف واضح
        _sleeps.clear()
        globals()["http_request_full"] = _fake_http(
            [(401, {}, b'{"error":{"message":"Invalid API Key"}}')])[0]
        ok, _d, msg = groq_generate_json("p", api_key=_FAKE_GROQ_KEY, model=DEFAULT_GROQ_MODEL)
        check("Groq: 401 (مفتاح غير صالح) لا يُعاد ويُصنَّف خطأ مصادقة",
              not ok and msg.startswith("http_401") and "مصادقة" in msg)

        _sleeps.clear()
        globals()["http_request_full"] = _fake_http(
            [(403, {}, b'{"error":{"message":"permission denied"}}')])[0]
        ok, _d, msg = groq_generate_json("p", api_key=_FAKE_GROQ_KEY, model=DEFAULT_GROQ_MODEL)
        check("Groq: 403 لا يُعاد ويُصنَّف خطأ صلاحية",
              not ok and msg.startswith("http_403") and "صلاحية" in msg)

        _sleeps.clear()
        globals()["http_request_full"] = _fake_http(
            [(404, {}, b'{"error":{"code":"model_not_found","message":"model not found"}}')])[0]
        ok, _d, msg = groq_generate_json("p", api_key=_FAKE_GROQ_KEY, model="غير-موجود")
        check("Groq: نموذج غير متاح لا يُعاد ويُصنَّف خطأ نموذج",
              not ok and msg.startswith("http_404") and "النموذج غير متاح" in msg)
        check("Groq: أخطاء 401/403/404 لم تُنتج أي انتظار",
              _sleeps == [])

        # (ك) 429 حصة يومية/فوترة: تكرار الطلب بلا فائدة ⇒ لا إعادة
        _sleeps.clear()
        fake, calls = _fake_http([
            (429, {"Retry-After": "3"},
             b'{"error":{"code":"rate_limit_exceeded","message":"Rate limit reached on requests per day (RPD)"}}'),
        ])
        globals()["http_request_full"] = fake
        ok, _d, msg = groq_generate_json("p", api_key=_FAKE_GROQ_KEY, model=DEFAULT_GROQ_MODEL)
        check("Groq: 429 حصة يومية/فوترة لا يُعاد (تجنّب تكرار بلا فائدة)",
              not ok and len(calls) == 1 and _sleeps == [] and "حصة" in msg)

        # (ل) لا يظهر المفتاح ولا أي جزء منه في السجل حتى لو أدرجته الاستجابة
        _sandbox()
        echo_body = json.dumps(
            {"error": {"message": f"Invalid API key: {_FAKE_GROQ_KEY}"}},
            ensure_ascii=False).encode("utf-8")
        globals()["http_request_full"] = _fake_http([(401, {}, echo_body)])[0]
        _saved_keys2 = {var: os.environ.pop(var, None) for var in PROVIDER_KEY_ENV.values()}
        try:
            os.environ["GROQ_API_KEY"] = _FAKE_GROQ_KEY
            rc, _out = _capture_run(mode="draft", provider="groq")
        finally:
            for var, val in _saved_keys2.items():
                if val is not None:
                    os.environ[var] = val
        check("لا يظهر المفتاح (ولا جزء منه) في السجل أو رسائل الفشل",
              _FAKE_GROQ_KEY not in _out and "gsk_" not in _out and "***" in _out
              and rc == EXIT_GENERATION_FAILED)

        # (م) لا انتقال تلقائي إلى Gemini عند فشل Groq
        _sandbox()
        fake, _calls, _urls = _fake_by_lang(en_ok=False)
        globals()["http_request_full"] = fake
        rc = run_once(mode="draft", provider="groq", api_key=_FAKE_GROQ_KEY)
        check("فشل Groq لا ينتقل تلقائياً إلى Gemini ولا يطلب أي مضيف آخر",
              rc == EXIT_GENERATION_FAILED and bool(_urls)
              and all(u == GROQ_URL for u in _urls)
              and not any("googleapis" in u for u in _urls))

        # (ن) فشل التوليد في وضع auto: لا نشر ولا مسودات ولا تغيير في الفهارس
        _sandbox()
        before = (ARTICLES_JSON.read_bytes(), SITEMAP_XML.read_bytes())
        fake, _calls, _urls = _fake_by_lang(en_ok=False)
        globals()["http_request_full"] = fake
        rc = run_once(mode="auto", provider="groq", api_key=_FAKE_GROQ_KEY)
        check("فشل Groq في وضع auto: لا نشر ولا مسودات ولا تغيير في articles.json/sitemap.xml",
              rc == EXIT_GENERATION_FAILED and not DRAFTS_DIR.exists()
              and not ARTICLES_DIR.exists() and not SOCIAL_TXT.exists()
              and (ARTICLES_JSON.read_bytes(), SITEMAP_XML.read_bytes()) == before)

        # (س) ثوابت المزوّد والموجِّه: الافتراضي Groq، والموجِّه لا يقبل مزوّداً مجهولاً
        check("ثوابت المزوّد: Groq هو الافتراضي وGemini خيار مدعوم",
              DEFAULT_PROVIDER == "groq" and DEFAULT_PROVIDER in AI_PROVIDERS
              and "gemini" in AI_PROVIDERS and DEFAULT_GROQ_MODEL == "openai/gpt-oss-20b"
              and GROQ_URL == "https://api.groq.com/openai/v1/chat/completions")
        check("موجِّه المزوّد: مزوّد مجهول يفشل بوضوح بلا أي طلب شبكة",
              generate_json("مجهول", "p", api_key="k", model="m")[0] is False
              and "unknown_provider" in generate_json("مجهول", "p", api_key="k", model="m")[2])
    finally:
        globals()["http_request_full"] = _real_http_full
        globals()["SLEEP"] = _real_sleep
        for _name, _val in _real_paths.items():
            globals()[_name] = _val
        for _root in _sandboxes:
            shutil.rmtree(_root, ignore_errors=True)

    if problems:
        log(f"[SELFTEST] فشل {len(problems)} فحصاً.")
        return 1
    log("[SELFTEST] كل الفحوص ناجحة.")
    return 0


def _rejects(fn) -> bool:
    try:
        fn()
        return False
    except Reject:
        return True


# =====================================================================================
# 13) فحص ملفات الموقع/الأرشفة
# =====================================================================================

def verify_outputs() -> list:
    """يرجع قائمة مشاكل؛ قائمة فارغة = نجاح. بلا شبكة."""
    problems = []

    # (أ) sitemap.xml — يُقرأ أولاً لأنه مرجع الفحص المتقاطع مع المقالات المنشورة.
    sitemap_locs = set()
    if SITEMAP_XML.exists():
        sitemap_text = SITEMAP_XML.read_text(encoding="utf-8")
        problems += validate_sitemap(sitemap_text)
        sitemap_locs = set(re.findall(r"<loc>\s*([^<]+?)\s*</loc>", sitemap_text))
        if "/drafts/" in sitemap_text:
            problems.append("sitemap.xml يشير إلى مسودات")
    else:
        problems.append("sitemap.xml غير موجود")

    # (ب) articles.json — وسجلاته المنشورة يجب أن يقابلها ملف فعلي وسطر في sitemap.
    records = load_json(ARTICLES_JSON, None)
    if records is None:
        problems.append("articles.json غير موجود أو غير قابل للقراءة")
    else:
        problems += validate_articles_json(records)
        if isinstance(records, list):
            for rec in records:
                if not isinstance(rec, dict) or rec.get("status") != "published":
                    continue
                rel = str(rec.get("url", "")).lstrip("/")
                if not rel:
                    problems.append("سجل منشور بلا رابط")
                    continue
                page = BASE_DIR / rel
                if not page.exists():
                    problems.append(f"سجل منشور بلا ملف مقابل: {rec.get('url')}")
                else:
                    page_html = page.read_text(encoding="utf-8", errors="replace")
                    if AD_SOCIAL_BAR_SRC not in page_html:
                        problems.append(f"مقال منشور بلا كود Social Bar المعتمد: {rec.get('url')}")
                    if AD_NATIVE_BANNER_SRC not in page_html:
                        problems.append(f"مقال منشور بلا كود Native Banner المعتمد: {rec.get('url')}")
                    if AD_CONTAINER_ID not in page_html:
                        problems.append(f"مقال منشور بلا حاوية الإعلان المعتمدة: {rec.get('url')}")
                    if LEGACY_AD_HOST in page_html:
                        problems.append(f"مقال منشور يحمل نطاق إعلان قديم: {rec.get('url')}")
                if SITEMAP_XML.exists() and (SITE_BASE + "/" + rel) not in sitemap_locs:
                    problems.append(f"مقال منشور غير مُدرج في sitemap.xml: {rec.get('url')}")

    # (ج) index.html — الهوية الأساسية وأكواد الإعلان لا تتغيّر.
    idx = BASE_DIR / "index.html"
    if not idx.exists():
        problems.append("index.html غير موجود")
    else:
        text = idx.read_text(encoding="utf-8", errors="replace")
        if "google-site-verification" not in text:
            problems.append("index.html: وسم تحقّق Google مفقود")
        if text.count("7cdd0a31b4560a6ce3906a22a43c5ed3") != 1:
            problems.append("index.html: كود Social Bar ليس مرة واحدة")
        if text.count("container-7af3b8325dba6708da88eed5e517ec89") != 1:
            problems.append("index.html: حاوية الإعلان ليست مرة واحدة")
        if LEGACY_AD_HOST in text:
            problems.append("index.html: يحمل نطاق إعلان قديم")
        if not text.rstrip().endswith("</html>"):
            problems.append("index.html: الملف لا ينتهي بـ </html>")

    return problems


# =====================================================================================
# 14) واجهة الأوامر
# =====================================================================================

def main(argv=None) -> int:
    parser = argparse.ArgumentParser(
        prog="auto_marketing.py",
        description="KSA Tools — توليد مقالات ثنائية اللغة وأرشفتها ومنشوراتها التسويقية.",
    )
    parser.add_argument("--selftest", action="store_true", help="اختبارات داخلية بلا شبكة ولا API")
    parser.add_argument("--verify", action="store_true", help="فحص ملفات الموقع والأرشفة")
    parser.add_argument("--dry-run", action="store_true", help="دورة كاملة بمحتوى تجريبي بلا كتابة")
    parser.add_argument("--topic", default=None, help="معرّف موضوع محدّد (مثال: eosb-resignation)")
    parser.add_argument("--mode", choices=["draft", "auto"], default=None, help="وضع النشر")
    parser.add_argument("--provider", choices=list(AI_PROVIDERS), default=None,
                        help="مزوّد المحتوى (الافتراضي من AI_PROVIDER أو groq؛ لا انتقال تلقائي)")
    parser.add_argument("--social-lang", choices=["ar", "en", "both"], default=None, help="لغة المنشور التسويقي")
    parser.add_argument("--skip-source-check", action="store_true",
                        help="تخطّي التحقّق الشبكي من المصادر الرسمية (استخدام يدوي فقط)")
    args = parser.parse_args(argv)

    if args.selftest:
        return selftest()

    if args.verify:
        problems = verify_outputs()
        if problems:
            for p in problems:
                log("[VERIFY] " + p)
            return 1
        log("[VERIFY] كل الفحوص ناجحة.")
        return 0

    mode = args.mode or os.environ.get("PUBLISH_MODE") or "draft"
    if mode not in ("draft", "auto"):
        log(f"[WARN] قيمة PUBLISH_MODE غير معروفة ({mode}) — سيُستخدم draft.")
        mode = "draft"
    social_lang = args.social_lang or os.environ.get("SOCIAL_LANGUAGE") or "both"
    if social_lang not in ("ar", "en", "both"):
        social_lang = "both"

    try:
        return run_once(mode=mode, topic_id=args.topic, social_lang=social_lang,
                        dry_run=args.dry_run, skip_source_check=args.skip_source_check,
                        provider=args.provider)
    except Exception as exc:  # noqa: BLE001
        log(f"[ERROR] فشل غير متوقّع: {redact(exc)}")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
