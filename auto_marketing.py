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
    python auto_marketing.py --topic labor-art81 --article-lang en  # توليد نسخة إنجليزية فقط
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
    Groq هو الافتراضي (‎/v1/chat/completions مع Structured Outputs: response_format=json_schema
    وstrict=true بمخطّط مطابق لبنية المقال بالحرف)، وGemini خيار
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
    4 = إعداد نشر غير آمن: mode=auto مع skip_source_check=true —
        يُرفض قبل قراءة/كتابة الحالة أو الاتصال بالشبكة.

الإعادة عند أخطاء المزوّد المؤقّتة:
    يُعاد الطلب عند 408/425/500/502/503/504 وعند 429 المؤقّت (تجاوز معدّل) بحدّ أقصى
    GEMINI_MAX_TRIES = 4 محاولات لكل نسخة لغوية، بتراجع تصاعدي 2/4/8s (سقف 30s) وباحترام
    Retry-After كرقم ثوانٍ فقط، وتُقرأ كذلك مهلة «try again in Xs» من نص 429 إن وُجدت.
    لا يُعاد عند 401/403 (مصادقة)، أو نموذج غير متاح، أو علامة صريحة على حصة يومية؛
    أما كلمات الخطة/الفوترة العامة فلا تتغلب على دليل TPM/RPM أو المهلة المؤقتة.
    الإعادة ليست محاولة موضوع جديدة ولا تزيد MAX_ATTEMPTS.
"""

from __future__ import annotations

import argparse
import hashlib
import html
import json
import os
import re
import shutil
import socket
import sys
import tempfile
import time
import urllib.error
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta, timezone
from email.utils import parsedate_to_datetime
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
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

# النطاقات المسموح بها للمصادر الرسمية (لا توسيع: كل نطاق ليس `.gov.sa` أو قوى مرفوض)
ALLOWED_SOURCE_SUFFIXES = (".gov.sa",)
ALLOWED_SOURCE_HOSTS = {"qiwa.sa", "www.qiwa.sa"}
# نطاقات منتهية/مهجورة تُرفض صراحةً فلا يمرّ مصدر ميت من البوابة الساكنة.
# `mol.gov.sa` هو الاسم السابق لوزارة العمل، وتحققنا عملياً أنه لا يُترجَم عبر DNS
# (NXDOMAIN) — البديل الرسمي الحالي هو `hrsd.gov.sa`.
BLOCKED_SOURCE_HOSTS = {"mol.gov.sa", "www.mol.gov.sa"}

# فحص المصادر عبر الشبكة: بعض المواقع الرسمية (مثل `hrsd.gov.sa`) ترفض الطلبات بلا
# ترويسات طلب عادية فتُعيد 403، وتُعيد 200 معها — لذا نرسل ترويسات قياسية.
SOURCE_CHECK_TIMEOUT = 20
SOURCE_MIN_BYTES = 200
# ترويسة `User-Agent` معرَّفة هنا (قبل `SOURCE_REQUEST_HEADERS`) لتُستعمل في فحص المصادر
# وفي بقية الطلبات دون تكرار.
UA = "KSA-Tools-Bot/1.0 (+https://ksatools.github.io/)"
SOURCE_REQUEST_HEADERS = {
    "User-Agent": UA,
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "ar,en;q=0.8",
}
# مكتبة المصادر الرسمية المعتمدة: الرابط الأساسي + بديل رسمي لنفس الجهة عند تعذّر الأول.
ARTICLE85_ENGLISH_SOURCES = (
    ("End-of-Service Award Regulations — Ministry of Human Resources and Social Development",
     "https://www.hrsd.gov.sa/en/knowledge-centre/articles/317"),
    ("Saudi Labour Law (official English translation, PDF) — Ministry of Human Resources and Social Development",
     "https://www.hrsd.gov.sa/sites/default/files/2023-02/Labor.pdf"),
)

OFFICIAL_SOURCE_LIBRARY = {
    "hrsd_home": (
        "وزارة الموارد البشرية والتنمية الاجتماعية",
        "https://www.hrsd.gov.sa/"),
    "hrsd_labor_relations": (
        "علاقات العمل — وزارة الموارد البشرية والتنمية الاجتماعية",
        "https://www.hrsd.gov.sa/علاقات-العمل"),
    "hrsd_labor_law": (
        "نظام العمل — وزارة الموارد البشرية والتنمية الاجتماعية",
        "https://www.hrsd.gov.sa/knowledge-centre/نظام-العمل"),
    "hrsd_eosb": (
        "نهاية الخدمة — وزارة الموارد البشرية والتنمية الاجتماعية",
        "https://www.hrsd.gov.sa/media-center/media/leendofservice"),
    "hrsd_services": (
        "دليل خدمات وزارة الموارد البشرية والتنمية الاجتماعية",
        "https://www.hrsd.gov.sa/ministry-services/services"),
    "gosi_home": (
        "المؤسسة العامة للتأمينات الاجتماعية",
        "https://www.gosi.gov.sa/"),
    "qiwa_eosb": (
        "منصة قوى — احتساب مكافأة نهاية الخدمة",
        "https://qiwa.sa/ar/employees/manage-your-current-job/how-calculate-your-end-service-benefits"),
}
# لكل موضوع: مصدر أساسي أولاً ثم بديل رسمي معتمد لنفس الجهة (عند تعذّر الأول).
DEFAULT_SOURCE_KEYS = ("hrsd_labor_law", "hrsd_home", "gosi_home")
TOPIC_SOURCE_KEYS = {
    "eosb-basics": ("hrsd_eosb", "hrsd_labor_law", "hrsd_home"),
    "eosb-resignation": ("hrsd_eosb", "hrsd_labor_law", "hrsd_home"),
    "eosb-full-entitlement": ("hrsd_eosb", "hrsd_labor_law", "hrsd_home"),
    "labor-art84": ("hrsd_labor_law", "hrsd_labor_relations", "hrsd_home"),
    "labor-art85": ("hrsd_labor_law", "hrsd_labor_relations", "hrsd_home"),
    "labor-art81": ("hrsd_labor_law", "hrsd_labor_relations", "hrsd_home"),
    "labor-art80": ("hrsd_labor_law", "hrsd_labor_relations", "hrsd_home"),
    "rights-contract-end": ("hrsd_labor_relations", "hrsd_labor_law", "hrsd_home"),
    "rights-employer-termination": ("hrsd_labor_relations", "hrsd_labor_law", "hrsd_home"),
    "annual-leave-balance": ("hrsd_labor_law", "hrsd_services", "hrsd_home"),
    "daily-monthly-wage": ("hrsd_labor_law", "hrsd_home", "hrsd_services"),
    "wage-definition": ("hrsd_labor_law", "hrsd_home", "hrsd_services"),
    "basic-vs-actual-wage": ("hrsd_labor_law", "hrsd_home", "gosi_home"),
    "payslip-reading": ("hrsd_labor_law", "gosi_home", "hrsd_home"),
    "net-salary-calculation": ("gosi_home", "hrsd_labor_law", "hrsd_home"),
    "final-settlement": ("hrsd_labor_relations", "hrsd_labor_law", "hrsd_home"),
    "contract-end-vs-resignation": ("hrsd_eosb", "hrsd_labor_law", "hrsd_home"),
    "notice-period": ("hrsd_labor_law", "hrsd_labor_relations", "hrsd_home"),
    "employee-exit-checklist": ("hrsd_labor_relations", "hrsd_labor_law", "hrsd_home"),
    "gosi-overview": ("gosi_home", "hrsd_labor_law", "hrsd_home"),
    "gosi-deduction-basis": ("gosi_home", "hrsd_labor_law", "hrsd_home"),
    "gosi-new-registrant": ("gosi_home", "hrsd_services", "hrsd_home"),
}


def official_sources_for(topic) -> list:
    """المصادر الرسمية المفضّلة لموضوع: الأساسي أولاً ثم بدائله الرسمية."""
    tid = topic.get("id") if isinstance(topic, dict) else ""
    keys = TOPIC_SOURCE_KEYS.get(tid) or DEFAULT_SOURCE_KEYS
    out = []
    for key in keys:
        entry = OFFICIAL_SOURCE_LIBRARY.get(key)
        if entry:
            out.append({"title": entry[0], "url": entry[1]})
    return out

MIN_WORDS = {"ar": 250, "en": 250}
MIN_SECTIONS = 3
MAX_SECTIONS = 12
MIN_TOTAL_CHARS = 1200
MAX_ATTEMPTS = 3

# سياسة إعادة المحاولة عند استدعاء مزوّد المحتوى (Groq/Gemini): أخطاء مؤقّتة فقط.
#   408/425 = انتهاء مهلة أو طلب مبكّر، 429 = تجاوز المعدّل، 5xx = خلل مؤقّت عند المزوّد.
#   503 (UNAVAILABLE) هو الأكثر وقوعاً: «النموذج يواجه طلباً مرتفعاً حالياً».
RETRYABLE_STATUS = frozenset({408, 425, 429, 500, 502, 503, 504})
# حدّ أعلى صريح لإعادات Groq المؤقّتة، مع سقف مستقل لكل نسخة لغوية.
# الإعادة الداخلية ليست محاولة موضوع جديدة ولا دورة تسويق جديدة: عدّاد `attempts`
# يُزاد مرة واحدة لكل دورة في run_once، لا لكل نداء شبكة.
GEMINI_MAX_TRIES = 4
GEMINI_BACKOFF_BASE = 2.0   # ثانية — الانتظار يتضاعف: 2s, 4s, 8s …
GEMINI_BACKOFF_MAX = 30.0   # سقف الانتظار التصاعدي العادي بين محاولتين
GROQ_INITIAL_HTTP_TRIES = 4
GROQ_MAX_REQUESTS_PER_LANGUAGE = 5  # hard cap including retries/schema and content repair; allows one bounded retry after transient repair 429
GROQ_LANGUAGE_GAP_SECONDS = 12.0  # cool-down between Arabic and English requests
# رمز خروج مميّز لفشل توليد المحتوى (لا نجاح مضلّل)، ويوقف كل خطوات النشر بعده.
EXIT_GENERATION_FAILED = 2
# رمز خروج مميّز لفشل الإعداد (غياب مفتاح المزوّد): لا توليد ولا نشر ولا استهلاك محاولات.
EXIT_CONFIG_FAILED = 3
# منع fail-closed للنشر التلقائي إذا طُلب تخطي التحقق من المصادر الرسمية.
EXIT_UNSAFE_PUBLISH_CONFIG = 4

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
# دلائل قاطعة على حصة يومية/منتهية: لا تُعاد حتى لو وُجدت ترويسة Retry-After.
DAILY_QUOTA_STOP_HINTS = (
    "requests per day", "per day", "daily limit", "daily quota",
    "insufficient_quota", "exceeded your current quota", "payment required",
)
# عبارات الخطة/الفوترة العامة قد تظهر مع حدّ TPM مؤقّت، لذا لا تكفي وحدها لمنع الإعادة.
QUOTA_STOP_HINTS = ("check your plan", "billing")
# دلائل صريحة على نافذة تحديد معدّل مؤقّت، حتى إن تضمنت الرسالة نصائح عامة عن الفوترة.
TEMPORARY_RATE_LIMIT_HINTS = ("tokens per minute", "requests per minute")
RETRY_DELAY_RE = re.compile(
    r"\b(?:try again|retry(?: after)?)\s+(?:in\s+)?"
    r"(?P<seconds>\d+(?:\.\d+)?)\s*"
    r"(?P<unit>s|sec(?:ond|onds)?|m|min(?:ute|utes)?)\b",
    re.IGNORECASE,
)

# نقطة استبدال للاختبارات: نصمت الانتظار الحقيقي في الاختبار الذاتي.
SLEEP = time.sleep

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


def today_iso(now: datetime | None = None) -> str:
    """Return the calendar date in Saudi Arabia (UTC+03, no daylight saving)."""
    riyadh_tz = timezone(timedelta(hours=3), name="Asia/Riyadh")
    current = now if now is not None else datetime.now(timezone.utc)
    if current.tzinfo is None:
        current = current.replace(tzinfo=timezone.utc)
    return current.astimezone(riyadh_tz).date().isoformat()


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


ARTICLE_NUMBER_PATTERN = re.compile(
    r"(?<![\w])(?:SAR\s+)?[<>≤≥]?\s*(?:\d{1,3}(?:,\d{3})+|\d+)(?:\.\d+)?"
    r"(?:\s*/\s*(?:\d{1,3}(?:,\d{3})+|\d+)(?:\.\d+)?)?"
    r"(?:\s*(?:[–—-]|\bto\b)\s*[<>≤≥]?\s*(?:\d{1,3}(?:,\d{3})+|\d+)(?:\.\d+)?)?"
    r"(?:\s?%)?(?![\w])",
    re.IGNORECASE,
)
ARTICLE_INLINE_MARKUP_PATTERN = re.compile(r"(\*\*.+?\*\*|__.+?__|\*[^*\n]+\*)")


def _render_numeric_text(value: str) -> str:
    """Escape plain text and isolate numeric values for consistent LTR rendering in both languages."""
    text = str(value or "")
    parts = []
    cursor = 0
    for match in ARTICLE_NUMBER_PATTERN.finditer(text):
        parts.append(esc(text[cursor:match.start()]))
        parts.append(f'<bdi class="numeric" dir="ltr">{esc(match.group(0))}</bdi>')
        cursor = match.end()
    parts.append(esc(text[cursor:]))
    return "".join(parts)


def render_inline_prose(value: str) -> str:
    """Render the small, safe inline-markup subset used in article drafts (bold/italic/numbers)."""
    text = str(value or "")
    # Correct punctuation spacing before numeric isolation; generated text occasionally
    # contains "Article 84 ." or "المادة 84 :" which looks unpolished in the final page.
    text = re.sub(r"\s+([.,;:!?؟،؛])", r"\1", text)
    chunks = ARTICLE_INLINE_MARKUP_PATTERN.split(text)
    out = []
    for chunk in chunks:
        if not chunk:
            continue
        if chunk.startswith("**") and chunk.endswith("**"):
            out.append("<strong>" + _render_numeric_text(chunk[2:-2]) + "</strong>")
        elif chunk.startswith("__") and chunk.endswith("__"):
            out.append("<strong>" + _render_numeric_text(chunk[2:-2]) + "</strong>")
        elif chunk.startswith("*") and chunk.endswith("*"):
            out.append("<em>" + _render_numeric_text(chunk[1:-1]) + "</em>")
        else:
            out.append(_render_numeric_text(chunk))
    return "".join(out)


def _split_article_sentences(value: str) -> list:
    """Conservative sentence splitting used only to break very long text walls into readable paragraphs."""
    text = str(value or "").strip()
    if not text:
        return []
    return [
        part.strip()
        for part in re.split(r"(?<=[.!?؟])\s+(?=[A-Z0-9\u0600-\u06FF])", text)
        if part.strip()
    ]


def _expand_inline_article_lists(value: str) -> str:
    """Turn inline bullets/numbered steps into line markers before HTML rendering."""
    text = str(value or "")
    # Strip invisible bidi controls before parsing list markers. They can appear
    # in Arabic LLM output and prevent "5." or "٢." from matching at line start.
    text = re.sub(r"[\u061c\u200e\u200f\u202a-\u202e\u2066-\u2069]", "", text)
    text = re.sub(r"^\s*[-–]\s+", "• ", text)
    # A single hyphen after a colon is a sub-step marker, not prose punctuation.
    # Split it even when the generator emits only one sub-step in the paragraph.
    text = re.sub(r":\s+[-–]\s+", ":\n• ", text)
    text = re.sub(r"\s+([•●▪])\s+", lambda match: "\n" + match.group(1) + " ", text)
    # Only split single-digit inline markers here: Article references such as "Article 86. The"
    # must remain normal prose, not be mistaken for numbered list items. Accept
    # both Western and Arabic-Indic digits used by bilingual article generation.
    text = re.sub(r"(?<!\d)\s+([1-9١-٩][.)])\s+", r"\n\1 ", text)
    # Arabic drafts sometimes encode every sub-step as '- item' inside a single sentence.
    # Require repeated spaced hyphens so a normal dash in prose is not mistaken for a list.
    if len(re.findall(r"\s+-\s+", text)) >= 2:
        text = re.sub(r"\s+-\s+", "\n• ", text)
    return text


def render_article_body(body: str) -> str:
    """Render readable paragraphs and semantic lists while keeping list numbering stable."""
    text = str(body or "").replace("\r\n", "\n").replace("\r", "\n")
    text = re.sub(r"[\u061c\u200e\u200f\u202a-\u202e\u2066-\u2069]", "", text)
    # The template renders its own FAQ section, so remove only a duplicated heading artifact.
    text = re.sub(
        r"(?:\bCommon Questions\s+)?\bFAQ(?:\s+FAQ){1,}\b",
        " ",
        text,
        flags=re.IGNORECASE,
    )
    text = re.sub(r"[ \t]+\n", "\n", text).strip()
    paragraphs = [part for part in re.split(r"\n\s*\n", text) if part.strip()]
    blocks = []

    for paragraph in paragraphs:
        expanded = _expand_inline_article_lists(
            re.sub(r"[ \t]*\n[ \t]*", " ", paragraph).strip()
        )
        lines = [line.strip() for line in expanded.split("\n") if line.strip()]
        tokens = []
        for line in lines:
            ordered = re.match(r"^(\d{1,2})[.)]\s+(.+)$", line)
            bullet = re.match(r"^[•●▪]\s+(.+)$", line)
            if ordered:
                tokens.append(("ol", ordered.group(2).strip(), int(ordered.group(1))))
            elif bullet:
                tokens.append(("ul", bullet.group(1).strip(), None))
            else:
                sentences = _split_article_sentences(line)
                if len(sentences) >= 4:
                    for index in range(0, len(sentences), 2):
                        tokens.append(("p", " ".join(sentences[index:index + 2]), None))
                else:
                    tokens.append(("p", line, None))

        # If prose follows the final inline list item, move that prose back to paragraphs.
        list_indexes = [i for i, token in enumerate(tokens) if token[0] in ("ul", "ol")]
        if list_indexes and list_indexes[-1] == len(tokens) - 1:
            last_index = list_indexes[-1]
            last_kind, last_text, last_number = tokens[last_index]
            sentences = _split_article_sentences(last_text)
            if len(sentences) > 1:
                tokens[last_index] = (last_kind, sentences[0], last_number)
                tokens.extend(("p", sentence, None) for sentence in sentences[1:])

        index = 0
        while index < len(tokens):
            kind, value, number = tokens[index]
            if kind == "p":
                blocks.append(f"<p>{render_inline_prose(value)}</p>")
                index += 1
                continue

            items = []
            list_start = number if kind == "ol" and number is not None else 1
            expected_number = list_start
            while index < len(tokens) and tokens[index][0] == kind:
                token_kind, token_text, token_number = tokens[index]
                if kind == "ol":
                    current_number = token_number if token_number is not None else expected_number
                    if items and current_number != expected_number:
                        break
                    if not items:
                        list_start = current_number
                    expected_number = current_number + 1
                items.append(token_text)
                index += 1

            # Bullets immediately following a numbered item ending in a colon are
            # visually and semantically part of that step; nest them in its <li>.
            nested_items = []
            if (
                kind == "ol"
                and items
                and items[-1].rstrip().endswith((":", "："))
                and index < len(tokens)
                and tokens[index][0] == "ul"
            ):
                while index < len(tokens) and tokens[index][0] == "ul":
                    nested_items.append(tokens[index][1])
                    index += 1

            rendered_items = [render_inline_prose(item) for item in items]
            if nested_items:
                nested_html = '<ul class="article-list">' + "".join(
                    f"<li>{render_inline_prose(item)}</li>" for item in nested_items
                ) + "</ul>"
                rendered_items[-1] += nested_html

            tag = "ol" if kind == "ol" else "ul"
            start_attr = (
                f' start="{list_start}"'
                if kind == "ol" and list_start != 1
                else ""
            )
            blocks.append(
                f'<{tag} class="article-list"{start_attr}>'
                + "".join(f"<li>{item}</li>" for item in rendered_items)
                + f"</{tag}>"
            )

    return "\n      ".join(blocks)

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


def fixture_data(lang: str, topic_id: str = "eosb-basics") -> dict:
    """نموذج اختباري داخلي؛ يتضمن مثال مكافأة مضبوطاً للموضوعات القانونية فقط."""
    is_eosb = topic_id in EOSB_TOPIC_IDS
    scenario = EOSB_REQUIRED_SCENARIO.get(
        topic_id,
        "resignation" if topic_id in {"labor-art85", "eosb-resignation", "contract-end-vs-resignation"}
        else "article81" if topic_id == "labor-art81"
        else "base",
    )
    calculation_example = ({
        "monthly_wage": "12000", "years": "6", "months": "0", "days": "0",
        "scenario": scenario, "full_benefit": "42000",
        "payable_benefit": "28000" if scenario == "resignation" else "42000",
    } if is_eosb else {
        "monthly_wage": "", "years": "", "months": "", "days": "",
        "scenario": "", "full_benefit": "", "payable_benefit": "",
    })
    if lang == "ar":
        example = ""
        if is_eosb and scenario == "resignation":
            example = (
                " مثال اختباري توضيحي: الأجر الشهري 12,000 ريال ومدة الخدمة 6 سنوات؛ "
                "المكافأة الأساسية 42,000 ريال، وبعد تطبيق نسبة الاستقالة يصبح المبلغ المستحق 28,000 ريال."
            )
        elif is_eosb and scenario == "article81":
            example = (
                " مثال اختباري توضيحي: الأجر الشهري 12,000 ريال ومدة الخدمة 6 سنوات؛ "
                "المكافأة الأساسية والمبلغ المستحق في هذا المثال 42,000 ريال."
            )
        elif is_eosb and scenario == "article87":
            example = (
                " مثال اختباري توضيحي: الأجر الشهري 12,000 ريال ومدة الخدمة 6 سنوات؛ "
                "يفترض هذا المثال ترك العامل العمل بسبب قوة قاهرة خارجة عن إرادته وفق المادة 87، "
                "وليس استقالة عادية تخضع لنسب المادة 85؛ المكافأة الأساسية والمبلغ المستحق 42,000 ريال."
            )
        elif is_eosb:
            example = (
                " مثال اختباري توضيحي: الأجر الشهري 12,000 ريال ومدة الخدمة 6 سنوات؛ "
                "المكافأة الأساسية قبل أي تعديل يعتمد على سبب انتهاء العلاقة 42,000 ريال."
            )
        return {
            "title": "مقال اختباري عن حساب مكافأة نهاية الخدمة",
            "meta_description": "وصف اختباري قصير يوضّح حساب مكافأة نهاية الخدمة للأغراض الداخلية فقط دون نشر.",
            "excerpt": "ملخص اختباري لصفحة توضيحية عن حساب المكافأة وشروط الاستحقاق الأساسية في الاختبار.",
            "sections": [
                {"heading": "أساس الحساب", "body": _AR_BODY + " " + _AR_BODY, "bullets": ["نقطة أولى", "نقطة ثانية"]},
                {"heading": "أجزاء السنة", "body": _AR_BODY + " " + _AR_BODY, "bullets": []},
                {"heading": "الاستقالة", "body": _AR_BODY + " " + _AR_BODY, "bullets": ["نقطة ثالثة"]},
                {"heading": "مثال توضيحي", "body": _AR_BODY + " " + _AR_BODY + example, "bullets": []},
            ],
            "faq": [
                {"q": "هل هذا المقال حقيقي؟", "a": "لا، هذا محتوى اختباري داخلي يُستخدم في فحوص الجودة الآلية فقط ولا يُنشر."},
                {"q": "متى يُستخدم؟", "a": "يُستخدم عند تشغيل السكربت في وضع الاختبار الذاتي أو المحاكاة بدون مفتاح API."},
            ],
            "official_sources": [
                {"title": "المؤسسة العامة للتأمينات الاجتماعية", "url": "https://www.gosi.gov.sa/"},
                {"title": "وزارة الموارد البشرية والتنمية الاجتماعية", "url": "https://www.hrsd.gov.sa/"},
            ],
            "calculation_example": calculation_example,
        }
    example = ""
    if is_eosb and scenario == "resignation":
        example = (
            " Internal illustrative test example: monthly wage SAR 12,000 and six years of service; "
            "the full base benefit is SAR 42,000, and the payable amount after the resignation ratio is SAR 28,000."
        )
    elif is_eosb and scenario == "article81":
        example = (
            " Internal illustrative test example: monthly wage SAR 12,000 and six years of service; "
            "the base benefit and payable amount in this example are SAR 42,000."
        )
    elif is_eosb and scenario == "article87":
        example = (
            " Internal illustrative test example: monthly wage SAR 12,000 and six years of service; "
            "this scenario assumes the worker left work due to force majeure beyond their control under Article 87, "
            "not an ordinary resignation under Article 85; the base benefit and payable amount are SAR 42,000."
        )
    elif is_eosb:
        example = (
            " Internal illustrative test example: monthly wage SAR 12,000 and six years of service; "
            "the base benefit before any reason-specific adjustment is SAR 42,000."
        )
    return {
        "title": "Sample Article About Entitlement Calculations",
        "meta_description": "A short sample description used only for internal testing of the publishing pipeline.",
        "excerpt": "A sample excerpt for an internal test page about entitlement calculation and eligibility rules.",
        "sections": [
            {"heading": "Calculation Basis", "body": _EN_BODY + " " + _EN_BODY, "bullets": ["First point", "Second point"]},
            {"heading": "Partial Years", "body": _EN_BODY + " " + _EN_BODY, "bullets": []},
            {"heading": "Resignation", "body": _EN_BODY + " " + _EN_BODY, "bullets": ["Third point"]},
            {"heading": "Worked Example", "body": _EN_BODY + " " + _EN_BODY + example, "bullets": []},
        ],
        "faq": [
            {"q": "Is this a real article?", "a": "No. It is internal test content used only by the automated quality checks and is never published."},
            {"q": "When is it used?", "a": "It is used when the script runs in self-test or simulation mode without an API key."},
        ],
        "official_sources": [
            {"title": "General Organization for Social Insurance", "url": "https://www.gosi.gov.sa/"},
            {"title": "Ministry of Human Resources and Social Development", "url": "https://www.hrsd.gov.sa/"},
        ],
        "calculation_example": calculation_example,
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


def retry_after_seconds(value, *, now=None):
    """Convert numeric Retry-After or an HTTP-date to a non-negative delay."""
    if value is None:
        return None
    text_value = str(value).strip()
    try:
        seconds = float(text_value)
        if seconds >= 0 and seconds == seconds:
            return seconds
    except (TypeError, ValueError):
        pass
    try:
        requested = parsedate_to_datetime(text_value)
        if requested.tzinfo is None:
            requested = requested.replace(tzinfo=timezone.utc)
        current = now or datetime.now(timezone.utc)
        if current.tzinfo is None:
            current = current.replace(tzinfo=timezone.utc)
        return max(0.0, (requested - current).total_seconds())
    except (TypeError, ValueError, OverflowError):
        return None


def backoff_delay(attempt, *, retry_after=None, base=GEMINI_BACKOFF_BASE,
                  cap=GEMINI_BACKOFF_MAX) -> float:
    """Exponential backoff; honor a valid Retry-After value even when above the normal cap."""
    delay = min(base * (2 ** max(0, int(attempt))), cap)
    asked = retry_after_seconds(retry_after)
    if asked is not None and asked > 0:
        # A server-provided delay wins over local backoff; do not retry earlier than requested.
        delay = max(delay, asked)
    return float(delay)


def _has_numeric_retry_after(value) -> bool:
    """Backward-compatible helper for callers/tests that specifically require numeric seconds."""
    seconds = retry_after_seconds(value)
    return seconds is not None and str(value).strip().replace(".", "", 1).isdigit()


def classify_failure(status, raw, *, retry_after=None) -> tuple:
    """يصنّف استجابة فشل من مزوّد المحتوى إلى (retryable, code, note).

    - auth  : 401/403 (مفتاح ناقص/غير صالح/بلا صلاحية) — لا يُعاد.
    - model : 404 أو رسالة تدلّ على نموذج غير متاح — لا يُعاد (العِلاج تغيير النموذج).
    - quota : 429 مع دلالة حصة يومية صريحة — لا يُعاد (تكراره بلا فائدة).
    - rate_limit : 429 مؤقّت، ومنها TPM أو Retry-After أو مهلة مذكورة في النص.
    - structured_output : 400 ذو الرمز json_validate_failed في Groq — إعادة محدودة
      بنفس JSON Schema الصارم لمعالجة فشل توليد عابر؛ لا تغيير إلى JSON mode.
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
        # الحصة اليومية الصريحة تتقدّم على أي مهلة؛ إعادة الطلب لن تحلّ نفادها.
        if any(h in low for h in DAILY_QUOTA_STOP_HINTS):
            return False, "quota", "حصة/فوترة يومية — تكرار الطلب بلا فائدة"
        # إشارات المعدّل/المهلة تتقدّم على عبارات عامة مثل "check your plan" أو "billing".
        if (any(h in low for h in TEMPORARY_RATE_LIMIT_HINTS)
                or RETRY_DELAY_RE.search(low)
                or retry_after_seconds(retry_after) is not None):
            return True, "rate_limit", "تجاوز معدّل مؤقّت"
        if any(h in low for h in QUOTA_STOP_HINTS):
            return False, "quota", "حصة/فوترة — تكرار الطلب بلا فائدة"
        return True, "rate_limit", "تجاوز معدّل مؤقّت"
    if status == 400 and "missing properties" in low and (
        "jsonschema" in low or "expected schema" in low or "does not validate" in low
    ):
        # Missing required keys is a deterministic shape failure, not a transient
        # transport failure. Return it immediately so Article 85 can make one
        # prompt-corrected request under the same strict schema instead of
        # repeating an identical request up to four times.
        return False, "schema_incomplete", "استجابة المخطط تفتقد حقولاً مطلوبة"
    if status == 400 and (
        "json_validate_failed" in low or "failed to generate json" in low
    ):
        # Groq may intermittently report a constrained-generation failure even for
        # a schema that passed our strict-schema checks. Retry only this exact
        # signature a bounded number of times with the same strict request.
        return True, "structured_output", "تعذّر توليد JSON المنظّم؛ ستُعاد المحاولة بنفس المخطط الصارم"
    if status in RETRYABLE_STATUS:
        return True, "transient", "خطأ مؤقّت"
    return False, "other", "خطأ غير قابل لإعادة المحاولة"


def format_failure(status, raw, tries_used, tries) -> str:
    """رسالة فشل موحّدة (بلا أسرار): الرمز + مقتطف الاستجابة + التصنيف وعدد المحاولات."""
    retryable, code, note = classify_failure(status, raw)
    if retryable and tries_used >= tries:
        note = "خطأ مؤقّت — استُنفدت المحاولات"
    response_text = raw.decode("utf-8", "replace") if isinstance(raw, (bytes, bytearray)) else ""
    if code == "schema_incomplete":
        low = response_text.lower()
        marker = low.find("missing properties:")
        missing_region = low[marker + len("missing properties:"):] if marker >= 0 else ""
        schema_fields = ("title", "meta_description", "excerpt", "sections", "faq",
                         "official_sources", "calculation_example")
        missing_fields = [
            field for field in schema_fields
            if re.search(rf"['\"]{re.escape(field)}['\"]", missing_region, re.IGNORECASE)
        ]
        snippet = "schema_missing_required: " + (", ".join(missing_fields) or "required fields")
    else:
        snippet = redact(response_text[:300])
    return f"http_{status}: {snippet} [{note} — محاولات {tries_used}/{tries}]"


class RequestBudgetExhausted(RuntimeError):
    """Raised before network access when a language has used all its API-call allowance."""


class RequestBudget:
    """Hard cap on actual HTTP requests, shared by retries and repair calls for one language."""
    def __init__(self, max_requests):
        self.max_requests = max(1, int(max_requests))
        self.used = 0
        self.prompt_tokens = 0
        self.completion_tokens = 0
        self.total_tokens = 0
        self.usage_responses = 0
        self.rate_limit_hits = 0
        self.last_rate_limit_limit_tokens = None
        self.last_rate_limit_remaining_tokens = None
        self.last_rate_limit_reset_tokens = None

    def record_usage(self, usage):
        if not isinstance(usage, dict):
            return
        def token_count(name):
            value = usage.get(name)
            try:
                parsed = int(value)
            except (TypeError, ValueError, OverflowError):
                return 0
            return max(0, parsed)
        prompt = token_count("prompt_tokens")
        completion = token_count("completion_tokens")
        total = token_count("total_tokens")
        if not any(name in usage for name in ("prompt_tokens", "completion_tokens", "total_tokens")):
            return
        self.prompt_tokens += prompt
        self.completion_tokens += completion
        self.total_tokens += total if "total_tokens" in usage else prompt + completion
        self.usage_responses += 1

    def record_response(self, status, headers):
        if status == 429:
            self.rate_limit_hits += 1
        for field, header_name in (
            ("last_rate_limit_limit_tokens", "x-ratelimit-limit-tokens"),
            ("last_rate_limit_remaining_tokens", "x-ratelimit-remaining-tokens"),
            ("last_rate_limit_reset_tokens", "x-ratelimit-reset-tokens"),
        ):
            value = header_get(headers, header_name)
            if value is not None:
                setattr(self, field, value)

    def consume(self):
        if self.used >= self.max_requests:
            raise RequestBudgetExhausted(
                f"API request budget exhausted ({self.used}/{self.max_requests})")
        self.used += 1


def provider_request(url, body, headers, *, provider, timeout=90, tries=GEMINI_MAX_TRIES,
                     sleep=None, request_budget=None):
    """يرسل طلب POST إلى مزوّد المحتوى ويعيد (status, raw, tries_used).

    إعادة المحاولة محدودة للأخطاء المؤقّتة فقط (خطأ شبكة أو رمز يُصنَّف مؤقّتاً)،
    ولا تحدث إطلاقاً عند 401/403 أو نموذج غير متاح أو حصة يومية صريحة، ويُحترم
    Retry-After ومهلة النص عند 429. `retries=0` في http_request_full يمنع تضاعف المحاولات.
    """
    sleep = SLEEP if sleep is None else sleep
    tries = max(1, int(tries))
    last_exc = None
    for attempt in range(tries):
        if request_budget is not None:
            request_budget.consume()
        try:
            status, resp_headers, raw, _ = http_request_full(
                url,
                method="POST",
                data=body,
                headers=headers,
                timeout=timeout,
                retries=0,
            )
            if request_budget is not None:
                request_budget.record_response(status, resp_headers)
        except (urllib.error.URLError, TimeoutError, OSError) as exc:
            last_exc = exc
            if attempt + 1 >= tries:
                break
            delay = backoff_delay(attempt)
            log(f"[RETRY] {provider}: خطأ شبكة مؤقّت ({type(exc).__name__}) — "
                f"المحاولة {attempt + 2}/{tries} بعد {delay:.1f}s")
            sleep(delay)
            continue

        retry_after = header_get(resp_headers, "Retry-After")
        retryable, _code, _note = classify_failure(status, raw, retry_after=retry_after)
        if retryable and attempt + 1 < tries:
            # Respect whichever server hint asks us to wait longer. Some gateways set
            # Retry-After=0/1 while the body gives the real TPM window (e.g. 9.7425s).
            response_text = raw.decode("utf-8", "replace") if isinstance(
                raw, (bytes, bytearray)) else str(raw or "")
            wait_match = RETRY_DELAY_RE.search(response_text)
            body_delay = None
            if wait_match:
                try:
                    body_delay = float(wait_match.group("seconds"))
                    if wait_match.group("unit").lower().startswith(("m", "min")):
                        body_delay *= 60.0
                except (TypeError, ValueError):
                    body_delay = None
            header_delay = retry_after_seconds(retry_after)
            if body_delay is not None and (
                    header_delay is None or body_delay > header_delay):
                retry_after = str(body_delay)
            delay = backoff_delay(attempt, retry_after=retry_after)
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


def groq_request(url, body, api_key, *, timeout=90, tries=GEMINI_MAX_TRIES, sleep=None,
                 request_budget=None):
    """طلب Groq (OpenAI-compatible) — المفتاح في ترويسة Authorization، ولا يُطبع أبداً."""
    return provider_request(
        url, body, {"Content-Type": "application/json; charset=utf-8",
                    "Accept": "application/json",
                    "Authorization": f"Bearer {api_key}"},
        provider="Groq", timeout=timeout, tries=tries, sleep=sleep,
        request_budget=request_budget)


# =====================================================================================
# 6) مزوّدو المحتوى (Groq افتراضياً، Gemini اختياري)
# =====================================================================================

# =====================================================================================
# 6.1) قواعد قانونية لموضوعات مكافأة نهاية الخدمة (المواد 80 و81 و84 و85 و86 و87 و88)
# =====================================================================================
# المحفّز: أخطاء قانونية فعلية في مسودات التشغيل 38946220138/38954366741 — نسب عامة
# مخترعة (21 يوماً عن كل سنة)، وقاعدة «نصف يوم عن كل شهر غير مكتمل» بدل احتساب
# أجزاء السنة تناسبياً، وحدّ ثلاثة أشهر لاستحقاق الاستقالة، وسقوط عام للمكافأة
# بأي إخلال بشروط الاستقالة، واستبعاد كامل للبدلات أو اعتماد الأجر الأساسي وحده،
# وتسوية نهائية في 30 يوماً، وأمثلة رقمية غير متسقة مع المعادلة.
# المرجع: نظام العمل السعودي — الفصل الرابع (نهاية الخدمة)، وفق النص الرسمي الحالي
# لوزارة الموارد البشرية والتنمية الاجتماعية (صفحة «علاقات العمل»، hrsd.gov.sa،
# تاريخ آخر تحديث 2026/10/14) — المادة 84 (الأساس: نصف شهر عن كل سنة من السنوات
# الخمس الأولى ثم شهر عن كل سنة بعدها، والأجر الأخير أساساً، وأجزاء السنة بنسبة ما
# قضاه منها)، والمادة 85 (الاستقالة: ثلث بعد سنتين متتاليتين إلى خمس سنوات، وثلثاها
# إذا زادت على خمس ولم تبلغ عشر، والكاملة عند عشر فأكثر)، والمادة 86 (يجوز الاتفاق
# على ألا تحسب العمولات ونِسَب المبيعات وما أشبهها القابلة للزيادة والنقص)، والمادة
# 88 (تصفية حقوق من انتهت خدمته أسبوع، ومن أنهى العقد أسبوعين كحدّ أقصى)، والمادة
# 87 (استثناء صريح من المادة 85: المكافأة كاملة عند ترك العمل لقوة قاهرة خارجة عن
# إرادة العامل، أو إنهاء العاملة العقد خلال ستة أشهر من تاريخ عقد زواجها أو ثلاثة
# أشهر من تاريخ وضعها)، والمادة 81 (يحق للعامل أن يترك العمل دون إشعار مع
# احتفاظه بحقوقه النظامية كلها في الحالات المحددة فيها). وترك العمل وفق المادة 81
# ليس استقالة؛ فالمادة 85 لا تُطبَّق إلا إذا كان انتهاء العلاقة بسبب استقالة العامل،
# فتستحق فيه المكافأة كاملة وفق المادة 84. والمادتان 87 و81 أُضيفتا في جولة مراجعة
# لاحقة لسدّ فجوتين مؤكَّدتين في وصف الاستحقاق الكامل وحقوق المادة 81.
# فصل صريح: مكافأة نهاية الخدمة (المادة 84) لا يُدمج بها تعويض المادة 77 عن الإنهاء
# لسبب غير مشروع؛ فلا يُضاف تلقائياً ولا يُفترض استحقاقه في جميع حالات المادة 81.
# كل نصّ هنا مُقروء من المصدر الرسمي أعلاه — لا يُضف استثناء قانوني غير مثبت.
EOSB_TOPIC_IDS = frozenset({
    "eosb-basics", "eosb-resignation", "labor-art84", "labor-art85",
    "eosb-full-entitlement", "rights-contract-end", "rights-employer-termination",
    "labor-art81", "labor-art80", "contract-end-vs-resignation",
    "final-settlement", "employee-exit-checklist",
})

EOSB_LEGAL_RULES = {
    "ar": (
        "قواعد قانونية إلزامية لمكافأة نهاية الخدمة (نظام العمل — الفصل الرابع، "
        "وفق النص الرسمي الحالي للوزارة):\n"
        "1) الأساس الحسابي (المادة 84): أجر نصف شهر عن كل سنة من السنوات الخمس "
        "الأولى، وأجر شهر كامل عن كل سنة من السنوات التالية، ويُتخذ الأجر الأخير "
        "أساساً للحساب. أجزاء السنة تُحتسب بنسبة ماقضى العامل منها فعلاً — لا "
        "بقاعدة «21 يوماً عن كل سنة»، ولا بنصف يوم عن كل شهر غير مكتمل.\n"
        "2) الاستحقاق عند الاستقالة (المادة 85): المادة 85 تنظّم نسب مكافأة نهاية الخدمة عند الاستقالة فقط؛ "
        "ولا تحدد مدة الإشعار ولا تعفي من متطلباته. يستحق العامل ثلث المكافأة بعد خدمة متتالية لا تقل عن سنتين متتاليتين "
        "ولا تزيد على خمس سنوات، والثلثين إذا زادت الخدمة على خمس سنوات ولم تبلغ عشرًا، والمكافأة كاملة "
        "إذا بلغت الخدمة عشر سنوات فأكثر. متطلبات الإشعار وإجراءات الاستقالة مسألة منفصلة قد تنطبق "
        "بحسب نوع العقد والأحكام النظامية. لا تقل إن المادة 85 تنص على عدم الحاجة إلى إشعار، ولا تخلط "
        "بين مهلة الإشعار وشروط استحقاق مكافأة نهاية الخدمة.\n"
        "3) عناصر الأجر (المادة 86): لا تُستبعد من أساس الحساب إلا العمولات والنسب "
        "المئوية عن ثمن المبيعات وما أشبهها من عناصر الأجر القابلة بطبيعتها للزيادة "
        "والنقص، وذلك باتفاق صريح بين الطرفين. فلا تدّعِ أن الأجر الأساسي وحده يدخل "
        "في الحساب في جميع الأحوال، ولا أن جميع البدلات مستبعدة بلا استثناء.\n"
        "4) تصفية الحقوق (المادة 88): إذا انتهت الخدمة من جهة صاحب العمل وُفِّي الأجر "
        "وصُفِّت الحقوق خلال أسبوع على الأكثر؛ وإذا أنهى العامل العقد صُفِّت حقوقه "
        "خلال مدة لا تزيد على أسبوعين. لا تذكر أن التسوية النهائية تستغرق 30 يوماً "
        "بصورة عامة.\n"
        "5) حرمان المكافأة ليس عاماً: حالات الحرمان محددة في المادة 80 وتُطبَّق عند "
        "فسخ العقد من صاحب العمل في الحالات المنصوص فيها؛ أما الاستقالة فتستحق وفق "
        "المادة 85 ومدة الخدمة، ويستحق العامل الذي انتهى عقده بالاستقالة جميع حقوقه "
        "المقررة في النظام. لا تزعم أن أي إخلال بشروط الاستقالة يسقط المكافأة.\n"
        "6) المثال الرقمي: أي مثال حسابي يجب أن يلتزم المعادلة أعلاه بالحرف (نصف شهر "
        "أو شهر عن كل سنة، وجزء السنة بنسبة ما قُضي منه)، ويُحسب بدقّة، ويُعلَّم "
        "صراحةً بأنه مثال توضيحي؛ ولا تنشر رقماً مخالفاً لهذه المعادلة.\n"
        "7) استثناءات الاستحقاق الكامل (المادة 87): تستحق المكافأة كاملة — "
        "استثناءً صريحًا من أحكام المادة 85 — في حالتين: (أ) ترك العامل العمل "
        "نتيجة لقوة قاهرة خارجة عن إرادته؛ (ب) إنهاء العاملة للعقد خلال ستة أشهر "
        "من تاريخ عقد زواجها أو ثلاثة أشهر من تاريخ وضعها. على هاتين الحالتين لا "
        "تُطبَّق نِسَب الاستقالة في المادة 85 ولا عتبة السنتين.\n"
        "8) ترك العمل بحالات المادة 81: يحق للعامل أن يترك العمل دون إشعار، مع "
        "احتفاظه بحقوقه النظامية كلها، في أي من الحالات المحددة في المادة 81 "
        "(منها عدم وفاء صاحب العمل بالتزاماته العقدية أو النظامية الجوهرية إزاء "
        "العامل). وترك العمل وفق المادة 81 ليس استقالة بالمعنى المقصود في المادة "
        "85 — فهي تُطبَّق فقط إذا كان انتهاء علاقة العمل بسبب استقالة العامل — "
        "بل تستحق فيه المكافأة كاملة وفق المادة 84. لا تصف هذه الحالات بأنها "
        "استقالة عادية، ولا تُطبَّق عليها عتبة السنتين أو نِسَب المادة 85 "
        "تعميمًا. ومكافأة نهاية الخدمة وحدها هي محلّ هذه القاعدة؛ فلا تُضِف "
        "تعويضًا آخر كتعويض المادة 77، ولا تفترض استحقاقه في جميع حالات المادة "
        "81، ولا تقدّمه كحقيقة مؤكدة دون سند نظامي أو قضائي موثّق.\n"
        "9) تعويض المادة 77 (منفصل عن المكافأة): تعويض المادة 77 عن الإنهاء لسبب "
        "غير مشروع منفصل تمامًا عن مكافأة نهاية الخدمة، ولا يدخل تلقائيًا في ناتج "
        "المكافأة عند اختيار أي سبب — ولا في أي من حالات المادة 81 السبع. وعدم "
        "الاحتساب التلقائي هو سياسة للبرنامج، وليس حكمًا بأنّ الحكم القضائي أو "
        "الصلح الموثّق شرط نظامي مطلق لوجود التعويض. واستحقاق التعويض وتقديره "
        "مسألة منفصلة تخضع للعقد وبنوده والوقائع والنظام؛ وأي احتساب مستقبلي يمكن "
        "أن يستند إلى مدخل مستقل اسمه المقترح Has_Judicial_Ruling_Or_Settlement "
        "وقيمته الافتراضية False، ولا يكفي المدخل وحده. وإذا لم تتوفر بيانات كافية "
        "للحساب بدقة فلا تُخمّن المبلغ ولا تُضِف قيمة تقديرية إلى التصفية. وهذه "
        "السياسة ليست نصًّا حرفيًا من المادة 77، ولا تنفي حقّ المطالبة القضائية "
        "قبل صدور الحكم.\n"
    ),
    "en": (
        "Mandatory legal rules for end-of-service benefits (Saudi Labour Law, "
        "Chapter IV, per the Ministry's current official text):\n"
        "1) Calculation basis (Article 84): half a month's wage for each of the "
        "first five years, and one full month's wage for each subsequent year, "
        "with the last wage as the basis of the calculation. Parts of a year are "
        "counted in proportion to the time actually served — not by a flat "
        "\"21 days per year\" rule, and not by half a day per incomplete month.\n"
        "2) Entitlement on resignation (Article 85): Article 85 sets the end-of-service benefit ratios for resignation only; "
        "it does not set or waive notice requirements. The entitlement is one third of the benefit after two consecutive years of service and up to five years; "
        "two thirds applies above five but below ten years; the full benefit applies at ten years or more. "
        "Notice and resignation procedures are separate questions governed by the applicable contract and law. "
        "Do not say Article 85 specifies that notice is not required or that resignation needs no three-month notice, "
        "and do not confuse notice requirements with EOSB eligibility.\n"
        "3) Wage elements (Article 86): only commissions, sales percentages and "
        "similar wage elements that are naturally subject to increase and "
        "decrease may be excluded from the basis of the calculation, and only by "
        "explicit agreement between the parties. Do not claim that the basic wage "
        "alone always enters the calculation, nor that all allowances are always "
        "excluded without exception.\n"
        "4) Settlement of rights (Article 88): when the service ends at the "
        "employer's side, wages are paid and rights settled within one week at "
        "most; when the worker ends the contract, his rights are settled within "
        "no more than two weeks. Do not state that the final settlement generally "
        "takes 30 days.\n"
        "5) Forfeiture is not general: forfeiture cases are exhaustively listed in "
        "Article 80 and apply when the employer ends the contract in those listed "
        "cases; resignation entitlement follows Article 85 and the length of "
        "service, and a worker whose contract ends by resignation is entitled to "
        "all rights stipulated by the Law. Do not claim that any breach of "
        "resignation conditions forfeits the benefit.\n"
        "6) Numeric examples: any worked example must follow the equation above "
        "exactly (half a month or one month per year, and parts of a year in "
        "proportion to time served), must be computed accurately, and must be "
        "clearly labelled as illustrative; never publish a figure that "
        "contradicts this equation.\n"
        "7) Full-entitlement exceptions (Article 87): the benefit is payable in "
        "full — as an express exception to Article 85 — in two cases: (a) the "
        "worker leaves work as a result of force majeure beyond his control; "
        "(b) the female worker ends the contract within six months of her "
        "marriage contract date or three months of giving birth. The Article 85 "
        "resignation ratios and the two-year threshold do not apply to these two "
        "cases.\n"
        "8) Leaving work under Article 81: the worker has the right to leave "
        "work without notice, while retaining all of his statutory rights, in "
        "any of the cases set out in Article 81 (including the employer's "
        "failure to perform his essential contractual or statutory obligations "
        "towards the worker). Leaving under Article 81 is not a resignation "
        "within the meaning of Article 85 — which applies only where the "
        "employment relationship ends because of the worker's resignation — and "
        "the benefit is therefore payable in full under Article 84. Do not "
        "describe these cases as ordinary resignation, and do not apply the "
        "Article 85 two-year threshold or ratios to them as a general rule. "
        "End-of-service benefit alone is the subject of this rule: do not add "
        "any other compensation such as Article 77 compensation, do not assume "
        "it is due in all Article 81 cases, and never state it as settled "
        "without a documented statutory or judicial basis.\n"
        "9) Article 77 compensation (separate from the benefit): Article 77 "
        "compensation for termination without a lawful cause is entirely "
        "separate from the end-of-service benefit and is never added "
        "automatically to the benefit result for any reason — nor in any of the "
        "seven Article 81 cases. Not computing it automatically is a program "
        "policy, not a ruling that a final judicial ruling or a documented "
        "settlement is an absolute statutory condition for the compensation. "
        "Entitlement to and assessment of the compensation are a separate "
        "matter, subject to the contract and its terms, the facts, and the law; "
        "any future computation may rely on an independent input whose proposed "
        "name is Has_Judicial_Ruling_Or_Settlement with a default value of "
        "False, and that input alone is not sufficient. If the data needed for "
        "an accurate calculation are unavailable, do not guess the amount and do "
        "not add an estimated value to the settlement. This policy is not a "
        "literal quotation of Article 77, nor does it deny any judicial claim "
        "before a ruling is issued.\n"
    ),
}


EOSB_ARTICLE85_LEGAL_RULES = {
    "ar": (
        "قواعد قانونية خاصة بموضوع المادة 85:\n"
        "المادة 84: نصف أجر عن كل سنة من السنوات الخمس الأولى، ثم أجر شهر عن كل سنة تالية؛ الأجر الأخير أساس الحساب، "
        "وأجزاء السنة تُحسب بنسبة المدة الفعلية.\n"
        "المادة 85 عند الاستقالة: لا استحقاق قبل سنتين متتاليتين؛ الثلث من سنتين إلى خمس سنوات شاملةً خمس سنوات؛ "
        "الثلثان بعد تجاوز خمس سنوات وقبل بلوغ عشر؛ والمكافأة كاملة عند عشر سنوات فأكثر.\n"
        "المادة 85 تحدد نسبة المكافأة ولا تحدد مدة إشعار العقد ولا تعفي منه؛ قد تبقى متطلبات الإشعار وإجراءات الاستقالة واجبة بحسب العقد والنظام.\n"
        "المادة 86: لا يجوز استبعاد العمولات ونسب المبيعات والعناصر المشابهة إلا باتفاق صريح إذا كانت بطبيعتها متغيرة بالزيادة والنقص؛ لا تصف ذلك باستبعاد الأجر الأساسي.\n"
        "المادة 81 تخص ترك العامل العمل دون إشعار في الحالات النظامية مع احتفاظه بحقوقه، وليست فصلاً من صاحب العمل.\n"
    ),
    "en": (
        "Legal rules specific to this Article 85 article:\n"
        "Article 84: half a month's wage for each of the first five years, then one full month's wage for each subsequent year; "
        "the last wage is the basis, and partial years are prorated to actual service.\n"
        "Article 85 on resignation: no entitlement before two consecutive years; one third from two through five years inclusive; "
        "two thirds only above five and below ten years; full benefit at ten years or more.\n"
        "Article 85 sets the benefit ratio, not contract notice requirements, and does not waive notice; notice and resignation procedures may still apply under the contract and law.\n"
        "Article 86: qualifying commissions, sales percentages and similar naturally variable wage elements may be excluded only by explicit agreement; this does not exclude basic wage.\n"
        "Article 81 concerns a worker leaving without notice in statutory cases while retaining rights, not employer dismissal.\n"
    ),
}


def legal_rules_for(topic, lang: str) -> str:
    """Return topic-scoped EOSB rules; unrelated legal clauses are omitted to reduce prompt tokens."""
    topic_id = topic.get("id")
    if topic_id not in EOSB_TOPIC_IDS:
        return ""
    language = "ar" if lang == "ar" else "en"
    if topic_id == "labor-art85":
        return EOSB_ARTICLE85_LEGAL_RULES[language]
    return EOSB_LEGAL_RULES[language]


def eosb_reference_amount(total_years, monthly_wage, *, resigned: bool) -> float:
    """مرجع حتمي لمكافأة نهاية الخدمة (المادتان 84 و85) — للاختبارات لا للإنتاج.

    يطابق معادلة `calculateEOS()` في index.html بالحرف: نصف أجر عن كل سنة من
    السنوات الخمس الأولى ثم أجر كامل عن كل سنة بعدها (المادة 84)، ونِسَب
    الاستقالة (المادة 85): صفر أقل من سنتين، والثلث من سنتين إلى خمس سنوات
    **بالضمن**، والثلثان إذا زادت على خمس ولم تبلغ عشر، والمكافأة كاملة عند
    عشر سنوات فأكثر. لا يُستدعى في أي مسار نشر؛ وظيفته إثبات صحّة القواعد
    المرسلة للنموذج ومنع انحراف الأمثلة العددية.
    """
    first5 = min(total_years, 5) * (monthly_wage / 2)
    after5 = max(0.0, total_years - 5) * monthly_wage
    full = first5 + after5
    if not resigned:
        return full
    if total_years < 2:
        return 0.0
    if total_years <= 5:
        return full / 3
    if total_years < 10:
        return full * 2 / 3
    return full



# تدقيق حسابي إنتاجي للمثال الرقمي: لا يكفي أن يطلب البرومبت من النموذج الدقة.
EOSB_CALCULATION_FIELDS = (
    "monthly_wage", "years", "months", "days", "scenario",
    "full_benefit", "payable_benefit",
)
EOSB_REQUIRED_SCENARIO = {
    "labor-art85": "resignation",
    "eosb-resignation": "resignation",
    "contract-end-vs-resignation": "resignation",
    "labor-art81": "article81",
    # This topic specifically covers full-entitlement exceptions; the worked
    # example is code-owned as Article 87 so AR/EN cannot drift into resignation.
    "eosb-full-entitlement": "article87",
}
EOSB_MONEY_CLAIM_RE = re.compile(
    r"\bSAR\s*([0-9][0-9,]*(?:\.[0-9]{1,2})?)"
    r"|ر\.?\s*س\.?\s*([0-9][0-9,]*(?:\.[0-9]{1,2})?)"
    r"|([0-9][0-9,]*(?:\.[0-9]{1,2})?)\s*"
    r"(?:ريال(?:\s+سعودي)?|SAR|Saudi\s+riyals?|riyals?|ر\.?\s*س\.?)",
    re.IGNORECASE,
)
EOSB_CENT = Decimal("0.01")


def _normalize_eosb_digits(value: str) -> str:
    digit_map = {}
    for source, western in zip("٠١٢٣٤٥٦٧٨٩۰۱۲۳۴۵۶۷۸۹", "01234567890123456789"):
        digit_map[ord(source)] = western
    digit_map.update({ord("٬"): ",", ord("٫"): ".", ord("،"): ","})
    return str(value).translate(digit_map)


EOSB_DURATION_NUMBER = (
    r"(?:[0-9]+(?:\.[0-9]+)?|zero|one|two|three|four|five|six|seven|eight|nine|ten|"
    r"eleven|twelve|thirteen|fourteen|fifteen|sixteen|seventeen|eighteen|"
    r"nineteen|twenty|صفر|واحد|واحدة|احد|إحدى|اثنان|اثنين|اثنتان|اثنتين|"
    r"ثلاث|ثلاثة|أربع|أربعة|اربع|اربعة|خمس|خمسة|ست|ستة|سبع|سبعة|"
    r"ثمان|ثمانية|ثماني|تسع|تسعة|عشر|عشرة|أحد عشر|احد عشر|إحدى عشرة|"
    r"احدى عشرة|اثنا عشر|اثني عشر|اثنتا عشرة|اثنتي عشرة|ثلاثة عشر|"
    r"أربعة عشر|اربعة عشر|خمسة عشر|ستة عشر|سبعة عشر|ثمانية عشر|"
    r"تسعة عشر|عشرون)"
)
EOSB_DURATION_UNIT = (
    r"(?:years?|yrs?|months?|mos?|days?|سنوات|سنة|سنتان|سنتين|عام|عامان|"
    r"أعوام|اعوام|شهر|أشهر|اشهر|شهراً|شهرًا|يوم|أيام|ايام|يوماً|يومًا)"
)
EOSB_DURATION_PAIR_RE = re.compile(
    rf"(?P<number>{EOSB_DURATION_NUMBER})\s*(?P<unit>{EOSB_DURATION_UNIT})",
    re.IGNORECASE,
)
EOSB_DURATION_SEQUENCE = (
    rf"{EOSB_DURATION_NUMBER}\s*{EOSB_DURATION_UNIT}"
    rf"(?:\s*(?:,|،|and|و)\s*{EOSB_DURATION_NUMBER}\s*{EOSB_DURATION_UNIT}){{0,2}}"
)
EOSB_SERVICE_DURATION_PATTERNS = (
    re.compile(rf"\b(?P<duration>{EOSB_DURATION_SEQUENCE})\s+(?:of\s+)?(?:continuous\s+)?service\b", re.IGNORECASE),
    re.compile(rf"\b(?:service|employment)\s+(?:period|duration|length)\s*(?::|=|is|of)?\s*(?P<duration>{EOSB_DURATION_SEQUENCE})", re.IGNORECASE),
    re.compile(rf"(?:مدة\s+(?:الخدمة|خدمته|العمل))\s*(?::|=|هي|تبلغ|قدرها)?\s*(?P<duration>{EOSB_DURATION_SEQUENCE})", re.IGNORECASE),
    re.compile(rf"(?P<duration>{EOSB_DURATION_SEQUENCE})\s*(?:من\s+)?الخدمة", re.IGNORECASE),
)


def _duration_number(value: str) -> Decimal:
    token = _normalize_eosb_digits(value).strip().lower()
    if re.fullmatch(r"[0-9]+(?:\.[0-9]+)?", token):
        return Decimal(token)
    words = {
        "zero": 0, "one": 1, "two": 2, "three": 3, "four": 4, "five": 5,
        "six": 6, "seven": 7, "eight": 8, "nine": 9, "ten": 10,
        "eleven": 11, "twelve": 12, "thirteen": 13, "fourteen": 14,
        "fifteen": 15, "sixteen": 16, "seventeen": 17, "eighteen": 18,
        "nineteen": 19, "twenty": 20,
        "صفر": 0, "واحد": 1, "واحدة": 1, "احد": 1, "أحد": 1,
        "إحدى": 1, "احدى": 1, "اثنان": 2, "اثنين": 2, "اثنتان": 2,
        "اثنتين": 2, "ثلاث": 3, "ثلاثة": 3, "أربع": 4, "أربعة": 4,
        "اربع": 4, "اربعة": 4, "خمس": 5, "خمسة": 5, "ست": 6, "ستة": 6,
        "سبع": 7, "سبعة": 7, "ثمان": 8, "ثمانية": 8, "ثماني": 8,
        "تسع": 9, "تسعة": 9, "عشر": 10, "عشرة": 10,
        "أحد عشر": 11, "احد عشر": 11, "إحدى عشرة": 11, "احدى عشرة": 11,
        "اثنا عشر": 12, "اثني عشر": 12, "اثنتا عشرة": 12, "اثنتي عشرة": 12,
        "ثلاثة عشر": 13, "أربعة عشر": 14, "اربعة عشر": 14, "خمسة عشر": 15,
        "ستة عشر": 16, "سبعة عشر": 17, "ثمانية عشر": 18, "تسعة عشر": 19,
        "عشرون": 20,
    }
    if token not in words:
        raise Reject("مدة الخدمة في المثال تستخدم رقماً أو صيغة عددية غير مدعومة")
    return Decimal(words[token])


def _extract_eosb_service_durations(example_text: str) -> list:
    """استخرج مدد الخدمة المذكورة صراحة داخل قسم المثال الحسابي وحوّلها إلى سنوات."""
    if not isinstance(example_text, str) or not example_text.strip():
        return []
    text = _normalize_eosb_digits(example_text).lower()
    claims = []
    seen = set()
    for pattern in EOSB_SERVICE_DURATION_PATTERNS:
        for match in pattern.finditer(text):
            pairs = list(EOSB_DURATION_PAIR_RE.finditer(match.group("duration")))
            if not pairs:
                continue
            total_years = Decimal(0)
            for pair in pairs:
                number = _duration_number(pair.group("number"))
                unit = pair.group("unit").lower()
                if unit.startswith(("year", "yr")) or unit in {"سنة", "سنوات", "سنتان", "سنتين", "عام", "عامان", "أعوام", "اعوام"}:
                    total_years += number
                elif unit.startswith(("month", "mo")) or unit in {"شهر", "أشهر", "اشهر", "شهراً", "شهرًا"}:
                    total_years += number / Decimal(12)
                else:
                    total_years += number / Decimal(365)
            if total_years not in seen:
                seen.add(total_years)
                claims.append(total_years)
    return claims


def _parse_eosb_number(value, field: str, *, integer: bool = False) -> Decimal:
    if not isinstance(value, str):
        raise Reject(f"calculation_example.{field}: يجب أن تكون القيمة نصاً رقمياً")
    raw = _normalize_eosb_digits(value.strip())
    pattern = r"[0-9]+" if integer else r"(?:[0-9]+|[0-9]{1,3}(?:,[0-9]{3})+)(?:\.[0-9]{1,2})?"
    if not re.fullmatch(pattern, raw):
        raise Reject(f"calculation_example.{field}: صيغة رقمية غير صالحة")
    try:
        number = Decimal(raw.replace(",", ""))
    except InvalidOperation as exc:
        raise Reject(f"calculation_example.{field}: رقم غير صالح") from exc
    if not number.is_finite() or number < 0:
        raise Reject(f"calculation_example.{field}: يجب ألا يكون الرقم سالباً")
    return number


def _article87_qualifying_basis(example_text: str) -> bool:
    """Return whether an Article 87 worked example states a recognized qualifying circumstance."""
    value = _normalize_eosb_digits(str(example_text or ""))
    lower = value.lower()
    if re.search(r"\bforce\s+majeure\b", lower) or re.search(r"قوة\s+قاهرة", value):
        return True
    female_worker = bool(re.search(
        r"\b(?:female worker|woman worker|working woman)\b|المرأة العاملة|العاملة|عاملة",
        value, re.IGNORECASE,
    ))
    if not female_worker:
        return False
    marriage = bool(re.search(r"\bmarriage\b|\bmarried\b|زواج|الزواج", lower))
    childbirth = bool(re.search(
        r"\b(?:childbirth|giving birth|delivery)\b|ولادة|الوضع|الولادة", lower
    ))
    six_months = bool(re.search(r"\b(?:six|6) months\b|ستة أشهر|٦ أشهر|6 أشهر", lower))
    three_months = bool(re.search(r"\b(?:three|3) months\b|ثلاثة أشهر|٣ أشهر|3 أشهر", lower))
    return (marriage and six_months) or (childbirth and three_months)


def _article87_ordinary_resignation_claim(example_text: str, *, lang: str) -> bool:
    """Detect explicit prose that defines the Article 87 numeric example as ordinary resignation."""
    patterns = (
        [
            re.compile(
                r"\b(?:this|the)\s+(?:worked\s+)?example\s+"
                r"(?:assumes|is|describes|covers|shows)\s+"
                r"(?:(?:an?|the)\s+)?(?:ordinary\s+)?resignation\b",
                re.IGNORECASE,
            ),
            re.compile(
                r"\b(?:the\s+)?(?:worker|employee)\s+"
                r"(?:resigned|resigns|is\s+resigning)\b.{0,70}"
                r"\b(?:in|for)\s+(?:this|the)\s+example\b",
                re.IGNORECASE,
            ),
        ]
        if lang != "ar"
        else [
            re.compile(
                r"(?:هذا المثال|المثال|هذا السيناريو|سيناريو المثال).{0,30}"
                r"(?:يفترض|يصف|يعرض|يتناول|هو).{0,40}"
                r"(?:استقالة عادية|الاستقالة العادية|استقالة|الاستقالة|استقال|استقالت)"
            ),
            re.compile(
                r"(?:العامل|العاملة)\s+(?:استقال|استقالت|يستقيل|تستقيل)"
                r".{0,50}(?:في هذا المثال|في المثال)"
            ),
        ]
    )
    for sentence in re.split(r"(?<=[.!?؟])\s+", str(example_text or "")):
        for pattern in patterns:
            match = pattern.search(sentence)
            if not match:
                continue
            prefix = sentence[:match.end()].lower()
            if lang == "ar":
                if re.search(r"(?:ليس|ليست|لا|لم|لن|غير|بدون|وليس|وليست).{0,35}(?:استقال|الاستقالة)", prefix):
                    continue
            elif re.search(
                r"\b(?:not|never|no|without|isn't|doesn't|don't|wasn't|weren't)\b"
                r".{0,45}\b(?:resign|resignation|resigned|resigns)\b",
                prefix, re.IGNORECASE,
            ):
                continue
            return True
    return False


def validate_eosb_scenario_narrative(*, topic_id: str, scenario: str,
                                      example_text: str, lang: str) -> None:
    """Fail closed when the numeric Article 87 scenario and its explanation contradict each other."""
    if topic_id != "eosb-full-entitlement" or scenario != "article87":
        return
    if _article87_ordinary_resignation_claim(example_text, lang=lang):
        raise Reject(
            "calculation_example.scenario: نص المثال يصف استقالة عادية بينما الحقول الحسابية تفترض استثناء المادة 87"
        )
    if not _article87_qualifying_basis(example_text):
        raise Reject(
            "calculation_example.scenario: نص المثال لا يذكر حالة مؤهلة وفق المادة 87"
        )


def validate_eosb_calculation_example(
    raw, *, topic, article_text: str, example_text: str,
    require_canonical_article85: bool = False,
) -> None:
    """يرفض مثال مكافأة نهاية خدمة إذا خالف معادلة المادتين 84/85 أو نص المقال."""
    if not isinstance(raw, dict) or set(raw) != set(EOSB_CALCULATION_FIELDS):
        raise Reject("calculation_example: الكائن أو حقوله غير مكتملة")
    topic_id = topic.get("id", "")
    if topic_id not in EOSB_TOPIC_IDS:
        if any(not isinstance(value, str) or value.strip() for value in raw.values()):
            raise Reject("calculation_example: يجب ترك الحقول فارغة لغير موضوعات مكافأة نهاية الخدمة")
        return dict(raw)

    if any(not isinstance(raw[field], str) or not raw[field].strip()
           for field in EOSB_CALCULATION_FIELDS):
        raise Reject("calculation_example: بيانات المثال الحسابي مطلوبة لموضوع مكافأة نهاية الخدمة")
    scenario = raw["scenario"].strip().lower()
    if scenario not in {"base", "resignation", "article81", "article87"}:
        raise Reject("calculation_example.scenario: قيمة غير مدعومة")
    expected_scenario = EOSB_REQUIRED_SCENARIO.get(topic_id)
    if expected_scenario and scenario != expected_scenario:
        raise Reject(f"calculation_example.scenario: الموضوع {topic_id} يتطلب {expected_scenario}")

    if not isinstance(example_text, str) or not example_text.strip():
        raise Reject("المثال الحسابي يجب أن يظهر داخل قسم عنوانه يتضمن مثالاً / Example")
    wage = _parse_eosb_number(raw["monthly_wage"], "monthly_wage")
    years = _parse_eosb_number(raw["years"], "years")
    months = _parse_eosb_number(raw["months"], "months", integer=True)
    days = _parse_eosb_number(raw["days"], "days", integer=True)
    if years != years.to_integral_value() and (months != 0 or days != 0):
        raise Reject(
            "calculation_example: عند استخدام سنوات كسرية يجب أن تكون الأشهر والأيام صفراً "
            "لتجنّب احتساب المدة مرتين"
        )
    claimed_full = _parse_eosb_number(raw["full_benefit"], "full_benefit")
    claimed_payable = _parse_eosb_number(raw["payable_benefit"], "payable_benefit")
    if wage <= 0:
        raise Reject("calculation_example.monthly_wage: يجب أن يكون الأجر أكبر من الصفر")
    if years > 80 or months > 11 or days > 30:
        raise Reject("calculation_example: سنوات الخدمة أو الأشهر أو الأيام خارج الحدود المقبولة")
    # Article 85 uses a code-owned worked example so the model cannot invent
    # a new duration or wage and drift across Arabic/English calculations.
    if require_canonical_article85 and topic_id == "labor-art85" and (
        wage != Decimal("12000") or years != Decimal("6")
        or months != 0 or days != 0
    ):
        raise Reject(
            "calculation_example: موضوع المادة 85 يتطلب المثال الثابت "
            "(أجر 12000، خدمة 6 سنوات، أشهر وأيام صفر)"
        )

    total_years = years + months / Decimal(12) + days / Decimal(365)
    first_five = min(total_years, Decimal(5))
    after_five = max(Decimal(0), total_years - Decimal(5))
    full_raw = wage * first_five / Decimal(2) + wage * after_five
    expected_full = full_raw.quantize(EOSB_CENT, rounding=ROUND_HALF_UP)
    if scenario == "resignation":
        if total_years < Decimal(2):
            ratio = Decimal(0)
        elif total_years <= Decimal(5):
            ratio = Decimal(1) / Decimal(3)
        elif total_years < Decimal(10):
            ratio = Decimal(2) / Decimal(3)
        else:
            ratio = Decimal(1)
    else:
        ratio = Decimal(1)
    expected_payable = (full_raw * ratio).quantize(EOSB_CENT, rounding=ROUND_HALF_UP)
    claimed_full = claimed_full.quantize(EOSB_CENT, rounding=ROUND_HALF_UP)
    claimed_payable = claimed_payable.quantize(EOSB_CENT, rounding=ROUND_HALF_UP)
    if claimed_full != expected_full:
        raise Reject(
            f"calculation_example.full_benefit: المتوقع {expected_full} وليس {claimed_full}"
        )
    if claimed_payable != expected_payable:
        raise Reject(
            f"calculation_example.payable_benefit: المتوقع {expected_payable} وليس {claimed_payable}"
        )

    duration_claims = _extract_eosb_service_durations(example_text)
    if not duration_claims:
        raise Reject(
            "قسم المثال الحسابي يجب أن يذكر مدة الخدمة صراحةً بصيغة مرتبطة بالخدمة / service"
        )
    mismatched_durations = [claim for claim in duration_claims if claim != total_years]
    if mismatched_durations:
        rendered = ", ".join(format(value, ".8f").rstrip("0").rstrip(".") for value in mismatched_durations)
        expected_rendered = format(total_years, ".8f").rstrip("0").rstrip(".")
        raise Reject(
            f"مدة الخدمة بالنص ({rendered} سنة) لا تطابق بيانات الحساب "
            f"({expected_rendered} سنة)"
        )

    validate_eosb_scenario_narrative(
        topic_id=topic_id, scenario=scenario, example_text=example_text,
        lang="ar" if has_arabic(example_text) else "en",
    )

    normalized_text = _normalize_eosb_digits(article_text)
    claims = []
    for match in EOSB_MONEY_CLAIM_RE.finditer(normalized_text):
        token = next((group for group in match.groups() if group), "")
        if token:
            try:
                claims.append(Decimal(token.replace(",", "")).quantize(
                    EOSB_CENT, rounding=ROUND_HALF_UP))
            except InvalidOperation:
                raise Reject("المثال الرقمي: تعذّر تحليل مبلغ مذكور بجانب العملة")
    allowed_amounts = {wage.quantize(EOSB_CENT, rounding=ROUND_HALF_UP),
                       expected_full, expected_payable}
    unexpected = sorted(set(claims) - allowed_amounts)
    if unexpected:
        raise Reject(
            "المثال الرقمي في النص يتضمن مبلغاً لا يطابق بيانات الحساب "
            + ", ".join(str(amount) for amount in unexpected)
        )
    missing = allowed_amounts - set(claims)
    if missing:
        raise Reject(
            "المثال الرقمي في النص يجب أن يذكر الأجر والمكافأة الأساسية والمبلغ المستحق "
            + ", ".join(str(amount) for amount in sorted(missing))
            + " بعملة واضحة"
        )
    return {
        "monthly_wage": format(wage.quantize(EOSB_CENT, rounding=ROUND_HALF_UP), "f"),
        "years": format(years.normalize(), "f"),
        "months": str(int(months)),
        "days": str(int(days)),
        "scenario": scenario,
        "full_benefit": format(expected_full, "f"),
        "payable_benefit": format(expected_payable, "f"),
    }

# --- سياسة تعويض المادة 77: منفصلة عن مكافأة نهاية الخدمة --------------------
# المدخل المستقل الاختياري لأي احتساب مستقبلي للتعويض، وقيمته الافتراضية False.
ARTICLE_77_FLAG_NAME = "Has_Judicial_Ruling_Or_Settlement"
ARTICLE_77_FLAG_DEFAULT = False

# مدخلات نموذج المادة 77 المطلوبة. غير مُعرَّفة في الواجهة بعد (تحقّق: لا حقل
# `eos-*` لنوع العقد ولا لقيمة التعويض المنصوص عليه في العقد ولا لسند الحكم).
# لذلك يبقى حساب التعويض مُعطَّلاً ولا يُفعَّل أي حساب مالي جديد بلا نموذج إدخال.
ARTICLE_77_REQUIRED_INPUTS = (
    ARTICLE_77_FLAG_NAME,
    "contract_type",
    "contract_compensation_amount",
)


def article_77_missing_inputs(*, has_judicial_ruling_or_settlement=False,
                              contract_type=None,
                              contract_compensation_amount=None):
    """قائمة مدخلات المادة 77 الناقصة — لعرض الفجوة بلا اختراع قيم."""
    missing = []
    if not has_judicial_ruling_or_settlement:
        missing.append(ARTICLE_77_FLAG_NAME)
    if contract_type not in ("fixed", "unlimited"):
        missing.append("contract_type")
    if contract_compensation_amount in (None, ""):
        missing.append("contract_compensation_amount")
    return missing


def article_77_compensation(*, has_judicial_ruling_or_settlement=False,
                            contract_type=None,
                            contract_compensation_amount=None):
    """تعويض المادة 77 — يعيد `None` دائمًا: نموذج الإدخال غير مُعرَّف بعد.

    السياسة (ملخّص): (١) منفصل تمامًا عن مكافأة نهاية الخدمة ولا يُضاف تلقائيًا
    لأي سبب، ولا في أي من حالات المادة 81 السبع. (٢) عدم الاحتساب التلقائي سياسة
    للبرنامج، وليس حكمًا بأنّ الحكم القضائي أو الصلح الموثّق شرط نظامي مطلق لوجود
    التعويض؛ واستحقاق التعويض وتقديره مسألة منفصلة تخضع للعقد وبنوده والوقائع
    والنظام. (٣) أي احتساب مستقبلي يستند إلى مدخل مستقل، والمدخل وحده لا يكفي؛
    فطريقة الاحتساب تختلف بحسب نوع العقد والتعويض المنصوص عليه في العقد والبيانات
    ذات الصلة. (٤) عند نقص بيانات الحساب لا يُخمَّن المبلغ ولا تُضاف قيمة تقديرية.
    لذلك تعيد الدالة `None` دائمًا، ونتيجتها لا تُخلط بمكافأة نهاية الخدمة ولا
    بنسبة `art81`. راجع `ARTICLE_77_REQUIRED_INPUTS` و`article_77_missing_inputs`.
    """
    # نموذج المادة 77 غير مُعرَّف بعد (لا حقول في الواجهة) ⇒ لا مبلغ وبلا تخمين.
    return None


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
    preferred = official_sources_for(topic)
    source_lines = "".join(
        f"   - {item['title']} — {item['url']}\n" for item in preferred)
    source_rule = (
        "4) official_sources: اختر من 2 إلى 4 مصادر من هذه القائمة الرسمية المعتمدة فقط، "
        "وانسخ الرابط كما هو بالحرف (ولا تخترع رابطاً ولا نطاقاً آخر):\n"
        f"{source_lines}"
        "   ممنوع تماماً استخدام النطاق المنتهي mol.gov.sa أو أي نطاق غير مذكور أعلاه.\n"
    )
    legal_block = legal_rules_for(topic, lang)
    if legal_block:
        legal_block = f"قواعد قانونية إلزامية لهذا الموضوع:\n{legal_block}\n"
    if topic.get("id") in EOSB_TOPIC_IDS:
        required_scenario = EOSB_REQUIRED_SCENARIO.get(topic["id"])
        if required_scenario:
            scenario_instruction = f"هذا الموضوع يتطلب scenario={required_scenario}.\n"
        else:
            scenario_instruction = (
                "اختر scenario يطابق المثال بدقة: base (أساس المادة 84 قبل أي نسبة خاصة)، "
                "resignation (نسبة المادة 85)، article81 (حالة المادة 81)، أو article87 (استثناء المادة 87).\n"
            )
        canonical_example_rule = ""
        article85_claims_rule = ""
        if topic.get("id") == "labor-art85":
            if lang == "ar":
                article85_claims_rule = (
                    "للمادة 85: ثلث المكافأة من سنتين إلى خمس سنوات شاملةً خمس سنوات، والثلثان بعد تجاوز خمس سنوات وقبل بلوغ عشر. "
                    "المادة 85 تحدد نسبة المكافأة عند الاستقالة ولا تحدد مدة إشعار العقد ولا تعفي منه؛ وقد تبقى متطلبات الإشعار وإجراءات الاستقالة واجبة بحسب العقد والنظام. "
                    "لا تقل إن عدم الالتزام بالإشعار يؤدي تلقائيًا إلى فقدان أو خفض مكافأة نهاية الخدمة؛ أي مسؤولية عن مهلة الإشعار مسألة منفصلة، ولا تستنتج أثرًا ماليًا دون سند رسمي محدد. "
                    "في سؤال الحد الأدنى لاستحقاق مكافأة الاستقالة، لا تقل إنه لا يوجد حد أدنى: تشترط المادة 85 سنتين متتاليتين كحد أدنى. "
                    "وفق المادة 86، لا تُستبعد العمولات ونسب المبيعات والعناصر المشابهة إلا باتفاق صريح عندما تكون بطبيعتها متغيرة بالزيادة والنقص؛ وهذا لا يستبعد الأجر الأساسي. "
                    "المادة 81 تخص ترك العامل العمل دون إشعار في الحالات النظامية مع احتفاظه بحقوقه، وليست فصلاً من صاحب العمل. "
                    "لجودة القراءة: لا تكرر شرح الإشعار نفسه في المقدمة والأسئلة الشائعة، ولا تكرر النسب نفسها في فقرة ثم قائمة؛ اجعل لكل قسم إضافة واضحة.\n"
                )
            else:
                article85_claims_rule = (
                    "For Article 85: one third applies from two through five years inclusive; two thirds applies only above five and below ten. "
                    "Article 85 sets the resignation benefit ratio, not contract notice requirements; notice and resignation procedures may still apply under the contract and law. "
                    "Do not claim that notice non-compliance automatically forfeits or reduces the end-of-service award; any notice-period liability is separate, and no financial consequence should be asserted without a specific official basis. "
                    "In any FAQ asking about the minimum service for a resignation award, do not say there is no minimum: Article 85 requires two consecutive years as the minimum. "
                    "Under Article 86, qualifying variable commissions/sales elements may be excluded only by explicit agreement; this does not exclude basic wage. "
                    "Article 81 concerns a worker leaving without notice in statutory cases while retaining rights, not employer dismissal. "
                    "For readability, do not repeat the same notice explanation in the introduction and FAQ, or restate the same ratios in prose and a list; each section must add distinct value.\n"
                )
            if lang == "ar":
                canonical_example_rule = (
                    "مثال هذا الموضوع ثابت ومحسوب مسبقاً؛ لا تخترع أرقاماً أخرى ولا تغيّر أي قيمة: "
                    "monthly_wage=12000, years=6, months=0, days=0, scenario=resignation, "
                    "full_benefit=42000, payable_benefit=28000. "
                    "اكتب داخل قسم «مثال» هذه الفكرة بالأرقام نفسها: الأجر الشهري 12,000 ريال، "
                    "مدة الخدمة 6 سنوات، المكافأة الأساسية 42,000 ريال، والمبلغ المستحق بعد نسبة الاستقالة 28,000 ريال. "
                    "لا تضف أي مبلغ نقدي آخر.\n"
                )
            else:
                canonical_example_rule = (
                    "This topic uses a fixed, pre-calculated example. Do not invent or change any value: "
                    "monthly_wage=12000, years=6, months=0, days=0, scenario=resignation, "
                    "full_benefit=42000, payable_benefit=28000. "
                    "In the Example section state these same figures: monthly wage SAR 12,000, "
                    "six years of service, full base benefit SAR 42,000, and payable benefit after the resignation ratio SAR 28,000. "
                    "Do not add any other currency amount.\n"
                )
        calculation_rule = (
            "7) calculation_example: املأ الحقول كلها بنصوص رقمية تستخدم أرقاماً غربية بلا فواصل داخل JSON؛ "
            "monthly_wage هو الأجر الشهري، وyears/months/days مدة الخدمة (الأشهر 0–11 والأيام 0–30). "
            "يمكن تمثيل السنة الكسرية مثل 6.5 في years بشرط أن يكون months وdays صفراً؛ أو استخدم سنوات صحيحة مع الأشهر والأيام حتى لا تُحتسب المدة مرتين. "
            "full_benefit هو ناتج المادة 84 (نصف أجر عن كل سنة من أول خمس سنوات ثم أجر شهر لكل سنة بعدها، "
            "مع احتساب كسر السنة بنسبة مدته)، وpayable_benefit هو المبلغ بعد نسبة المادة 85 إذا كان السيناريو "
            "resignation، وإلا الأساس الكامل في هذا المثال. استخدم منزلتين عشريتين كحد أقصى للمبالغ.\n"
            "ضع المثال الرقمي داخل قسم عنوانه يتضمن كلمة «مثال» أو “Example”، واذكر مدة الخدمة فيه صراحةً "
            "بصيغة مرتبطة بالخدمة؛ يجب أن تتطابق السنوات والأشهر والأيام المكتوبة في هذا القسم مع الحقول المنظمة.\n"
            + scenario_instruction
            + article85_claims_rule
            + canonical_example_rule
            + "يُعاد حساب هذه القيم آلياً؛ إن لم تستطع ضبط المثال حسابياً فلا تخمّن ولا تكتب مثالاً مخالفاً. "
            "كل مبلغ نقدي مذكور في نص المقال يجب أن يكون أحد هذه المبالغ فقط، ويجب إظهاره بعملة واضحة مثل ريال أو SAR. وعند إنتاج النسختين، استخدم الأجر ومدة الخدمة والسيناريو والنتائج الحسابية نفسها في العربية والإنجليزية.\n"
        )
    else:
        calculation_rule = (
            "7) calculation_example: أعد الكائن المطلوب لكن اترك جميع قيمه كسلاسل فارغة، "
            "لأن هذا الموضوع ليس من موضوعات مكافأة نهاية الخدمة.\n"
        )
    return (
        "أنت محرّر محتوى إرشادي-عملي لمنصة أدوات سعودية. ما تكتبه إرشاد عام وليس استشارة قانونية.\n"
        f"الموضوع: {title}\n"
        f"لغة المخرجات: {lang_name}\n"
        f"{guidance}\n\n"
        "قواعد إلزامية:\n"
        "1) أعد كائن JSON واحداً صالحاً فقط، بلا نص خارجه وبلا أسوار markdown.\n"
        "2) لا تُدرج أي HTML أو وسوم أو سكربتات داخل النصوص؛ نصّ عادي فقط.\n"
        "3) لا تخترع أرقام مواد أو نِسَباً أو مُدداً أو جهات. إن لم تكن واثقاً فاذكر القاعدة العامة بتحفّظ.\n"
        f"{source_rule}"
        "5) لا أسلوب دعائياً، ولا وعوداً بنتائج توظيف مضمونة، ولا ادّعاء بأن المحتوى مُراجَع قانونياً.\n"
        "6) لا تذكر أنك نموذج ذكاء اصطناعي.\n\n"
        f"{legal_block}"
        "بنية JSON المطلوبة بالحرف:\n"
        "{\n"
        '  "title": "عنوان المقال",\n'
        '  "meta_description": "وصف من 50 إلى 160 حرفاً",\n'
        '  "excerpt": "ملخص من 40 إلى 240 حرفاً",\n'
        '  "sections": [{"heading": "عنوان فرعي", "body": "فقرة أو فقرات مفصولة بسطر فارغ", "bullets": ["نقطة"]}],\n'
        '  "faq": [{"q": "سؤال", "a": "جواب"}],\n'
        '  "official_sources": [{"title": "اسم الجهة", "url": "https://....gov.sa/..."}],\n'
        '  "calculation_example": {"monthly_wage": "", "years": "", "months": "", "days": "", "scenario": "", "full_benefit": "", "payable_benefit": ""}\n'
        "}\n\n"
        f"- sections: من {MIN_SECTIONS} إلى {MAX_SECTIONS} عناصر، و bullets اختيارية (اتركها [] عند عدم الحاجة).\n"
        "- يجب أن يكون body في كل قسم غير فارغ ويتراوح بين 120 و5000 حرف. لا تترك عنواناً بلا محتوى؛ ادمج الأقسام الفارغة مع أقسام مناسبة مع الحفاظ على كل المعلومات القانونية المهمة.\n"
        "- يجب ألا يتجاوز نص body في أي قسم منفرد 5000 حرف، بما في ذلك المسافات؛ وزّع المحتوى على أقسام متعددة ولا تضع معظم المقال في قسم واحد.\n"
        "- faq: من سؤالين إلى أربعة أسئلة.\n"
        "- إجمالي المحتوى لا يقل عن 350 كلمة.\n"
        "- لا تُضِف حقولاً خارج البنية أعلاه.\n"
        f"{calculation_rule}"
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

# اسم المخطّط داخل response_format — اسم ASCII بسيط بلا مسافات.
GROQ_SCHEMA_NAME = "article"

# مخطّط Structured Outputs الصارم (strict: true) المطابق لبنية المقال في build_prompt
# وحقول validate_article بالحرف. التزم بمتطلبات Groq الصارمة وبكلمات المخطط المدعومة
# فقط: كل الحقول في `required`، وكل كائن بـ`additionalProperties: false`،
# ولا أي قيد JSON Schema غير مدعوم (بلا minLength/minItems/maxItems/pattern/anyOf).
# لزوم ذلك: امتثال مضمون عند التوليد (constrained decoding)، فيتعذّر وقوع الحقول
# الناقصة أو الزائدة أو الأنواع الخاطئة أصلاً — وتبقى بوابات الجودة قائمة كما هي
# تحقق دفاعاً عن الآخر، لا استثناءً له.
GROQ_ARTICLE_SCHEMA = {
    "type": "object",
    "properties": {
        "title": {"type": "string", "description": "عنوان المقال"},
        "meta_description": {"type": "string", "description": "وصف من 50 إلى 160 حرفاً"},
        "excerpt": {"type": "string", "description": "ملخص من 40 إلى 240 حرفاً"},
        "sections": {
            "type": "array",
            "description": "من 3 إلى 12 قسماً",
            "items": {
                "type": "object",
                "properties": {
                    "heading": {"type": "string", "description": "عنوان فرعي"},
                    "body": {"type": "string", "description": "فقرة أو فقرات مفصولة بسطر فارغ"},
                    "bullets": {"type": "array", "description": "نقاط اختيارية",
                                "items": {"type": "string"}},
                },
                "required": ["heading", "body", "bullets"],
                "additionalProperties": False,
            },
        },
        "faq": {
            "type": "array", "description": "من سؤالين إلى أربعة أسئلة",
            "items": {
                "type": "object",
                "properties": {"q": {"type": "string"}, "a": {"type": "string"}},
                "required": ["q", "a"], "additionalProperties": False,
            },
        },
        "official_sources": {
            "type": "array", "description": "من 2 إلى 4 مصادر رسمية من قائمة البرومبت",
            "items": {
                "type": "object",
                "properties": {"title": {"type": "string"}, "url": {"type": "string"}},
                "required": ["title", "url"], "additionalProperties": False,
            },
        },
        "calculation_example": {
            "type": "object",
            "description": "بيانات مستقلة لتدقيق المثال الحسابي؛ تُترك فارغة لغير موضوعات مكافأة نهاية الخدمة",
            "properties": {
                "monthly_wage": {"type": "string"},
                "years": {"type": "string"},
                "months": {"type": "string"},
                "days": {"type": "string"},
                "scenario": {"type": "string"},
                "full_benefit": {"type": "string"},
                "payable_benefit": {"type": "string"},
            },
            "required": ["monthly_wage", "years", "months", "days", "scenario",
                         "full_benefit", "payable_benefit"],
            "additionalProperties": False,
        },
    },
    "required": ["title", "meta_description", "excerpt", "sections", "faq",
                 "official_sources", "calculation_example"],
    "additionalProperties": False,
}



def groq_response_format() -> dict:
    """إعدادات Structured Outputs الصارمة لطلب Groq: json_schema + strict=true.

    التزم بوضع الصارم لا بالوضع الأضعف: عند تعذّر المخطّط يفشل الطلب بوضوح ولا
    يُستبدل تلقائياً بوضع أدنى (json_object أو strict=false).
    """
    return {"type": "json_schema",
            "json_schema": {"name": GROQ_SCHEMA_NAME, "strict": True,
                            "schema": GROQ_ARTICLE_SCHEMA}}


def groq_generate_json(prompt, *, api_key, model, timeout=90, tries=GEMINI_MAX_TRIES,
                       sleep=None, request_budget=None, reasoning_effort="low"):
    """يرجع (ok, data|None, message) من Groq عبر Structured Outputs بوضع صارم.

    المفتاح يُرسل في ترويسة Authorization ولا يُطبع أبداً، ولا يظهر في أي رسالة خطأ.
    الطلب يفرض `response_format` من نوع json_schema بـstrict=true ومخطّط مطابق لبنية
    المقال، فيلتزم النموذج بالمخطّط عند التوليد (constrained decoding). المخرجات
    تمرّر كما هي إلى بوابات التحقّق الحالية (لا استثناءات ولا تجاوز).
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
        # Default remains low; medium is an explicit comparison option for English only.
        # Strict JSON schema and all downstream validation gates remain enabled.
        "reasoning_effort": reasoning_effort if reasoning_effort in {"low", "medium", "high"} else "low",
        "max_tokens": 12000,
        "response_format": groq_response_format(),
    }
    body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    try:
        status, raw, tries_used = groq_request(
            GROQ_URL, body, api_key, timeout=timeout, tries=tries, sleep=sleep,
            request_budget=request_budget)
    except RequestBudgetExhausted as exc:
        used = request_budget.used if request_budget is not None else 0
        limit = request_budget.max_requests if request_budget is not None else 0
        return False, None, f"request_budget_exhausted ({used}/{limit}): {redact(exc)}"
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
    if request_budget is not None:
        request_budget.record_usage(envelope.get("usage"))
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
                  sleep=None, request_budget=None, reasoning_effort="low"):
    """يوجّه التوليد إلى المزوّد المطلوب فقط — بلا انتقال تلقائي عند الفشل."""
    if provider == "groq":
        return groq_generate_json(prompt, api_key=api_key, model=model,
                                  timeout=timeout, tries=tries, sleep=sleep,
                                  request_budget=request_budget,
                                  reasoning_effort=reasoning_effort)
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


def normalize_source_url(url: str) -> str:
    """يطبّع رابط المصدر: يحذف المسافات، يرمّز المسارات العربية (UTF-8 %)، ويُسقط fragment."""
    url = strip_ws(url)
    if not url:
        return ""
    try:
        parts = urllib.parse.urlsplit(url)
    except ValueError:
        return url
    path = urllib.parse.quote(parts.path, safe="/%:@!$&'()*+,;=-._~")
    query = urllib.parse.quote(parts.query, safe="=&%:@!$'()*+,;/?-._~")
    return urllib.parse.urlunsplit((parts.scheme, parts.netloc, path, query, ""))


def is_blocked_source_host(host: str) -> bool:
    """يحجب النطاق الميت نفسه وكل نطاقاته الفرعية (مثل `portal.mol.gov.sa`).

    لولاه لمرّ `portal.mol.gov.sa` من فحص اللاحقة `.gov.sa` — وهذا توسيعٌ للثقة مرفوض.
    """
    host = (host or "").lower()
    return any(host == b or host.endswith("." + b) for b in BLOCKED_SOURCE_HOSTS)


def is_allowed_source_url(url: str) -> bool:
    try:
        parts = urllib.parse.urlsplit(url or "")
    except ValueError:
        return False
    if parts.scheme != "https":
        return False
    # `hostname` يحذف المنفذ وبيانات المستخدم ويحوّل إلى أحرف صغيرة (خلاف `netloc`).
    host = (parts.hostname or "").lower()
    if not host:
        return False
    if is_blocked_source_host(host):
        return False
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
        url = normalize_source_url(item.get("url"))
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


def is_article85_legal_rejection(reason: str) -> bool:
    """Only known Article 85/86/81 legal-claim failures are eligible for one repair attempt."""
    value = str(reason or "")
    return value.startswith((
        "Article 85:", "Article 86:", "Article 81 ",
        "المادة 85:", "المادة 86:", "المادة 81 ",
    ))


def is_article85_repairable_rejection(reason: str) -> bool:
    """Article 85 gets one bounded re-generation for known legal/shape defects."""
    value = str(reason or "")
    short_section = bool(re.search(
        r"sections\[\d+\]\.body: الطول \d+ خارج المدى 120-8000", value
    ))
    overlong_excerpt = bool(re.search(r"excerpt: الطول \d+ خارج المدى 40-300", value))
    unexpected_money = value.startswith("المثال الرقمي في النص يتضمن مبلغاً لا يطابق بيانات الحساب")
    missing_money = value.startswith("المثال الرقمي في النص يجب أن يذكر الأجر والمكافأة الأساسية والمبلغ المستحق")
    unparseable_money = value.startswith("المثال الرقمي: تعذّر تحليل مبلغ مذكور بجانب العملة")
    canonical_example = value.startswith("calculation_example: موضوع المادة 85 يتطلب المثال الثابت")
    section_count = re.fullmatch(r"sections: العدد (\d+) خارج المدى \d+-\d+", value)
    # Permit one full-JSON repair only for a small overflow (e.g. 13-16 sections),
    # rather than silently dropping any generated content or retrying unboundedly.
    too_many_sections = bool(
        section_count and MAX_SECTIONS < int(section_count.group(1)) <= MAX_SECTIONS + 4
    )
    empty_section = bool(re.fullmatch(r"sections\[\d+\]\.body: فارغ", value))
    boundary_conflict = value.startswith(("Article 85 boundary:", "المادة 85 boundary:"))
    return (is_article85_legal_rejection(value) or short_section
            or overlong_excerpt or too_many_sections or unexpected_money
            or missing_money or unparseable_money or canonical_example or empty_section or boundary_conflict)


def is_quality_repairable_rejection(reason: str, *, topic_id: str) -> bool:
    """Allow one bounded model repair for safe structural defects and validated EOSB calculation mismatches."""
    value = str(reason or "")
    if re.fullmatch(r"sections\[\d+\]\.body: فارغ", value):
        return True
    if re.search(r"sections\[\d+\]\.body: الطول \d+ خارج المدى 120-8000", value):
        return True
    if re.fullmatch(r"excerpt: الطول \d+ خارج المدى 40-300", value):
        return True
    section_count = re.fullmatch(r"sections: العدد (\d+) خارج المدى \d+-\d+", value)
    if section_count:
        count = int(section_count.group(1))
        return MAX_SECTIONS < count <= MAX_SECTIONS + 4

    # The structured EOSB calculator remains authoritative. Only allow a rewrite
    # when the validator identifies a known calculation/example mismatch.
    if topic_id not in EOSB_TOPIC_IDS:
        return False
    if value.startswith("calculation_example.scenario: نص المثال"):
        return True
    return value.startswith((
        "calculation_example.full_benefit: المتوقع ",
        "calculation_example.payable_benefit: المتوقع ",
        "مدة الخدمة بالنص (",
        "المثال الرقمي في النص يتضمن مبلغاً لا يطابق بيانات الحساب",
        "المثال الرقمي في النص يجب أن يذكر الأجر والمكافأة الأساسية والمبلغ المستحق",
        "المثال الرقمي: تعذّر تحليل مبلغ مذكور بجانب العملة",
        "calculation_example: عند استخدام سنوات كسرية",
        "calculation_example: سنوات الخدمة أو الأشهر أو الأيام خارج الحدود المقبولة",
    ))


def ensure_article85_notice_caveat(data, *, lang: str):
    """Copy an article and add only the standard notice caveat when that specific caveat is missing."""
    if not isinstance(data, dict) or not isinstance(data.get("sections"), list):
        raise Reject("Article 85 notice caveat: invalid article structure")
    fixed = json.loads(json.dumps(data, ensure_ascii=False))
    if lang == "ar":
        clause = (
            "المادة 85 تحدد نسب مكافأة نهاية الخدمة عند الاستقالة فقط، ولا تحدد مدة إشعار العقد ولا تعفي من متطلباته؛ "
            "وقد تبقى متطلبات الإشعار وإجراءات الاستقالة واجبة بحسب نوع العقد والأحكام النظامية المنطبقة."
        )
        heading_pattern = r"(استقالة|المادة\s*85|الإشعار)"
    else:
        clause = (
            "Article 85 sets the resignation benefit ratio only; it does not set or waive contract notice requirements. "
            "Applicable notice requirements and resignation procedures may still apply depending on the contract and law."
        )
        heading_pattern = r"(resignation|article\s*85|notice)"
    combined = " ".join(
        str(sec.get("heading", "")) + " " + str(sec.get("body", ""))
        for sec in fixed["sections"] if isinstance(sec, dict)
    )
    if clause not in combined:
        target = next((
            sec for sec in fixed["sections"]
            if isinstance(sec, dict)
            and re.search(heading_pattern, str(sec.get("heading", "")) + " " + str(sec.get("body", "")), re.IGNORECASE)
        ), None)
        if target is None:
            target = next((sec for sec in fixed["sections"] if isinstance(sec, dict)), None)
        if target is None:
            raise Reject("Article 85 notice caveat: no section is available")
        existing_body = str(target.get("body", "")).strip()
        target["body"] = existing_body + ("\n\n" if existing_body else "") + clause
    return fixed


def ensure_article85_boundary_caveat(data, *, lang: str):
    """Copy the article and add the precise two-thirds boundary explanation when missing."""
    if not isinstance(data, dict) or not isinstance(data.get("sections"), list):
        raise Reject("Article 85 boundary: invalid article structure")
    fixed = json.loads(json.dumps(data, ensure_ascii=False))
    if lang == "ar":
        clause = (
            "تكون نسبة ثلثي المكافأة عند الاستقالة فقط إذا كانت مدة الخدمة أكثر من خمس سنوات وأقل من عشر سنوات؛ "
            "أما خمس سنوات بالضبط فتقع ضمن نطاق الثلث."
        )
        heading_pattern = r"(استقالة|المادة\s*85|الثلث|المكافأة)"
        bad_range = re.compile(
            r"(?:من\s+(?:خمس|5)\s*(?:إلى|الى|حتى|[-–—])\s*(?:عشر|10)\s+سنوات?).{0,100}(?:ثلثي|الثلثين)|"
            r"(?:ثلثي|الثلثين).{0,100}(?:من\s+(?:خمس|5)\s*(?:إلى|الى|حتى|[-–—])\s*(?:عشر|10)\s+سنوات?)"
        )
    else:
        clause = (
            "The two-thirds resignation ratio applies only when service is more than five years and less than ten years; "
            "exactly five years remains in the one-third band."
        )
        heading_pattern = r"(resignation|article\s*85|two.thirds|benefit)"
        bad_range = re.compile(
            r"(?:two[\s-]+thirds|2\s*/\s*3).{0,100}\b(?:5|five)\s*(?:to|[-–—])\s*(?:10|ten)\s+years?\b|"
            r"\b(?:5|five)\s*(?:to|[-–—])\s*(?:10|ten)\s+years?.{0,100}(?:two[\s-]+thirds|2\s*/\s*3)",
            re.IGNORECASE,
        )
    combined = " ".join(
        str(sec.get("heading", "")) + " " + str(sec.get("body", ""))
        for sec in fixed["sections"] if isinstance(sec, dict)
    )
    if bad_range.search(combined):
        raise Reject("Article 85 boundary: conflicting five-to-ten-year two-thirds claim")
    if clause not in combined:
        target = next((
            sec for sec in fixed["sections"]
            if isinstance(sec, dict)
            and re.search(heading_pattern, str(sec.get("heading", "")) + " " + str(sec.get("body", "")), re.IGNORECASE)
        ), None)
        if target is None:
            target = next((sec for sec in fixed["sections"] if isinstance(sec, dict)), None)
        if target is None:
            raise Reject("Article 85 boundary: no section is available")
        existing_body = str(target.get("body", "")).strip()
        target["body"] = existing_body + ("\n\n" if existing_body else "") + clause
    return fixed


def repair_empty_article85_section(data, *, reason: str, lang: str = "ar"):
    """Repair an empty Article 85 body while preserving its heading and any bullets."""
    match = re.fullmatch(r"sections\[(\d+)\]\.body: فارغ", str(reason or "").strip())
    if not match or not isinstance(data, dict) or not isinstance(data.get("sections"), list):
        raise Reject(str(reason or "Article 85 empty section: unsupported rejection"))

    fixed = json.loads(json.dumps(data, ensure_ascii=False))
    sections = fixed["sections"]
    index = int(match.group(1))
    if not (0 <= index < len(sections)) or not isinstance(sections[index], dict):
        raise Reject(str(reason))

    empty_section = sections[index]
    if str(empty_section.get("body") or "").strip():
        raise Reject(str(reason))
    heading = str(empty_section.get("heading") or "").strip()
    if not heading:
        raise Reject(str(reason))
    raw_bullets = empty_section.get("bullets") or []
    if not isinstance(raw_bullets, list) or any(not isinstance(item, str) for item in raw_bullets):
        raise Reject(str(reason))
    bullet_text = "\n".join(item.strip() for item in raw_bullets if item.strip())
    preserved_payload = heading + (("\n" + bullet_text) if bullet_text else "")

    if len(sections) > MIN_SECTIONS:
        # Put the empty heading and its bullets in another body before removing the shell.
        # Exclude an out-of-range neighbor before sorting: index+1 equals len(sections)
        # when the empty section is the final item, and indexing it in the sort key crashes.
        candidates = [i for i in (index - 1, index + 1)
                      if 0 <= i < len(sections) and i != index]
        candidates.extend(i for i in range(len(sections)) if i != index and i not in candidates)
        candidates.sort(key=lambda i: (
            bool(re.search(r"(?:مثال|example)", str(sections[i].get("heading", "")), re.I)),
            abs(i - index),
            len(str(sections[i].get("body") or "")),
        ))
        for target_index in candidates:
            if not (0 <= target_index < len(sections)) or target_index == index:
                continue
            target = sections[target_index]
            if not isinstance(target, dict) or not isinstance(target.get("body"), str):
                continue
            existing_body = target["body"].strip()
            combined = existing_body + ("\n\n" if existing_body else "") + preserved_payload
            if existing_body and len(combined) <= 8000:
                target["body"] = combined
                sections.pop(index)
                return fixed, "empty section merged with heading and bullets preserved"

    # At the minimum section count, keep the section and give it a short, factual body.
    if lang == "ar":
        context = (
            f"يتناول هذا القسم موضوع «{heading}» ضمن شرح الاستحقاق عند الاستقالة. "
            "تُقرأ التفاصيل مع بقية قواعد المادة 85، ويجب التحقق من انطباقها بحسب مدة الخدمة وسبب انتهاء العلاقة "
            "والوقائع ذات الصلة، بالرجوع إلى النص الرسمي لنظام العمل السعودي."
        )
    else:
        context = (
            f"This section covers “{heading}” in the context of resignation benefits. "
            "Read it alongside the other Article 85 rules and assess applicability using the length of service, "
            "the reason employment ended, the relevant facts, and the official Saudi Labour Law text."
        )
    empty_section["body"] = context
    return fixed, "empty section populated without removing its heading or bullets"


def merge_article85_sections(data, *, target_count=MAX_SECTIONS):
    """Merge surplus sections into another body without dropping headings, prose, or bullets."""
    if not isinstance(data, dict) or not isinstance(data.get("sections"), list):
        raise Reject("Article 85 section merge: invalid article structure")
    fixed = json.loads(json.dumps(data, ensure_ascii=False))
    sections = fixed["sections"]
    if len(sections) > MAX_SECTIONS + 4:
        raise Reject(f"sections: العدد {len(sections)} خارج المدى {MIN_SECTIONS}-{MAX_SECTIONS}")
    if target_count < MIN_SECTIONS or target_count > MAX_SECTIONS:
        raise Reject("Article 85 section merge: invalid target count")

    while len(sections) > target_count:
        pairs = []
        for source_index, source in enumerate(sections):
            if not isinstance(source, dict):
                continue
            source_heading = str(source.get("heading") or "").strip()
            source_body = str(source.get("body") or "").strip()
            source_bullets = source.get("bullets") or []
            if not source_heading or not source_body or not isinstance(source_bullets, list):
                continue
            bullets = [str(item).strip() for item in source_bullets if str(item).strip()]
            source_payload = source_heading + "\n" + source_body
            if bullets:
                source_payload += "\n\n" + ("Key points:\n" if source_heading.isascii() else "نقاط مرتبطة:\n")
                source_payload += "\n".join(f"- {item}" for item in bullets)
            source_is_example = bool(re.search(r"(?:مثال|example)", source_heading, re.I))
            for target_index, target in enumerate(sections):
                if target_index == source_index or not isinstance(target, dict):
                    continue
                target_heading = str(target.get("heading") or "").strip()
                target_body = str(target.get("body") or "").strip()
                if not target_heading or not target_body:
                    continue
                target_is_example = bool(re.search(r"(?:مثال|example)", target_heading, re.I))
                combined = target_body + "\n\n" + source_payload
                if len(combined) <= 8000:
                    # Preserve an Example section as a dedicated section where possible.
                    priority = (
                        source_is_example,
                        target_is_example,
                        abs(target_index - source_index),
                        len(target_body),
                    )
                    pairs.append((priority, source_index, target_index, combined))
        if not pairs:
            raise Reject(f"sections: العدد {len(sections)} خارج المدى {MIN_SECTIONS}-{MAX_SECTIONS}؛ لا يوجد دمج آمن ضمن حد طول القسم")
        _, source_index, target_index, combined = min(pairs, key=lambda item: item[0])
        sections[target_index]["body"] = combined
        sections.pop(source_index)
    return fixed


ARTICLE85_CANONICAL_VALUES = {
    "monthly_wage": "12000", "years": "6", "months": "0", "days": "0",
    "scenario": "resignation", "full_benefit": "42000", "payable_benefit": "28000",
}


def ensure_article85_critical_content(data, *, lang: str):
    """Inject canonical Article 85 boundary and worked-example text before any content gate."""
    if not isinstance(data, dict) or not isinstance(data.get("sections"), list):
        raise Reject("Article 85 canonical content: invalid article structure")
    fixed = json.loads(json.dumps(data, ensure_ascii=False))
    sections = fixed["sections"]
    actions = []

    # Repair empty sections before overflow: titles and bullets are moved or kept, never silently dropped.
    for _ in range(MAX_SECTIONS + 5):
        empty_index = next((
            i for i, sec in enumerate(sections)
            if isinstance(sec, dict) and not str(sec.get("body") or "").strip()
        ), None)
        if empty_index is not None:
            fixed, action = repair_empty_article85_section(
                fixed, reason=f"sections[{empty_index}].body: فارغ", lang=lang)
            sections = fixed["sections"]
            actions.append(action)
            continue
        if len(sections) > MAX_SECTIONS:
            fixed = merge_article85_sections(fixed, target_count=MAX_SECTIONS)
            sections = fixed["sections"]
            actions.append("excess sections merged with full text preserved")
            continue
        break
    else:
        raise Reject("Article 85 canonical content: bounded structure repair did not converge")

    if not (MIN_SECTIONS <= len(sections) <= MAX_SECTIONS):
        raise Reject(f"sections: العدد {len(sections)} خارج المدى {MIN_SECTIONS}-{MAX_SECTIONS}")

    if lang == "ar":
        boundary = (
            "عند الاستقالة وفق المادة 85، يستحق العامل ثلث المكافأة بعد سنتين متتاليتين من الخدمة وحتى خمس سنوات شاملةً خمس سنوات؛ "
            "ولا تنطبق نسبة الثلثين إلا إذا كانت مدة الخدمة أكثر من خمس سنوات وأقل من عشر سنوات؛ "
            "وتستحق المكافأة كاملة إذا بلغت مدة الخدمة عشر سنوات فأكثر."
        )
        example_text = (
            "مثال توضيحي ثابت: إذا كان الأجر الشهري الأخير 12,000 ريال وكانت مدة الخدمة 6 سنوات، "
            "فإن المكافأة الأساسية المحسوبة وفق المادة 84 تبلغ 42,000 ريال. "
            "وعند انتهاء العلاقة بسبب استقالة العامل، وبعد انطباق نسبة الثلثين وفق المادة 85، "
            "يكون المبلغ المستحق 28,000 ريال. هذا المثال خاص بالاستقالة بعد استيفاء شرط الخدمة، "
            "ولا يغيّر القواعد التي تنطبق على أسباب انتهاء الخدمة الأخرى."
        )
        example_heading = "مثال حسابي توضيحي"
        boundary_pattern = r"(استقالة|المادة\s*85|الثلث|المكافأة)"
    else:
        boundary = (
            "For resignation under Article 85, one third applies after two consecutive years of service through exactly five years; "
            "the two-thirds ratio applies only when service is more than five years and less than ten years; "
            "the full benefit applies at ten years or more."
        )
        example_text = (
            "Fixed illustrative example: With a last monthly wage of SAR 12,000 and six years of service, "
            "the base end-of-service benefit calculated under Article 84 is SAR 42,000. "
            "Where employment ends by the employee’s resignation and Article 85’s two-thirds ratio applies, "
            "the payable amount is SAR 28,000. This example is specific to resignation after the qualifying service threshold; "
            "other termination reasons follow their own applicable rules."
        )
        example_heading = "Worked Example"
        boundary_pattern = r"(resignation|article\s*85|two.thirds|benefit)"

    # Ensure a dedicated canonical example section exists. If at capacity, merge first without losing text.
    example_indices = [
        i for i, sec in enumerate(sections)
        if isinstance(sec, dict) and re.search(r"(?:مثال|example)", str(sec.get("heading", "")), re.I)
    ]
    if len(example_indices) > 1:
        fixed, duplicate_actions = merge_duplicate_article85_example_sections(fixed, lang=lang)
        sections = fixed["sections"]
        actions.extend(duplicate_actions)
        example_indices = [
            i for i, sec in enumerate(sections)
            if isinstance(sec, dict) and re.search(r"(?:مثال|example)", str(sec.get("heading", "")), re.I)
        ]

    if not example_indices:
        if len(sections) >= MAX_SECTIONS:
            fixed = merge_article85_sections(fixed, target_count=MAX_SECTIONS - 1)
            sections = fixed["sections"]
            actions.append("sections merged to make room for canonical example")
        sections.append({"heading": example_heading, "body": example_text, "bullets": []})
        actions.append("canonical example section added")
    else:
        target_example = sections[example_indices[0]]
        if target_example.get("body") != example_text:
            target_example["body"] = example_text
            actions.append("canonical example prose enforced")

    # Structured values for this fixed example are constants, not model-controlled fields.
    if fixed.get("calculation_example") != ARTICLE85_CANONICAL_VALUES:
        fixed["calculation_example"] = dict(ARTICLE85_CANONICAL_VALUES)
        actions.append("canonical calculation values enforced")

    # Inject the critical ratio sentence into the most relevant non-example section with sufficient capacity.
    all_text = " ".join(
        str(sec.get("heading", "")) + " " + str(sec.get("body", ""))
        for sec in sections if isinstance(sec, dict)
    )
    if boundary not in all_text:
        candidates = [
            i for i, sec in enumerate(sections)
            if isinstance(sec, dict) and not re.search(r"(?:مثال|example)", str(sec.get("heading", "")), re.I)
        ]
        candidates.sort(key=lambda i: (
            not bool(re.search(boundary_pattern, str(sections[i].get("heading", "")), re.I)),
            len(str(sections[i].get("body") or "")),
        ))
        target_index = next((
            i for i in candidates
            if len(str(sections[i].get("body") or "").strip()) + 2 + len(boundary) <= 8000
        ), None)
        if target_index is not None:
            body = str(sections[target_index].get("body") or "").strip()
            sections[target_index]["body"] = body + "\n\n" + boundary
        elif len(sections) < MAX_SECTIONS:
            sections.append({
                "heading": "نسب الاستقالة" if lang == "ar" else "Resignation benefit ratios",
                "body": boundary, "bullets": [],
            })
        else:
            fixed = merge_article85_sections(fixed, target_count=MAX_SECTIONS - 1)
            sections = fixed["sections"]
            sections.append({
                "heading": "نسب الاستقالة" if lang == "ar" else "Resignation benefit ratios",
                "body": boundary, "bullets": [],
            })
            actions.append("sections merged to make room for canonical boundary")
        actions.append("canonical two-thirds boundary enforced")

    # Reapply local binding after any structure merge copied the object.
    fixed["sections"] = sections

    before_faq = json.dumps(fixed, ensure_ascii=False, sort_keys=True)
    fixed, faq_repaired = ensure_article85_minimum_faq(fixed, lang=lang)
    if faq_repaired:
        actions.append("minimum-service FAQ corrected")
    if json.dumps(fixed, ensure_ascii=False, sort_keys=True) != before_faq and not faq_repaired:
        actions.append("FAQ content normalized")

    before_notice = json.dumps(fixed, ensure_ascii=False, sort_keys=True)
    fixed = ensure_article85_notice_caveat(fixed, lang=lang)
    if json.dumps(fixed, ensure_ascii=False, sort_keys=True) != before_notice:
        actions.append("notice/resignation caveat enforced")

    before_article86 = json.dumps(fixed, ensure_ascii=False, sort_keys=True)
    fixed = ensure_article85_article86_clause(fixed, lang=lang)
    if json.dumps(fixed, ensure_ascii=False, sort_keys=True) != before_article86:
        actions.append("Article 86 rule enforced")

    return fixed, actions


def trim_article85_excerpt(data, *, max_chars: int = 300):
    """Copy and minimally shorten a slightly overlong excerpt; all downstream gates still rerun."""
    if not isinstance(data, dict) or not isinstance(data.get("excerpt"), str):
        raise Reject("Article 85 excerpt: invalid excerpt")
    fixed = json.loads(json.dumps(data, ensure_ascii=False))
    excerpt = strip_ws(fixed["excerpt"])
    if len(excerpt) <= max_chars:
        return fixed
    if len(excerpt) > max_chars + 60:
        raise Reject("Article 85 excerpt: too far beyond the length limit for deterministic trimming")
    prefix = excerpt[:max_chars]
    sentence_ends = [
        m.end() for m in re.finditer(r"[.!?؟](?:\s|$)", prefix)
        if m.end() >= 200
    ]
    if sentence_ends:
        trimmed = prefix[:sentence_ends[-1]].strip()
    else:
        cut = prefix.rfind(" ")
        if cut < 40:
            raise Reject("Article 85 excerpt: no safe word boundary within the limit")
        trimmed = prefix[:cut].rstrip(" ,;:—-") + "…"
    if not (40 <= len(trimmed) <= max_chars):
        raise Reject("Article 85 excerpt: deterministic trim did not meet the length bounds")
    fixed["excerpt"] = trimmed
    return fixed


def repair_article85_notice_loss_claim(data, *, lang: str):
    """Replace only unsupported notice-causes-automatic-forfeiture sentences with the approved caveat."""
    if not isinstance(data, dict) or not isinstance(data.get("sections"), list):
        raise Reject("Article 85 notice-loss repair: invalid article structure")
    fixed = json.loads(json.dumps(data, ensure_ascii=False))
    if lang == "ar":
        replacement = (
            "المادة 85 تحدد نسب مكافأة نهاية الخدمة عند الاستقالة فقط، ولا تحدد مدة إشعار العقد ولا تعفي من متطلباته؛ "
            "وقد تبقى متطلبات الإشعار وإجراءات الاستقالة واجبة بحسب نوع العقد والأحكام النظامية المنطبقة."
        )
        claim_pattern = re.compile(
            r"(?:قد\s+)?(?:يؤدي|يترتب|يتسبب|يسبب|ينتج)\s*(?:إلى|الى|في|عن)?\s*"
            r".{0,50}(?:فقدان|خسارة|حرمان|خصم|حسم|تقليل|خفض).{0,80}(?:المكافأة|مكافأة نهاية الخدمة)"
        )
        negated_pattern = re.compile(
            r"(?:قد\s+)?(?:لا|ليس|لم|لن)\s*(?:يؤدي|يترتب|يتسبب|يسبب|ينتج)"
        )
        unsupported_exception_pattern = re.compile(
            r"(?:عدم الالتزام|مخالفة|الإخلال).{0,80}(?:الإشعار|اشعار|مهلة الإشعار)"
            r".{0,180}لا\s*(?:يؤدي|يترتب|يسبب|ينتج).{0,150}"
            r"(?:فقدان|خسارة|حرمان|خصم|حسم|تقليل|خفض).{0,120}(?:المكافأة|مكافأة نهاية الخدمة)"
            r".{0,120}(?:إلا\s+إذا|ما\s+لم).{0,120}(?:بند|شرط|العقد|قرار قضائي|حكم قضائي)"
        )
    else:
        replacement = (
            "Article 85 sets the resignation benefit ratio only; it does not set or waive contract notice requirements. "
            "Applicable notice requirements and resignation procedures may still apply depending on the contract and law."
        )
        claim_pattern = re.compile(
            r"\b(?:may|can|could|might|will|would)\s+(?:(?:automatically|directly)\s+)?"
            r"(?:lead to|result in|cause)\b.{0,100}\b"
            r"(?:loss|forfeit(?:ure)?|deduct(?:ion)?|reduction|withholding)\b"
            r".{0,100}\b(?:eosb|end[- ]of[- ]service|indemnity|severance|award|benefit)\b",
            re.IGNORECASE,
        )
        negated_pattern = re.compile(
            r"\b(?:does not|doesn't|cannot|can't|will not|won't|would not|wouldn't)\s+"
            r"(?:(?:automatically|directly)\s+)?(?:lead to|result in|cause)\b",
            re.IGNORECASE,
        )
        unsupported_exception_pattern = re.compile(
            r"(?:failure to (?:give|comply with)|non-compliance with|breach of).{0,80}\bnotice(?: period)?\b"
            r".{0,160}\b(?:does not|doesn't|will not|won't)\s+(?:automatically\s+)?"
            r"(?:lead to|result in|cause|reduce|forfeit|deduct).{0,120}\b"
            r"(?:eosb|end[- ]of[- ]service|award|benefit|loss|reduction)\b"
            r".{0,100}\b(?:unless|except when|except if)\b.{0,100}\b"
            r"(?:contract|clause|court|judgment|ruling)\b",
            re.IGNORECASE,
        )

    changed = False

    def repair_text(value):
        nonlocal changed
        if not isinstance(value, str) or not value:
            return value
        parts = re.split(r"(?<=[.!?؟])\s+|\n+", value)
        repaired = []
        for part in parts:
            if unsupported_exception_pattern.search(part) or (
                claim_pattern.search(part) and not negated_pattern.search(part)
            ):
                repaired.append(replacement)
                changed = True
            else:
                repaired.append(part)
        return " ".join(repaired)

    for key in ("title", "meta_description", "excerpt"):
        if key in fixed:
            fixed[key] = repair_text(fixed[key])
    for section in fixed["sections"]:
        if not isinstance(section, dict):
            continue
        for key in ("heading", "body"):
            if key in section:
                section[key] = repair_text(section[key])
        bullets = section.get("bullets")
        if isinstance(bullets, list):
            section["bullets"] = [repair_text(item) for item in bullets]
    faq = fixed.get("faq")
    if isinstance(faq, list):
        for item in faq:
            if isinstance(item, dict):
                for key in ("q", "a"):
                    if key in item:
                        item[key] = repair_text(item[key])
    sources = fixed.get("official_sources")
    if isinstance(sources, list):
        for item in sources:
            if isinstance(item, dict) and "title" in item:
                item["title"] = repair_text(item["title"])

    if not changed:
        raise Reject("Article 85 notice-loss repair: no matching unsupported claim found")
    return fixed


def repair_short_article85_section(data, *, reason: str, lang: str):
    """Expand only a reported short Article 85 section with neutral, topic-relevant context."""
    match = re.fullmatch(
        r"sections\[(\d+)\]\.body: الطول (\d+) خارج المدى 120-8000",
        str(reason or "").strip(),
    )
    if not match or not isinstance(data, dict) or not isinstance(data.get("sections"), list):
        raise Reject(str(reason or "Article 85 short section: unsupported rejection"))

    fixed = json.loads(json.dumps(data, ensure_ascii=False))
    index, reported_length = int(match.group(1)), int(match.group(2))
    if not (0 <= index < len(fixed["sections"])):
        raise Reject(str(reason))
    section = fixed["sections"][index]
    if not isinstance(section, dict):
        raise Reject(str(reason))
    body = str(section.get("body") or "").strip()
    if len(body) != reported_length or len(body) >= 120:
        # Do not repair stale or mismatched validation errors by guessing.
        raise Reject(str(reason))
    if lang == "ar":
        context = (
            "يرتبط تطبيق هذه النقطة بمدة الخدمة ونوع العقد وسبب انتهاء العلاقة والوقائع ذات الصلة؛ "
            "لذا ينبغي مراجعة النص الرسمي لنظام العمل السعودي قبل تطبيقها على حالة بعينها."
        )
    else:
        context = (
            "Apply this point only after checking the service period, contract type, reason employment ended, "
            "and relevant facts against the official Saudi Labour Law text."
        )
    if context not in body:
        body = body + ("\n\n" if body else "") + context
    if not (120 <= len(body) <= 8000):
        raise Reject(str(reason))
    section["body"] = body
    return fixed, "short section expanded with neutral legal context"


def ensure_article85_article86_clause(data, *, lang: str):
    """Add the bounded, approved Article 86 rule and replace direct basic-wage exclusion claims."""
    if not isinstance(data, dict) or not isinstance(data.get("sections"), list):
        raise Reject("Article 86 repair: invalid article structure")
    fixed = json.loads(json.dumps(data, ensure_ascii=False))
    if lang == "ar":
        clause = (
            "وفق المادة 86، يجوز بالاتفاق الصريح استبعاد العمولات ونسب المبيعات والعناصر المشابهة "
            "من الأجر المحتسب للمكافأة فقط إذا كانت بطبيعتها قابلة للزيادة والنقص؛ "
            "ولا يعني ذلك استبعاد الأجر الأساسي."
        )
        bad_basic_wage = re.compile(
            r"(?:لا\s*يُ?ستبعد\s+الأجر الأساسي\s+إلا.{0,80}|"
            r"(?:يجوز|يمكن)\s+استبعاد\s+(?:الأجر الأساسي|الراتب الأساسي).{0,80})",
            re.IGNORECASE,
        )
        heading_pattern = r"(المادة\s*86|الأجر|العمولات|المبيعات)"
    else:
        clause = (
            "Under Article 86, commissions, sales percentages, and similar wage elements naturally subject to "
            "increase and decrease may be excluded from the benefit calculation only by explicit agreement; "
            "this does not exclude basic wage."
        )
        bad_basic_wage = re.compile(
            r"\b(?:the\s+)?basic\s+(?:wage|salary)\s+(?:may|can|could|is)\s+be\s+excluded\b",
            re.IGNORECASE,
        )
        heading_pattern = r"(article\s*86|wage|commission|sales)"

    def repair_value(value):
        if not isinstance(value, str) or not value:
            return value
        parts = re.split(r"(?<=[.!?؟])\s+|\n+", value)
        repaired = [clause if bad_basic_wage.search(part) else part for part in parts]
        return " ".join(repaired)

    # Work through all reader-facing text fields so a false statement cannot survive in an FAQ or excerpt.
    for key in ("title", "meta_description", "excerpt"):
        if key in fixed:
            fixed[key] = repair_value(fixed[key])
    for section in fixed["sections"]:
        if not isinstance(section, dict):
            continue
        for key in ("heading", "body"):
            if key in section:
                section[key] = repair_value(section[key])
        if isinstance(section.get("bullets"), list):
            section["bullets"] = [repair_value(item) for item in section["bullets"]]
    if isinstance(fixed.get("faq"), list):
        for item in fixed["faq"]:
            if isinstance(item, dict):
                for key in ("q", "a"):
                    if key in item:
                        item[key] = repair_value(item[key])

    combined = " ".join(
        str(value)
        for value in (
            [fixed.get("title", ""), fixed.get("meta_description", ""), fixed.get("excerpt", "")]
            + [
                str(section.get(key, "")) if isinstance(section, dict) else ""
                for section in fixed["sections"] for key in ("heading", "body")
            ]
            + [
                str(bullet)
                for section in fixed["sections"] if isinstance(section, dict)
                for bullet in (section.get("bullets") or [])
            ]
            + [
                str(item.get(key, "")) for item in (fixed.get("faq") or [])
                if isinstance(item, dict) for key in ("q", "a")
            ]
        )
    )
    if clause not in combined:
        candidates = [
            index for index, section in enumerate(fixed["sections"])
            if isinstance(section, dict)
        ]
        candidates.sort(key=lambda index: (
            not bool(re.search(
                heading_pattern,
                str(fixed["sections"][index].get("heading", "")) + " "
                + str(fixed["sections"][index].get("body", "")),
                re.IGNORECASE,
            )),
            len(str(fixed["sections"][index].get("body") or "")),
        ))
        target = next((
            fixed["sections"][index] for index in candidates
            if len(str(fixed["sections"][index].get("body") or "").strip())
            + 2 + len(clause) <= 8000
        ), None)
        if target is None:
            raise Reject("Article 86 repair: no section has room for the required legal caveat")
        body = str(target.get("body") or "").strip()
        target["body"] = body + ("\n\n" if body else "") + clause
    return fixed


def merge_duplicate_article85_example_sections(data, *, lang: str):
    """Keep one canonical Example section while preserving all duplicate sections' text and bullets."""
    if not isinstance(data, dict) or not isinstance(data.get("sections"), list):
        raise Reject("Article 85 duplicate-example repair: invalid article structure")
    fixed = json.loads(json.dumps(data, ensure_ascii=False))
    sections = fixed["sections"]
    actions = []

    while True:
        examples = [
            i for i, section in enumerate(sections)
            if isinstance(section, dict)
            and re.search(r"(?:مثال|example)", str(section.get("heading", "")), re.IGNORECASE)
        ]
        if len(examples) <= 1:
            return fixed, actions

        canonical_index = examples[0]
        for source_index in reversed(examples[1:]):
            source = sections[source_index]
            if not isinstance(source, dict):
                raise Reject("Article 85 duplicate-example repair: invalid duplicate section")
            heading = str(source.get("heading") or "").strip()
            body = str(source.get("body") or "").strip()
            raw_bullets = source.get("bullets") or []
            if not heading or not body or not isinstance(raw_bullets, list):
                raise Reject("Article 85 duplicate-example repair: incomplete duplicate section")
            if any(not isinstance(item, str) for item in raw_bullets):
                raise Reject("Article 85 duplicate-example repair: invalid duplicate bullets")

            if lang == "ar":
                label = "محتوى محفوظ من قسم المثال الإضافي"
                bullet_label = "نقاط محفوظة من القسم الإضافي"
            else:
                label = "Preserved content from an additional generated example section"
                bullet_label = "Preserved points from the additional section"

            payload = f"{label} — {heading}\n{body}"
            bullets = [item.strip() for item in raw_bullets if item.strip()]
            if bullets:
                payload += "\n\n" + bullet_label + ":\n" + "\n".join(f"- {item}" for item in bullets)

            candidates = [
                i for i, target in enumerate(sections)
                if i != source_index and i != canonical_index
                and isinstance(target, dict)
                and not re.search(r"(?:مثال|example)", str(target.get("heading", "")), re.IGNORECASE)
                and isinstance(target.get("body"), str)
            ]
            candidates.sort(key=lambda i: (
                abs(i - source_index),
                len(str(sections[i].get("body") or "")),
            ))
            target_index = next((
                i for i in candidates
                if len(str(sections[i].get("body") or "").strip())
                + 2 + len(payload) <= 8000
            ), None)
            if target_index is None:
                raise Reject(
                    "Article 85 duplicate-example repair: no non-example section has room; refusing to discard content"
                )

            target_body = str(sections[target_index].get("body") or "").strip()
            sections[target_index]["body"] = target_body + "\n\n" + payload
            sections.pop(source_index)
            actions.append("duplicate example section merged with all prose and bullets preserved")
    return fixed, actions


def ensure_article85_minimum_faq(data, *, lang: str):
    """Correct only FAQs that deny a minimum service period despite asking about Article 85 eligibility."""
    if not isinstance(data, dict) or not isinstance(data.get("faq"), list):
        return json.loads(json.dumps(data, ensure_ascii=False)), False
    fixed = json.loads(json.dumps(data, ensure_ascii=False))
    changed = False
    if lang == "ar":
        asks_minimum_pattern = re.compile(
            r"(?:الحد الأدنى|حد أدنى|أقل مدة|أدنى مدة).{0,100}(?:الخدمة|الاستحقاق|المكافأة)?",
            re.IGNORECASE,
        )
        denies_minimum_pattern = re.compile(
            r"(?:لا\s*(?:يتوفر|تتوفر|يوجد|توجد|يوجد\s+أي|توجد\s+أي)\s+حد\s+أدنى|لا\s+حد\s+أدنى)",
            re.IGNORECASE,
        )
        standard_answer = (
            "وفق المادة 85، لا يستحق العامل مكافأة الاستقالة قبل إكمال سنتين متتاليتين من الخدمة. "
            "من سنتين إلى خمس سنوات شاملةً خمس سنوات، يستحق ثلث المكافأة؛ وبعد تجاوز خمس سنوات وقبل بلوغ عشر سنوات، "
            "يستحق الثلثين؛ وعند عشر سنوات فأكثر، يستحق المكافأة كاملة. تتعلق هذه النسب بالاستقالة، "
            "مع مراعاة الحالات النظامية المستثناة."
        )
    else:
        asks_minimum_pattern = re.compile(
            r"\b(?:minimum|minimum service|minimum period|how long).{0,100}\b(?:service|eligible|entitled|award|eosb)?\b",
            re.IGNORECASE,
        )
        denies_minimum_pattern = re.compile(
            r"\b(?:there is|there's|is) no minimum\b|\bno minimum (?:service|period|threshold)\b",
            re.IGNORECASE,
        )
        standard_answer = (
            "Under Article 85, no resignation benefit is due before two consecutive years of service. "
            "For ordinary resignation, one third applies from two through five years inclusive, two thirds applies "
            "only after five years and before ten years, and the full benefit applies at ten years or more. "
            "These ratios are specific to resignation and remain subject to any statutory exceptions that apply."
        )

    for item in fixed["faq"]:
        if not isinstance(item, dict):
            continue
        question = str(item.get("q") or "")
        answer = str(item.get("a") or "")
        if asks_minimum_pattern.search(question) and denies_minimum_pattern.search(answer):
            item["a"] = standard_answer
            changed = True
    return fixed, changed


def repair_article85_notice_attribution_claim(data, *, lang: str):
    """Replace sentences that wrongly assign notice rules or a notice waiver to Article 85."""
    if not isinstance(data, dict) or not isinstance(data.get("sections"), list):
        raise Reject("Article 85 notice-attribution repair: invalid article structure")
    fixed = json.loads(json.dumps(data, ensure_ascii=False))
    if lang == "ar":
        clause = (
            "المادة 85 تحدد نسب مكافأة نهاية الخدمة عند الاستقالة فقط، ولا تحدد مدة إشعار العقد ولا تعفي من متطلباته؛ "
            "وقد تبقى متطلبات الإشعار وإجراءات الاستقالة واجبة بحسب نوع العقد والأحكام النظامية المنطبقة."
        )
        safe_title = "شرح نسب مكافأة الاستقالة وفق المادة 85"
        safe_heading = "مكافأة الاستقالة"
        safe_question = "ما الذي تحدده المادة 85 بشأن مكافأة الاستقالة؟"
    else:
        clause = (
            "Article 85 sets the resignation benefit ratio only; it does not set or waive contract notice requirements. "
            "Applicable notice requirements and resignation procedures may still apply depending on the contract and law."
        )
        safe_title = "Article 85: resignation benefit ratios explained"
        safe_heading = "Resignation benefits"
        safe_question = "What does Article 85 determine about resignation benefits?"

    def is_bad_sentence(value):
        sentence = re.sub(r"\s+", " ", str(value or "")).strip().lower()
        if lang == "en":
            if not re.search(r"\barticle\s*85\b", sentence) or "notice" not in sentence:
                return False
            denies = bool(re.search(
                r"\b(?:does not|doesn't|never|not)\s+(?:set|specify|determine|govern|address|waive)\b",
                sentence,
            ))
            attributes = bool(re.search(
                r"\b(?:specifies|states|says|provides|requires|sets|waives)\b", sentence
            ))
            asserts_no_notice = bool(re.search(
                r"\b(?:not required|isn't required|not necessary|unnecessary|no need|"
                r"does not require|doesn't require|does not need|doesn't need)\b",
                sentence,
            ))
        else:
            if not re.search(r"المادة\s*(?:85|الخامسة\s+والثمانون)", sentence):
                return False
            if not re.search(
                r"(?:الإشعار|اشعار|فترة الإشعار|مهلة الإشعار|ثلاثة أشهر|ثلاثين يوماً|ثلاثين يوما)",
                sentence,
            ):
                return False
            denies = bool(re.search(
                r"(?:لا\s+(?:تحدد|تنظم|تتناول|تعفي|تقرر)|ليست من اختصاص المادة\s*85)",
                sentence,
            ))
            attributes = bool(re.search(
                r"(?:تنص|تذكر|تقول|تقرر|تحدد|توجب|تشترط|تعفي|لا تستلزم|لا تشترط)",
                sentence,
            ))
            asserts_no_notice = bool(re.search(
                r"(?:غير مطلوب|لا يلزم|لا يتطلب|لا تحتاج|لا يستلزم|لا تشترط)",
                sentence,
            ))
        return (attributes or asserts_no_notice) and not denies

    changed = False

    def repair_text(value, *, role="prose"):
        nonlocal changed
        if not isinstance(value, str) or not value:
            return value
        parts = re.split(r"(?<=[.!?؟])\s+", value)
        repaired = []
        for part in parts:
            if is_bad_sentence(part):
                if role == "question":
                    replacement = safe_question
                elif role == "heading":
                    replacement = safe_heading
                elif role == "title":
                    replacement = safe_title
                else:
                    replacement = clause
                repaired.append(replacement)
                changed = True
            else:
                repaired.append(part)
        return " ".join(repaired)

    for key in ("title", "meta_description", "excerpt"):
        if key in fixed:
            fixed[key] = repair_text(fixed[key], role="title" if key == "title" else "prose")
    for section in fixed["sections"]:
        if not isinstance(section, dict):
            continue
        if "heading" in section:
            section["heading"] = repair_text(section["heading"], role="heading")
        if "body" in section:
            section["body"] = repair_text(section["body"])
        if isinstance(section.get("bullets"), list):
            section["bullets"] = [repair_text(item) for item in section["bullets"]]
    if isinstance(fixed.get("faq"), list):
        for item in fixed["faq"]:
            if isinstance(item, dict):
                if "q" in item:
                    item["q"] = repair_text(item["q"], role="question")
                if "a" in item:
                    item["a"] = repair_text(item["a"])
    if not changed:
        raise Reject("Article 85 notice-attribution repair: no offending sentence found")
    return fixed


def repair_article85_unexpected_money_claims(data, *, lang: str):
    """Replace sentences with extra currency amounts; Article 85 uses a fixed canonical example."""
    if not isinstance(data, dict) or not isinstance(data.get("sections"), list):
        raise Reject("Article 85 money repair: invalid article structure")
    fixed = json.loads(json.dumps(data, ensure_ascii=False))
    allowed = {
        Decimal("12000.00"),
        Decimal("42000.00"),
        Decimal("28000.00"),
    }
    if lang == "ar":
        safe_sentence = (
            "يُحسب أي مبلغ فعلي وفق بيانات الحالة والأحكام النظامية المنطبقة، ولا يُستنتج من مبلغ افتراضي إضافي."
        )
        safe_heading = "تقدير المبلغ وفق بيانات الحالة"
        safe_question = "كيف يُحسب المبلغ المستحق وفق بيانات الحالة؟"
        safe_title = "حساب مكافأة نهاية الخدمة وفق بيانات الحالة"
    else:
        safe_sentence = (
            "Any actual entitlement must be calculated from the relevant case data under the applicable rules, "
            "not from an additional illustrative amount."
        )
        safe_heading = "Calculating the applicable amount"
        safe_question = "How is the applicable benefit calculated?"
        safe_title = "Calculating end-of-service benefits from case data"

    changed = False

    def contains_unexpected_money(value):
        normalized = _normalize_eosb_digits(re.sub(r"\s+", " ", str(value or "")))
        for match in EOSB_MONEY_CLAIM_RE.finditer(normalized):
            token = next((group for group in match.groups() if group), "")
            try:
                amount = Decimal(token.replace(",", "")).quantize(
                    EOSB_CENT, rounding=ROUND_HALF_UP)
            except (InvalidOperation, ValueError):
                return True
            if amount not in allowed:
                return True
        return False

    def repair_text(value, *, role="prose"):
        nonlocal changed
        if not isinstance(value, str) or not value:
            return value
        parts = re.split(r"(?<=[.!?؟])\s+", value)
        repaired = []
        for part in parts:
            if contains_unexpected_money(part):
                if role == "question":
                    replacement = safe_question
                elif role == "heading":
                    replacement = safe_heading
                elif role == "title":
                    replacement = safe_title
                else:
                    replacement = safe_sentence
                repaired.append(replacement)
                changed = True
            else:
                repaired.append(part)
        return " ".join(repaired)

    for key in ("title", "meta_description", "excerpt"):
        if key in fixed:
            fixed[key] = repair_text(fixed[key], role="title" if key == "title" else "prose")
    for section in fixed["sections"]:
        if not isinstance(section, dict):
            continue
        if "heading" in section:
            section["heading"] = repair_text(section["heading"], role="heading")
        if "body" in section:
            section["body"] = repair_text(section["body"])
        if isinstance(section.get("bullets"), list):
            section["bullets"] = [repair_text(item) for item in section["bullets"]]
    if isinstance(fixed.get("faq"), list):
        for item in fixed["faq"]:
            if isinstance(item, dict):
                if "q" in item:
                    item["q"] = repair_text(item["q"], role="question")
                if "a" in item:
                    item["a"] = repair_text(item["a"])
    if not changed:
        raise Reject("Article 85 money repair: no unexpected currency amount found")
    return fixed


def repair_eosb_unexpected_money_claims(data, *, lang: str):
    """Remove prose sentences with currency claims not matching an already-validated EOSB example.

    Call only when validate_article has checked the calculation fields and the sole
    rejection is an unexpected currency amount elsewhere in the article. The official
    calculator fields are never modified; the complete article is validated again after
    this narrowly scoped text repair.
    """
    if not isinstance(data, dict) or not isinstance(data.get("sections"), list):
        raise Reject("EOSB money repair: invalid article structure")
    fixed = json.loads(json.dumps(data, ensure_ascii=False))
    example = fixed.get("calculation_example")
    if not isinstance(example, dict):
        raise Reject("EOSB money repair: calculation example missing")

    # The caller reaches this helper only after the validator has confirmed these
    # values against the EOSB formula. Use dynamic values, never Article 85 constants.
    allowed = set()
    for field in ("monthly_wage", "full_benefit", "payable_benefit"):
        amount = _parse_eosb_number(example.get(field), field)
        allowed.add(amount.quantize(EOSB_CENT, rounding=ROUND_HALF_UP))

    if lang == "ar":
        safe_sentence = (
            "يُحسب أي مبلغ فعلي من بيانات الحالة نفسها وفق الأحكام النظامية المنطبقة، "
            "ويجب التحقق من أي مثال إضافي بصورة مستقلة."
        )
        safe_heading = "حساب المبلغ وفق بيانات الحالة"
        safe_question = "كيف يُحسب المبلغ المستحق وفق بيانات الحالة؟"
        safe_title = "حساب مكافأة نهاية الخدمة وفق بيانات الحالة"
    else:
        safe_sentence = (
            "Any actual amount must be calculated from the case data under the applicable rules; "
            "any additional example should be checked independently."
        )
        safe_heading = "Calculating the amount from case data"
        safe_question = "How is the applicable benefit calculated from the case data?"
        safe_title = "Calculating end-of-service benefits from case data"

    changed = False

    def contains_unexpected_money(value):
        normalized = _normalize_eosb_digits(re.sub(r"\s+", " ", str(value or "")))
        for match in EOSB_MONEY_CLAIM_RE.finditer(normalized):
            token = next((group for group in match.groups() if group), "")
            try:
                amount = Decimal(token.replace(",", "")).quantize(
                    EOSB_CENT, rounding=ROUND_HALF_UP
                )
            except (InvalidOperation, ValueError):
                return True
            if amount not in allowed:
                return True
        return False

    def repair_text(value, *, role="prose"):
        nonlocal changed
        if not isinstance(value, str) or not value:
            return value
        # Keep blank-line paragraphs independent even when the preceding generated
        # sentence lacks terminal punctuation, so a safe duration line is not dropped
        # with a neighboring unsupported currency claim.
        parts = re.split(r"(?<=[.!?؟])\s+|\n[ \t]*\n+", value)
        repaired = []
        for part in parts:
            if contains_unexpected_money(part):
                if role == "question":
                    replacement = safe_question
                elif role == "heading":
                    replacement = safe_heading
                elif role == "title":
                    replacement = safe_title
                else:
                    replacement = safe_sentence
                repaired.append(replacement)
                changed = True
            else:
                repaired.append(part)
        return " ".join(repaired)

    for key in ("title", "meta_description", "excerpt"):
        if key in fixed:
            fixed[key] = repair_text(
                fixed[key], role="title" if key == "title" else "prose"
            )
    for section in fixed["sections"]:
        if not isinstance(section, dict):
            continue
        if "heading" in section:
            section["heading"] = repair_text(section["heading"], role="heading")
        if "body" in section:
            section["body"] = repair_text(section["body"])
        if isinstance(section.get("bullets"), list):
            section["bullets"] = [repair_text(item) for item in section["bullets"]]
    if isinstance(fixed.get("faq"), list):
        for item in fixed["faq"]:
            if isinstance(item, dict):
                if "q" in item:
                    item["q"] = repair_text(item["q"], role="question")
                if "a" in item:
                    item["a"] = repair_text(item["a"])
    if not changed:
        raise Reject("EOSB money repair: no unexpected currency amount found")
    return fixed


def prepare_eosb_example_deterministically(data, *, topic, lang: str, canonical_example=None):
    """Make the structured EOSB calculator authoritative before any model-repair request.

    This does not relax validation. It corrects only derived benefit fields from the
    topic's chosen wage/service/scenario, ensures the Example section states that same
    duration, removes prose currency claims inconsistent with the validated calculator,
    and re-adds missing calculator figures explicitly. The caller still runs every
    existing validation gate after this deterministic preparation.
    """
    topic_id = topic.get("id", "") if isinstance(topic, dict) else ""
    if topic_id not in EOSB_TOPIC_IDS or topic_id == "labor-art85":
        raise Reject("EOSB deterministic example repair: unsupported topic")
    if not isinstance(data, dict) or not isinstance(data.get("sections"), list):
        raise Reject("EOSB deterministic example repair: invalid article structure")
    fixed = json.loads(json.dumps(data, ensure_ascii=False))
    if canonical_example is not None:
        if (not isinstance(canonical_example, dict)
                or set(canonical_example) != set(EOSB_CALCULATION_FIELDS)
                or any(not isinstance(canonical_example[field], str)
                       or not canonical_example[field].strip()
                       for field in EOSB_CALCULATION_FIELDS)):
            raise Reject("EOSB deterministic example repair: invalid canonical bilingual example")
        # The Arabic version is validated first in a both-language run. Treat its
        # calculator inputs as the shared pair source, then repair/revalidate English
        # prose against those same values instead of accepting independently invented
        # wage/service inputs in each translation.
        fixed["calculation_example"] = {
            field: canonical_example[field].strip()
            for field in EOSB_CALCULATION_FIELDS
        }
    example = fixed.get("calculation_example")
    if not isinstance(example, dict) or set(example) != set(EOSB_CALCULATION_FIELDS):
        raise Reject("EOSB deterministic example repair: calculation fields missing")
    if any(not isinstance(example[field], str) or not example[field].strip()
           for field in EOSB_CALCULATION_FIELDS):
        raise Reject("EOSB deterministic example repair: calculation fields empty")

    actions = []
    if canonical_example is not None:
        actions.append("bilingual calculation example synchronized from Arabic version")
    required_scenario = EOSB_REQUIRED_SCENARIO.get(topic_id)
    current_scenario = example["scenario"].strip().lower()
    scenario = required_scenario or current_scenario
    if scenario not in {"base", "resignation", "article81", "article87"}:
        raise Reject("calculation_example.scenario: قيمة غير مدعومة")
    if scenario != current_scenario:
        example["scenario"] = scenario
        actions.append("topic-specific calculation scenario enforced")

    wage = _parse_eosb_number(example["monthly_wage"], "monthly_wage")
    years = _parse_eosb_number(example["years"], "years")
    months = _parse_eosb_number(example["months"], "months", integer=True)
    days = _parse_eosb_number(example["days"], "days", integer=True)
    if wage <= 0:
        raise Reject("calculation_example.monthly_wage: يجب أن يكون الأجر أكبر من الصفر")
    if years > 80 or months > 11 or days > 30:
        raise Reject("calculation_example: سنوات الخدمة أو الأشهر أو الأيام خارج الحدود المقبولة")
    if years != years.to_integral_value() and (months != 0 or days != 0):
        raise Reject("calculation_example: السنوات الكسرية لا يجوز جمعها مع أشهر أو أيام")

    total_years = years + months / Decimal(12) + days / Decimal(365)
    first_five = min(total_years, Decimal(5))
    after_five = max(Decimal(0), total_years - Decimal(5))
    full_raw = wage * first_five / Decimal(2) + wage * after_five
    expected_full = full_raw.quantize(EOSB_CENT, rounding=ROUND_HALF_UP)
    if scenario == "resignation":
        if total_years < Decimal(2):
            ratio = Decimal(0)
        elif total_years <= Decimal(5):
            ratio = Decimal(1) / Decimal(3)
        elif total_years < Decimal(10):
            ratio = Decimal(2) / Decimal(3)
        else:
            ratio = Decimal(1)
    else:
        ratio = Decimal(1)
    expected_payable = (full_raw * ratio).quantize(EOSB_CENT, rounding=ROUND_HALF_UP)

    if _parse_eosb_number(example["full_benefit"], "full_benefit") != expected_full:
        example["full_benefit"] = format(expected_full, "f")
        actions.append("calculator-derived full benefit corrected")
    if _parse_eosb_number(example["payable_benefit"], "payable_benefit") != expected_payable:
        example["payable_benefit"] = format(expected_payable, "f")
        actions.append("calculator-derived payable benefit corrected")

    years_text = format(years.normalize(), "f")
    months_int, days_int = int(months), int(days)
    if lang == "ar":
        duration_parts = []
        if years:
            duration_parts.append(f"{years_text} " + ("سنة" if years == 1 else "سنتان" if years == 2 else "سنوات"))
        if months_int:
            duration_parts.append(f"{months_int} " + ("شهر" if months_int == 1 else "شهران" if months_int == 2 else "أشهر"))
        if days_int:
            duration_parts.append(f"{days_int} " + ("يوم" if days_int == 1 else "يومان" if days_int == 2 else "أيام"))
        duration_phrase = " و".join(duration_parts) if duration_parts else "0 يوم"
        service_sentence = f"مدة الخدمة هي {duration_phrase}."
    else:
        duration_parts = []
        if years:
            duration_parts.append(f"{years_text} " + ("year" if years == 1 else "years"))
        if months_int:
            duration_parts.append(f"{months_int} " + ("month" if months_int == 1 else "months"))
        if days_int:
            duration_parts.append(f"{days_int} " + ("day" if days_int == 1 else "days"))
        if len(duration_parts) > 1:
            duration_phrase = ", ".join(duration_parts[:-1]) + " and " + duration_parts[-1]
        else:
            duration_phrase = duration_parts[0] if duration_parts else "0 days"
        service_sentence = f"The example assumes {duration_phrase} of service."

    example_sections = [
        section for section in fixed["sections"]
        if isinstance(section, dict)
        and re.search(r"(?:مثال|example)", str(section.get("heading", "")), re.IGNORECASE)
    ]
    if not example_sections:
        raise Reject("المثال الحسابي يجب أن يظهر داخل قسم عنوانه يتضمن مثالاً / Example")

    def duration_claims(text):
        return _extract_eosb_service_durations(str(text or ""))

    def repair_duration_text(value):
        # Paragraph breaks are boundaries too; generated text may omit punctuation
        # immediately before the deterministic service-duration paragraph.
        pieces = re.split(r"(?<=[.!?؟])\s+|\n[ \t]*\n+", str(value or ""))
        output = []
        changed = False
        for piece in pieces:
            claims = duration_claims(piece)
            if claims and any(claim != total_years for claim in claims):
                output.append(service_sentence)
                changed = True
            else:
                output.append(piece)
        return " ".join(output), changed

    changed_duration = False
    for section in example_sections:
        if isinstance(section.get("body"), str):
            section["body"], changed = repair_duration_text(section["body"])
            changed_duration = changed_duration or changed
        if isinstance(section.get("bullets"), list):
            bullets = []
            for bullet in section["bullets"]:
                if isinstance(bullet, str):
                    bullet, changed = repair_duration_text(bullet)
                    changed_duration = changed_duration or changed
                bullets.append(bullet)
            section["bullets"] = bullets

    example_text = " ".join(
        str(section.get("body", "")) + " " + " ".join(
            item for item in section.get("bullets", []) if isinstance(item, str)
        )
        for section in example_sections
    )
    claims = duration_claims(example_text)
    if not any(claim == total_years for claim in claims):
        section = example_sections[0]
        section["body"] = str(section.get("body", "")).rstrip() + "\n\n" + service_sentence
        changed_duration = True
    if changed_duration:
        actions.append("example service duration made explicit and consistent")

    if topic_id == "eosb-full-entitlement" and scenario == "article87":
        example_text = " ".join(
            str(section.get("body", "")) + " " + " ".join(
                item for item in section.get("bullets", []) if isinstance(item, str)
            )
            for section in example_sections
        )
        if not _article87_qualifying_basis(example_text):
            if lang == "ar":
                scenario_sentence = (
                    "افتراض المثال وفق المادة 87: ترك العامل العمل بسبب قوة قاهرة خارجة عن إرادته، "
                    "وليس استقالة عادية تخضع لنسب المادة 85."
                )
            else:
                scenario_sentence = (
                    "Article 87 assumption: the worker leaves work due to force majeure beyond their control, "
                    "not an ordinary resignation under Article 85."
                )
            example_sections[0]["body"] = (
                str(example_sections[0].get("body", "")).rstrip() + "\n\n" + scenario_sentence
            )
            actions.append("Article 87 qualifying scenario made explicit")

    # The same gate used by validate_eosb_calculation_example disallows unsupported
    # currency figures anywhere in article prose; remove those sentences, not the
    # calculator data, then ensure all authoritative amounts appear with a currency.
    normalized_article_text = " ".join([
        str(fixed.get("title", "")),
        str(fixed.get("meta_description", "")),
        str(fixed.get("excerpt", "")),
        *[
            str(section.get("body", "")) + " " + " ".join(
                item for item in section.get("bullets", []) if isinstance(item, str)
            )
            for section in fixed["sections"] if isinstance(section, dict)
        ],
        *[
            str(item.get("q", "")) + " " + str(item.get("a", ""))
            for item in fixed.get("faq", []) if isinstance(item, dict)
        ],
    ])
    allowed_amounts = {
        wage.quantize(EOSB_CENT, rounding=ROUND_HALF_UP),
        expected_full,
        expected_payable,
    }
    claims_in_text = set()
    normalized_article_text = _normalize_eosb_digits(normalized_article_text)
    for match in EOSB_MONEY_CLAIM_RE.finditer(normalized_article_text):
        token = next((group for group in match.groups() if group), "")
        if token:
            try:
                claims_in_text.add(Decimal(token.replace(",", "")).quantize(
                    EOSB_CENT, rounding=ROUND_HALF_UP
                ))
            except InvalidOperation:
                raise Reject("المثال الرقمي: تعذّر تحليل مبلغ مذكور بجانب العملة")
    if claims_in_text - allowed_amounts:
        fixed = repair_eosb_unexpected_money_claims(fixed, lang=lang)
        # The money repair deep-copies the article, so refresh section references before
        # appending any missing authoritative figures.
        example_sections = [
            section for section in fixed["sections"]
            if isinstance(section, dict)
            and re.search(r"(?:مثال|example)", str(section.get("heading", "")), re.IGNORECASE)
        ]
        actions.append("unsupported currency claims removed from prose")

    # Re-check after sanitizing; if one of the authoritative amounts is not named
    # with a currency anywhere, add one compact, code-generated line to the Example.
    normalized_article_text = " ".join([
        str(fixed.get("title", "")),
        str(fixed.get("meta_description", "")),
        str(fixed.get("excerpt", "")),
        *[
            str(section.get("body", "")) + " " + " ".join(
                item for item in section.get("bullets", []) if isinstance(item, str)
            )
            for section in fixed["sections"] if isinstance(section, dict)
        ],
        *[
            str(item.get("q", "")) + " " + str(item.get("a", ""))
            for item in fixed.get("faq", []) if isinstance(item, dict)
        ],
    ])
    claims_in_text = set()
    normalized_article_text = _normalize_eosb_digits(normalized_article_text)
    for match in EOSB_MONEY_CLAIM_RE.finditer(normalized_article_text):
        token = next((group for group in match.groups() if group), "")
        if token:
            try:
                claims_in_text.add(Decimal(token.replace(",", "")).quantize(
                    EOSB_CENT, rounding=ROUND_HALF_UP
                ))
            except InvalidOperation:
                raise Reject("المثال الرقمي: تعذّر تحليل مبلغ مذكور بجانب العملة")
    if not allowed_amounts.issubset(claims_in_text):
        wage_txt = format(wage.quantize(EOSB_CENT, rounding=ROUND_HALF_UP), ",.2f")
        full_txt = format(expected_full, ",.2f")
        payable_txt = format(expected_payable, ",.2f")
        if lang == "ar":
            amounts_sentence = (
                f"الأرقام التوضيحية: الأجر الشهري {wage_txt} ريال، "
                f"والمكافأة الأساسية {full_txt} ريال، والمبلغ المستحق {payable_txt} ريال."
            )
        else:
            amounts_sentence = (
                f"Illustrative figures: monthly wage SAR {wage_txt}, "
                f"full base benefit SAR {full_txt}, and payable benefit SAR {payable_txt}."
            )
        example_sections[0]["body"] = str(example_sections[0].get("body", "")).rstrip() + "\n\n" + amounts_sentence
        actions.append("authoritative currency figures made explicit")

    # Reassert the service-duration invariant after all currency cleanup. The cleanup
    # above works on a deep copy and may rewrite a whole sentence/paragraph; a generated
    # paragraph without terminal punctuation must never erase the calculator-aligned
    # service duration. Keep this as a fail-closed gate rather than relaxing validation.
    example_sections = [
        section for section in fixed["sections"]
        if isinstance(section, dict)
        and re.search(r"(?:مثال|example)", str(section.get("heading", "")), re.IGNORECASE)
    ]
    if not example_sections:
        raise Reject("EOSB deterministic example repair: worked-example section missing after cleanup")

    def final_example_text():
        return " ".join(
            str(section.get("body", "")) + " " + " ".join(
                item for item in section.get("bullets", []) if isinstance(item, str)
            )
            for section in example_sections
        )

    final_claims = duration_claims(final_example_text())
    if any(claim != total_years for claim in final_claims):
        for section in example_sections:
            if isinstance(section.get("body"), str):
                section["body"], _ = repair_duration_text(section["body"])
            if isinstance(section.get("bullets"), list):
                section["bullets"] = [
                    repair_duration_text(item)[0] if isinstance(item, str) else item
                    for item in section["bullets"]
                ]
        final_claims = duration_claims(final_example_text())

    if not any(claim == total_years for claim in final_claims):
        example_sections[0]["body"] = (
            str(example_sections[0].get("body", "")).rstrip() + "\n\n" + service_sentence
        )
        final_claims = duration_claims(final_example_text())
        actions.append("post-sanitization service duration enforced")

    if not final_claims or any(claim != total_years for claim in final_claims):
        raise Reject("EOSB deterministic example repair: service duration invariant could not be enforced")

    # Currency sanitization can remove an entire sentence that contains both an
    # unsupported amount and the only qualifying Article 87 circumstance. Reassert
    # that legal basis after all prose cleanup, then let the normal validator reject
    # any remaining contradictory ordinary-resignation claim.
    if topic_id == "eosb-full-entitlement" and scenario == "article87":
        cleaned_example_text = final_example_text()
        if not _article87_qualifying_basis(cleaned_example_text):
            if _article87_ordinary_resignation_claim(cleaned_example_text, lang=lang):
                raise Reject(
                    "EOSB deterministic example repair: Article 87 prose conflicts with ordinary resignation"
                )
            if lang == "ar":
                scenario_sentence = (
                    "افتراض المادة 87 في هذا المثال: يترك العامل العمل بسبب قوة قاهرة خارجة عن إرادته، "
                    "وهي حالة استثنائية وليست استقالة عادية."
                )
            else:
                scenario_sentence = (
                    "Article 87 assumption for this example: the worker leaves work due to force majeure "
                    "beyond their control; this is an exceptional circumstance, not an ordinary resignation."
                )
            example_sections[0]["body"] = (
                str(example_sections[0].get("body", "")).rstrip() + "\n\n" + scenario_sentence
            )
            actions.append("Article 87 qualifying scenario reasserted after currency cleanup")

    return fixed, actions


def repair_article85_deterministic_omissions(data, *, topic, lang: str, published_at: str):
    """Apply only known deterministic Article 85 fixes sequentially, validating after each one."""
    working = json.loads(json.dumps(data, ensure_ascii=False))
    actions = []

    # Several independent deterministic omissions may coexist in one generated article.
    # Keep the process strictly bounded and stop immediately when a repair cannot be made safely.
    for _ in range(MAX_SECTIONS + 4):
        try:
            article = validate_article(
                working, topic=topic, lang=lang, published_at=published_at,
                require_canonical_article85=True,
            )
            return working, article, actions, ""
        except Reject as exc:
            reason = str(exc)
            try:
                section_count = re.fullmatch(r"sections: العدد (\d+) خارج المدى \d+-\d+", reason)
                if section_count and MAX_SECTIONS < int(section_count.group(1)) <= MAX_SECTIONS + 4:
                    updated = merge_article85_sections(working, target_count=MAX_SECTIONS)
                    action = "excess sections merged with full text preserved"
                elif re.fullmatch(r"sections\[\d+\]\.body: فارغ", reason):
                    updated, action = repair_empty_article85_section(working, reason=reason, lang=lang)
                elif re.fullmatch(r"sections\[\d+\]\.body: الطول \d+ خارج المدى 120-8000", reason):
                    updated, action = repair_short_article85_section(working, reason=reason, lang=lang)
                elif reason.startswith((
                    "المادة 85: لا تنسب فقدان المكافأة أو خفضها تلقائيًا",
                    "Article 85: do not claim notice non-compliance automatically reduces or forfeits",
                    "المادة 85: لا تربط أثر الإشعار على المكافأة باستثناء تعاقدي أو قضائي غير موثق",
                    "Article 85: do not add an unsupported contract/court exception to notice-related EOSB effects",
                )):
                    updated = repair_article85_notice_loss_claim(working, lang=lang)
                    action = "notice loss claim"
                elif reason.startswith((
                    "المادة 85: لا تنسب مدة الإشعار أو الإعفاء منه إلى المادة 85",
                    "Article 85: do not attribute notice-period rules or a notice waiver to Article 85",
                )):
                    updated = repair_article85_notice_attribution_claim(working, lang=lang)
                    action = "notice authority claim"
                elif reason.startswith((
                    "المثال الرقمي في النص يتضمن مبلغاً لا يطابق بيانات الحساب",
                    "المثال الرقمي: تعذّر تحليل مبلغ مذكور بجانب العملة",
                )):
                    updated = repair_article85_unexpected_money_claims(working, lang=lang)
                    action = "unexpected currency amount removed"
                elif reason.startswith((
                    "المثال الرقمي في النص يجب أن يذكر الأجر والمكافأة الأساسية والمبلغ المستحق",
                    "calculation_example: موضوع المادة 85 يتطلب المثال الثابت",
                )):
                    updated, canonical_actions = ensure_article85_critical_content(working, lang=lang)
                    action = "canonical example restored"
                elif reason.startswith((
                    "المادة 85: لا تصف مدة استحقاق مكافأة الاستقالة بأنها بلا حد أدنى",
                    "Article 85: FAQ about minimum service cannot say there is no minimum",
                    "Article 85: contradictory minimum-service FAQ",
                )):
                    updated, faq_repaired = ensure_article85_minimum_faq(working, lang=lang)
                    if not faq_repaired:
                        return working, None, actions, reason
                    action = "minimum-service FAQ corrected"
                elif reason.startswith((
                    "المادة 85: وضّح أن عدم اشتراط الإشعار لاستحقاق المكافأة",
                    "Article 85: distinguish EOSB eligibility from notice/resignation requirements",
                )):
                    updated = ensure_article85_notice_caveat(working, lang=lang)
                    action = "notice caveat"
                elif reason.startswith((
                    "المادة 86:", "Article 86:",
                )):
                    updated = ensure_article85_article86_clause(working, lang=lang)
                    action = "Article 86 legal clause"
                elif reason.startswith((
                    "المادة 85: يجب توضيح أن الثلثين يبدأان",
                    "Article 85: clarify that two-thirds applies only after five years and before ten years",
                )):
                    updated = ensure_article85_boundary_caveat(working, lang=lang)
                    action = "two-thirds boundary"
                else:
                    excerpt_match = re.fullmatch(r"excerpt: الطول (\d+) خارج المدى 40-300", reason)
                    if excerpt_match and 301 <= int(excerpt_match.group(1)) <= 360:
                        updated = trim_article85_excerpt(working, max_chars=300)
                        action = "excerpt length"
                    else:
                        return working, None, actions, reason
            except Reject as repair_exc:
                return working, None, actions, str(repair_exc)

            before = json.dumps(working, ensure_ascii=False, sort_keys=True)
            after = json.dumps(updated, ensure_ascii=False, sort_keys=True)
            if before == after:
                return working, None, actions, reason
            working = updated
            actions.append(action)

    try:
        article = validate_article(
            working, topic=topic, lang=lang, published_at=published_at,
            require_canonical_article85=True,
        )
        return working, article, actions, ""
    except Reject as exc:
        return working, None, actions, str(exc)


def is_groq_incomplete_schema_failure(message: str) -> bool:
    """True only for Groq's explicit missing-required-properties schema failure."""
    value = str(message or "").lower()
    return "schema_missing_required" in value or (
        "schema_incomplete" in value and "http_400" in value
    )


def build_groq_schema_repair_prompt(base_prompt: str, *, lang: str) -> str:
    """One-shot schema reminder for Groq; response_format remains json_schema/strict=true."""
    if lang == "ar":
        reminder = (
            "تذكير تصحيحي للمخطط بعد رفض الاستجابة السابقة: أعد كائن JSON كاملاً يتضمن كل المفاتيح المطلوبة "
            "مرة واحدة بالضبط: title وmeta_description وexcerpt وsections وfaq وofficial_sources وcalculation_example. "
            "لا تحذف faq أو official_sources أو calculation_example مطلقاً. "
            "في calculation_example أدرج جميع المفاتيح السبعة: monthly_wage وyears وmonths وdays وscenario وfull_benefit وpayable_benefit. "
            "اتبع القواعد والبيانات الخاصة بالموضوع كما وردت في البرومبت الأصلي؛ لا تنقل أرقاماً أو قواعد من موضوع آخر. التزم بمخطط JSON الصارم نفسه؛ لا تغيّر صيغة الإخراج ولا تستخدم JSON mode."
        )
    else:
        reminder = (
            "Schema correction after the prior response was rejected: return one complete JSON object containing every required top-level key "
            "exactly once: title, meta_description, excerpt, sections, faq, official_sources, and calculation_example. "
            "Never omit faq, official_sources, or calculation_example. "
            "calculation_example must contain all seven keys: monthly_wage, years, months, days, scenario, full_benefit, and payable_benefit. "
            "Follow the topic-specific rules and calculation data from the original prompt; do not import figures or rules from another topic. Keep the same strict JSON Schema response format; do not switch to JSON mode."
        )
    return base_prompt + "\n\n" + reminder + "\n"


def build_article85_repair_prompt(base_prompt: str, *, lang: str, reason: str) -> str:
    """Add one compact, declarative correction after a known Article 85/86/81 or section-length rejection."""
    reason_text = str(reason or "")
    is_empty_section = bool(re.fullmatch(r"sections\[\d+\]\.body: فارغ", reason_text))
    is_short_section = bool(re.search(
        r"sections\[\d+\]\.body: الطول \d+ خارج المدى 120-8000", reason_text
    ))
    section_count_match = re.fullmatch(r"sections: العدد (\d+) خارج المدى \d+-\d+", reason_text)
    is_sections_count = bool(
        section_count_match and MAX_SECTIONS < int(section_count_match.group(1)) <= MAX_SECTIONS + 4
    )
    is_notice = bool(re.search(r"(?:notice|الإشعار|اشعار|إشعار)", reason_text, re.IGNORECASE))
    is_notice_loss = bool(
        re.search(r"(?:notice|الإشعار|اشعار|إشعار)", reason_text, re.IGNORECASE)
        and re.search(r"(?:loss|forfeit|reduc|deduct|فقدان|خسارة|حرمان|خصم|حسم|خفض|المكافأة)", reason_text, re.IGNORECASE)
    )
    is_minimum_conflict = bool(
        re.search(r"(?:minimum|حد أدنى|الحد الأدنى)", reason_text, re.IGNORECASE)
    )
    is_money_mismatch = bool(re.search(
        r"(?:المثال الرقمي في النص يتضمن مبلغاً لا يطابق بيانات الحساب|"
        r"المثال الرقمي في النص يجب أن يذكر الأجر والمكافأة الأساسية|"
        r"موضوع المادة 85 يتطلب المثال الثابت)", reason_text
    ))
    is_article86 = bool(re.search(r"(?:article\s*86|المادة\s*86|commission|العمولات|المبيعات)", reason_text, re.IGNORECASE))
    is_article81 = bool(re.search(r"(?:article\s*81|المادة\s*81)", reason_text, re.IGNORECASE))

    if lang == "ar":
        if is_empty_section:
            clause = (
                "لا تترك body فارغاً في أي قسم. يجب أن يتراوح نص body في كل قسم بين 120 و5000 حرف. "
                "إذا احتوى القسم على bullets مفيدة، فحافظ على مضمونها داخل فقرة مناسبة؛ وإذا لم يكن له محتوى، فادمج موضوعه في قسم مجاور أو أزل العنوان الفارغ مع الحفاظ على جميع المعلومات القانونية والحسابية المهمة، "
                "مع بقاء عدد الأقسام بين 3 و12."
            )
        elif is_money_mismatch:
            clause = (
                "صحّح المثال الرقمي فقط مع إبقاء الحقول المنظمة ثابتة تمامًا: الأجر الشهري 12,000 ريال، "
                "مدة الخدمة 6 سنوات، المكافأة الأساسية 42,000 ريال، والمبلغ المستحق بعد نسبة الاستقالة 28,000 ريال. "
                "لا تذكر مبلغًا نقديًا آخر ولا تضع رقمًا بديلًا أو تقريبًا، ولا تغيّر الأجر أو مدة الخدمة أو السيناريو. "
                "يجب أن يتطابق نص المثال حرفيًا في المعنى مع calculation_example وأن تجتاز جميع بوابات الحساب مجددًا."
            )
        elif is_sections_count:
            clause = (
                "يجب أن يحتوي sections على 3 إلى 12 قسمًا فقط. أعد تنظيم المحتوى بدمج الأقسام المتقاربة موضوعيًا عند الحاجة، "
                "ولا تحذف أي قاعدة قانونية أساسية أو المثال الحسابي أو التحذيرات. اجعل كل body بطول صالح وأعد كائن JSON كاملًا مطابقًا للمخطط."
            )
        elif is_notice_loss:
            clause = (
                "لا تقل إن عدم الالتزام بمهلة الإشعار يؤدي تلقائيًا إلى فقدان جزء من مكافأة نهاية الخدمة. "
                "افصل بين نسبة مكافأة الاستقالة وفق المادة 85 وأي مسؤولية مستقلة عن مهلة الإشعار قد تنطبق بحسب نوع العقد والوقائع والنظام؛ "
                "ولا تجزم بأثر مالي دون سند رسمي محدد."
            )
        elif is_minimum_conflict:
            clause = (
                "في سياق مكافأة الاستقالة وفق المادة 85، لا تقل إنه لا يوجد حد أدنى للخدمة: لا يستحق العامل مكافأة الاستقالة قبل سنتين متتاليتين؛ "
                "من سنتين إلى خمس سنوات شاملًا خمس سنوات يستحق الثلث، وبعد خمس سنوات وقبل عشر سنوات يستحق الثلثين، وعشر سنوات فأكثر تستحق المكافأة كاملة. "
                "لا تعمم نسب الاستقالة على جميع حالات انتهاء علاقة العمل."
            )
        elif is_short_section:
            clause = (
                "يجب أن يتراوح نص body في كل قسم بين 120 و5000 حرف. وسّع أي قسم قصير بمعلومات مفيدة ودقيقة مرتبطة بعنوانه، "
                "ولا تحذف معلومات أو تنسخ تعليمات التحرير إلى المقال."
            )
        elif is_notice:
            clause = (
                "المادة 85 تحدد نسب المكافأة عند الاستقالة فقط، ولا تحدد مدة إشعار العقد ولا تعفي من متطلباته؛ "
                "وقد تبقى متطلبات الإشعار وإجراءات الاستقالة واجبة بحسب نوع العقد والأحكام النظامية المنطبقة."
            )
        elif is_article86:
            clause = (
                "وفق المادة 86، يجوز بالاتفاق الصريح استبعاد العمولات ونسب المبيعات والعناصر المشابهة "
                "إذا كانت بطبيعتها قابلة للزيادة والنقص؛ ولا يعني ذلك استبعاد الأجر الأساسي."
            )
        elif is_article81:
            clause = (
                "المادة 81 تتعلق بحالات نظامية يترك فيها العامل العمل دون إشعار مع احتفاظه بحقوقه النظامية؛ "
                "وليست فصلاً من صاحب العمل ولا تُعامل كاستقالة عادية."
            )
        else:
            clause = (
                "ثلث المكافأة يكون من سنتين إلى خمس سنوات شاملًا خمس سنوات، والثلثان فقط إذا زادت الخدمة على خمس سنوات ولم تبلغ عشرًا."
            )
        instructions = (
            "أعد إنشاء كائن JSON كاملاً وفق المخطط الأصلي. صحح المسألة المحددة فقط، "
            "ولا تنسخ هذه التعليمات أو وصف الخطأ إلى نص المقال. أدرج التصحيح التالي بوضوح موجّه للقارئ، "
            "مع إبقاء جميع بوابات التحقق كما هي:\n"
        )
    else:
        if is_empty_section:
            clause = (
                "Do not leave any section body empty. Every body must contain 120 to 5000 characters. "
                "Preserve useful bullet content by moving it into a suitable neighboring paragraph; if a section has no content, merge its topic into a neighboring section or remove only the empty heading while preserving all substantive legal and calculation information. "
                "Keep the section count between 3 and 12."
            )
        elif is_money_mismatch:
            clause = (
                "Correct only the worked example and keep the structured values fixed: monthly wage SAR 12,000, "
                "six years of service, full base benefit SAR 42,000, and payable benefit after the resignation ratio SAR 28,000. "
                "Do not include any other currency amount, alternative figure, or approximation; do not change the wage, service duration, or scenario. "
                "Make the prose agree with calculation_example and retain all calculation validation gates."
            )
        elif is_sections_count:
            clause = (
                "The schema permits only 3 to 12 sections. Reorganize by merging closely related sections where needed; "
                "preserve every material legal rule, the worked calculation, and the caveats. Do not silently omit substantive content. "
                "Keep every section body within the valid length bounds and return the complete JSON object under the original schema."
            )
        elif is_notice_loss:
            clause = (
                "Do not claim that failure to comply with notice requirements automatically forfeits or reduces part of the end-of-service award. "
                "Keep the Article 85 resignation-benefit ratio separate from any distinct notice-period liability that may apply under the contract and law; "
                "do not assert a financial consequence without a specific official legal basis."
            )
        elif is_minimum_conflict:
            clause = (
                "For resignation under Article 85, do not say there is no minimum service period: no resignation award is due before two consecutive years; "
                "one third applies from two through five years inclusive, two thirds applies above five but below ten years, and the full award applies at ten years or more. "
                "Do not generalize these resignation ratios to every kind of employment termination."
            )
        elif is_short_section:
            clause = (
                "Every section body must contain 120 to 5000 characters. Expand any short section with useful, accurate detail relevant to its heading; "
                "do not delete information or copy editing instructions into the article."
            )
        elif is_notice:
            clause = (
                "Article 85 sets the resignation benefit ratio only; it does not set or waive contract notice requirements. "
                "Applicable notice requirements and resignation procedures may still apply depending on the contract and law."
            )
        elif is_article86:
            clause = (
                "Under Article 86, qualifying commissions, sales percentages and similar wage elements naturally subject to increase or decrease "
                "may be excluded from the calculation only by explicit agreement; this does not exclude basic wage."
            )
        elif is_article81:
            clause = (
                "Article 81 concerns statutory cases where a worker leaves without notice while retaining statutory rights; "
                "it is not an employer dismissal or ordinary resignation."
            )
        else:
            clause = (
                "One third applies from two years through five years inclusive; two thirds applies only above five years and below ten years."
            )
        instructions = (
            "Regenerate the complete JSON object under the original strict schema. Correct only the identified issue; "
            "do not copy these instructions or the rejection text into the article. Insert the following clear, declarative reader-facing correction "
            "and retain all existing validation gates:\n"
        )
    return base_prompt + "\n\n" + instructions + clause + "\n"


def build_quality_repair_prompt(base_prompt: str, *, lang: str, reason: str) -> str:
    """Create a single bounded repair instruction without borrowing Article 85-only example values."""
    value = str(reason or "")
    empty_section = bool(re.fullmatch(r"sections\[\d+\]\.body: فارغ", value))
    short_section = bool(re.search(
        r"sections\[\d+\]\.body: الطول \d+ خارج المدى 120-8000", value
    ))
    section_count = re.fullmatch(r"sections: العدد (\d+) خارج المدى \d+-\d+", value)
    is_section_overflow = bool(
        section_count and MAX_SECTIONS < int(section_count.group(1)) <= MAX_SECTIONS + 4
    )
    is_excerpt_overflow = bool(re.fullmatch(r"excerpt: الطول \d+ خارج المدى 40-300", value))
    scenario_mismatch = value.startswith("calculation_example.scenario: نص المثال")
    calculation_mismatch = value.startswith((
        "calculation_example.full_benefit: المتوقع ",
        "calculation_example.payable_benefit: المتوقع ",
        "مدة الخدمة بالنص (",
        "المثال الرقمي في النص يتضمن مبلغاً لا يطابق بيانات الحساب",
        "المثال الرقمي في النص يجب أن يذكر الأجر والمكافأة الأساسية والمبلغ المستحق",
        "المثال الرقمي: تعذّر تحليل مبلغ مذكور بجانب العملة",
        "calculation_example: عند استخدام سنوات كسرية",
        "calculation_example: سنوات الخدمة أو الأشهر أو الأيام خارج الحدود المقبولة",
    ))

    if lang == "ar":
        if empty_section:
            correction = (
                "يوجد قسم ذو body فارغ. أصلح القسم بإضافة شرح فعلي ودقيق مرتبط بعنوانه، "
                "أو ادمج مضمونه في قسم مجاور ثم أزل العنوان الفارغ، مع الحفاظ على جميع المعلومات القانونية "
                "والحسابية والنقاط المفيدة. يجب أن يكون كل body غير فارغ وبطول صالح، وأعد JSON كاملاً."
            )
        elif short_section:
            correction = (
                "وسّع القسم القصير بمعلومات مفيدة ودقيقة ذات صلة بعنوانه حتى يقع body ضمن الطول المسموح. "
                "لا تكرر الحشو ولا تحذف قواعد أو تحذيرات مهمة، وأعد JSON كاملاً."
            )
        elif is_section_overflow:
            correction = (
                "عدد الأقسام يتجاوز الحد المسموح بقليل. ادمج الأقسام المتقاربة مع حفظ كل النصوص والنقاط "
                "والقواعد الجوهرية، واجعل العدد ضمن الحد المسموح دون إسقاط محتوى مهم، وأعد JSON كاملاً."
            )
        elif is_excerpt_overflow:
            correction = (
                "اختصر excerpt فقط ليقع ضمن 40 إلى 300 حرف مع الحفاظ على المعنى الأساسي، ثم أعد JSON كاملاً."
            )
        elif scenario_mismatch:
            correction = (
                "اجعل شرح المثال الحسابي متوافقاً مع سيناريو المادة 87 المحدد في البيانات: اذكر بوضوح أن العامل ترك "
                "العمل بسبب قوة قاهرة خارجة عن إرادته، أو اشرح إحدى حالتي العاملة ضمن المدد النظامية الواردة في المادة 87. "
                "لا تصف المثال نفسه بأنه استقالة عادية ولا تخلط بين نسب المادة 85 واستثناء المادة 87. حافظ على الأجر "
                "ومدة الخدمة والأرقام التي يعتمدها المدقق الحتمي، وأعد JSON كاملاً."
            )
        elif calculation_mismatch:
            correction = (
                "أعد حساب المثال من حقول calculation_example المنظمة ومن القواعد الحسابية الواردة في الطلب الأصلي. "
                "صحح الحقل الرقمي غير المطابق، واجعل المثال المكتوب والعناوين والملخص والأسئلة المتكررة متسقة مع النتيجة "
                "المعاد حسابها. لا تستخدم أرقاماً ثابتة من موضوع آخر، ولا تخمّن أو تقرّب نتيجة تخالف الحساب، ولا تغيّر "
                "الأجر أو مدة الخدمة أو السيناريو إلا إذا كان هناك خطأ مثبت فيها. أعد JSON كاملاً."
            )
        else:
            correction = "صحح سبب الرفض المحدد فقط مع الحفاظ على صحة المحتوى، ثم أعد JSON كاملاً."
        instructions = (
            "محاولة إصلاح واحدة محدودة بعد رفض بوابة الجودة. لا تنسخ رسالة الخطأ أو هذه التعليمات داخل المقال. "
            "حافظ على جميع القواعد القانونية والمعلومات والمصادر المفيدة، ولا تتجاوز أي بوابة تحقق:\n"
        )
    else:
        if empty_section:
            correction = (
                "A section body is empty. Repair it by adding accurate, useful prose relevant to its heading, "
                "or merge its substance into a neighboring section and then remove the empty heading. Preserve all "
                "material legal rules, calculation details, and useful bullets. Every body must be non-empty and valid "
                "in length. Return the complete JSON object."
            )
        elif short_section:
            correction = (
                "Expand the short section with accurate, useful information relevant to its heading until its body "
                "is within the allowed length. Do not pad with repetition or remove important rules or caveats. "
                "Return the complete JSON object."
            )
        elif is_section_overflow:
            correction = (
                "The section count exceeds the permitted limit by a small amount. Merge closely related sections "
                "while preserving their prose, bullets, substantive legal rules, and caveats. Keep the count within "
                "the allowed range without discarding material content. Return the complete JSON object."
            )
        elif is_excerpt_overflow:
            correction = (
                "Shorten only the excerpt to 40–300 characters while preserving its core meaning, then return the complete JSON object."
            )
        elif scenario_mismatch:
            correction = (
                "Align the worked-example prose with the structured Article 87 scenario: explicitly state that the worker left "
                "work due to force majeure beyond their control, or explain one of the statutory female-worker cases within "
                "the relevant marriage or childbirth period. Do not describe this same example as ordinary resignation or mix "
                "Article 85 resignation ratios with the Article 87 exception. Preserve the wage, service duration, and amounts "
                "controlled by the deterministic calculator. Return the complete JSON object."
            )
        elif calculation_mismatch:
            correction = (
                "Recalculate the worked example from the structured calculation_example fields and the rules in the original prompt. "
                "Correct the mismatched numeric field, and make the worked-example prose, title, summary, and FAQs consistent with "
                "the recalculated result. Do not borrow fixed figures from another topic, guess, or round to a value that fails the "
                "calculation. Do not change the wage, service duration, or scenario unless it is itself demonstrably invalid. "
                "Return the complete JSON object."
            )
        else:
            correction = "Correct only the identified rejection while preserving content validity, then return the complete JSON object."
        instructions = (
            "One bounded repair attempt after a quality-gate rejection. Do not copy the error message or these instructions into the article. "
            "Preserve all material legal rules, useful information, and sources, and do not bypass any validation gate:\n"
        )
    return base_prompt + "\n\n" + instructions + correction + "\n"


def validate_article85_legal_claims(article_text: str, *, lang: str) -> None:
    """Reject material wording errors in generated Article 85 articles before any draft is saved."""
    text_norm = re.sub(r"\s+", " ", str(article_text or "")).strip().lower()

    # A notice-period issue must not be presented as an automatic loss/reduction
    # of the end-of-service award. Keep this detector sentence-scoped and allow
    # explicit negation so a correct disclaimer is not rejected.
    sentences = re.split(r"(?<=[.!?؟])\s+", text_norm)
    if lang == "en":
        for sentence in sentences:
            loss_claim = re.search(
                r"\b(?:may|can|could|might|will|would)\s+(?:(?:automatically|directly)\s+)?"
                r"(?:lead to|result in|cause)\b.{0,100}\b(?:loss|forfeit(?:ure)?|deduct(?:ion)?|reduction|withholding)\b"
                r".{0,100}\b(?:eosb|end[- ]of[- ]service|indemnity|severance|award|benefit)\b",
                sentence,
            )
            negated = bool(re.search(
                r"\b(?:does not|doesn't|cannot|can't|will not|won't|would not|wouldn't)\s+"
                r"(?:(?:automatically|directly)\s+)?(?:lead to|result in|cause)\b",
                sentence,
            ))
            unsupported_notice_exception = bool(re.search(
                r"(?:failure to (?:give|comply with)|non-compliance with|breach of).{0,80}\bnotice(?: period)?\b"
                r".{0,160}\b(?:does not|doesn't|will not|won't)\s+(?:automatically\s+)?"
                r"(?:lead to|result in|cause|reduce|forfeit|deduct).{0,120}\b"
                r"(?:eosb|end[- ]of[- ]service|award|benefit|loss|reduction)\b"
                r".{0,100}\b(?:unless|except when|except if)\b.{0,100}\b"
                r"(?:contract|clause|court|judgment|ruling)\b",
                sentence,
            ))
            if unsupported_notice_exception:
                raise Reject(
                    "Article 85: do not add an unsupported contract/court exception to notice-related EOSB effects"
                )
            if loss_claim and not negated:
                raise Reject(
                    "Article 85: do not claim notice non-compliance automatically reduces or forfeits the EOSB award"
                )
    else:
        for sentence in sentences:
            loss_claim = re.search(
                r"(?:قد\s+)?(?:يؤدي|يترتب|يتسبب|يسبب|ينتج)\s*(?:إلى|الى|في|عن)?\s*"
                r".{0,50}(?:فقدان|خسارة|حرمان|خصم|حسم|تقليل|خفض).{0,80}(?:المكافأة|مكافأة نهاية الخدمة)",
                sentence,
            )
            negated = bool(re.search(
                r"(?:قد\s+)?(?:لا|ليس|لم|لن)\s*(?:يؤدي|يترتب|يتسبب|يسبب|ينتج)",
                sentence,
            ))
            unsupported_notice_exception = bool(
                re.search(r"(?:عدم الالتزام|مخالفة|الإخلال).{0,80}(?:الإشعار|اشعار|مهلة الإشعار)", sentence)
                and re.search(
                    r"لا\s*(?:يؤدي|يترتب|يسبب|ينتج).{0,150}"
                    r"(?:فقدان|خسارة|حرمان|خصم|حسم|تقليل|خفض).{0,120}(?:المكافأة|مكافأة نهاية الخدمة)",
                    sentence,
                )
                and re.search(
                    r"(?:إلا\s+إذا|ما\s+لم).{0,120}(?:بند|شرط|العقد|قرار قضائي|حكم قضائي)",
                    sentence,
                )
            )
            if unsupported_notice_exception:
                raise Reject(
                    "المادة 85: لا تربط أثر الإشعار على المكافأة باستثناء تعاقدي أو قضائي غير موثق"
                )
            if loss_claim and not negated:
                raise Reject(
                    "المادة 85: لا تنسب فقدان المكافأة أو خفضها تلقائيًا إلى عدم الالتزام بالإشعار"
                )

    if lang == "en":
        # Exactly five years still falls in the one-third band. Two-thirds starts
        # only after five years and ends before ten years.
        for match in re.finditer(
            r"\b(?:5|five)\s*(?:to|[-–—])\s*(?:10|ten)\s+years?\b",
            text_norm,
        ):
            window = text_norm[max(0, match.start() - 100):match.end() + 100]
            if re.search(r"\b(?:two[\s-]+thirds|2\s*/\s*3)\b", window):
                raise Reject(
                    "Article 85: the two-thirds band must start after five years, not at five years"
                )
        mentions_two_thirds = bool(re.search(r"\b(?:two[\s-]+thirds|2\s*/\s*3)\b", text_norm))
        correct_boundary = bool(re.search(
            r"\b(?:above|exceeds?|more than)\s+(?:five|5)\b"
            r".{0,100}\b(?:below|less than|not reach(?:es|ed)?|has not reached)\s+(?:ten|10)\b",
            text_norm,
        ))
        if mentions_two_thirds and not correct_boundary:
            raise Reject(
                "Article 85: clarify that two-thirds applies only after five years and before ten years"
            )
        for sentence in re.split(r"(?<=[.!?])\s+", text_norm):
            if not re.search(r"\barticle\s*85\b", sentence) or "notice" not in sentence:
                continue
            denies_notice_authority = bool(re.search(
                r"\b(?:does not|doesn't|never|not)\s+(?:set|specify|determine|govern|address|waive)\b",
                sentence,
            ))
            attributes_notice_rule = bool(re.search(
                r"\b(?:specifies|states|says|provides|requires|sets|waives)\b", sentence
            ))
            asserts_no_notice = bool(re.search(
                r"\b(?:not required|isn't required|not necessary|unnecessary|no need|"
                r"does not require|doesn't require|does not need|doesn't need)\b",
                sentence,
            ))
            if (attributes_notice_rule or asserts_no_notice) and not denies_notice_authority:
                raise Reject(
                    "Article 85: do not attribute notice-period rules or a notice waiver to Article 85"
                )
        if "notice" in text_norm:
            notice_caveat = (
                "notice requirements" in text_norm
                and any(x in text_norm for x in ("may still apply", "still apply", "remain applicable"))
                and any(x in text_norm for x in (
                    "depending on the contract", "depend on the contract",
                    "contract type", "contract and law",
                ))
            )
            if not notice_caveat:
                raise Reject(
                    "Article 85: distinguish EOSB eligibility from notice/resignation requirements that may still apply"
                )
        for match in re.finditer(
            r"\b(?:dismissal|dismissed|fired)\s+(?:under|pursuant to)\s+article\s*81\b",
            text_norm,
        ):
            prefix = text_norm[max(0, match.start() - 40):match.start()]
            is_negated = bool(re.search(
                r"\b(?:not|isn't|never|incorrectly|do not call|don't call)\s+(?:a\s+)?$",
                prefix,
            ))
            if not is_negated:
                raise Reject(
                    "Article 81 concerns the worker leaving without notice in statutory cases, not dismissal under Article 81"
                )
        if re.search(
            r"\b(?:the\s+)?basic\s+(?:wage|salary)\s+(?:may|can|could|is)\s+be\s+excluded\b",
            text_norm,
        ):
            raise Reject(
                "Article 86: do not claim that the basic wage itself may be excluded"
            )
        if re.search(r"\b(?:commission|commissions|sales percentages?)\b", text_norm):
            wage_rule = (
                "commission" in text_norm
                and ("increase" in text_norm)
                and ("decrease" in text_norm)
                and "agreement" in text_norm
            )
            if not wage_rule:
                raise Reject(
                    "Article 86: explain that qualifying variable commissions/sales elements are excluded only by agreement"
                )
    else:
        # Catch a recurring malformed Arabic rendering of Article 88's settlement rule.
        # Strip diacritics and normalize hamza variants, but keep this narrowly scoped
        # so ordinary Arabic phrasing about wages and settlement remains allowed.
        plain_ar = re.sub(r"[ًٌٍَُِّْٰ]", "", text_norm)
        plain_ar = plain_ar.translate(str.maketrans({"أ": "ا", "إ": "ا", "آ": "ا", "ى": "ي"}))
        if re.search(r"يجب\s+في\s+الاجر.{0,50}وصفت\s+الحقوق", plain_ar):
            raise Reject(
                "جودة العربية: صياغة مشوّهة في جملة دفع الأجر وتصفية الحقوق؛ أعد صياغتها بوضوح"
            )
        for sentence in re.split(r"(?<=[.!؟])\s+", text_norm):
            if not re.search(r"المادة\s*(?:85|الخامسة\s+والثمانون)", sentence):
                continue
            if not re.search(r"(?:الإشعار|اشعار|فترة الإشعار|مهلة الإشعار|ثلاثة أشهر|ثلاثين يوماً|ثلاثين يوما)", sentence):
                continue
            denies_notice_authority = bool(re.search(
                r"(?:لا\s+(?:تحدد|تنظم|تتناول|تعفي|تقرر)|ليست من اختصاص المادة\s*85)", sentence
            ))
            attributes_notice_rule = bool(re.search(
                r"(?:تنص|تذكر|تقول|تقرر|تحدد|توجب|تشترط|تعفي|لا تستلزم|لا تشترط)", sentence
            ))
            asserts_no_notice = bool(re.search(
                r"(?:غير مطلوب|لا يلزم|لا يتطلب|لا تحتاج|لا يستلزم|لا تشترط)", sentence
            ))
            if (attributes_notice_rule or asserts_no_notice) and not denies_notice_authority:
                raise Reject(
                    "المادة 85: لا تنسب مدة الإشعار أو الإعفاء منه إلى المادة 85"
                )
        has_resignation_ratio = any(x in text_norm for x in ("ثلث", "ثلثي", "الثلث"))
        if has_resignation_ratio:
            bad_range = re.search(
                r"(?:من\s+(?:خمس|5)\s*(?:إلى|الى|حتى|[-–—])\s*(?:عشر|10)\s+سنوات?).{0,100}(?:ثلثي|الثلثين)|"
                r"(?:ثلثي|الثلثين).{0,100}(?:من\s+(?:خمس|5)\s*(?:إلى|الى|حتى|[-–—])\s*(?:عشر|10)\s+سنوات?)",
                text_norm,
            )
            if bad_range:
                raise Reject(
                    "المادة 85: لا تُدرج خمس سنوات ضمن نطاق الثلثين؛ النسبة تبدأ بعد خمس سنوات"
                )
            correct_boundary = (
                ("أكثر من خمس" in text_norm or "زادت مدة خدمته على خمس" in text_norm)
                and ("أقل من عشر" in text_norm or "لم تبلغ عشر" in text_norm)
            )
            if not correct_boundary:
                raise Reject(
                    "المادة 85: يجب توضيح أن الثلثين يبدأان بعد تجاوز خمس سنوات وقبل بلوغ عشر سنوات"
                )
        if "الإشعار" in text_norm or "اشعار" in text_norm:
            notice_caveat = (
                "متطلبات الإشعار" in text_norm
                and "نوع العقد" in text_norm
                and any(x in text_norm for x in ("تبقى", "تظل", "تنطبق", "واجبة"))
                and any(x in text_norm for x in ("النظام", "الأحكام النظامية", "العقد"))
            )
            if not notice_caveat:
                raise Reject(
                    "المادة 85: وضّح أن عدم اشتراط الإشعار لاستحقاق المكافأة لا يلغي متطلبات الإشعار وإجراءات الاستقالة المطبقة"
                )
        if re.search(r"لا\s*يُستبعد\s+الأجر الأساسي إلا|لا\s*يستبعد\s+الأجر الأساسي إلا", text_norm):
            raise Reject(
                "المادة 86: لا تصف الحكم بأنه استبعاد للأجر الأساسي؛ النص يتعلق ببعض العمولات وعناصر الأجر المتغيرة"
            )
        if any(x in text_norm for x in ("العمولات", "النسب المئوية", "نسب المبيعات")):
            wage_rule = (
                "اتفاق" in text_norm and "بطبيعتها" in text_norm
                and "زيادة" in text_norm and "نقص" in text_norm
            )
            if not wage_rule:
                raise Reject(
                    "المادة 86: وضّح أن الاتفاق يتعلق بعناصر الأجر المتغيرة بطبيعتها للزيادة والنقص"
                )


def validate_article85_faq_consistency(faq: list, *, lang: str) -> None:
    """Reject FAQ answers that deny a service threshold while also describing it."""
    for item in faq:
        question = str(item.get("q", "")).strip().lower()
        answer = re.sub(r"\s+", " ", str(item.get("a", ""))).strip().lower()
        if lang == "en":
            asks_minimum = bool(re.search(
                r"\b(?:minimum|minimum service|minimum period|how long).{0,100}\b(?:service|eligible|entitled|award|eosb)?\b",
                question,
            ))
            denies_minimum = bool(re.search(
                r"\b(?:there is|there's|is) no minimum\b|\bno minimum (?:service|period|threshold)\b",
                answer,
            ))
            states_two_year_bar = bool(re.search(
                r"\b(?:no award|no entitlement|not entitled|not eligible|cannot receive|can't receive).{0,90}"
                r"\b(?:before|less than|under)\s+(?:two|2)\s+consecutive?\s+years?\b",
                answer,
            ))
            if denies_minimum and states_two_year_bar:
                raise Reject(
                    "Article 85: contradictory minimum-service FAQ; Article 85 has a two-consecutive-year threshold for resignation"
                )
            if asks_minimum and denies_minimum:
                raise Reject(
                    "Article 85: FAQ about minimum service cannot say there is no minimum for resignation entitlement"
                )
        else:
            asks_minimum = bool(re.search(
                r"(?:الحد الأدنى|حد أدنى|أقل مدة|أدنى مدة).{0,100}(?:الخدمة|الاستحقاق|المكافأة)?",
                question,
            ))
            denies_minimum = bool(re.search(
                r"(?:لا\s+يوجد|ليس\s+هناك|لا\s+يتوفر|لا\s+توجد)\s+(?:أي\s+)?حد\s+أدنى|لا\s+حد\s+أدنى",
                answer,
            ))
            states_two_year_bar = bool(re.search(
                r"(?:لا\s*(?:يُ?ستحق|يستحق|استحقاق)|لا\s+تستحق).{0,90}"
                r"(?:قبل|أقل\s+من|دون).{0,25}(?:سنتين|عامين|سنتين\s+متتاليتين)",
                answer,
            ))
            if denies_minimum and states_two_year_bar:
                raise Reject(
                    "المادة 85: إجابة الحد الأدنى متناقضة؛ تشترط المادة 85 سنتين متتاليتين لاستحقاق مكافأة الاستقالة"
                )
            if asks_minimum and denies_minimum:
                raise Reject(
                    "المادة 85: لا تصف مدة استحقاق مكافأة الاستقالة بأنها بلا حد أدنى"
                )


def validate_article(
    data, *, topic, lang, published_at, require_canonical_article85: bool = False,
) -> dict:
    """يرفع Reject عند فشل أي بوابة، بما فيها تدقيق حتمي لأي مثال EOSB رقمي."""
    if not isinstance(data, dict):
        raise Reject("المخرجات ليست كائن JSON")

    required = {"title", "meta_description", "excerpt", "sections", "faq",
                "official_sources", "calculation_example"}
    missing = required - set(data)
    if missing:
        raise Reject("حقول مطلوبة مفقودة: " + ", ".join(sorted(missing)))
    extra = set(data) - required
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
    if require_canonical_article85 and topic.get("id") == "labor-art85":
        validate_article85_faq_consistency(faq, lang=lang)

    body_text = " ".join(s["body"] + " " + " ".join(s["bullets"]) for s in sections)
    faq_text = " ".join(f"{f['q']} {f['a']}" for f in faq)
    audit_text = " ".join((title, meta_description, excerpt, body_text, faq_text))
    if require_canonical_article85 and topic.get("id") == "labor-art85":
        validate_article85_legal_claims(audit_text, lang=lang)
    example_sections = [
        section for section in sections
        if re.search(r"(?:مثال|example)", section["heading"], re.IGNORECASE)
    ]
    example_text = " ".join(
        section["body"] + " " + " ".join(section["bullets"])
        for section in example_sections
    )
    calculation_example = validate_eosb_calculation_example(
        data.get("calculation_example"), topic=topic, article_text=audit_text,
        example_text=example_text,
        require_canonical_article85=require_canonical_article85,
    )
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
        "calculation_example": calculation_example,
        "tool": topic["tool"],
        "published_at": published_at,
        "updated_at": published_at,
        "url": f"/articles/{lang}/{slug}.html",
        "word_count": words,
    }



def validate_eosb_translation_pair(ar_article, en_article) -> list:
    """Return problems when Arabic and English versions disagree on their EOSB example."""
    if not isinstance(ar_article, dict) or not isinstance(en_article, dict):
        return ["النسختان العربية والإنجليزية غير متاحتين"]
    if ar_article.get("translation_id") != en_article.get("translation_id"):
        return ["النسختان لا تنتميان إلى الموضوع نفسه"]
    if ar_article.get("lang") != "ar" or en_article.get("lang") != "en":
        return ["ترتيب أو لغة النسختين غير صحيح"]
    if ar_article.get("translation_id") not in EOSB_TOPIC_IDS:
        return []
    fields = EOSB_CALCULATION_FIELDS
    ar_calc = ar_article.get("calculation_example")
    en_calc = en_article.get("calculation_example")
    if not isinstance(ar_calc, dict) or not isinstance(en_calc, dict):
        return ["بيانات تدقيق المثال الحسابي غير موجودة في إحدى اللغتين"]
    mismatches = [field for field in fields if ar_calc.get(field) != en_calc.get(field)]
    return (["المثال الحسابي غير متطابق بين العربية والإنجليزية: " + ", ".join(mismatches)]
            if mismatches else [])


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


SOURCE_FAILURE_LABEL = {
    "dns": "فشل DNS: تعذّر ترجمة اسم المضيف",
    "timeout": "انتهت المهلة قبل استجابة الخادم",
    "network": "خطأ شبكة",
    "empty": f"استجابة فارغة أو أقصر من {SOURCE_MIN_BYTES} بايت",
}


def _source_failure_code(exc) -> str:
    """يصنّف استثناء الشبكة: dns أو timeout أو network (بلا كشف أي أسرار)."""
    for candidate in (getattr(exc, "reason", None), exc):
        if isinstance(candidate, socket.gaierror):
            return "dns"
        if isinstance(candidate, (TimeoutError, socket.timeout)):
            return "timeout"
    return "network"


def probe_source(url, *, timeout=None) -> tuple:
    """يفحص مصدراً واحداً ويرجع (ok, code, note).

    code: ok / dns / timeout / network / http_<status> / empty.
    """
    url = normalize_source_url(url)
    if timeout is None:
        timeout = SOURCE_CHECK_TIMEOUT
    try:
        status, body, _ = http_request(
            url, method="GET", headers=dict(SOURCE_REQUEST_HEADERS),
            timeout=timeout, retries=1)
    except Exception as exc:  # noqa: BLE001
        code = _source_failure_code(exc)
        if code == "network":
            note = f"{SOURCE_FAILURE_LABEL['network']}: {redact(exc)}"
        else:
            note = SOURCE_FAILURE_LABEL[code]
        return False, code, note
    if status != 200:
        note = f"أعادت الحالة {status}"
        if status in RETRYABLE_STATUS:
            note += " (خلل مؤقّت عند الخادم)"
        return False, f"http_{status}", note
    if not (body and len(body) > SOURCE_MIN_BYTES):
        return False, "empty", SOURCE_FAILURE_LABEL["empty"]
    return True, "ok", f"استجابة 200 ({len(body)} بايت)"


def probe_sources(sources, *, timeout=None) -> list:
    """يفحص قائمة مصادر مرة واحدة ويرجع نتائج منظّمة [{title,url,ok,code,note}]."""
    results = []
    for src in sources or []:
        url = src.get("url") if isinstance(src, dict) else src
        title = src.get("title") if isinstance(src, dict) else ""
        ok, code, note = probe_source(url, timeout=timeout)
        results.append({"title": title or "", "url": normalize_source_url(url),
                        "ok": ok, "code": code, "note": note})
    return results


def check_sources(sources, *, timeout=None) -> list:
    """يتحقّق من إمكانية الوصول للمصادر الرسمية. يرجع قائمة مشاكل (فارغة = نجاح)."""
    return [f"{r['url']} — {r['note']} [{r['code']}]"
            for r in probe_sources(sources, timeout=timeout) if not r["ok"]]


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
  $hreflang_html
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
    h2 { font-size:1.2rem; line-height:1.55; margin:0 0 12px; color:var(--brand); }
    p { margin:0 0 14px; }
    .meta { color:var(--muted); font-size:.86rem; margin-bottom:22px; }
    .article-section + .article-section { border-top:1px solid var(--line); margin-top:24px; padding-top:20px; }
    .article-section p { max-width:74ch; }
    .article-list { margin:10px 0 18px; padding-inline-start:1.5rem; }
    .article-list li { padding-inline-start:.22rem; margin:0 0 .58rem; }
    .article-list li:last-child { margin-bottom:0; }
    .numeric { direction:ltr; unicode-bidi:isolate; white-space:nowrap; font-variant-numeric:tabular-nums; font-weight:750; color:var(--brand); }
    .article-section strong { font-weight:750; color:#173f30; }
    .worked-example { margin-top:22px; padding:16px 18px; border:1px solid #cfe0d6; border-radius:12px; background:#f1f7f3; }
    .worked-example h2 { margin-top:0; }
    .faq { margin-top:24px; }
    .faq details { border:1px solid var(--line); border-radius:10px; padding:12px 14px; margin:10px 0; background:#fff; }
    .faq summary { cursor:pointer; font-weight:750; line-height:1.6; }
    .faq details p { margin:10px 0 0; }
    .cta { margin:28px 0; padding:16px 18px; background:#eef6f2; border:1px solid var(--line); border-radius:12px; }
    .cta a { color:var(--brand); font-weight:700; }
    .sources ul { padding-inline-start:1.5rem; }
    .sources li { margin:0 0 8px; }
    .sources a { color:var(--brand); }
    .note { font-size:.88rem; color:var(--muted); border-top:1px solid var(--line); margin-top:24px; padding-top:14px; }
    .ad-slot { max-width:820px; margin:18px auto; padding:0 18px; text-align:center; }
    footer.site { max-width:820px; margin:0 auto; padding:18px; color:var(--muted); font-size:.85rem; text-align:center; }
    footer.site a { color:var(--brand); }
    @media (max-width:600px) {
      main { padding:16px 14px 42px; }
      h1 { font-size:1.35rem; }
      .worked-example { padding:14px 12px; }
    }
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
    hreflang_html = (
        f'<link rel="alternate" hreflang="ar" href="{esc(alt_ar)}" />\n  '
        f'<link rel="alternate" hreflang="en" href="{esc(alt_en)}" />\n  '
        f'<link rel="alternate" hreflang="x-default" href="{esc(alt_ar)}" />'
        if published else ""
    )

    section_blocks = []
    for sec in article["sections"]:
        heading = str(sec.get("heading") or "")
        example_class = (
            " article-section worked-example"
            if re.search(r"(?:مثال|example)", heading, re.IGNORECASE)
            else " article-section"
        )
        parts = [f'<section class="{example_class.strip()}"><h2>{esc(heading)}</h2>']
        parts.append(render_article_body(sec.get("body", "")))
        if sec.get("bullets"):
            bullet_items = "".join(
                f"<li>{render_inline_prose(item)}</li>" for item in sec["bullets"]
            )
            parts.append(f'<ul class="article-list">{bullet_items}</ul>')
        parts.append("</section>")
        section_blocks.append("\n      ".join(parts))
    sections_html = "\n      ".join(section_blocks)

    faq_html = ""
    if article["faq"]:
        items = "".join(
            f"<details><summary>{render_inline_prose(f['q'])}</summary><p>{render_inline_prose(f['a'])}</p></details>\n      "
            for f in article["faq"]
        )
        faq_html = (
            f'<section class="faq"><h2>{esc("الأسئلة الشائعة" if ar else "Frequently asked questions")}</h2>\n      '
            f'{items}</section>'
        )

    if lang == "en" and tid == "labor-art85":
        # The English draft must cite English-language ministry material, not Arabic page titles.
        source_items = ARTICLE85_ENGLISH_SOURCES
    else:
        source_items = tuple((s["title"], s["url"]) for s in article["official_sources"])
    sources_html = "".join(
        f'<li><a href="{esc(url)}" rel="noopener noreferrer" target="_blank">{esc(title)}</a></li>'
        for title, url in source_items
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
        if ar else f'<a href="{esc(alt_ar)}">اقرأ هذا الدليل بالعربية</a>'
    ) if published else ""

    return ARTICLE_TEMPLATE.substitute(
        lang=lang,
        dir="rtl" if ar else "ltr",
        title_tag=esc(article["title"] + " | KSA Tools"),
        title=esc(article["title"]),
        meta_description=esc(article["meta_description"]),
        robots_meta="index,follow" if published else "noindex,nofollow",
        canonical=esc(canonical),
        hreflang_html=hreflang_html,
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


def run_once(*, mode, topic_id=None, social_lang="both", article_lang="both", dry_run=False,
             skip_source_check=False, provider=None, api_key=None, model=None) -> int:
    # حاجز أمان: لا نسمح بمسار النشر auto عند تجاوز تحقق المصادر.
    # يسبق قراءة الحالة/المقالات وفحص المفتاح وطلبات الشبكة وأي كتابة للملفات.
    if mode == "auto" and skip_source_check:
        log("[FAIL] إعداد نشر غير آمن: auto يتطلب التحقق من المصادر الرسمية؛ "
            "--skip-source-check مسموح فقط مع draft.")
        return EXIT_UNSAFE_PUBLISH_CONFIG

    # لغة المقال مستقلة عن social_lang: تحدد أي نسخة لغوية تُولَّد في هذه الدورة.
    # القيمة غير المعروفة تعود إلى "both" (نفس سلوك --social-lang و--mode).
    if article_lang not in ("ar", "en", "both"):
        article_lang = "both"
    lang_order = ("ar", "en") if article_lang == "both" else (article_lang,)

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
    attempted_languages = set()
    request_budgets = {}
    generation_report = []
    report_path = os.environ.get("GENERATION_REPORT_PATH")

    try:
        requested_english_effort = str(os.environ.get("GROQ_EN_REASONING_EFFORT", "low")).strip().lower()
    except Exception:
        requested_english_effort = "low"
    if requested_english_effort not in {"low", "medium"}:
        log(f"[WARN] GROQ_EN_REASONING_EFFORT غير صالح ({redact(requested_english_effort)}); سيُستخدم low.")
        requested_english_effort = "low"
    log(f"[CONFIG] Groq reasoning_effort: Arabic=low, English={requested_english_effort}; "
        "الافتراضي low ولا يُستخدم medium إلا عند اختياره صراحةً.")

    def record_generation_result(lang, status, stage, reason=""):
        budget = request_budgets.get(lang)
        row = {
            "topic": topic["id"],
            "language": lang,
            "provider": provider,
            "stage": stage,
            "status": status,
            "reason": redact(str(reason or ""))[:500],
            "http_requests": budget.used if budget is not None else None,
            "http_request_limit": budget.max_requests if budget is not None else None,
            "token_usage_scope": "cumulative_per_language" if budget is not None else None,
            "prompt_tokens": budget.prompt_tokens if budget is not None else None,
            "completion_tokens": budget.completion_tokens if budget is not None else None,
            "total_tokens": budget.total_tokens if budget is not None else None,
            "usage_responses": budget.usage_responses if budget is not None else None,
            "rate_limit_hits": budget.rate_limit_hits if budget is not None else None,
            "rate_limit_limit_tokens": budget.last_rate_limit_limit_tokens if budget is not None else None,
            "rate_limit_remaining_tokens": budget.last_rate_limit_remaining_tokens if budget is not None else None,
            "rate_limit_reset_tokens": budget.last_rate_limit_reset_tokens if budget is not None else None,
            "reasoning_effort": (
                requested_english_effort if provider == "groq" and lang == "en" else
                "low" if provider == "groq" else None
            ),
        }
        generation_report.append(row)
        log("[RESULT] " + json.dumps(row, ensure_ascii=False, sort_keys=True))
        if report_path:
            report_file = Path(report_path)
            report_file.parent.mkdir(parents=True, exist_ok=True)
            atomic_write_json(report_file, {
                "topic": topic["id"],
                "provider": provider,
                "model": model,
                "results": generation_report,
            })

    for lang in lang_order:
        if (topic["id"], lang) in published_pairs:
            log(f"[SKIP] النسخة {lang} منشورة سابقاً — لا إعادة إنشاء.")
            continue
        if provider == "groq" and lang == "en" and "ar" in attempted_languages:
            log(f"[WAIT] فاصل بين التوليد العربي والإنجليزي لتخفيف ضغط TPM: {GROQ_LANGUAGE_GAP_SECONDS:.0f}s.")
            SLEEP(GROQ_LANGUAGE_GAP_SECONDS)
        attempted_languages.add(lang)
        attempted = True
        request_budget = RequestBudget(GROQ_MAX_REQUESTS_PER_LANGUAGE) if provider == "groq" else None
        request_budgets[lang] = request_budget
        reasoning_effort = (
            requested_english_effort
            if provider == "groq" and lang == "en"
            else "low"
        )
        log(f"توليد النسخة {lang}…")
        prompt = build_prompt(topic, lang)
        if dry_run:
            ok, data, msg = True, fixture_data(lang, topic_id=topic["id"]), "fixture"
        else:
            ok, data, msg = generate_json(
                provider, prompt, api_key=api_key, model=model,
                tries=GROQ_INITIAL_HTTP_TRIES if provider == "groq" else GEMINI_MAX_TRIES,
                request_budget=request_budget, reasoning_effort=reasoning_effort)
            if (not ok and provider == "groq"
                    and is_groq_incomplete_schema_failure(msg)):
                record_generation_result(lang, "retrying", "schema_incomplete", msg)
                log(f"[RETRY] النسخة {lang}: استجابة Groq افتقدت حقولاً مطلوبة؛ محاولة واحدة بتذكير المخطط مع بقاء strict=true.")
                ok, data, msg = generate_json(
                    provider,
                    build_groq_schema_repair_prompt(prompt, lang=lang),
                    api_key=api_key,
                    model=model,
                    tries=1,
                    request_budget=request_budget,
                    reasoning_effort=reasoning_effort,
                )
        if not ok:
            log(f"[FAIL] تعذّر توليد النسخة {lang}: {redact(msg)}")
            state["topics"][topic["id"]][lang] = "error"
            record_generation_result(lang, "error", "generation", msg)
            continue
        deterministic_actions = []
        if topic["id"] == "labor-art85":
            try:
                data, deterministic_actions = ensure_article85_critical_content(data, lang=lang)
                if deterministic_actions:
                    log(f"[FIX] النسخة {lang}: فرض النص القانوني والمثال الحسابي الثابتين برمجياً "
                        f"مع حفظ البنية والمحتوى القابل للدمج ({', '.join(deterministic_actions)}).")
            except Reject as exc:
                reason = str(exc)
                log(f"[REJECT] النسخة {lang} لم تجتز إصلاح البنية الآمن: {redact(reason)}")
                state["topics"][topic["id"]][lang] = "rejected"
                record_generation_result(lang, "rejected", "deterministic_preflight", reason)
                continue
        elif topic["id"] in EOSB_TOPIC_IDS:
            try:
                canonical_example = (
                    results["ar"].get("calculation_example")
                    if lang == "en" and results.get("ar") is not None
                    else None
                )
                data, eosb_fixes = prepare_eosb_example_deterministically(
                    data, topic=topic, lang=lang,
                    canonical_example=canonical_example,
                )
                deterministic_actions.extend(eosb_fixes)
                if eosb_fixes:
                    log(f"[FIX] النسخة {lang}: صحّح المدقق الحسابي الحقول المشتقة ومثال الخدمة "
                        f"دون طلب توليد إضافي ({', '.join(eosb_fixes)}).")
            except Reject as prep_exc:
                # Preserve the raw response for the standard validator and its fail-closed rejection.
                log(f"[NOTE] النسخة {lang}: تعذّر الإصلاح الحسابي الحتمي ({redact(prep_exc)}); "
                    "ستعمل بوابات التحقق المعتادة.")
        repaired = False
        rejection_history = []
        try:
            article = validate_article(
                data, topic=topic, lang=lang, published_at=today_iso(),
                require_canonical_article85=True,
            )
        except Reject as exc:
            reason = str(exc)
            rejection_history.append(reason)
            record_generation_result(lang, "repairing", "quality_gate_rejection", reason)
            deterministic_repair_done = False
            if topic["id"] == "labor-art85":
                repaired_data, repaired_article, applied_fixes, remaining_reason = (
                    repair_article85_deterministic_omissions(
                        data, topic=topic, lang=lang, published_at=today_iso()
                    )
                )
                if repaired_article is not None and applied_fixes:
                    data = repaired_data
                    article = repaired_article
                    deterministic_repair_done = True
                    log(f"[FIX] النسخة {lang}: طبّقت الإصلاحات المحددة ({', '.join(applied_fixes)}) ثم اجتازت جميع الفحوص.")
                elif repaired_article is not None:
                    # The original rejection is unexpectedly gone on a repeat validation;
                    # accept only the result that passed every gate.
                    data = repaired_data
                    article = repaired_article
                    deterministic_repair_done = True
                else:
                    reason = remaining_reason or reason
                    if reason and reason != rejection_history[-1]:
                        rejection_history.append(reason)
                        record_generation_result(lang, "repairing", "deterministic_repair_rejection", reason)

            if not deterministic_repair_done:
                repairable = (
                    is_article85_repairable_rejection(reason)
                    if topic["id"] == "labor-art85"
                    else is_quality_repairable_rejection(reason, topic_id=topic["id"])
                )
                if not repairable:
                    log(f"[REJECT] النسخة {lang} لم تجتز بوابة الجودة: {redact(reason)}")
                    state["topics"][topic["id"]][lang] = "rejected"
                    record_generation_result(lang, "rejected", "quality_gate", reason)
                    continue

                log(f"[RETRY] النسخة {lang} رُفضت لجودة/صياغة محددة؛ محاولة إصلاح واحدة ثم إعادة جميع الفحوص.")
                if dry_run:
                    repair_ok, repair_data, repair_msg = True, fixture_data(lang, topic_id=topic["id"]), "fixture"
                else:
                    repair_prompt = (
                        build_article85_repair_prompt(prompt, lang=lang, reason=reason)
                        if topic["id"] == "labor-art85"
                        else build_quality_repair_prompt(prompt, lang=lang, reason=reason)
                    )
                    repair_ok, repair_data, repair_msg = generate_json(
                        provider,
                        repair_prompt,
                        api_key=api_key,
                        model=model,
                        # One content-repair attempt, with at most one bounded HTTP retry for 429/5xx.
                        # The shared request budget remains the hard ceiling, including this retry.
                        tries=2 if provider == "groq" else GEMINI_MAX_TRIES,
                        request_budget=request_budget,
                        reasoning_effort=reasoning_effort,
                    )
                # A quality-repair response may itself fail Groq required-key validation.
                # Spend at most one remaining request on a schema reminder, retaining strict JSON
                # Schema and the same per-language hard request budget.
                if (not repair_ok and provider == "groq"
                        and is_groq_incomplete_schema_failure(repair_msg)
                        and request_budget is not None
                        and request_budget.used < request_budget.max_requests):
                    record_generation_result(lang, "repairing", "schema_incomplete_after_content_repair", repair_msg)
                    log(f"[RETRY] النسخة {lang}: استجابة إصلاح المحتوى افتقدت حقولاً مطلوبة؛ محاولة واحدة بتذكير المخطط الصارم.")
                    repair_ok, repair_data, repair_msg = generate_json(
                        provider,
                        build_groq_schema_repair_prompt(repair_prompt, lang=lang),
                        api_key=api_key,
                        model=model,
                        tries=1,
                        request_budget=request_budget,
                        reasoning_effort=reasoning_effort,
                    )
                if not repair_ok:
                    repair_failure = (
                        f"المحاولة الإضافية غير متاحة ضمن حد الاستدعاءات: {redact(repair_msg)}"
                        if "request_budget_exhausted" in str(repair_msg)
                        else f"تعذّر التوليد ({redact(repair_msg)})"
                    )
                    log(f"[REJECT] النسخة {lang} بقيت مرفوضة بعد محاولة إصلاح واحدة: {repair_failure}.")
                    state["topics"][topic["id"]][lang] = "rejected"
                    record_generation_result(lang, "rejected", "content_repair", repair_failure)
                    continue
                if topic["id"] == "labor-art85":
                    try:
                        repair_data, repair_actions = ensure_article85_critical_content(repair_data, lang=lang)
                        if repair_actions:
                            log(f"[FIX] النسخة {lang}: فرض النص القانوني والمثال الثابتين بعد الإصلاح ({', '.join(repair_actions)}).")
                    except Reject as prep_exc:
                        repair_failure = str(prep_exc)
                        log(f"[REJECT] النسخة {lang} بقيت مرفوضة بعد الإصلاح البنيوي: {redact(repair_failure)}")
                        state["topics"][topic["id"]][lang] = "rejected"
                        record_generation_result(lang, "rejected", "deterministic_repair", repair_failure)
                        continue
                if topic["id"] == "labor-art85":
                    repair_data, article, post_repair_fixes, post_repair_reason = (
                        repair_article85_deterministic_omissions(
                            repair_data, topic=topic, lang=lang, published_at=today_iso()
                        )
                    )
                else:
                    post_repair_fixes = []
                    if topic["id"] in EOSB_TOPIC_IDS:
                        try:
                            canonical_example = (
                                results["ar"].get("calculation_example")
                                if lang == "en" and results.get("ar") is not None
                                else None
                            )
                            repair_data, post_repair_fixes = prepare_eosb_example_deterministically(
                                repair_data, topic=topic, lang=lang,
                                canonical_example=canonical_example,
                            )
                        except Reject as prep_repair_exc:
                            log(f"[NOTE] النسخة {lang}: لم يكتمل الإصلاح الحسابي الحتمي بعد محاولة النموذج "
                                f"({redact(prep_repair_exc)}); ستُحكم بوابات التحقق المعتادة.")
                            post_repair_fixes = []
                    try:
                        article = validate_article(
                            repair_data, topic=topic, lang=lang, published_at=today_iso(),
                            require_canonical_article85=True,
                        )
                        post_repair_reason = ""
                    except Reject as post_repair_exc:
                        article = None
                        post_repair_reason = str(post_repair_exc)
                    # For non-Article-85 EOSB topics, remove only extra money-bearing
                    # prose after the numeric calculation fields have passed validation.
                    # Do not ask the model to invent a second calculation; re-run every gate.
                    if (article is None and topic["id"] in EOSB_TOPIC_IDS
                            and topic["id"] != "labor-art85"
                            and post_repair_reason.startswith(
                                "المثال الرقمي في النص يتضمن مبلغاً لا يطابق بيانات الحساب")):
                        try:
                            repair_data = repair_eosb_unexpected_money_claims(
                                repair_data, lang=lang
                            )
                            article = validate_article(
                                repair_data, topic=topic, lang=lang,
                                published_at=today_iso(),
                                require_canonical_article85=True,
                            )
                            post_repair_reason = ""
                            post_repair_fixes.append("unexpected non-calculator currency claim removed")
                        except Reject as money_repair_exc:
                            article = None
                            post_repair_reason = str(money_repair_exc)
                if article is None:
                    repair_failure = post_repair_reason or "تعذّر اجتياز التحقق النهائي بعد الإصلاح"
                    log(f"[REJECT] النسخة {lang} بقيت مرفوضة بعد محاولة الإصلاح: {redact(repair_failure)}")
                    state["topics"][topic["id"]][lang] = "rejected"
                    record_generation_result(lang, "rejected", "final_validation", repair_failure)
                    continue
                if post_repair_fixes:
                    deterministic_actions.extend(
                        f"post-model: {fix}" for fix in post_repair_fixes
                    )
                    log(f"[FIX] النسخة {lang}: إصلاحات تحقق حتمية بعد استجابة النموذج "
                        f"({', '.join(post_repair_fixes)}).")
                repaired = True
        problems = duplicate_check(article, records)
        if problems:
            duplicate_reason = "; ".join(problems)
            log(f"[REJECT] النسخة {lang}: " + duplicate_reason)
            state["topics"][topic["id"]][lang] = "rejected"
            record_generation_result(lang, "rejected", "duplicate_check", duplicate_reason)
            continue
        article["content_hash"] = sha256_text(json.dumps(article["sections"], ensure_ascii=False))
        results[lang] = article
        accepted_notes = []
        if rejection_history:
            accepted_notes.append("rejection_history=" + " | ".join(rejection_history))
        accepted_notes.append(
            "deterministic_fixes=" + ", ".join(
                deterministic_actions + (["model repair"] if repaired else [])))
        record_generation_result(lang, "valid", "quality_gate", " ; ".join(accepted_notes))
        if repaired:
            log(f"[OK] النسخة {lang} اجتازت بوابة الجودة بعد محاولة إصلاح واحدة ({article['word_count']} كلمة).")
        else:
            log(f"[OK] النسخة {lang} اجتازت بوابة الجودة ({article['word_count']} كلمة).")

    if topic["id"] in EOSB_TOPIC_IDS and results.get("ar") and results.get("en"):
        pair_problems = validate_eosb_translation_pair(results["ar"], results["en"])
        if pair_problems:
            reason = "; ".join(pair_problems)
            log("[REJECT] مثال المكافأة مختلف بين النسختين؛ لن تُحفظ أي منهما: " + reason)
            for lang in ("ar", "en"):
                state["topics"][topic["id"]][lang] = "rejected"
                record_generation_result(lang, "rejected", "translation_pair", reason)
                results.pop(lang, None)

    ready = [results[l] for l in lang_order if results.get(l)]
    if not ready:
        if not attempted:
            log("[SKIP] النسختان (ar/en) منشورتان سابقاً — لا شيء لتوليده في هذه الدورة.")
            return 0
        statuses = ", ".join(
            f"{lang}={state['topics'][topic['id']].get(lang)}" for lang in lang_order)
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

    # --- فحص المصادر الرسمية: يجري لكل مصدر مستشهد به في كل نسخة اجتازت بوابة
    # الجودة، حتى لو اجتازت نسخة واحدة فقط. النسخة الواحدة غير مؤهلة للنشر على أي
    # حال، لكن نتيجة الفحص تحدّد تصنيف المسودة: نجاح كل المصادر ⇒ «draft»، وفشل أي
    # مصدر أو تعذّر التحقّق ⇒ «draft_unverified» (لا تُصنَّف النسخة متحقَّقة).
    if skip_source_check:
        log("[WARN] تم تخطّي التحقّق الشبكي من المصادر بأمر صريح (استخدام يدوي فقط).")
    else:
        # نجمع مصادر النسخ الجاهزة ونوحّدها (ar/en قد تتشارك المصادر) بلا طلب مزدوج.
        sources, seen_urls = [], set()
        for art in ready:
            for src in art.get("official_sources") or []:
                if not isinstance(src, dict):
                    continue
                url = normalize_source_url(src.get("url"))
                if url and url not in seen_urls:
                    seen_urls.add(url)
                    sources.append({"title": src.get("title", ""), "url": url})
        source_results = probe_sources(sources)
        problems = [f"{r['url']} — {r['note']} [{r['code']}]"
                    for r in source_results if not r["ok"]]
        log(f"[SOURCES] فحص {len(source_results)} مصدراً رسمياً عبر الشبكة "
            f"(بمهلة {SOURCE_CHECK_TIMEOUT}s وبترويسات طلب عادية).")
        for r in source_results:
            log(f"   {'[OK]' if r['ok'] else '[FAIL]'} {r['url']} — {r['note']} [{r['code']}]")
        if problems:
            log("[REJECT] تعذّر التحقّق من المصادر الرسمية — تبقى النسخ المولَّدة "
                "مسودات غير منشورة (unverified)، ولا يُلمس articles.json ولا sitemap.xml:")
            for p in problems:
                log("   - " + redact(p))
            for art in ready:
                write_article_files(art, published=False)
                state["topics"][topic["id"]][art["lang"]] = "draft_unverified"
            save_state(state)
            log(f"[DONE] اكتملت الدورة بلا نشر: {len(ready)} مسودة بحالة "
                "draft_unverified لإعادة المحاولة لاحقاً.")
            return 0

    if len(ready) != 2:
        missing = [l for l in lang_order if l not in results]
        _missing_txt = ", ".join(missing) if missing else "لا شيء (لغة واحدة مطلوبة)"
        log(f"[WARN] نسخة واحدة فقط اجتازت هذه الدورة (الناقص: {_missing_txt}) — "
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

    check("تاريخ المقال: يحوّل UTC إلى تاريخ الرياض عند عبور منتصف الليل",
          today_iso(datetime(2026, 10, 19, 23, 30, tzinfo=timezone.utc)) == "2026-10-20")

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

        # 2-أ) تدقيق الحساب الرقمي وفق المادتين 84 و85.
    eosb_topic = topic_by_id("labor-art85")
    eosb_good = fixture_data("ar", topic_id="labor-art85")
    eosb_good_article = validate_article(
        eosb_good, topic=eosb_topic, lang="ar", published_at="2026-01-01")
    check("تدقيق EOSB: يقبل أساس 42,000 ومستحق 28,000 لأجر 12,000 وخدمة 6 سنوات",
          eosb_good_article["calculation_example"]["payable_benefit"] == "28000.00")
    eosb_good_en = fixture_data("en", topic_id="labor-art85")
    eosb_good_en_article = validate_article(
        eosb_good_en, topic=eosb_topic, lang="en", published_at="2026-01-01")
    check("تدقيق EOSB: المثالان العربي والإنجليزي متطابقان عند تطابق البيانات",
          validate_eosb_translation_pair(eosb_good_article, eosb_good_en_article) == [])

    # Exercise the translation-pair guard independently of the per-topic
    # canonical-example guard by mutating an already-normalized valid article.
    eosb_pair_bad_article = dict(eosb_good_en_article)
    eosb_pair_bad_article["calculation_example"] = dict(
        eosb_good_en_article["calculation_example"])
    eosb_pair_bad_article["calculation_example"].update({
        "monthly_wage": "10000", "full_benefit": "35000", "payable_benefit": "23333.33",
    })
    check("تدقيق EOSB: يرفض اختلاف المثال الحسابي بين اللغتين",
          validate_eosb_translation_pair(eosb_good_article, eosb_pair_bad_article) != [])

    eosb_bad = fixture_data("ar", topic_id="labor-art85")
    eosb_bad["calculation_example"]["payable_benefit"] = "48000"
    check("تدقيق EOSB: يرفض نتيجة استقالة خاطئة داخل بيانات الحساب",
          _rejects(lambda: validate_article(
              eosb_bad, topic=eosb_topic, lang="ar", published_at="2026-01-01")))

    eosb_bad = fixture_data("ar", topic_id="labor-art85")
    eosb_bad["sections"][3]["body"] = eosb_bad["sections"][3]["body"].replace(
        "28,000 ريال", "48,000 ريال")
    check("تدقيق EOSB: يرفض مبلغاً خاطئاً بالنص ولو كانت بيانات الحساب سليمة",
          _rejects(lambda: validate_article(
              eosb_bad, topic=eosb_topic, lang="ar", published_at="2026-01-01")))

    eosb_bad = fixture_data("ar", topic_id="labor-art85")
    eosb_bad["calculation_example"]["full_benefit"] = "72000"
    check("تدقيق EOSB: يرفض ضرب الأجر الشهري في كل سنوات الخدمة",
          _rejects(lambda: validate_article(
              eosb_bad, topic=eosb_topic, lang="ar", published_at="2026-01-01")))

    eosb_bad = fixture_data("ar", topic_id="labor-art85")
    eosb_bad["calculation_example"]["scenario"] = "base"
    check("تدقيق EOSB: موضوع المادة 85 يتطلب نسبة الاستقالة",
          _rejects(lambda: validate_article(
              eosb_bad, topic=eosb_topic, lang="ar", published_at="2026-01-01")))

    eosb_noncanonical = fixture_data("ar", topic_id="labor-art85")
    eosb_noncanonical["calculation_example"]["monthly_wage"] = "12500"
    check("تدقيق EOSB: يرفض تغيير الأجر في المثال الثابت للمادة 85",
          _rejects(lambda: validate_article(
              eosb_noncanonical, topic=eosb_topic, lang="ar", published_at="2026-01-01",
              require_canonical_article85=True)))
    _prompt_ar85 = build_prompt(eosb_topic, "ar")
    _prompt_en85 = build_prompt(eosb_topic, "en")
    check("تدقيق EOSB: المثال الثابت 12000/6 سنوات/42000/28000 محدد للغتين",
          all(value in _prompt_ar85 and value in _prompt_en85
              for value in ("monthly_wage=12000", "years=6", "scenario=resignation",
                            "full_benefit=42000", "payable_benefit=28000"))
          and "لا تخترع أرقاماً أخرى" in _prompt_ar85
          and "Do not invent or change any value" in _prompt_en85)
    check("بوابة الجودة: تعليمات التوليد تحدّ طول كل قسم إلى 5000 حرف",
          "نص body في أي قسم منفرد 5000 حرف" in _prompt_ar85
          and "نص body في أي قسم منفرد 5000 حرف" in _prompt_en85)
    check("بوابة قانونية: تعليمات المادة 85 توضّح حدود الخمس سنوات والإشعار والمادة 86",
          "الثلثان بعد تجاوز خمس سنوات وقبل بلوغ عشر" in _prompt_ar85
          and "two thirds applies only above five and below ten" in _prompt_en85
          and "متطلبات الإشعار وإجراءات الاستقالة واجبة بحسب العقد والنظام" in _prompt_ar85
          and "notice and resignation procedures may still apply under the contract and law" in _prompt_en85)

    _ar85_legal_good = (
        "تستحق ثلث المكافأة من سنتين إلى خمس سنوات، بما فيها خمس سنوات، "
        "ويستحق العامل الثلثين إذا زادت مدة خدمته على خمس سنوات ولم تبلغ عشر سنوات، "
        "والمكافأة كاملة عند عشر سنوات فأكثر. عدم كون الإشعار شرطاً لاستحقاق المكافأة "
        "لا يعني أن الإشعار غير مطلوب لإنهاء العقد؛ فقد تبقى متطلبات الإشعار وإجراءات "
        "الاستقالة واجبة بحسب نوع العقد والأحكام النظامية المنطبقة. يجوز الاتفاق على "
        "استبعاد العمولات والنسب المئوية عن المبيعات وما يماثلها من عناصر الأجر القابلة "
        "بطبيعتها للزيادة والنقص. المادة 81 تتعلق بترك العامل العمل دون إشعار مع احتفاظه "
        "بحقوقه النظامية وليست فصلاً من صاحب العمل."
    )
    check("بوابة قانونية: تقبل الصياغة العربية السليمة للمادة 85",
          not _rejects(lambda: validate_article85_legal_claims(_ar85_legal_good, lang="ar")))
    _en85_legal_good = (
        "Under Article 85, one-third applies from two through five years inclusive; "
        "two-thirds applies only when service exceeds five years but has not reached ten. "
        "The fact that notice is not an EOSB eligibility threshold does not mean notice is "
        "unnecessary to end a contract; applicable notice requirements and resignation "
        "procedures may still apply depending on the contract and law. Article 86 allows "
        "explicit agreement to exclude commissions, sales percentages and similar wage "
        "elements naturally subject to increase or decrease. Leaving work under Article 81 "
        "means the worker leaves without notice in statutory cases while retaining rights; "
        "it is not dismissal under Article 81."
    )
    check("بوابة قانونية: تقبل الصياغة الإنجليزية السليمة للمادة 85",
          not _rejects(lambda: validate_article85_legal_claims(_en85_legal_good, lang="en")))
    _en85_bad_range = _en85_legal_good.replace(
        "exceeds five years but has not reached ten", "5 to 10 years")
    check("بوابة قانونية: ترفض إدراج الخمس سنوات ضمن نسبة الثلثين",
          _rejects(lambda: validate_article85_legal_claims(_en85_bad_range, lang="en")))
    _ar85_bad_range = _ar85_legal_good.replace(
        "ويستحق العامل الثلثين إذا زادت مدة خدمته على خمس سنوات ولم تبلغ عشر سنوات، ",
        "ويستحق العامل الثلثين من خمس إلى عشر سنوات، ")
    check("بوابة قانونية: ترفض نطاق خمس إلى عشر سنوات للثلثين (عربي)",
          _rejects(lambda: validate_article85_legal_claims(_ar85_bad_range, lang="ar")))
    check("بوابة قانونية: تقبل التصريح بأن المادة 85 لا تحدد مدة الإشعار",
          not _rejects(lambda: validate_article85_legal_claims(
              "Article 85 sets the benefit ratios only; it does not set or waive notice requirements. "
              "Applicable notice requirements and resignation procedures may still apply depending on the contract and law.",
              lang="en")))
    _en85_bad_notice_attribution = _en85_legal_good.replace(
        "Under Article 85, one-third applies from two through five years inclusive; ",
        "Article 85 specifies that resignation does not require a three-month notice. "
        "Under Article 85, one-third applies from two through five years inclusive; ")
    check("بوابة قانونية: ترفض نسبة الإعفاء من الإشعار إلى المادة 85 (إنجليزي)",
          _rejects(lambda: validate_article85_legal_claims(
              _en85_bad_notice_attribution, lang="en")))
    _ar85_bad_notice_attribution = _ar85_legal_good.replace(
        "تستحق ثلث المكافأة من سنتين إلى خمس سنوات، بما فيها خمس سنوات، ",
        "تنص المادة 85 على أن الاستقالة لا تتطلب إشعارًا لمدة ثلاثة أشهر. "
        "تستحق ثلث المكافأة من سنتين إلى خمس سنوات، بما فيها خمس سنوات، ")
    check("بوابة قانونية: ترفض نسبة الإعفاء من الإشعار إلى المادة 85 (عربي)",
          _rejects(lambda: validate_article85_legal_claims(
              _ar85_bad_notice_attribution, lang="ar")))

    _notice_repair_probe, _ = ensure_article85_critical_content(
        fixture_data("en", topic_id="labor-art85"), lang="en")
    _notice_repair_probe["sections"][0]["body"] += (
        "\n\nArticle 85 specifies that resignation does not require a three-month notice."
    )
    (_notice_repaired_data, _notice_repaired_article,
     _notice_repair_actions, _notice_repair_reason) = repair_article85_deterministic_omissions(
        _notice_repair_probe, topic=eosb_topic, lang="en", published_at="2026-01-01")
    check("إصلاح حتمي: يصحح نسبة الإعفاء من الإشعار إلى المادة 85 دون طلب نموذج جديد",
          _notice_repaired_article is not None
          and "Article 85 specifies that resignation does not require" not in json.dumps(
              _notice_repaired_data, ensure_ascii=False)
          and "notice authority claim" in _notice_repair_actions)

    _money_repair_probe, _ = ensure_article85_critical_content(
        fixture_data("ar", topic_id="labor-art85"), lang="ar")
    _money_repair_probe["sections"][0]["body"] += (
        "\n\nوقد يذكر وصف غير معتمد مبلغ 30,000 ريال في مثال منفصل."
    )
    (_money_repaired_data, _money_repaired_article,
     _money_repair_actions, _money_repair_reason) = repair_article85_deterministic_omissions(
        _money_repair_probe, topic=eosb_topic, lang="ar", published_at="2026-01-01")
    check("إصلاح حتمي: يعالج المبالغ النقدية غير المعتمدة مع إبقاء المثال الثابت",
          _money_repaired_article is not None
          and "30,000 ريال" not in json.dumps(_money_repaired_data, ensure_ascii=False)
          and "unexpected currency amount removed" in _money_repair_actions)

    _generic_money_topic = topic_by_id("eosb-full-entitlement")
    _generic_money_probe = fixture_data("ar", topic_id="eosb-full-entitlement")
    _generic_money_probe["sections"][0]["body"] += (
        "\n\nوقد يذكر وصف غير معتمد مبلغ 30,000 ريال في مثال منفصل."
    )
    try:
        validate_article(
            _generic_money_probe, topic=_generic_money_topic, lang="ar",
            published_at="2026-01-01", require_canonical_article85=True,
        )
        _generic_money_original_reason = ""
    except Reject as _generic_money_original_exc:
        _generic_money_original_reason = str(_generic_money_original_exc)
    _generic_money_clean = repair_eosb_unexpected_money_claims(
        _generic_money_probe, lang="ar"
    )
    _generic_money_article = validate_article(
        _generic_money_clean, topic=_generic_money_topic, lang="ar",
        published_at="2026-01-01", require_canonical_article85=True,
    )
    check("إصلاح EOSB عام: يزيل المبلغ النقدي الزائد دون تبديل قيم الحاسبة",
          _generic_money_original_reason.startswith(
              "المثال الرقمي في النص يتضمن مبلغاً لا يطابق بيانات الحساب")
          and _generic_money_article is not None
          and "30,000 ريال" not in json.dumps(_generic_money_clean, ensure_ascii=False)
          and _generic_money_clean["calculation_example"]
              == _generic_money_probe["calculation_example"])

    _eosb_deterministic_probe = fixture_data("ar", topic_id="eosb-full-entitlement")
    _eosb_deterministic_example = next(
        section for section in _eosb_deterministic_probe["sections"]
        if re.search(r"(?:مثال|example)", section["heading"], re.IGNORECASE)
    )
    _eosb_deterministic_example["body"] = (
        _AR_BODY + " ويذكر النص مبلغاً زائداً قدره 12,500 ريال."
    )
    _eosb_deterministic_probe["calculation_example"]["full_benefit"] = "37900"
    _eosb_deterministic_probe["calculation_example"]["payable_benefit"] = "5833.33"
    _eosb_deterministic_probe["calculation_example"]["scenario"] = "resignation"
    _eosb_deterministic_fixed, _eosb_deterministic_actions = (
        prepare_eosb_example_deterministically(
            _eosb_deterministic_probe,
            topic=topic_by_id("eosb-full-entitlement"),
            lang="ar",
        )
    )
    _eosb_deterministic_article = validate_article(
        _eosb_deterministic_fixed,
        topic=topic_by_id("eosb-full-entitlement"),
        lang="ar",
        published_at="2026-01-01",
        require_canonical_article85=True,
    )
    check("EOSB: إصلاح حتمي يجبر سيناريو الاستحقاق الكامل ويعيد حساب المبالغ دون API",
          _eosb_deterministic_article is not None
          and _eosb_deterministic_fixed["calculation_example"]["scenario"] == "article87"
          and _eosb_deterministic_fixed["calculation_example"]["full_benefit"] == "42000.00"
          and _eosb_deterministic_fixed["calculation_example"]["payable_benefit"] == "42000.00"
          and "calculator-derived full benefit corrected" in _eosb_deterministic_actions
          and "calculator-derived payable benefit corrected" in _eosb_deterministic_actions
          and "topic-specific calculation scenario enforced" in _eosb_deterministic_actions
          and "Article 87 qualifying scenario made explicit" in _eosb_deterministic_actions)

    _article87_conflict_probe = fixture_data("en", topic_id="eosb-full-entitlement")
    _article87_example = next(
        section for section in _article87_conflict_probe["sections"]
        if re.search(r"(?:مثال|example)", section["heading"], re.IGNORECASE)
    )
    _article87_example["body"] += (
        " This example assumes an ordinary resignation after six years."
    )
    _article87_conflict_reason = ""
    try:
        validate_article(
            _article87_conflict_probe,
            topic=topic_by_id("eosb-full-entitlement"),
            lang="en", published_at="2026-01-01",
            require_canonical_article85=True,
        )
    except Reject as exc:
        _article87_conflict_reason = str(exc)
    check("Article 87: رفض تناقض وصف المثال مع سيناريو الحساب حتى عند ذكر القوة القاهرة",
          _article87_conflict_reason.startswith(
              "calculation_example.scenario: نص المثال يصف استقالة عادية"
          ))

    _article87_missing_basis_probe = fixture_data("ar", topic_id="eosb-full-entitlement")
    _article87_missing_example = next(
        section for section in _article87_missing_basis_probe["sections"]
        if re.search(r"(?:مثال|example)", section["heading"], re.IGNORECASE)
    )
    _article87_missing_example["body"] = re.sub(
        r"يفترض هذا المثال ترك العامل العمل بسبب قوة قاهرة خارجة عن إرادته وفق المادة 87، "
        r"وليس استقالة عادية تخضع لنسب المادة 85؛\s*",
        "", _article87_missing_example["body"]
    )
    _article87_missing_reason = ""
    try:
        validate_article(
            _article87_missing_basis_probe,
            topic=topic_by_id("eosb-full-entitlement"),
            lang="ar", published_at="2026-01-01",
            require_canonical_article85=True,
        )
    except Reject as exc:
        _article87_missing_reason = str(exc)
    check("Article 87: رفض مثال لا يذكر أي حالة استحقاق مؤهلة",
          _article87_missing_reason.startswith(
              "calculation_example.scenario: نص المثال لا يذكر حالة مؤهلة وفق المادة 87"
          ))

    check("EOSB: يضمن ذكر مدة الخدمة والقيم المحسوبة ويزيل مبلغاً زائداً ثم يعيد كل البوابات",
          _eosb_deterministic_article is not None
          and "12,500 ريال" not in json.dumps(_eosb_deterministic_fixed, ensure_ascii=False)
          and _extract_eosb_service_durations(
              " ".join(section["body"] for section in _eosb_deterministic_fixed["sections"]
                       if re.search(r"(?:مثال|example)", section["heading"], re.IGNORECASE))
          ) == [Decimal("6")]
          and "unsupported currency claims removed from prose" in _eosb_deterministic_actions
          and "authoritative currency figures made explicit" in _eosb_deterministic_actions)

    # Regression for the production failure: the generated paragraph ends with an
    # unsupported amount but no punctuation, then the service sentence is appended as
    # a separate paragraph. Currency cleanup must preserve the safe duration sentence.
    _eosb_paragraph_money_probe = fixture_data("ar", topic_id="eosb-full-entitlement")
    _eosb_paragraph_money_example = next(
        section for section in _eosb_paragraph_money_probe["sections"]
        if re.search(r"(?:مثال|example)", section["heading"], re.IGNORECASE)
    )
    _eosb_paragraph_money_example["body"] = (
        _AR_BODY + " ويذكر النص مبلغاً زائداً قدره 12,500 ريال"
    )
    _eosb_paragraph_money_example["bullets"] = []
    _eosb_paragraph_money_fixed, _eosb_paragraph_money_actions = (
        prepare_eosb_example_deterministically(
            _eosb_paragraph_money_probe,
            topic=topic_by_id("eosb-full-entitlement"),
            lang="ar",
        )
    )
    _eosb_paragraph_money_article = None
    try:
        _eosb_paragraph_money_article = validate_article(
            _eosb_paragraph_money_fixed,
            topic=topic_by_id("eosb-full-entitlement"),
            lang="ar", published_at="2026-01-01",
            require_canonical_article85=True,
        )
    except Reject:
        pass
    _eosb_paragraph_money_text = " ".join(
        str(section["body"]) + " " + " ".join(section.get("bullets", []))
        for section in _eosb_paragraph_money_fixed["sections"]
        if re.search(r"(?:مثال|example)", str(section.get("heading", "")), re.IGNORECASE)
    )
    check("EOSB: لا يحذف تنظيف العملة مدة الخدمة عند غياب النقطة قبل فقرة جديدة",
          _eosb_paragraph_money_article is not None
          and "12,500 ريال" not in json.dumps(_eosb_paragraph_money_fixed, ensure_ascii=False)
          and Decimal("6") in _extract_eosb_service_durations(_eosb_paragraph_money_text))

    # Regression: an unsupported currency claim shares the sentence carrying the
    # only Article 87 qualifying basis. Cleanup must remove the amount, then restore
    # the qualifying circumstance deterministically without a second model request.
    _article87_money_probe = fixture_data("en", topic_id="eosb-full-entitlement")
    _article87_money_example = next(
        section for section in _article87_money_probe["sections"]
        if re.search(r"(?:مثال|example)", section["heading"], re.IGNORECASE)
    )
    _article87_money_example["body"] = (
        "This worked example assumes force majeure beyond the worker's control and includes "
        "an unsupported amount of SAR 12,500."
    )
    _article87_money_fixed, _article87_money_actions = (
        prepare_eosb_example_deterministically(
            _article87_money_probe,
            topic=topic_by_id("eosb-full-entitlement"),
            lang="en",
        )
    )
    _article87_money_article = None
    try:
        _article87_money_article = validate_article(
            _article87_money_fixed,
            topic=topic_by_id("eosb-full-entitlement"),
            lang="en", published_at="2026-01-01",
            require_canonical_article85=True,
        )
    except Reject:
        pass
    _article87_money_text = " ".join(
        str(section.get("body", "")) + " " + " ".join(section.get("bullets", []))
        for section in _article87_money_fixed["sections"]
        if re.search(r"(?:مثال|example)", str(section.get("heading", "")), re.IGNORECASE)
    )
    check("Article 87: restores qualifying circumstance after currency cleanup",
          _article87_money_article is not None
          and "force majeure" in _article87_money_text.lower()
          and "12,500" not in json.dumps(_article87_money_fixed, ensure_ascii=False)
          and "Article 87 qualifying scenario reasserted after currency cleanup"
              in _article87_money_actions)

    check("بوابة قانونية: ترفض الادعاء بأن مخالفة الإشعار تفقد العامل جزءاً من المكافأة (عربي)",
          _rejects(lambda: validate_article85_legal_claims(
              "عدم الالتزام قد يؤدي إلى فقدان جزء من المكافأة أو تعويضات أخرى. "
              "وقد تبقى متطلبات الإشعار وإجراءات الاستقالة واجبة بحسب نوع العقد والأحكام النظامية المنطبقة.",
              lang="ar")))

    _unsupported_notice_exception_ar = (
        "عدم الالتزام بالإشعار لا يؤدي تلقائيًا إلى فقدان أو خفض المكافأة، إلا إذا كان هناك بند خاص في العقد أو قرار قضائي يحدد ذلك."
    )
    check("بوابة قانونية: ترفض استثناءً تعاقديًا أو قضائيًا غير موثق لأثر الإشعار (عربي)",
          _rejects(lambda: validate_article85_legal_claims(_unsupported_notice_exception_ar, lang="ar")))
    _notice_exception_fix, _ = ensure_article85_critical_content(
        fixture_data("ar", topic_id="labor-art85"), lang="ar")
    _notice_exception_fix["sections"][0]["body"] += "\n\n" + _unsupported_notice_exception_ar
    (_notice_exception_fixed, _notice_exception_article,
     _notice_exception_actions, _notice_exception_reason) = repair_article85_deterministic_omissions(
        _notice_exception_fix, topic=eosb_topic, lang="ar", published_at="2026-01-01")
    check("إصلاح حتمي: يستبدل استثناء أثر الإشعار غير الموثق ويعيد اجتياز كل البوابات",
          _notice_exception_article is not None
          and _unsupported_notice_exception_ar not in json.dumps(_notice_exception_fixed, ensure_ascii=False)
          and "notice loss claim" in _notice_exception_actions)
    check("بوابة قانونية: ترفض الادعاء بأن مخالفة الإشعار تفقد العامل جزءاً من المكافأة (إنجليزي)",
          _rejects(lambda: validate_article85_legal_claims(
              "Failure to comply may lead to loss of part of the end-of-service award. "
              "Applicable notice requirements and resignation procedures may still apply depending on the contract and law.",
              lang="en")))
    _ar85_bad_minimum_faq = [{
        "q": "ما الحد الأدنى لسن الخدمة لاستحقاق المكافأة؟",
        "a": "لا يوجد حد أدنى، لكن لا يُستحق أي مكافأة قبل سنتين متتاليتين من الخدمة."
    }]
    _ar85_good_minimum_faq = [{
        "q": "ما الحد الأدنى لسن الخدمة لاستحقاق مكافأة الاستقالة؟",
        "a": "وفق المادة 85، لا يستحق العامل مكافأة الاستقالة قبل سنتين متتاليتين من الخدمة."
    }]
    _en85_bad_minimum_faq = [{
        "q": "What is the minimum service period for a resignation award?",
        "a": "There is no minimum, but no award is due before two consecutive years of service."
    }]
    check("بوابة FAQ: ترفض تناقض عدم وجود حد أدنى مع شرط السنتين (عربي)",
          _rejects(lambda: validate_article85_faq_consistency(_ar85_bad_minimum_faq, lang="ar")))
    check("بوابة FAQ: ترفض تناقض عدم وجود حد أدنى مع شرط السنتين (إنجليزي)",
          _rejects(lambda: validate_article85_faq_consistency(_en85_bad_minimum_faq, lang="en")))
    check("بوابة FAQ: تقبل بيان شرط السنتين بوضوح (عربي)",
          not _rejects(lambda: validate_article85_faq_consistency(_ar85_good_minimum_faq, lang="ar")))
    check("بوابة جودة العربية: ترفض الجملة المشوّهة في تصفية الحقوق",
          _rejects(lambda: validate_article85_legal_claims(
              "إذا انتهت الخدمة من جهة صاحب العمل، يجب فُي الأجر وصُفِّت الحقوق خلال أسبوع على الأكثر.",
              lang="ar")))
    _en85_bad_notice = _en85_legal_good.replace(
        "applicable notice requirements and resignation procedures may still apply depending on the contract and law.", "")
    check("بوابة قانونية: ترفض ذكر الإشعار دون توضيح المتطلبات المستقلة",
          _rejects(lambda: validate_article85_legal_claims(_en85_bad_notice, lang="en")))
    _ar85_bad_wage = _ar85_legal_good.replace(
        "عناصر الأجر القابلة بطبيعتها للزيادة والنقص", "عناصر الأجر")
    check("بوابة قانونية: ترفض شرح المادة 86 دون بيان طبيعة العناصر المتغيرة",
          _rejects(lambda: validate_article85_legal_claims(_ar85_bad_wage, lang="ar")))
    _en85_bad_article81 = _en85_legal_good.replace(
        "it is not dismissal under Article 81", "dismissal under Article 81")
    check("بوابة قانونية: ترفض وصف المادة 81 بأنها فصل من صاحب العمل",
          _rejects(lambda: validate_article85_legal_claims(_en85_bad_article81, lang="en")))

    art81_topic = topic_by_id("labor-art81")
    art81_good = fixture_data("ar", topic_id="labor-art81")
    check("تدقيق EOSB: يقبل سيناريو المادة 81 بالمكافأة الكاملة",
          not _rejects(lambda: validate_article(
              art81_good, topic=art81_topic, lang="ar", published_at="2026-01-01")))
    art81_bad = fixture_data("ar", topic_id="labor-art81")
    art81_bad["calculation_example"]["scenario"] = "resignation"
    art81_bad["calculation_example"]["payable_benefit"] = "28000"
    art81_bad["sections"][3]["body"] = art81_bad["sections"][3]["body"].replace(
        "والمبلغ المستحق في هذا المثال 42,000 ريال.",
        "والمكافأة الأساسية 42,000 ريال، وبعد نسبة الاستقالة المبلغ المستحق 28,000 ريال.")
    check("تدقيق EOSB: يرفض نسبة الاستقالة في موضوع المادة 81",
          _rejects(lambda: validate_article(
              art81_bad, topic=art81_topic, lang="ar", published_at="2026-01-01")))

    eosb_duration_bad = fixture_data("ar", topic_id="labor-art85")
    eosb_duration_bad["sections"][3]["body"] = eosb_duration_bad["sections"][3]["body"].replace(
        "مدة الخدمة 6 سنوات", "مدة الخدمة 10 سنوات")
    check("تدقيق EOSB: يرفض تناقض مدة الخدمة بين النص وبيانات الحساب",
          _rejects(lambda: validate_article(
              eosb_duration_bad, topic=eosb_topic, lang="ar", published_at="2026-01-01")))

    eosb_duration_bad_en = fixture_data("en", topic_id="labor-art85")
    eosb_duration_bad_en["sections"][3]["body"] = eosb_duration_bad_en["sections"][3]["body"].replace(
        "six years of service", "ten years of service")
    check("تدقيق EOSB: يرفض تناقض مدة الخدمة في المثال الإنجليزي",
          _rejects(lambda: validate_article(
              eosb_duration_bad_en, topic=eosb_topic, lang="en", published_at="2026-01-01")))

    eosb_fractional_year = fixture_data("ar", topic_id="labor-art85")
    eosb_fractional_year["calculation_example"].update({
        "years": "6.5", "months": "0", "days": "0",
        "full_benefit": "48000", "payable_benefit": "32000",
    })
    eosb_fractional_year["sections"][3]["body"] = (
        eosb_fractional_year["sections"][3]["body"]
        .replace("مدة الخدمة 6 سنوات", "مدة الخدمة 6.5 سنوات")
        .replace("42,000 ريال", "48,000 ريال")
        .replace("28,000 ريال", "32,000 ريال")
    )
    fractional_article = validate_article(
        eosb_fractional_year, topic=eosb_topic, lang="ar", published_at="2026-01-01")
    check("تدقيق EOSB: يقبل 6.5 سنوات ويحسب الأساس 48,000 والمستحق 32,000",
          fractional_article["calculation_example"]["years"] == "6.5"
          and fractional_article["calculation_example"]["full_benefit"] == "48000.00"
          and fractional_article["calculation_example"]["payable_benefit"] == "32000.00")

    eosb_article87_fraction_ar = fixture_data("ar", topic_id="eosb-full-entitlement")
    eosb_article87_fraction_ar["calculation_example"].update({
        "years": "4.5", "months": "0", "days": "0",
        "full_benefit": "27000", "payable_benefit": "27000",
    })
    eosb_article87_fraction_ar["sections"][3]["body"] = (
        eosb_article87_fraction_ar["sections"][3]["body"]
        .replace("مدة الخدمة 6 سنوات", "مدة الخدمة 4.5 سنوات")
        .replace("42,000 ريال", "27,000 ريال")
    )
    article87_fraction_ar = validate_article(
        eosb_article87_fraction_ar, topic=topic_by_id("eosb-full-entitlement"),
        lang="ar", published_at="2026-01-01")
    eosb_article87_fraction_en = fixture_data("en", topic_id="eosb-full-entitlement")
    eosb_article87_fraction_en["calculation_example"].update({
        "years": "4.5", "months": "0", "days": "0",
        "full_benefit": "27000", "payable_benefit": "27000",
    })
    eosb_article87_fraction_en["sections"][3]["body"] = (
        eosb_article87_fraction_en["sections"][3]["body"]
        .replace("six years of service", "4.5 years of service")
        .replace("42,000", "27,000")
    )
    article87_fraction_en = validate_article(
        eosb_article87_fraction_en, topic=topic_by_id("eosb-full-entitlement"),
        lang="en", published_at="2026-01-01")
    check("المادة 87: يقبل 4.5 سنوات في اللغتين ويحسب المكافأة كاملة تناسبياً دون نسبة الاستقالة",
          article87_fraction_ar["calculation_example"]["full_benefit"] == "27000.00"
          and article87_fraction_ar["calculation_example"]["payable_benefit"] == "27000.00"
          and article87_fraction_en["calculation_example"]["full_benefit"] == "27000.00"
          and article87_fraction_en["calculation_example"]["payable_benefit"] == "27000.00"
          and not validate_eosb_translation_pair(article87_fraction_ar, article87_fraction_en))

    eosb_components = fixture_data("ar", topic_id="labor-art85")
    eosb_components["calculation_example"].update({
        "years": "6", "months": "6", "days": "15",
        "full_benefit": "48493.15", "payable_benefit": "32328.77",
    })
    eosb_components["sections"][3]["body"] = (
        eosb_components["sections"][3]["body"]
        .replace("مدة الخدمة 6 سنوات", "مدة الخدمة 6 سنوات و6 أشهر و15 يوماً")
        .replace("42,000 ريال", "48,493.15 ريال")
        .replace("28,000 ريال", "32,328.77 ريال")
    )
    components_article = validate_article(
        eosb_components, topic=eosb_topic, lang="ar", published_at="2026-01-01")
    check("تدقيق EOSB: يحتسب 6 سنوات و6 أشهر و15 يوماً وفق التناسب بالأيام",
          components_article["calculation_example"]["full_benefit"] == "48493.15"
          and components_article["calculation_example"]["payable_benefit"] == "32328.77")

    eosb_fraction_double_count = fixture_data("ar", topic_id="labor-art85")
    eosb_fraction_double_count["calculation_example"].update({
        "years": "6.5", "months": "6", "days": "15",
    })
    check("تدقيق EOSB: يمنع جمع سنوات كسرية مع أشهر/أيام تسبب احتساب المدة مرتين",
          _rejects(lambda: validate_article(
              eosb_fraction_double_count, topic=eosb_topic, lang="ar", published_at="2026-01-01")))

    eosb_partial = fixture_data("ar", topic_id="labor-art85")
    eosb_partial["calculation_example"].update({
        "years": "4", "months": "6", "full_benefit": "27000",
        "payable_benefit": "9000",
    })
    eosb_partial["sections"][3]["body"] = (
        eosb_partial["sections"][3]["body"]
        .replace("مدة الخدمة 6 سنوات", "مدة الخدمة 4 سنوات و6 أشهر")
        .replace("42,000 ريال", "27,000 ريال")
        .replace("28,000 ريال", "9,000 ريال")
    )
    check("تدقيق EOSB: يحتسب كسر السنة تناسبياً قبل تطبيق ثلث المكافأة",
          not _rejects(lambda: validate_article(
              eosb_partial, topic=eosb_topic, lang="ar", published_at="2026-01-01")))

    non_eosb_topic = topic_by_id("net-salary-calculation")
    non_eosb_data = fixture_data("ar", topic_id="net-salary-calculation")
    check("تدقيق EOSB: الحقول الفارغة مقبولة للموضوعات غير المرتبطة بالمكافأة",
          not _rejects(lambda: validate_article(
              non_eosb_data, topic=non_eosb_topic, lang="ar", published_at="2026-01-01")))
    non_eosb_data["calculation_example"]["monthly_wage"] = "12000"
    check("تدقيق EOSB: يمنع تمرير بيانات مكافأة على موضوع آخر",
          _rejects(lambda: validate_article(
              non_eosb_data, topic=non_eosb_topic, lang="ar", published_at="2026-01-01")))

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
    _art85_en_for_render = validate_article(
        fixture_data("en", topic_id="labor-art85"),
        topic=eosb_topic, lang="en", published_at="2026-01-01")
    _art85_en_html = render_article_html(_art85_en_for_render, published=True)
    check("المادة 85 الإنجليزية: مصادر رسمية بعناوين إنجليزية وروابط الوزارة المعتمدة",
          all(title in _art85_en_html and url in _art85_en_html
              for title, url in ARTICLE85_ENGLISH_SOURCES))
    check("كود Social Bar مرة واحدة", html_out.count(AD_SOCIAL_BAR) == 1)
    check("حاوية الإعلان مرة واحدة", html_out.count("container-7af3b8325dba6708da88eed5e517ec89") == 1)
    check("صفحة منشورة قابلة للفهرسة", "noindex" not in html_out)
    check("صفحة مسودة غير قابلة للفهرسة", "noindex" in draft_out)
    check("المسودة لا تعرض روابط لغة مقابلة غير متاحة",
          'hreflang=' not in draft_out
          and "Read this guide in English" not in draft_out
          and "اقرأ هذا الدليل بالعربية" not in draft_out)
    check("JSON-LD صالح", '"@type": "Article"' in html_out)
    _format_probe = dict(art)
    _format_probe["sections"] = [dict(section) for section in art["sections"]]
    _format_probe["sections"][0]["body"] = "Formatting marker remains contiguous with SAR 12,000."
    _format_probe["sections"][0]["bullets"] = []
    _format_probe_html = render_article_html(_format_probe, published=True)
    check("عرض المقال: يحتفظ HTML النهائي بالنص والأرقام ككتلة منسّقة",
          "Formatting marker remains contiguous" in _format_probe_html
          and '<bdi class="numeric" dir="ltr">SAR 12,000</bdi>' in _format_probe_html)
    _formatted_bullets = render_article_body(
        "Key points: • one **important** rule applies. • SAR 12,000 is the example amount. Further explanation follows."
    )
    check("عرض المقال: تحويل التعداد المضمّن إلى قائمة HTML",
          '<ul class="article-list">' in _formatted_bullets
          and _formatted_bullets.count("<li>") == 2)
    check("عرض المقال: تنسيق النص الغامق والأرقام النقدية",
          "<strong>important</strong>" in _formatted_bullets
          and '<bdi class="numeric" dir="ltr">SAR 12,000</bdi>' in _formatted_bullets)
    _formatted_ratio = render_inline_prose("The ratio is 1/3 and the range is >5–<10 years.")
    check("عرض المقال: إبقاء الكسر والنطاق الرقمي متماسكين لاتجاه النص",
          '<bdi class="numeric" dir="ltr">1/3</bdi>' in _formatted_ratio
          and '&gt;5–&lt;10' in _formatted_ratio)
    _formatted_steps = render_article_body("Steps: 1. Calculate the base amount. 2. Apply the ratio.")
    check("عرض المقال: تحويل الخطوات المرقمة إلى قائمة مرتبة",
          '<ol class="article-list">' in _formatted_steps
          and _formatted_steps.count("<li>") == 2)
    _stable_lists = render_article_body(
        "Steps: 1. Calculate the base amount: • half a month per year. • a full month after five years. "
        "\u200f2. Apply the resignation ratio."
    )
    check("عرض المقال: يعالج علامات اتجاه النص المخفية ويُبقي ترقيم الخطوات متسلسلاً",
          '<ol class="article-list" start="2">' in _stable_lists
          and '<ul class="article-list"><li>half a month per year.</li><li>a full month after five years.</li></ul>' in _stable_lists
          and '<bdi class="numeric" dir="ltr">2</bdi>.' not in _stable_lists)

    _single_colon_substep = render_article_body(
        "3. Apply the ratio: - from two years to five years. 4. Check the result."
    )
    check("عرض المقال: يحوّل الشرطة المفردة بعد النقطتين إلى تعداد فرعي مستقل",
          '<ul class="article-list"><li>from two years to five years.</li></ul>' in _single_colon_substep
          and '<ol class="article-list" start="4">' in _single_colon_substep)
    _punctuation_spacing = render_inline_prose("Article 84 . المادة 85 : SAR 12,000 .")
    check("عرض المقال: يصلح المسافة الخاطئة قبل علامات الترقيم والأرقام",
          "84</bdi>." in _punctuation_spacing
          and "85</bdi>:" in _punctuation_spacing
          and "12,000</bdi>." in _punctuation_spacing
          and "</bdi> ." not in _punctuation_spacing
          and "</bdi> :" not in _punctuation_spacing)
    _article_numbers_prose = render_article_body(
        "Articles 84 and 86. The key points are: • first rule applies. • second rule applies."
    )
    check("عرض المقال: أرقام مواد النظام لا تتحول إلى عناصر قائمة",
          '<ul class="article-list">' in _article_numbers_prose
          and '<ol class="article-list">' not in _article_numbers_prose)
    _clean_faq_artifact = render_article_body("Common Questions FAQ FAQ FAQ FAQ For resignation, check the rules.")
    check("عرض المقال: حذف تكرار FAQ الذي يسرّب من التوليد",
          "FAQ" not in _clean_faq_artifact and "Common Questions" not in _clean_faq_artifact)
    _escaped_formatted = render_article_body("Do not render <script>alert(1)</script>; use 28,000.")
    check("عرض المقال: لا يسمح بتمرير HTML خام مع تنسيق الأرقام",
          "<script>" not in _escaped_formatted and "&lt;script&gt;" in _escaped_formatted
          and '<bdi class="numeric" dir="ltr">28,000</bdi>' in _escaped_formatted)

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

    def _envelope(lang, topic_id="eosb-basics"):
        text = json.dumps(fixture_data(lang, topic_id=topic_id), ensure_ascii=False)
        blob = {"candidates": [{"content": {"parts": [{"text": text}]}}]}
        return 200, {}, json.dumps(blob, ensure_ascii=False).encode("utf-8")

    def _groq_envelope(content=None, lang=None, finish="stop", topic_id="eosb-basics"):
        """ظرف Groq (OpenAI-compatible) بنصّ JSON داخل message.content."""
        if content is None:
            content = json.dumps(fixture_data(lang, topic_id=topic_id), ensure_ascii=False)
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

    def _topic_id_from_prompt(prompt):
        line = next((value.strip() for value in prompt.splitlines()
                     if value.startswith("الموضوع: ")), "")
        title = line.removeprefix("الموضوع: ").strip()
        for candidate in TOPICS:
            if title in (candidate.get("title_ar"), candidate.get("title_en")):
                return candidate["id"]
        return "eosb-basics"

    def _provider_of(url):
        return "groq" if "api.groq.com" in url else "gemini"

    def _fake_by_lang(en_ok):
        """503 للنسخة العربية دائماً، و(503 أو نجاح) للنسخة الإنجليزية — بحسب شكل الطلب.

        طلبات فحص المصادر الرسمية (GET بلا جسم: `data=None`) تُقابَل بمصدر متاح،
        فيبقى التصنيف المقصود (`draft` أو `draft_unverified`) محكوماً بمحاكاة التوليد لا بالمصادر.
        """
        calls = {"ar": 0, "en": 0}
        urls = []

        def _fn(url, **kwargs):
            urls.append(url)
            if kwargs.get("data") is None:   # طلب فحص مصدر رسمي (GET بلا جسم)
                return 200, {}, b"<html>" + b"s" * 2000 + b"</html>", url
            prompt = _request_prompt(kwargs)
            lang = "en" if "لغة المخرجات: English" in prompt else "ar"
            topic_id = _topic_id_from_prompt(prompt)
            calls[lang] += 1
            if lang == "en" and en_ok:
                ok_env = (_groq_envelope(lang=lang, topic_id=topic_id)
                          if _provider_of(url) == "groq" else _envelope(lang, topic_id=topic_id))
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

        # (أ-0) حماية fail-closed: auto + skip_source_check يُرفض قبل شبكة/كتابة.
        _sandbox()
        _publish_guard_before = (ARTICLES_JSON.read_bytes(), SITEMAP_XML.read_bytes())
        _publish_guard_calls = []

        def _publish_guard_http(url, **kwargs):
            _publish_guard_calls.append(url)
            return 500, {}, b'{"error":{"message":"must not be called"}}', url

        globals()["http_request_full"] = _publish_guard_http
        _publish_guard_rc = run_once(
            mode="auto", provider="groq", api_key=_FAKE_GROQ_KEY,
            skip_source_check=True)
        check("حماية النشر: auto + skip_source_check مرفوض قبل الشبكة والكتابة",
              _publish_guard_rc == EXIT_UNSAFE_PUBLISH_CONFIG
              and not _publish_guard_calls
              and (ARTICLES_JSON.read_bytes(), SITEMAP_XML.read_bytes()) == _publish_guard_before
              and not DRAFTS_DIR.exists() and not ARTICLES_DIR.exists()
              and not STATE_JSON.exists())

        # (أ-1) حماية طبقة GitHub Actions: البوابة تسبق خطوة تشغيل التوليد.
        _workflow_path = BASE_DIR / ".github" / "workflows" / "ai_marketing.yml"
        try:
            _workflow_text = _workflow_path.read_text(encoding="utf-8")
        except OSError:
            _workflow_text = ""
        _workflow_gate = 'if [ "${MODE}" = "auto" ] && [ "${SKIP_SOURCE_CHECK_INPUT}" = "true" ]; then'
        _workflow_gate_pos = _workflow_text.find(_workflow_gate)
        _workflow_run_pos = _workflow_text.find("- name: تشغيل دورة إنتاج المحتوى")
        check("Workflow: يرفض auto + skip_source_check قبل بدء توليد المحتوى",
              _workflow_gate_pos >= 0 and _workflow_run_pos >= 0
              and _workflow_gate_pos < _workflow_run_pos)

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
              and backoff_delay(0, retry_after="600") == 600.0
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

        # اختبار إصلاح قانوني واحد: الاستجابة الأولى تفتقد تحذير الإشعار،
        # والثانية تضيف العبارات النظامية؛ لا نتجاوز البوابة ولا نكتب ملفات عامة.
        _sandbox()
        _repair_before = (ARTICLES_JSON.read_bytes(), SITEMAP_XML.read_bytes())
        _repair_calls, _repair_requests = {"ar": 0, "en": 0}, []
        _legal_repair_ar = (
            " تنطبق نسبة الثلث على مدة خدمة من سنتين حتى خمس سنوات شاملةً خمس سنوات، "
            "ولا تنطبق نسبة الثلثين إلا إذا كانت مدة الخدمة أكثر من خمس سنوات وأقل من عشر سنوات. "
            "عدم كون الإشعار شرطًا لاستحقاق المكافأة لا يعني أن الإشعار غير مطلوب لإنهاء العقد؛ "
            "فقد تبقى متطلبات الإشعار وإجراءات الاستقالة واجبة بحسب نوع العقد والأحكام النظامية المنطبقة. "
            "وفق المادة 86، يجوز بالاتفاق استبعاد العمولات والنسب المئوية عن المبيعات وما يماثلها "
            "من عناصر الأجر التي تكون بطبيعتها قابلة للزيادة والنقص من الأجر الذي تُحسب على أساسه "
            "مكافأة نهاية الخدمة؛ ولا يعني ذلك استبعاد الأجر الأساسي. "
            "المادة 81 تتعلق بحالات نظامية يترك فيها العامل العمل دون إشعار مع احتفاظه بحقوقه، "
            "ولا تمثل فصلًا من صاحب العمل."
        )

        def _article85_repair_http(url, **kwargs):
            request = json.loads(kwargs["data"].decode("utf-8"))
            _repair_requests.append(request)
            request_prompt = _request_prompt(kwargs)
            lang = "en" if "لغة المخرجات: English" in request_prompt else "ar"
            _repair_calls[lang] += 1
            data = fixture_data(lang, topic_id="labor-art85")
            if lang == "ar" and _repair_calls[lang] == 1:
                data = ensure_article85_notice_caveat(data, lang="ar")
                data["sections"][0]["body"] += " لا يستبعد الأجر الأساسي إلا باتفاق."
            else:
                data["sections"][0]["body"] += _legal_repair_ar
            return _groq_envelope(content=json.dumps(data, ensure_ascii=False)) + (url,)

        _repair_base_prompt = build_prompt(topic_by_id("labor-art85"), "ar")
        _repair_prompt = build_article85_repair_prompt(
            _repair_base_prompt, lang="ar", reason="المادة 85: تحذير الإشعار ناقص")
        _repair_prompt_en86 = build_article85_repair_prompt(
            build_prompt(topic_by_id("labor-art85"), "en"),
            lang="en", reason="Article 86: missing agreement")
        _repair_prompt_ar_suffix = _repair_prompt.rsplit(chr(10) * 2, 1)[-1]
        _repair_prompt_en86_suffix = _repair_prompt_en86.rsplit(chr(10) * 2, 1)[-1]
        _repair_prompt_en_short = build_article85_repair_prompt(
            build_prompt(topic_by_id("labor-art85"), "en"),
            lang="en", reason="sections[10].body: الطول 73 خارج المدى 120-8000")
        _repair_prompt_en_sections = build_article85_repair_prompt(
            build_prompt(topic_by_id("labor-art85"), "en"),
            lang="en", reason="sections: العدد 14 خارج المدى 3-12")
        _repair_prompt_ar_minimum = build_article85_repair_prompt(
            build_prompt(topic_by_id("labor-art85"), "ar"),
            lang="ar", reason="المادة 85: إجابة الحد الأدنى متناقضة مع شرط السنتين")
        _repair_prompt_en_notice_loss = build_article85_repair_prompt(
            build_prompt(topic_by_id("labor-art85"), "en"),
            lang="en", reason="Article 85: do not claim notice non-compliance automatically reduces the award")
        _repair_prompt_en_empty = build_article85_repair_prompt(
            build_prompt(topic_by_id("labor-art85"), "en"),
            lang="en", reason="sections[5].body: فارغ")
        _repair_prompt_ar_money = build_article85_repair_prompt(
            build_prompt(topic_by_id("labor-art85"), "ar"),
            lang="ar", reason="المثال الرقمي في النص يتضمن مبلغاً لا يطابق بيانات الحساب 30000.00")
        _repair_prompt_en_money = build_article85_repair_prompt(
            build_prompt(topic_by_id("labor-art85"), "en"),
            lang="en", reason="المثال الرقمي في النص يتضمن مبلغاً لا يطابق بيانات الحساب 30000.00")
        _strict_schema_retry_ar = build_groq_schema_repair_prompt(
            build_prompt(topic_by_id("labor-art85"), "ar"), lang="ar")
        _strict_schema_retry_en = build_groq_schema_repair_prompt(
            build_prompt(topic_by_id("labor-art85"), "en"), lang="en")
        _schema_missing_body = (
            '{"error":{"message":"Generated JSON does not match the expected schema. '
            'Error: jsonschema: missing properties: \'faq\', \'official_sources\', '
            '\'calculation_example\'","type":"invalid_request_error"}}'
        )
        _schema_flag = classify_failure(400, _schema_missing_body)
        _schema_message = format_failure(400, _schema_missing_body.encode("utf-8"), 1, GEMINI_MAX_TRIES)
        check("Groq: فشل الحقول الناقصة يُشخّص بدقة ولا يعيد الطلب المتماثل أربع مرات",
              _schema_flag[0] is False and _schema_flag[1] == "schema_incomplete"
              and "schema_missing_required" in _schema_message
              and "faq" in _schema_message and "official_sources" in _schema_message
              and "calculation_example" in _schema_message)
        check("Groq: محاولة المخطط الإضافية تبقي كل الحقول ومخطط JSON الصارم",
              all(key in _strict_schema_retry_ar for key in (
                  "title", "meta_description", "excerpt", "sections", "faq",
                  "official_sources", "calculation_example", "monthly_wage",
                  "payable_benefit", "لا تستخدم JSON mode"))
              and all(key in _strict_schema_retry_en for key in (
                  "title", "meta_description", "excerpt", "sections", "faq",
                  "official_sources", "calculation_example", "monthly_wage",
                  "payable_benefit", "do not switch to JSON mode"))
              and is_groq_incomplete_schema_failure(_schema_message))
        check("Article 85: الإصلاح موجه لسبب واحد وبعبارة تقريرية قصيرة",
              "المادة 85 تحدد نسب المكافأة عند الاستقالة فقط" in _repair_prompt_ar_suffix
              and "بحسب نوع العقد والأحكام النظامية المنطبقة" in _repair_prompt_ar_suffix
              and "وفق المادة 86" not in _repair_prompt_ar_suffix
              and "Under Article 86" in _repair_prompt_en86_suffix
              and "Every section body must contain 120 to 5000 characters" in _repair_prompt_en_short
              and "schema permits only 3 to 12 sections" in _repair_prompt_en_sections
              and "لا تقل إنه لا يوجد حد أدنى" in _repair_prompt_ar_minimum
              and "Do not claim that failure to comply with notice requirements" in _repair_prompt_en_notice_loss
              and "Do not leave any section body empty" in _repair_prompt_en_empty
              and "صحّح المثال الرقمي فقط" in _repair_prompt_ar_money
              and "SAR 42,000" in _repair_prompt_en_money
              and "SAR 28,000" in _repair_prompt_en_money
              and "Do not attribute to Article 85" not in _repair_prompt_en86_suffix)
        _stacked_ar = fixture_data("ar", topic_id="labor-art85")
        _stacked_ar["sections"][0]["body"] += (
            " يرد هنا ذكر الإشعار عند الاستقالة. وتستحق نسبة الثلثين في حالة الاستقالة. "
            "وفق المادة 86، يجوز بالاتفاق الصريح استبعاد العمولات ونسب المبيعات والعناصر المشابهة "
            "إذا كانت بطبيعتها قابلة للزيادة والنقص؛ ولا يعني ذلك استبعاد الأجر الأساسي. "
            "المادة 81 تخص حالات نظامية يترك فيها العامل العمل دون إشعار مع احتفاظه بحقوقه، وليست فصلاً من صاحب العمل."
        )
        _stacked_ar_before = json.dumps(_stacked_ar, ensure_ascii=False, sort_keys=True)
        _stacked_ar_data, _stacked_ar_article, _stacked_ar_fixes, _stacked_ar_error = (
            repair_article85_deterministic_omissions(
                _stacked_ar, topic=topic_by_id("labor-art85"), lang="ar",
                published_at=today_iso())
        )
        _stacked_en = fixture_data("en", topic_id="labor-art85")
        _stacked_en["excerpt"] = (
            "This is a helpful introductory summary with practical information. " * 5
        )[:318]
        _stacked_en["sections"][0]["body"] += (
            " Notice may apply when a worker resigns. Article 85 discusses the two-thirds ratio. "
            "Under Article 86, qualifying commissions, sales percentages and similar wage elements naturally subject "
            "to increase or decrease may be excluded only by explicit agreement; this does not exclude basic wage. "
            "Article 81 concerns a worker leaving without notice in statutory cases while retaining rights, not employer dismissal."
        )
        _stacked_en_before = json.dumps(_stacked_en, ensure_ascii=False, sort_keys=True)
        _stacked_en_data, _stacked_en_article, _stacked_en_fixes, _stacked_en_error = (
            repair_article85_deterministic_omissions(
                _stacked_en, topic=topic_by_id("labor-art85"), lang="en",
                published_at=today_iso())
        )
        check("Article 85: الإصلاحات المحددة المتراكبة تُطبق بالتتابع دون استدعاء نموذج إضافي",
              _stacked_ar_article is not None and _stacked_en_article is not None
              and "notice caveat" in _stacked_ar_fixes
              and "two-thirds boundary" in _stacked_ar_fixes
              and "excerpt length" in _stacked_en_fixes
              and "notice caveat" in _stacked_en_fixes
              and "two-thirds boundary" in _stacked_en_fixes
              and len(_stacked_en_data["excerpt"]) <= 300
              and json.dumps(_stacked_ar, ensure_ascii=False, sort_keys=True) == _stacked_ar_before
              and json.dumps(_stacked_en, ensure_ascii=False, sort_keys=True) == _stacked_en_before
              and not _stacked_ar_error and not _stacked_en_error)
        # Known Article 85/86 omissions and short bodies should be repaired without a second model call.
        for _article86_lang, _article86_bad_claim in (
            ("ar", "لا يستبعد الأجر الأساسي إلا باتفاق."),
            ("en", "The basic wage may be excluded by agreement."),
        ):
            _article86_bad = fixture_data(_article86_lang, topic_id="labor-art85")
            _article86_bad["sections"][0]["body"] += " " + _article86_bad_claim
            _article86_original = json.dumps(_article86_bad, ensure_ascii=False, sort_keys=True)
            check(f"Article 86: بوابة الجودة ترفض ادعاء استبعاد الأجر الأساسي ({_article86_lang})",
                  _rejects(lambda: validate_article85_legal_claims(
                      _article86_bad_claim, lang=_article86_lang)))
            _article86_fixed = ensure_article85_article86_clause(_article86_bad, lang=_article86_lang)
            _article86_text = " ".join(
                str(section.get("heading", "")) + " " + str(section.get("body", "")) + " "
                + " ".join(str(bullet) for bullet in section.get("bullets", []))
                for section in _article86_fixed["sections"] if isinstance(section, dict)
            )
            _article86_clause = (
                "وفق المادة 86، يجوز بالاتفاق الصريح استبعاد العمولات" if _article86_lang == "ar"
                else "Under Article 86, commissions, sales percentages"
            )
            check(f"Article 86: الإصلاح الحتمي يضيف القاعدة الدقيقة ويزيل الادعاء عن الأجر الأساسي ({_article86_lang})",
                  _article86_clause in _article86_text
                  and _article86_bad_claim not in _article86_text
                  and json.dumps(_article86_bad, ensure_ascii=False, sort_keys=True) == _article86_original)

        for _short_lang in ("ar", "en"):
            _short_data = fixture_data(_short_lang, topic_id="labor-art85")
            _short_index = 2
            _short_body = ("شرح موجز لهذه النقطة القانونية مع مراعاة العقد والوقائع." if _short_lang == "ar"
                           else "A short explanation of this point under the applicable contract and facts.")
            _short_data["sections"][_short_index]["body"] = _short_body
            _short_original = json.dumps(_short_data, ensure_ascii=False, sort_keys=True)
            _short_length = len(_short_body)
            _short_repaired, _short_action = repair_short_article85_section(
                _short_data,
                reason=f"sections[{_short_index}].body: الطول {_short_length} خارج المدى 120-8000",
                lang=_short_lang,
            )
            check(f"Article 85: القسم القصير يُوسّع حتمياً دون فقد النص ({_short_lang})",
                  len(_short_repaired["sections"][_short_index]["body"]) >= 120
                  and _short_body in _short_repaired["sections"][_short_index]["body"]
                  and json.dumps(_short_data, ensure_ascii=False, sort_keys=True) == _short_original)

        # Regression: the model can return an incorrect minimum-service FAQ even when the article body is sound.
        for _faq_lang in ("ar", "en"):
            _faq_bad = fixture_data(_faq_lang, topic_id="labor-art85")
            if _faq_lang == "ar":
                _faq_bad["faq"][0] = {
                    "q": "ما الحد الأدنى لمدة الخدمة لاستحقاق مكافأة الاستقالة؟",
                    "a": "لا يوجد حد أدنى، لكن لا يستحق العامل مكافأة قبل سنتين متتاليتين من الخدمة.",
                }
            else:
                _faq_bad["faq"][0] = {
                    "q": "What is the minimum service period for a resignation award?",
                    "a": "There is no minimum, but no award is due before two consecutive years of service.",
                }
            _faq_fixed, _faq_changed = ensure_article85_minimum_faq(_faq_bad, lang=_faq_lang)
            _faq_answer = str(_faq_fixed["faq"][0]["a"])
            _faq_denial = ("لا يوجد حد أدنى" in _faq_answer) if _faq_lang == "ar" else ("There is no minimum" in _faq_answer)
            check(f"Article 85: يناقض FAQ الحد الأدنى يُصحَّح حتميًا ({_faq_lang})",
                  _faq_changed and not _faq_denial
                  and "سنتين" in _faq_answer if _faq_lang == "ar"
                  else _faq_changed and not _faq_denial and "two consecutive years" in _faq_answer)

        # Regression: duplicate example headings are folded into a non-example section without dropping their prose/bullets.
        _dup_example = fixture_data("en", topic_id="labor-art85")
        _dup_heading = "Additional Example — alternative reader context"
        _dup_body = (
            "This original supplemental explanation must be preserved verbatim during safe restructuring. "
            "It describes how a reader should compare their contract terms, employment dates, and applicable facts "
            "with the official statutory text before drawing a conclusion about a personal case."
        )
        _dup_bullet = "Preserve this bullet from the additional example section"
        _dup_example["sections"].append({
            "heading": _dup_heading,
            "body": _dup_body,
            "bullets": [_dup_bullet],
        })
        _dup_original = json.dumps(_dup_example, ensure_ascii=False, sort_keys=True)
        _dup_fixed, _dup_actions = merge_duplicate_article85_example_sections(_dup_example, lang="en")
        _dup_sections = _dup_fixed["sections"]
        _dup_nonexample_text = " ".join(
            str(sec.get("body", "")) + " " + " ".join(sec.get("bullets") or [])
            for sec in _dup_sections if isinstance(sec, dict)
            and not re.search(r"(?:مثال|example)", str(sec.get("heading", "")), re.I)
        )
        check("Article 85: يُدمج المثال الإضافي مع الحفاظ على العنوان والنص والنقاط",
              len([sec for sec in _dup_sections if re.search(r"(?:مثال|example)", str(sec.get("heading", "")), re.I)]) == 1
              and _dup_heading in _dup_nonexample_text
              and _dup_body in _dup_nonexample_text
              and _dup_bullet in _dup_nonexample_text
              and "duplicate example section merged" in " ".join(_dup_actions)
              and json.dumps(_dup_example, ensure_ascii=False, sort_keys=True) == _dup_original)

        # Critical preflight must guarantee the notice and Article 86 caveats independently of model wording.
        for _critical_lang in ("ar", "en"):
            _critical = fixture_data(_critical_lang, topic_id="labor-art85")
            _critical["sections"][0]["body"] = (
                _critical["sections"][0]["body"].replace(
                    "وقد تبقى متطلبات الإشعار وإجراءات الاستقالة واجبة بحسب نوع العقد والأحكام النظامية المنطبقة.", ""
                ).replace(
                    "Applicable notice requirements and resignation procedures may still apply depending on the contract and law.", ""
                )
            )
            _critical, _critical_actions = ensure_article85_critical_content(_critical, lang=_critical_lang)
            _critical_text = " ".join(
                str(sec.get("heading", "")) + " " + str(sec.get("body", ""))
                for sec in _critical["sections"] if isinstance(sec, dict)
            )
            _notice_present = (
                "متطلبات الإشعار" in _critical_text if _critical_lang == "ar"
                else "notice requirements" in _critical_text and "may still apply" in _critical_text
            )
            _article86_present = (
                "وفق المادة 86، يجوز بالاتفاق الصريح استبعاد العمولات" in _critical_text
                if _critical_lang == "ar"
                else "Under Article 86, commissions, sales percentages" in _critical_text
            )
            check(f"Article 85: يضمن preflight توضيح الإشعار والمادة 86 ({_critical_lang})",
                  _notice_present and _article86_present)

        # A narrowly scoped deterministic repair avoids a second model call for known notice-loss claims.
        for _notice_lang, _notice_bad_claim in (
            ("ar", "عدم الالتزام بالإشعار قد يؤدي إلى خفض مكافأة نهاية الخدمة."),
            ("en", "Failure to comply with notice may lead to a reduction of the end-of-service award."),
        ):
            _notice_bad = fixture_data(_notice_lang, topic_id="labor-art85")
            _notice_bad["sections"][0]["body"] += " " + _notice_bad_claim
            _notice_original = json.dumps(_notice_bad, ensure_ascii=False, sort_keys=True)
            _notice_data, _notice_article, _notice_fixes, _notice_error = (
                repair_article85_deterministic_omissions(
                    _notice_bad, topic=topic_by_id("labor-art85"), lang=_notice_lang,
                    published_at=today_iso())
            )
            _notice_repaired_text = json.dumps(_notice_data, ensure_ascii=False)
            check(f"Article 85: claim الإشعار لا يفقد/يخفض المكافأة يُصلح حتمياً ({_notice_lang})",
                  _notice_article is not None and "notice loss claim" in _notice_fixes
                  and _notice_bad_claim not in _notice_repaired_text
                  and _notice_error == ""
                  and json.dumps(_notice_bad, ensure_ascii=False, sort_keys=True) == _notice_original)

        _fixture_for_notice = fixture_data("ar", topic_id="labor-art85")
        _fixture_original_text = json.dumps(_fixture_for_notice, ensure_ascii=False)
        _fixture_with_caveat = ensure_article85_notice_caveat(_fixture_for_notice, lang="ar")
        _fixture_with_caveat_text = " ".join(
            str(sec.get("body", "")) for sec in _fixture_with_caveat.get("sections", [])
            if isinstance(sec, dict))
        check("Article 85: إدراج توضيح الإشعار القياسي لا يغيّر الكائن الأصلي",
              "وقد تبقى متطلبات الإشعار وإجراءات الاستقالة واجبة بحسب نوع العقد والأحكام النظامية المنطبقة."
              in _fixture_with_caveat_text
              and json.dumps(_fixture_for_notice, ensure_ascii=False) == _fixture_original_text)
        _fixture_for_boundary = fixture_data("ar", topic_id="labor-art85")
        _fixture_for_boundary["sections"][0]["body"] = re.sub(
            r"أكثر من خمس سنوات", "حتى خمس سنوات", _fixture_for_boundary["sections"][0]["body"])
        _boundary_original = json.dumps(_fixture_for_boundary, ensure_ascii=False)
        _fixture_with_boundary = ensure_article85_boundary_caveat(_fixture_for_boundary, lang="ar")
        _fixture_boundary_text = " ".join(
            str(sec.get("body", "")) for sec in _fixture_with_boundary.get("sections", [])
            if isinstance(sec, dict))
        check("Article 85: إضافة حدّ الثلثين القياسي تنجح ولا تعدل الكائن الأصلي",
              "أكثر من خمس سنوات وأقل من عشر سنوات" in _fixture_boundary_text
              and json.dumps(_fixture_for_boundary, ensure_ascii=False) == _boundary_original)
        _empty_shell_ar = fixture_data("ar", topic_id="labor-art85")
        _empty_shell_ar["sections"][0]["body"] = ""
        _empty_shell_ar["sections"][0]["bullets"] = []
        _empty_shell_original = json.dumps(_empty_shell_ar, ensure_ascii=False, sort_keys=True)
        _empty_shell_data, _empty_shell_article, _empty_shell_fixes, _empty_shell_error = (
            repair_article85_deterministic_omissions(
                _empty_shell_ar, topic=topic_by_id("labor-art85"), lang="ar",
                published_at=today_iso())
        )
        check("Article 85: دمج العنوان الفارغ يحافظ على العنوان ولا يسقط محتوى",
              _empty_shell_article is not None
              and any("أساس الحساب" in sec["body"] for sec in _empty_shell_data["sections"])
              and any("empty section merged" in fix for fix in _empty_shell_fixes)
              and len(_empty_shell_data["sections"]) >= MIN_SECTIONS
              and json.dumps(_empty_shell_ar, ensure_ascii=False, sort_keys=True) == _empty_shell_original
              and not _empty_shell_error)

        _empty_bullets_en = fixture_data("en", topic_id="labor-art85")
        _empty_bullets_en["sections"][0]["body"] = ""
        _empty_note = "This supplemental practical note must remain available after the empty section is repaired."
        _empty_bullets_en["sections"][0]["bullets"] = [_empty_note]
        _empty_bullets_original = json.dumps(_empty_bullets_en, ensure_ascii=False, sort_keys=True)
        _empty_bullets_data, _empty_bullets_article, _empty_bullets_fixes, _empty_bullets_error = (
            repair_article85_deterministic_omissions(
                _empty_bullets_en, topic=topic_by_id("labor-art85"), lang="en",
                published_at=today_iso())
        )
        check("Article 85: إصلاح القسم ذي body الفارغ يحافظ على العنوان وbullets المفيدة",
              _empty_bullets_article is not None
              and any("empty section merged" in fix for fix in _empty_bullets_fixes)
              and any("Calculation Basis" in sec["body"] for sec in _empty_bullets_data["sections"])
              and any(_empty_note in sec["body"] for sec in _empty_bullets_data["sections"])
              and len(_empty_bullets_data["sections"]) >= MIN_SECTIONS
              and json.dumps(_empty_bullets_en, ensure_ascii=False, sort_keys=True) == _empty_bullets_original
              and not _empty_bullets_error)

        # Regression: an empty final section previously put len(sections) in the sort candidates.
        _empty_tail_en = fixture_data("en", topic_id="labor-art85")
        _empty_tail_index = len(_empty_tail_en["sections"]) - 1
        _empty_tail_heading = "Trailing notice section"
        _empty_tail_bullet = "Keep this trailing-section point after repair."
        _empty_tail_en["sections"][_empty_tail_index].update({
            "heading": _empty_tail_heading, "body": "", "bullets": [_empty_tail_bullet],
        })
        _empty_tail_original = json.dumps(_empty_tail_en, ensure_ascii=False, sort_keys=True)
        _empty_tail_fixed, _empty_tail_action = repair_empty_article85_section(
            _empty_tail_en, reason=f"sections[{_empty_tail_index}].body: فارغ", lang="en")
        check("Article 85: إصلاح آخر قسم فارغ لا يسبب list index out of range ويحفظ العنوان والنقاط",
              len(_empty_tail_fixed["sections"]) == len(_empty_tail_en["sections"]) - 1
              and any(_empty_tail_heading in sec["body"] for sec in _empty_tail_fixed["sections"])
              and any(_empty_tail_bullet in sec["body"] for sec in _empty_tail_fixed["sections"])
              and "empty section merged" in _empty_tail_action
              and json.dumps(_empty_tail_en, ensure_ascii=False, sort_keys=True) == _empty_tail_original)

        # Critical Article 85 wording and the fixed worked example must not depend on model luck.
        _canonicalized = {}
        _canonical_inputs_before = {}
        for _canonical_lang in ("ar", "en"):
            _canonical_input = fixture_data(_canonical_lang, topic_id="labor-art85")
            _canonical_input["calculation_example"]["payable_benefit"] = "30000"
            _canonical_example_sec = next(
                sec for sec in _canonical_input["sections"]
                if re.search(r"(?:مثال|example)", sec["heading"], re.I))
            _canonical_example_sec["body"] = (
                "Wrong example: SAR 30,000." if _canonical_lang == "en"
                else "مثال غير صحيح: 30,000 ريال.")
            _canonical_inputs_before[_canonical_lang] = json.dumps(
                _canonical_input, ensure_ascii=False, sort_keys=True)
            _canonicalized[_canonical_lang] = ensure_article85_critical_content(
                _canonical_input, lang=_canonical_lang)
            check(f"Article 85: canonicalizer لا يعدّل مدخل {_canonical_lang} الأصلي",
                  json.dumps(_canonical_input, ensure_ascii=False, sort_keys=True)
                  == _canonical_inputs_before[_canonical_lang])
        _critical_ar, _critical_ar_fixes = _canonicalized["ar"]
        _critical_en, _critical_en_fixes = _canonicalized["en"]
        _critical_ar_text = " ".join(sec["heading"] + " " + sec["body"]
                                     for sec in _critical_ar["sections"])
        _critical_en_text = " ".join(sec["heading"] + " " + sec["body"]
                                     for sec in _critical_en["sections"])
        check("Article 85: حدّ الثلثين والمثال الحسابي يُحقنان حتمياً قبل التحقق",
              _critical_ar["calculation_example"] == ARTICLE85_CANONICAL_VALUES
              and _critical_en["calculation_example"] == ARTICLE85_CANONICAL_VALUES
              and "أكثر من خمس سنوات وأقل من عشر سنوات" in _critical_ar_text
              and "more than five years and less than ten years" in _critical_en_text
              and "28,000 ريال" in _critical_ar_text and "SAR 28,000" in _critical_en_text
              and "30,000" not in _critical_ar_text and "30,000" not in _critical_en_text
              and "canonical example prose enforced" in _critical_ar_fixes
              and "canonical calculation values enforced" in _critical_en_fixes)

        _overflow_data = fixture_data("en", topic_id="labor-art85")
        for _n in range(10):
            _overflow_data["sections"].append({
                "heading": f"Supplemental section {_n}",
                "body": f"Supplemental retained content marker {_n}. " * 8,
                "bullets": [f"Supplemental bullet marker {_n}"],
            })
        _overflow_fixed = merge_article85_sections(_overflow_data, target_count=MAX_SECTIONS)
        _overflow_text = " ".join(sec["heading"] + " " + sec["body"] + " " +
                                  " ".join(sec["bullets"]) for sec in _overflow_fixed["sections"])
        check("Article 85: تقليل الأقسام الزائدة يحافظ على العناوين والنصوص والنقاط",
              len(_overflow_data["sections"]) == 14
              and len(_overflow_fixed["sections"]) == MAX_SECTIONS
              and all(f"Supplemental retained content marker {_n}." in _overflow_text
                      and f"Supplemental bullet marker {_n}" in _overflow_text
                      and f"Supplemental section {_n}" in _overflow_text
                      for _n in range(10)))
        _fixture_excerpt = fixture_data("en", topic_id="labor-art85")
        _fixture_excerpt["excerpt"] = ("This is a helpful introductory summary with practical information. " * 5)[:318]
        _trimmed_excerpt = trim_article85_excerpt(_fixture_excerpt)
        check("Article 85: قص excerpt الزائد قصاً محدوداً يحافظ على الحد الأعلى",
              len(_trimmed_excerpt["excerpt"]) <= 300
              and len(_trimmed_excerpt["excerpt"]) >= 40
              and len(_fixture_excerpt["excerpt"]) == 318)
        check("Article 85: إعادة الإصلاح محصورة بأخطاء الصياغة القانونية أو قِصر القسم",
              is_article85_legal_rejection("المادة 85: حد الخدمة غير واضح")
              and is_article85_legal_rejection("Article 86: missing agreement")
              and is_article85_repairable_rejection("sections[10].body: الطول 73 خارج المدى 120-8000")
              and is_article85_repairable_rejection("excerpt: الطول 318 خارج المدى 40-300")
              and is_article85_repairable_rejection("sections: العدد 14 خارج المدى 3-12")
              and is_article85_repairable_rejection("sections[5].body: فارغ")
              and is_article85_repairable_rejection("Article 85 boundary: conflicting five-to-ten-year two-thirds claim")
              and is_article85_repairable_rejection("المثال الرقمي في النص يتضمن مبلغاً لا يطابق بيانات الحساب 30000.00")
              and is_article85_repairable_rejection("المثال الرقمي في النص يجب أن يذكر الأجر والمكافأة الأساسية والمبلغ المستحق")
              and is_article85_repairable_rejection("calculation_example: موضوع المادة 85 يتطلب المثال الثابت")
              and not is_article85_repairable_rejection("sections: العدد 18 خارج المدى 3-12")
              and not is_article85_legal_rejection("حقول مطلوبة مفقودة: sections")
              and not is_article85_repairable_rejection("حقول مطلوبة مفقودة: sections"))

        globals()["http_request_full"] = _article85_repair_http
        _repair_rc, _repair_out = _capture_run(
            mode="draft", provider="groq", api_key=_FAKE_GROQ_KEY,
            model=DEFAULT_GROQ_MODEL, skip_source_check=True,
            topic_id="labor-art85", article_lang="ar")
        _repair_drafts = list(DRAFTS_DIR.glob("**/*.html"))
        check("Article 85: إصلاح المادة 86 حتمياً يجتاز البوابات ويحفظ مسودة فقط",
              _repair_rc == 0 and _repair_calls == {"ar": 1, "en": 0}
              and len(_repair_requests) == 1
              and "Article 86 rule enforced" in _repair_out
              and len(_repair_drafts) == 1
              and not ARTICLES_DIR.exists() and not SOCIAL_TXT.exists()
              and (ARTICLES_JSON.read_bytes(), SITEMAP_XML.read_bytes()) == _repair_before)
        check("Article 85: التوليد يبقي Groq على JSON Schema صارم وreasoning_effort=low",
              len(_repair_requests) == 1
              and all(r.get("reasoning_effort") == "low"
                      and (r.get("response_format") or {}).get("type") == "json_schema"
                      and ((r.get("response_format") or {}).get("json_schema") or {}).get("strict") is True
                      for r in _repair_requests))
        check("Article 85: إصلاح المادة 86 الحتمي لا يستدعي النموذج ثانية",
              len(_repair_requests) == 1
              and _repair_calls == {"ar": 1, "en": 0}
              and "Article 86 rule enforced" in _repair_out)

        # Regression: quality repair also covers non-Article-85 EOSB topics, without
        # importing Article 85's canonical example numbers or bypassing validation.
        check("الإصلاح العام: يقبل عيوب البنية والحساب المعروفة فقط",
              is_quality_repairable_rejection("sections[7].body: فارغ",
                                              topic_id="eosb-full-entitlement")
              and is_quality_repairable_rejection(
                  "calculation_example.full_benefit: المتوقع 42000.00 وليس 41900.00",
                  topic_id="eosb-full-entitlement")
              and not is_quality_repairable_rejection(
                  "calculation_example.full_benefit: المتوقع 42000.00 وليس 41900.00",
                  topic_id="salary-net-gosi-guide")
              and not is_quality_repairable_rejection(
                  "sections: العدد 18 خارج المدى 3-12",
                  topic_id="eosb-full-entitlement"))
        _generic_calc_prompt_ar = build_quality_repair_prompt(
            build_prompt(topic_by_id("eosb-full-entitlement"), "ar"), lang="ar",
            reason="calculation_example.full_benefit: المتوقع 42000.00 وليس 41900.00")
        _generic_empty_prompt_en = build_quality_repair_prompt(
            build_prompt(topic_by_id("eosb-full-entitlement"), "en"), lang="en",
            reason="sections[7].body: فارغ")
        check("الإصلاح العام: تعليمات ثنائية اللغة لا تفرض أرقام المادة 85 الثابتة",
              "أعد حساب المثال من حقول calculation_example المنظمة" in _generic_calc_prompt_ar
              and "A section body is empty" in _generic_empty_prompt_en
              and "42,000 ريال" not in _generic_calc_prompt_ar
              and "SAR 42,000" not in _generic_empty_prompt_en)

        _sandbox()
        _generic_before = (ARTICLES_JSON.read_bytes(), SITEMAP_XML.read_bytes())
        _generic_calls, _generic_requests = {"ar": 0, "en": 0}, []

        def _generic_quality_repair_http(url, **kwargs):
            request = json.loads(kwargs["data"].decode("utf-8"))
            _generic_requests.append(request)
            request_prompt = _request_prompt(kwargs)
            _generic_lang = "en" if "لغة المخرجات: English" in request_prompt else "ar"
            _generic_calls[_generic_lang] += 1
            generated = fixture_data(_generic_lang, topic_id="eosb-full-entitlement")
            if _generic_lang == "en":
                # Simulate a fluent but inconsistent second translation: its own
                # numbers and prose are valid in isolation, but differ from Arabic.
                generated["calculation_example"].update({
                    "monthly_wage": "15000", "years": "4", "months": "0", "days": "0",
                    "scenario": "article87", "full_benefit": "30000", "payable_benefit": "30000",
                })
                _example = generated["sections"][3]
                _example["body"] = (
                    _example["body"].replace("12,000", "15,000")
                    .replace("six years", "four years")
                    .replace("42,000", "30,000")
                )
            if _generic_calls[_generic_lang] == 1:
                if _generic_lang == "ar":
                    generated["calculation_example"]["full_benefit"] = "41900"
                else:
                    generated["sections"][0]["body"] = ""
            return _groq_envelope(content=json.dumps(generated, ensure_ascii=False)) + (url,)

        globals()["http_request_full"] = _generic_quality_repair_http
        _generic_rc, _generic_out = _capture_run(
            mode="draft", provider="groq", api_key=_FAKE_GROQ_KEY,
            model=DEFAULT_GROQ_MODEL, skip_source_check=True,
            topic_id="eosb-full-entitlement")
        _generic_drafts = list(DRAFTS_DIR.glob("**/*.html"))
        _generic_state = load_state()["topics"]["eosb-full-entitlement"]
        _generic_repair_prompts = [
            req["messages"][-1]["content"] for req in _generic_requests
            if isinstance(req.get("messages"), list) and req["messages"]
        ]
        check("الإصلاح العام: الحساب يُصحّح دون طلب API إضافي، والقسم الفارغ يحتاج إصلاحاً واحداً",
              _generic_rc == 0 and _generic_calls == {"ar": 1, "en": 2}
              and len(_generic_drafts) == 2
              and _generic_state.get("ar") == "draft" and _generic_state.get("en") == "draft"
              and "calculator-derived full benefit corrected" in _generic_out
              and "bilingual calculation example synchronized from Arabic version" in _generic_out
              and "[REJECT] مثال المكافأة مختلف بين النسختين" not in _generic_out
              and not ARTICLES_DIR.exists() and not SOCIAL_TXT.exists()
              and (ARTICLES_JSON.read_bytes(), SITEMAP_XML.read_bytes()) == _generic_before)
        check("الإصلاح العام: لا يرسل طلب إصلاح حسابي إلى النموذج ولا يفرض مبالغ المادة 85",
              len(_generic_requests) == 3
              and any("A section body is empty" in p for p in _generic_repair_prompts)
              and not any("SAR 42,000" in p or "42,000 ريال" in p
                          for p in _generic_repair_prompts))

        # أعد عزل مساحة الاختبار حتى لا تؤثر المسودة السابقة على اختبارات الإعداد.
        _sandbox()
        globals()["http_request_full"] = _no_network

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
            topic_id = _topic_id_from_prompt(prompt)
            return _groq_envelope(lang=lang, topic_id=topic_id) + (url,)

        globals()["http_request_full"] = _fake_groq_ok
        rc = run_once(mode="draft", provider="groq", api_key=_FAKE_GROQ_KEY,
                      skip_source_check=True)
        drafts = sorted(DRAFTS_DIR.glob("**/*.html"))
        check("Groq: ظرف JSON صالح يمرّ إلى بوابات التحقّق ويُحفظ مسودتين",
              rc == 0 and len(drafts) == 2 and len(_groq_reqs) == 2
              and all(r["url"] == GROQ_URL for r in _groq_reqs)
              and (ARTICLES_JSON.read_bytes(), SITEMAP_XML.read_bytes()) == before
              and load_state()["topics"][TOPICS[0]["id"]]["ar"] == "draft")
        check("Groq: الطلب يستخدم Structured Outputs (json_schema + strict) ويمرّر التعليمات",
              all(r["body"].get("response_format") == groq_response_format()
                  and r["body"]["response_format"]["type"] == "json_schema"
                  and r["body"]["response_format"]["json_schema"]["strict"] is True
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
        _retry_date = datetime(2026, 1, 1, 0, 0, 45, tzinfo=timezone.utc)
        _retry_now = datetime(2026, 1, 1, 0, 0, 0, tzinfo=timezone.utc)
        _retry_date_header = _retry_date.strftime("%a, %d %b %Y %H:%M:%S GMT")
        check("Retry-After: يقبل تاريخ HTTP ويفسره كمهلة صريحة",
              retry_after_seconds(_retry_date_header, now=_retry_now) == 45.0)
        fake, calls = _fake_http([
            (429, {"Retry-After": "7"}, b'{"error":{"message":"rate limit reached"}}'),
            _groq_envelope(lang="ar"),
        ])
        globals()["http_request_full"] = fake
        ok, data, msg = groq_generate_json("p", api_key=_FAKE_GROQ_KEY, model=DEFAULT_GROQ_MODEL)
        check("Groq: 429 مؤقّت يُعاد ويحترم Retry-After (ثوانٍ) ثم ينجح",
              bool(ok) and isinstance(data, dict) and msg == "ok"
              and len(calls) == 2 and _sleeps == [7.0])

        # (ي-1) استجابة TPM الواقعية: عبارات plan/billing لا تتغلب على مؤشّر المعدّل والمهلة.
        _sleeps.clear()
        _tpm_body = (
            b'{"error":{"message":"Rate limit reached for openai/gpt-oss-20b on tokens per '
            b'minute (TPM): Limit 8000, Used 6718, Requested 2581. Please try again in '
            b'9.7425s. Please check your plan and billing details."}}'
        )
        fake, calls = _fake_http([
            (429, {}, _tpm_body),
            _groq_envelope(lang="ar"),
        ])
        globals()["http_request_full"] = fake
        ok, data, msg = groq_generate_json("p", api_key=_FAKE_GROQ_KEY, model=DEFAULT_GROQ_MODEL)
        check("Groq: TPM 429 مع مهلة نصية يتجاوز عبارات plan/billing ويُعاد في الوقت المطلوب",
              bool(ok) and isinstance(data, dict) and msg == "ok"
              and len(calls) == 2 and _sleeps == [9.7425])

        # A short/zero Retry-After header must not override a longer TPM delay in the body.
        _sleeps.clear()
        _tpm_header_short_body = (
            b'{"error":{"message":"Rate limit reached on tokens per minute (TPM): '
            b'Limit 8000, Used 6718, Requested 2581. Please try again in 9.7425s."}}'
        )
        fake, calls = _fake_http([
            (429, {"Retry-After": "1"}, _tpm_header_short_body),
            _groq_envelope(lang="ar"),
        ])
        globals()["http_request_full"] = fake
        ok, data, msg = groq_generate_json(
            "p", api_key=_FAKE_GROQ_KEY, model=DEFAULT_GROQ_MODEL,
            sleep=_sleeps.append,
        )
        check("Groq: مهلة TPM في الجسم تتقدّم على Retry-After أقصر",
              bool(ok) and isinstance(data, dict) and msg == "ok"
              and len(calls) == 2 and _sleeps == [9.7425])

        # Content repair uses a single model-repair pass but allows one HTTP retry after transient TPM 429.
        _sleeps.clear()
        _repair_tpm_body = (
            b'{"error":{"message":"Rate limit reached on tokens per minute (TPM): '
            b'Limit 8000, Used 6327, Requested 2477. Please try again in 6.03s."}}'
        )
        _repair_success = _groq_envelope(lang="en")
        fake, calls = _fake_http([
            (429, {
                "x-ratelimit-limit-tokens": "8000",
                "x-ratelimit-remaining-tokens": "0",
                "x-ratelimit-reset-tokens": "6.03s",
            }, _repair_tpm_body),
            (200, {
                "x-ratelimit-limit-tokens": "8000",
                "x-ratelimit-remaining-tokens": "7300",
                "x-ratelimit-reset-tokens": "0.3s",
            }, _repair_success[2]),
        ])
        globals()["http_request_full"] = fake
        _repair_budget = RequestBudget(2)
        ok, data, msg = groq_generate_json(
            "repair prompt", api_key=_FAKE_GROQ_KEY, model=DEFAULT_GROQ_MODEL,
            tries=2, request_budget=_repair_budget, sleep=_sleeps.append)
        check("Groq repair: يعيد 429 المؤقت مرة واحدة بعد مهلة الخادم ضمن سقف الطلبات",
              bool(ok) and isinstance(data, dict) and msg == "ok"
              and len(calls) == 2 and _repair_budget.used == 2 and _sleeps == [6.03])
        check("Groq: يسجّل الاستخدام الفعلي ورأس TPM دون حفظ نص المقال أو البرومبت",
              _repair_budget.prompt_tokens == 10
              and _repair_budget.completion_tokens == 20
              and _repair_budget.total_tokens == 30
              and _repair_budget.usage_responses == 1
              and _repair_budget.rate_limit_hits == 1
              and _repair_budget.last_rate_limit_limit_tokens == "8000"
              and _repair_budget.last_rate_limit_remaining_tokens == "7300"
              and _repair_budget.last_rate_limit_reset_tokens == "0.3s")

        # (ي-2) Retry-After الرقمي يتقدّم على تلميحات فوترة عامة، لكن الحصة اليومية أدناه تبقى استثناءً.
        _sleeps.clear()
        fake, calls = _fake_http([
            (429, {"Retry-After": "6"},
             b'{"error":{"message":"Please check your plan and billing details."}}'),
            _groq_envelope(lang="ar"),
        ])
        globals()["http_request_full"] = fake
        ok, data, msg = groq_generate_json("p", api_key=_FAKE_GROQ_KEY, model=DEFAULT_GROQ_MODEL)
        check("Groq: Retry-After رقمي يسمح بإعادة المحاولة رغم عبارات plan/billing العامة",
              bool(ok) and isinstance(data, dict) and msg == "ok"
              and len(calls) == 2 and _sleeps == [6.0])

        _sleeps.clear()
        fake, calls = _fake_http([(503, {}, b'{"error":{"message":"overloaded"}}')])
        globals()["http_request_full"] = fake
        ok, data, msg = groq_generate_json("p", api_key=_FAKE_GROQ_KEY, model=DEFAULT_GROQ_MODEL)
        check("Groq: خطأ مؤقّت مستمرّ يستنفد الحدّ الأعلى الافتراضي (4 محاولات) ثم يفشل بوضوح",
              not ok and data is None and len(calls) == GEMINI_MAX_TRIES
              and msg.startswith("http_503") and "استُنفدت المحاولات" in msg
              and len(_sleeps) == GEMINI_MAX_TRIES - 1)

        _sleeps.clear()
        _budget_http, _budget_calls = _fake_http([
            (503, {}, b'{"error":{"message":"overloaded"}}')])
        globals()["http_request_full"] = _budget_http
        _hard_budget = RequestBudget(2)
        _budget_ok, _budget_data, _budget_msg = groq_generate_json(
            "p", api_key=_FAKE_GROQ_KEY, model=DEFAULT_GROQ_MODEL,
            tries=4, request_budget=_hard_budget, sleep=_sleeps.append)
        check("Groq: حدّ الاستدعاءات المشترك يوقف الطلبات فعلياً عند السقف",
              not _budget_ok and len(_budget_calls) == 2 and _hard_budget.used == 2
              and "request_budget_exhausted" in _budget_msg)

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

        # (ع) فحص المصادر الرسمية: رفض النطاق الميت، تمييز DNS/المهلة/HTTP،
        #     وعدم النشر عند تعذّر التحقّق — كلها باستجابات وهمية وبلا أي طلب حقيقي.
        check("المصادر: النطاقات الرسمية المعتمدة مقبولة (hrsd.gov.sa / gosi.gov.sa / qiwa.sa)",
              is_allowed_source_url("https://www.hrsd.gov.sa/")
              and is_allowed_source_url("https://www.hrsd.gov.sa/علاقات-العمل")
              and is_allowed_source_url("https://www.gosi.gov.sa/")
              and is_allowed_source_url("https://qiwa.sa/x"))
        check("المصادر: النطاق المنتهي mol.gov.sa مرفوض صراحةً من البوابة الساكنة",
              not is_allowed_source_url("https://www.mol.gov.sa/")
              and not is_allowed_source_url("https://www.mol.gov.sa/portal/Pages/Default.aspx"))
        check("المصادر: نطاقات mol.gov.sa الفرعية مرفوضة (لا يمرّ نطاق ميت بدعوى لاحقة .gov.sa)",
              not is_allowed_source_url("https://portal.mol.gov.sa/x")
              and not is_allowed_source_url("https://a.b.mol.gov.sa/")
              and is_blocked_source_host("portal.mol.gov.sa")
              and not is_blocked_source_host("www.hrsd.gov.sa"))
        check("المصادر: لا توسيع للقائمة المسموحة (خارجي · http · تصيّد النطاق مرفوضة)",
              not is_allowed_source_url("https://evil.example.com/x")
              and not is_allowed_source_url("http://www.hrsd.gov.sa/")
              and not is_allowed_source_url("https://www.hrsd.gov.sa.evil.com/")
              and not is_allowed_source_url("https://evil.com/?u=https://www.hrsd.gov.sa/")
              and not is_allowed_source_url("https://www.hrsd.gov.sa@evil.com/"))
        check("المصادر: تطبيع الرابط العربي (UTF-8) وإسقاط fragment",
              normalize_source_url("https://www.hrsd.gov.sa/علاقات-العمل#x")
              == "https://www.hrsd.gov.sa/%D8%B9%D9%84%D8%A7%D9%82%D8%A7%D8%AA-%D8%A7%D9%84%D8%B9%D9%85%D9%84")

        _dead = fixture_data("ar")
        _dead["official_sources"] = [
            {"title": "وزارة الموارد البشرية", "url": "https://www.mol.gov.sa/portal/Pages/Default.aspx"},
            {"title": "المؤسسة العامة للتأمينات الاجتماعية", "url": "https://www.gosi.gov.sa/"},
        ]
        check("المصادر: مقال يستشهد بـ mol.gov.sa يُرفض في بوابة الجودة (لتفادي مسودة غير موثوقة)",
              _rejects(lambda: validate_article(
                  _dead, topic=topic, lang="ar", published_at="2026-01-01")))

        _prompt_src = build_prompt(topic, "ar")
        _preferred = official_sources_for(topic)
        check("البرومبت: يضمّن الروابط الرسمية المعتمدة ويحظر mol.gov.sa",
              "hrsd.gov.sa" in _prompt_src and "mol.gov.sa" in _prompt_src
              and _preferred[0]["url"] in _prompt_src
              and _preferred[0]["url"] == OFFICIAL_SOURCE_LIBRARY["hrsd_eosb"][1])

        def _probe_with(*, exc=None, status=200, body=b""):
            def _fn(url, **kwargs):
                if exc is not None:
                    raise exc
                return status, {}, body, url
            return _fn

        _saved_http = globals()["http_request_full"]
        _hdrs_sent = {}
        try:
            globals()["http_request_full"] = _probe_with(
                exc=urllib.error.URLError(socket.gaierror(-2, "Name or service not known")))
            _ok, _code, _note = probe_source("https://www.hrsd.gov.sa/")
            check("فحص المصدر: فشل DNS يُصنَّف dns برسالة تشخيص واضحة",
                  _ok is False and _code == "dns" and "DNS" in _note)

            globals()["http_request_full"] = _probe_with(
                exc=urllib.error.URLError(socket.timeout("timed out")))
            _ok, _code, _note = probe_source("https://www.hrsd.gov.sa/")
            check("فحص المصدر: انتهاء المهلة يُصنَّف timeout",
                  _ok is False and _code == "timeout" and "المهلة" in _note)

            globals()["http_request_full"] = _probe_with(exc=OSError("boom"))
            _ok, _code, _note = probe_source("https://www.hrsd.gov.sa/")
            check("فحص المصدر: خطأ شبكة آخر يُصنَّف network بلا كشف أسرار",
                  _ok is False and _code == "network")

            for _st in (403, 404, 500, 503):
                globals()["http_request_full"] = _probe_with(status=_st, body=b"x" * 400)
                _ok, _code, _note = probe_source("https://www.hrsd.gov.sa/")
                check(f"فحص المصدر: حالة HTTP {_st} تُصنَّف http_{_st} ولا تُعدّ تحقّقاً",
                      _ok is False and _code == f"http_{_st}" and str(_st) in _note)

            globals()["http_request_full"] = _probe_with(status=200, body=b"<html></html>")
            _ok, _code, _note = probe_source("https://www.hrsd.gov.sa/")
            check("فحص المصدر: استجابة قصيرة جداً (empty) لا تُعدّ تحقّقاً",
                  _ok is False and _code == "empty")

            def _capture_probe(url, **kwargs):
                _hdrs_sent.update(kwargs.get("headers") or {})
                return 200, {}, b"<html>" + b"a" * 4000 + b"</html>", url

            globals()["http_request_full"] = _capture_probe
            _ok, _code, _note = probe_source("https://www.hrsd.gov.sa/")
            check("فحص المصدر: مصدر رسمي سليم (200 + جسم كافٍ) ينجح",
                  _ok is True and _code == "ok"
                  and check_sources([{"title": "t", "url": "https://www.hrsd.gov.sa/"}]) == [])
            check("فحص المصدر: يرسل ترويسات طلب عادية (User-Agent/Accept/Accept-Language)",
                  _hdrs_sent.get("User-Agent") == UA
                  and _hdrs_sent.get("Accept") == SOURCE_REQUEST_HEADERS["Accept"]
                  and _hdrs_sent.get("Accept-Language") == SOURCE_REQUEST_HEADERS["Accept-Language"])
        finally:
            globals()["http_request_full"] = _saved_http

        # دورة كاملة: التوليد ينجح لكن DNS يفشل ⇒ مسودتان unverified فقط بلا نشر.
        _sandbox()
        before = (ARTICLES_JSON.read_bytes(), SITEMAP_XML.read_bytes())

        def _dns_for_sources(url, **kwargs):
            if "generativelanguage.googleapis.com" in url:
                return _envelope("en" if "لغة المخرجات: English" in _request_prompt(kwargs)
                                 else "ar") + (url,)
            raise urllib.error.URLError(socket.gaierror(-2, "Name or service not known"))

        globals()["http_request_full"] = _dns_for_sources
        rc, _out = _capture_run(mode="draft", provider="gemini", api_key="k", model="m")
        _rec = load_state()["topics"][TOPICS[0]["id"]]
        check("تعذّر التحقّق من المصادر (DNS): مسودتان unverified فقط ولا نشر",
              rc == 0 and len(list(DRAFTS_DIR.glob("**/*.html"))) == 2
              and not ARTICLES_DIR.exists() and not SOCIAL_TXT.exists()
              and _rec.get("ar") == "draft_unverified" and _rec.get("en") == "draft_unverified"
              and (ARTICLES_JSON.read_bytes(), SITEMAP_XML.read_bytes()) == before)
        check("تعذّر التحقّق: السجل يميّز DNS ويذكر unverified وعدم لمس الفهارس",
              "DNS" in _out and "unverified" in _out and "[SOURCES]" in _out
              and "articles.json" in _out)

        # دورة كاملة: التوليد والمصادر ينجحان ⇒ النشر السليم ما زال يعمل (auto)
        _sandbox()
        _saved_base = globals()["BASE_DIR"]
        globals()["BASE_DIR"] = ARTICLES_DIR.parent

        def _ok_for_all(url, **kwargs):
            if "generativelanguage.googleapis.com" in url:
                return _envelope("en" if "لغة المخرجات: English" in _request_prompt(kwargs)
                                 else "ar") + (url,)
            return 200, {}, b"<html>" + b"ok" * 500 + b"</html>", url

        try:
            globals()["http_request_full"] = _ok_for_all
            rc = run_once(mode="auto", provider="gemini", api_key="k", model="m")
            check("مصادر متحقَّق منها + وضع auto: يُنشر المقالان وتُحدَّث articles.json/sitemap.xml",
                  rc == 0 and len(list(ARTICLES_DIR.glob("**/*.html"))) == 2
                  and not DRAFTS_DIR.exists()
                  and '"published"' in ARTICLES_JSON.read_text(encoding="utf-8")
                  and "<loc>" in SITEMAP_XML.read_text(encoding="utf-8"))
        finally:
            globals()["BASE_DIR"] = _saved_base

        # (ف) مسار فحص المصادر مع نسخة واحدة جاهزة (جوهر الإصلاح بعد دليل التشغيل
        #     38938331321): كان الفحص لا يُنفّذ إلا عند اكتمال النسختين، فبقيت النسخة
        #     الواحدة تُصنَّف «draft» دون أي تحقّق. الآن يُفحص كل مصدر في كل نسخة جاهزة.
        def _src_ok(url):
            return 200, {}, b"<html>" + b"s" * 2000 + b"</html>", url

        def _src_404(url):
            return 404, {}, b"<html>404 not found</html>", url

        def _src_dns(url):
            raise urllib.error.URLError(socket.gaierror(-2, "Name or service not known"))

        def _src_timeout(url):
            raise urllib.error.URLError(socket.timeout("timed out"))

        def _fake_run(*, fail_langs=(), source=_src_ok):
            """توليد Gemini وهمي (لغات محدّدة تفشل) + استجابة فحص مصادر مخصّصة."""
            probes = []

            def _fn(url, **kwargs):
                if "generativelanguage.googleapis.com" in url:
                    prompt = _request_prompt(kwargs)
                    lang = "en" if "لغة المخرجات: English" in prompt else "ar"
                    topic_id = _topic_id_from_prompt(prompt)
                    if lang in fail_langs:
                        return 503, {}, b'{"error":{"status":"UNAVAILABLE"}}', url
                    return _envelope(lang, topic_id=topic_id) + (url,)
                probes.append(url)
                return source(url)

            return _fn, probes

        # 1) النسختان جاهزتان وجميع المصادر متاحة ⇒ مسودتان «draft» (لا نشر).
        _sandbox()
        before = (ARTICLES_JSON.read_bytes(), SITEMAP_XML.read_bytes())
        fake, probes = _fake_run(source=_src_ok)
        globals()["http_request_full"] = fake
        rc, out = _capture_run(mode="draft", provider="gemini", api_key="k", model="m")
        st = load_state()["topics"][TOPICS[0]["id"]]
        check("مصادر/نسختان: كل المصادر متاحة ⇒ draft للنسختين وبلا نشر",
              rc == 0 and len(probes) == 2 and "[SOURCES]" in out
              and st.get("ar") == "draft" and st.get("en") == "draft"
              and len(list(DRAFTS_DIR.glob("**/*.html"))) == 2
              and not ARTICLES_DIR.exists()
              and (ARTICLES_JSON.read_bytes(), SITEMAP_XML.read_bytes()) == before)

        # 2) النسختان جاهزتان ومصدر واحد يفشل (404) في وضع auto ⇒ draft_unverified
        #    للنسختين، بلا نشر وبلا تعديل فهارس، وبلا استبدال صامت للاستشهادات.
        _sandbox()
        before = (ARTICLES_JSON.read_bytes(), SITEMAP_XML.read_bytes())
        fake, probes = _fake_run(source=lambda u: _src_404(u) if "hrsd" in u else _src_ok(u))
        globals()["http_request_full"] = fake
        rc, out = _capture_run(mode="auto", provider="gemini", api_key="k", model="m")
        st = load_state()["topics"][TOPICS[0]["id"]]
        drafts = sorted(DRAFTS_DIR.glob("**/*.html"))
        check("مصادر/نسختان: مصدر واحد يفشل ⇒ draft_unverified للنسختين ولا نشر",
              rc == 0 and len(probes) == 2 and "[http_404]" in out and "unverified" in out
              and st.get("ar") == "draft_unverified" and st.get("en") == "draft_unverified"
              and len(drafts) == 2 and not ARTICLES_DIR.exists() and not SOCIAL_TXT.exists()
              and (ARTICLES_JSON.read_bytes(), SITEMAP_XML.read_bytes()) == before)
        check("مصادر/نسختان: فشل المصدر لا يستبدل الاستشهادات (تبقى كما ولّدها النموذج)",
              len(drafts) == 2 and all(
                  "https://www.gosi.gov.sa/" in p.read_text(encoding="utf-8")
                  and "https://www.hrsd.gov.sa/" in p.read_text(encoding="utf-8")
                  for p in drafts)
              and "https://www.hrsd.gov.sa/" in out)

        # 3) العربية وحدها جاهزة (الإنجليزية تفشل) ⇒ يُنفَّذ الفحص فعلاً ومسودة draft واحدة.
        _sandbox()
        before = (ARTICLES_JSON.read_bytes(), SITEMAP_XML.read_bytes())
        fake, probes = _fake_run(fail_langs=("en",), source=_src_ok)
        globals()["http_request_full"] = fake
        rc, out = _capture_run(mode="draft", provider="gemini", api_key="k", model="m")
        st = load_state()["topics"][TOPICS[0]["id"]]
        drafts = sorted(DRAFTS_DIR.glob("**/*.html"))
        check("مصادر/نسخة عربية وحدها: يُنفَّذ فحص المصادر فعلاً (جوهر الإصلاح)",
              rc == 0 and len(probes) == 2 and "[SOURCES]" in out and st.get("ar") == "draft"
              and st.get("en") == "error" and len(drafts) == 1
              and "/ar/" in drafts[0].as_posix() and not ARTICLES_DIR.exists()
              and (ARTICLES_JSON.read_bytes(), SITEMAP_XML.read_bytes()) == before)

        # 4) الإنجليزية وحدها جاهزة + مصدر فاشل في وضع auto ⇒ draft_unverified (نسخة واحدة).
        _sandbox()
        before = (ARTICLES_JSON.read_bytes(), SITEMAP_XML.read_bytes())
        fake, probes = _fake_run(fail_langs=("ar",),
                                 source=lambda u: _src_dns(u) if "hrsd" in u else _src_ok(u))
        globals()["http_request_full"] = fake
        rc, out = _capture_run(mode="auto", provider="gemini", api_key="k", model="m")
        st = load_state()["topics"][TOPICS[0]["id"]]
        drafts = sorted(DRAFTS_DIR.glob("**/*.html"))
        check("مصادر/نسخة إنجليزية وحدها: فشل مصدر ⇒ draft_unverified وبلا نشر",
              rc == 0 and len(probes) == 2 and st.get("en") == "draft_unverified"
              and st.get("ar") == "error" and len(drafts) == 1
              and "/en/" in drafts[0].as_posix() and not ARTICLES_DIR.exists()
              and (ARTICLES_JSON.read_bytes(), SITEMAP_XML.read_bytes()) == before)

        # 5) أنواع الفشل الثلاثة عبر مسار الدورة كاملاً: DNS · HTTP 404 · انتهاء المهلة.
        for _label, _src, _code in (("DNS", _src_dns, "dns"),
                                    ("HTTP 404", _src_404, "http_404"),
                                    ("انتهاء المهلة", _src_timeout, "timeout")):
            _sandbox()
            before = (ARTICLES_JSON.read_bytes(), SITEMAP_XML.read_bytes())
            fake, _probes = _fake_run(source=_src)
            globals()["http_request_full"] = fake
            rc, out = _capture_run(mode="auto", provider="gemini", api_key="k", model="m")
            st = load_state()["topics"][TOPICS[0]["id"]]
            check(f"مصادر: فشل {_label} ⇒ draft_unverified للنسختين وبلا نشر ولا تغيير فهارس",
                  rc == 0 and f"[{_code}]" in out
                  and st.get("ar") == "draft_unverified" and st.get("en") == "draft_unverified"
                  and len(list(DRAFTS_DIR.glob("**/*.html"))) == 2
                  and not ARTICLES_DIR.exists() and not SOCIAL_TXT.exists()
                  and (ARTICLES_JSON.read_bytes(), SITEMAP_XML.read_bytes()) == before)

        # (ص) Structured Outputs الصارم من Groq — إصلاح فشل التوليد الموثّق في
        #     التشغيل 38946220138 (http_400 / json_validate_failed للنسختين معاً).
        #     يُثبت: شكل الطلب (json_schema + strict)، ومطابقة المخطّط لبنية المقال
        #     وبلا كلمات غير مدعومة، ومرور الاستجابة الكاملة إلى البوابات، ورفض
        #     الناقص أو خاطئ النوع، ومنع النشر عند فشل المزوّد — كلها باستجابات
        #     وهمية وبلا أي طلب شبكة حقيقي.
        _schema_reqs = []

        def _fake_schema_run(fail=None):
            """يلتقط جسم كل طلب Groq ويردّ (فشل مُعطى) أو ظرف صالح باللغة الصحيحة."""
            def _fn(url, **kwargs):
                _schema_reqs.append(json.loads(kwargs["data"].decode("utf-8")))
                if fail is not None:
                    return fail + (url,)
                prompt = _request_prompt(kwargs)
                lang = "en" if "لغة المخرجات: English" in prompt else "ar"
                topic_id = _topic_id_from_prompt(prompt)
                return _groq_envelope(lang=lang, topic_id=topic_id) + (url,)
            return _fn

        def _schema_problems(node, path="$"):
            """يتحقق من متطلبات Groq الصارمة ومن كلمات المخطّط المدعومة في كل مستوًى."""
            found = []
            if not isinstance(node, dict):
                return [f"{path}: ليست كائناً"]
            kind = node.get("type")
            words = {"type", "properties", "required", "additionalProperties",
                     "items", "description"}
            extra = set(node) - words
            if extra:
                found.append(f"{path}: كلمات غير مدعومة {sorted(extra)}")
            if kind == "object":
                props = node.get("properties")
                if not isinstance(props, dict) or not props:
                    found.append(f"{path}: properties ناقصة")
                else:
                    if set(node.get("required") or []) != set(props):
                        found.append(f"{path}: required لا يغطي كل الحقول")
                    if node.get("additionalProperties") is not False:
                        found.append(f"{path}: additionalProperties ليس false")
                    for key, child in props.items():
                        found += _schema_problems(child, f"{path}.{key}")
            elif kind == "array":
                found += _schema_problems(node.get("items"), f"{path}[]")
            elif kind in ("string", "number", "integer", "boolean"):
                pass
            else:
                found.append(f"{path}: نوع غير مدعوم {kind!r}")
            return found

        # 1) شكل الطلب: json_schema + strict=true، ولا رجوع تلقائي إلى json_object.
        _schema_reqs.clear()
        _sandbox()
        before = (ARTICLES_JSON.read_bytes(), SITEMAP_XML.read_bytes())
        globals()["http_request_full"] = _fake_schema_run()
        rc = run_once(mode="draft", provider="groq", api_key=_FAKE_GROQ_KEY,
                      skip_source_check=True)
        _rf = (_schema_reqs[0].get("response_format") or {}) if _schema_reqs else {}
        _js = _rf.get("json_schema") or {}
        _schema = _js.get("schema") or {}
        _props = _schema.get("properties") or {}
        check("Structured Outputs: الطلب يستخدم json_schema وstrict=true وreasoning_effort=low بلا json_object",
              rc == 0 and len(_schema_reqs) == 2
              and all(r.get("reasoning_effort") == "low" for r in _schema_reqs)
              and _rf.get("type") == "json_schema" and _js.get("strict") is True
              and _js.get("name") == GROQ_SCHEMA_NAME
              and _rf == groq_response_format()
              and "json_object" not in json.dumps(_rf, ensure_ascii=False))

        # 2) المخطّط: حقول المقال المطلوبة بالضبط، وكل كائن مغلق ومتطلبه كامل، وبلا أي
        #    كلمة JSON Schema غير مدعومة (فلا يُرفض الطلب عند Groq بسببها).
        check("Structured Outputs: المخطّط يحقق متطلبات Groq الصارمة وبلا كلمات غير مدعومة",
              _schema.get("type") == "object" and _schema_problems(_schema) == [])
        check("Structured Outputs: المخطّط يضمّ الحقول المطلوبة بما فيها تدقيق الحساب",
              set(_props) == set(fixture_data("ar")) == set(fixture_data("en"))
              and set(_schema.get("required") or []) == set(fixture_data("ar")))

        def _items_of(name):
            return ((_props.get(name) or {}).get("items") or {}).get("properties") or {}

        check("Structured Outputs: البنية المتداخلة مطابقة للمقال (sections/faq/official_sources)",
              (_props.get("sections") or {}).get("type") == "array"
              and set(_items_of("sections")) == {"heading", "body", "bullets"}
              and (_items_of("sections").get("body") or {}).get("type") == "string"
              and (_props.get("faq") or {}).get("type") == "array"
              and set(_items_of("faq")) == {"q", "a"}
              and (_props.get("official_sources") or {}).get("type") == "array"
              and set(_items_of("official_sources")) == {"title", "url"}
              and all((_props.get(f) or {}).get("type") == "string"
                      for f in ("title", "meta_description", "excerpt")))

        # 3) استجابة JSON كاملة وصالحة تمرّ إلى بوابات الجودة الحالية بلا أي تيسير.
        _schema_reqs.clear()
        globals()["http_request_full"] = _fake_http(
            [_groq_envelope(content=json.dumps(fixture_data("ar"), ensure_ascii=False))])[0]
        ok, data, msg = groq_generate_json("p", api_key=_FAKE_GROQ_KEY,
                                           model=DEFAULT_GROQ_MODEL)
        try:
            _gate_art = validate_article(data, topic=topic, lang="ar",
                                         published_at="2026-01-01")
            _gate_ok = (_gate_art["word_count"] >= MIN_WORDS["ar"]
                        and len(_gate_art["sections"]) >= MIN_SECTIONS
                        and len(_gate_art["faq"]) >= 1)
        except (Reject, TypeError, KeyError, AttributeError):
            _gate_ok = False
        check("Structured Outputs: استجابة كاملة وصالحة تمرّ إلى بوابات الجودة الحالية كما هي",
              bool(ok) and msg == "ok" and _gate_ok
              and isinstance(data, dict) and set(data) == set(fixture_data("ar")))

        # 4) نقص الحقول أو الأنواع الخاطئة لا تتجاوز validate_article أبداً.
        _bad = fixture_data("ar")
        del _bad["title"]
        check("بوابة الجودة: نقص الحقل title لا يتجاوز validate_article",
              _rejects(lambda: validate_article(_bad, topic=topic, lang="ar",
                                                published_at="2026-01-01")))
        _bad = fixture_data("en")
        del _bad["sections"]
        check("بوابة الجودة: نقص الحقل sections لا يتجاوز validate_article",
              _rejects(lambda: validate_article(_bad, topic=topic, lang="en",
                                                published_at="2026-01-01")))
        for _missing_field in ("faq", "official_sources", "calculation_example"):
            _bad = fixture_data("ar")
            del _bad[_missing_field]
            check(f"بوابة الجودة: نقص الحقل {_missing_field} لا يتجاوز validate_article",
                  _rejects(lambda bad=_bad: validate_article(
                      bad, topic=topic, lang="ar", published_at="2026-01-01")))
        _bad = fixture_data("ar")
        _bad["sections"] = "ليست قائمة"
        check("بوابة الجودة: نوع خاطئ في sections لا يتجاوز validate_article",
              _rejects(lambda: validate_article(_bad, topic=topic, lang="ar",
                                                published_at="2026-01-01")))
        _bad = fixture_data("ar")
        _bad["sections"][0]["body"] = 123
        check("بوابة الجودة: نوع خاطئ في sections[0].body لا يتجاوز validate_article",
              _rejects(lambda: validate_article(_bad, topic=topic, lang="ar",
                                                published_at="2026-01-01")))
        _bad = fixture_data("en")
        _bad["official_sources"] = ["ليست كائناً"]
        check("بوابة الجودة: نوع خاطئ في official_sources لا يتجاوز validate_article",
              _rejects(lambda: validate_article(_bad, topic=topic, lang="en",
                                                published_at="2026-01-01")))

        # 5) فشل متكرر في Groq Structured Outputs:
        #    تُعاد نفس الاستجابة الصارمة حتى الحدّ الأعلى، ثم يفشل المسار
        #    من دون نشر أو مسودات أو تعديل الملفات العامة.
        # 5-أ) 400 json_validate_failed مرة واحدة ثم نجاح: التكرار لا يخفف المخطط.
        _sandbox()
        _recovery_before = (ARTICLES_JSON.read_bytes(), SITEMAP_XML.read_bytes())
        _recovery_calls, _recovery_requests = {"ar": 0, "en": 0}, []

        _repair_ar_markers = (
            " تنطبق نسبة الثلث على مدة خدمة من سنتين حتى خمس سنوات شاملةً خمس سنوات، "
            "ولا تنطبق نسبة الثلثين إلا إذا كانت مدة الخدمة أكثر من خمس سنوات وأقل من عشر سنوات. "
            "عدم كون الإشعار شرطًا لاستحقاق المكافأة لا يعني أن الإشعار غير مطلوب لإنهاء العقد؛ "
            "فقد تبقى متطلبات الإشعار وإجراءات الاستقالة واجبة بحسب نوع العقد والأحكام النظامية المنطبقة. "
            "وفق المادة 86، يجوز بالاتفاق استبعاد العمولات والنسب المئوية عن المبيعات وما يماثلها "
            "من عناصر الأجر التي تكون بطبيعتها قابلة للزيادة والنقص من الأجر الذي تُحسب على أساسه "
            "مكافأة نهاية الخدمة؛ ولا يعني ذلك استبعاد الأجر الأساسي. "
            "المادة 81 تتعلق بحالات نظامية يترك فيها العامل العمل دون إشعار مع احتفاظه بحقوقه، "
            "ولا تمثل فصلًا من صاحب العمل."
        )

        def _schema_recovery(url, **kwargs):
            request = json.loads(kwargs["data"].decode("utf-8"))
            _recovery_requests.append(request)
            request_prompt = _request_prompt(kwargs)
            lang = "en" if "لغة المخرجات: English" in request_prompt else "ar"
            _recovery_calls[lang] += 1
            if _recovery_calls[lang] == 1:
                return (400, {}, b'{"error":{"message":"Failed to generate JSON",'
                        b'"code":"json_validate_failed"}}', url)
            data = fixture_data(lang, topic_id="labor-art85")
            if lang == "ar":
                data["sections"][0]["body"] += _repair_ar_markers
            return _groq_envelope(content=json.dumps(data, ensure_ascii=False)) + (url,)

        globals()["http_request_full"] = _schema_recovery
        _recovery_rc, _recovery_out = _capture_run(
            mode="draft", provider="groq", api_key=_FAKE_GROQ_KEY,
            model=DEFAULT_GROQ_MODEL, skip_source_check=True,
            topic_id="labor-art85", article_lang="ar")
        _recovery_drafts = list(DRAFTS_DIR.glob("**/*.html"))
        check("Groq Structured Outputs: نجاح بعد 400 json_validate_failed بإعادة محدودة",
              _recovery_rc == 0 and _recovery_calls == {"ar": 2, "en": 0}
              and len(_recovery_requests) == 2
              and "استجابة مؤقّتة http_400" in _recovery_out
              and len(_recovery_drafts) == 1)
        check("Groq Structured Outputs: إعادة المحاولة تحتفظ بـjson_schema strict بلا json_object",
              len(_recovery_requests) == 2
              and all(r.get("reasoning_effort") == "low"
                      and (r.get("response_format") or {}).get("type") == "json_schema"
                      and ((r.get("response_format") or {}).get("json_schema") or {}).get("strict") is True
                      for r in _recovery_requests)
              and (ARTICLES_JSON.read_bytes(), SITEMAP_XML.read_bytes()) == _recovery_before
              and not ARTICLES_DIR.exists() and not SOCIAL_TXT.exists()
              and "json_object" not in json.dumps(_recovery_requests, ensure_ascii=False))

        # 5-ب) فشل مستمر: لا نشر ولا مسودة، ولا تعديل على الملفات العامة.
        _fail_reqs, _fail_calls = [], {"ar": 0, "en": 0}

        def _schema_400(url, **kwargs):
            _fail_reqs.append(json.loads(kwargs["data"].decode("utf-8")))
            prompt = _request_prompt(kwargs)
            _fail_calls["en" if "لغة المخرجات: English" in prompt else "ar"] += 1
            return (400, {},
                    b'{"error":{"message":"Failed to validate JSON",'
                    b'"code":"json_validate_failed"}}', url)

        _sandbox()
        _fail_before = (ARTICLES_JSON.read_bytes(), SITEMAP_XML.read_bytes())
        globals()["http_request_full"] = _schema_400
        rc, out = _capture_run(mode="auto", provider="groq", api_key=_FAKE_GROQ_KEY)
        st = load_state()["topics"][TOPICS[0]["id"]]
        check("فشل Groq المتكرر (json_validate_failed): لا نشر ولا أي كتابة في ملفات عامة",
              rc == EXIT_GENERATION_FAILED and st.get("ar") == "error"
              and st.get("en") == "error" and not DRAFTS_DIR.exists()
              and not ARTICLES_DIR.exists() and not SOCIAL_TXT.exists()
              and (ARTICLES_JSON.read_bytes(), SITEMAP_XML.read_bytes()) == _fail_before)
        check("فشل Groq المتكرر: المحاولات محدودة وتبقى على المخطط الصارم",
              _fail_calls == {"ar": GROQ_INITIAL_HTTP_TRIES, "en": GROQ_INITIAL_HTTP_TRIES}
              and len(_fail_reqs) == 2 * GROQ_INITIAL_HTTP_TRIES
              and all(r.get("reasoning_effort") == "low"
                      and (r.get("response_format") or {}).get("type") == "json_schema"
                      and ((r.get("response_format") or {}).get("json_schema") or {}
                           ).get("strict") is True
                      for r in _fail_reqs)
              and "json_validate_failed" in out
              and "استُنفدت المحاولات" in out
              and "json_object" not in out)

        # (ض) دقة المحتوى القانوني لمكافأة نهاية الخدمة — إصلاح الأخطاء المكتشفة
        #     فعلياً في مسودات التشغيل 38946220138 و38954366741: نسب عامة مخترعة
        #     (21 يوماً عن كل سنة)، ونصف يوم عن الشهر غير المكتمل بدل النسبة،
        #     وحدّ ثلاثة أشهر للاستحقاق، وسقوط عام بأي إخلال بشروط، واستبعاد كامل
        #     للبدلات أو الأجر الأساسي وحده، وتسوية في 30 يوماً، وأمثلة رقمية
        #     مخالفة للمعادلة. الفحوص تثبت: وصول القواعد (80 و81 و84–88) إلى بروموت
        #     كل موضوعات المكافأة في اللغتين، ومنع الادعاءات السبعة صراحةً، والتمييز
        #     بين الأساس والنِّسَب، وفصل استثناءات المادة 87 عن نِسَب المادة 85،
        #     واستحقاق المادة 81 الكامل وفق المادة 84 بلا عتبة سنتين، وفصل تعويض
        #     المادة 77 كقاعدة مستقلة (9) منفصلة تماماً لا تُضاف تلقائياً (بمدخل
        #     مستقل اسمه Has_Judicial_Ruling_Or_Settlement افتراضياً False، وبلا
        #     مبلغ مخمّن عند نقص البيانات)، وسلامة المعادلة حسابياً بمرجع حتمي
        #     (لا بحساب يقدّمه النموذج)، وبلا أي ضعف لبوابات الجودة أو فحص المصادر.
        _eosb_ar_markers = (
            "أجر نصف شهر عن كل سنة",
            "أجر شهر كامل عن كل سنة",
            "الأجر الأخير أساساً",
            "بنسبة ماقضى العامل منها فعلاً",
            "لا بقاعدة «21 يوماً عن كل سنة»",
            "ولا بنصف يوم عن كل شهر غير مكتمل",
            "المادة 85 تنظّم نسب مكافأة نهاية الخدمة عند الاستقالة فقط",
            "متطلبات الإشعار وإجراءات الاستقالة مسألة منفصلة",
            "خدمة متتالية لا تقل عن سنتين",
            "المكافأة كاملة إذا بلغت الخدمة عشر سنوات فأكثر",
            "متطلبات الإشعار وإجراءات الاستقالة مسألة منفصلة",
            "فلا تدّعِ أن الأجر الأساسي وحده",
            "ولا أن جميع البدلات مستبعدة بلا استثناء",
            "خلال أسبوع على الأكثر",
            "لا تزيد على أسبوعين",
            "لا تذكر أن التسوية النهائية تستغرق 30 يوماً بصورة عامة",
            "حالات الحرمان محددة في المادة 80",
            "لا تزعم أن أي إخلال بشروط الاستقالة يسقط المكافأة",
            "يُعلَّم صراحةً بأنه مثال توضيحي",
            "المادة 87",
            "استثناءً صريحًا من أحكام المادة 85",
            "قوة قاهرة خارجة عن إرادته",
            "خلال ستة أشهر من تاريخ عقد زواجها",
            "أو ثلاثة أشهر من تاريخ وضعها",
            "لا تُطبَّق نِسَب الاستقالة في المادة 85 ولا عتبة السنتين",
            "المادة 81",
            "ترك العمل دون إشعار",
            "بحقوقه النظامية كلها",
            "لا تصف هذه الحالات بأنها استقالة عادية",
            "ليس استقالة بالمعنى المقصود في المادة 85",
            "تستحق فيه المكافأة كاملة وفق المادة 84",
            "فلا تُضِف تعويضًا آخر كتعويض المادة 77",
            "ولا تفترض استحقاقه في جميع حالات المادة 81",
            "تعويض المادة 77 (منفصل عن المكافأة)",
            "ولا يدخل تلقائيًا في ناتج المكافأة عند اختيار أي سبب",
            "ولا في أي من حالات المادة 81 السبع",
            "الاحتساب التلقائي هو سياسة للبرنامج",
            "الصلح الموثّق شرط نظامي مطلق",
            "Has_Judicial_Ruling_Or_Settlement",
            "وقيمته الافتراضية False",
            "فلا تُخمّن المبلغ ولا تُضِف قيمة تقديرية إلى التصفية",
            "ليست نصًّا حرفيًا من المادة 77",
        )
        _eosb_en_markers = (
            "half a month's wage for each of the first five years",
            "one full month's wage for each subsequent year",
            "the last wage as the basis",
            "in proportion to the time actually served",
            'not by a flat "21 days per year" rule',
            "not by half a day per incomplete month",
            "Article 85 sets the end-of-service benefit ratios for resignation only",
            "Notice and resignation procedures are separate questions",
            "two consecutive years of service",
            "one third of the benefit",
            "two thirds",
            "the full benefit",
            "Notice and resignation procedures are separate questions",
            "Do not claim that the basic wage alone",
            "nor that all allowances are always excluded",
            "within one week at most",
            "no more than two weeks",
            "Do not state that the final settlement generally takes 30 days",
            "forfeiture cases are exhaustively listed in Article 80",
            "Do not claim that any breach of resignation conditions forfeits the benefit",
            "must follow the equation above exactly",
            "clearly labelled as illustrative",
            "Article 87",
            "as an express exception to Article 85",
            "force majeure beyond his control",
            "within six months of her marriage contract date",
            "three months of giving birth",
            "do not apply to these two cases",
            "Article 81",
            "leave work without notice",
            "retaining all of his statutory rights",
            "Do not describe these cases as ordinary resignation",
            "is not a resignation within the meaning of Article 85",
            "payable in full under Article 84",
            "do not add any other compensation such as Article 77 compensation",
            "do not assume it is due in all Article 81 cases",
            "Article 77 compensation (separate from the benefit)",
            "is never added automatically to the benefit result for any reason",
            "seven Article 81 cases",
            "Not computing it automatically is a program policy",
            "an absolute statutory condition",
            "Has_Judicial_Ruling_Or_Settlement",
            "default value of False",
            "do not guess the amount and do not add an estimated value to the settlement",
            "is not a literal quotation of Article 77",
        )
        _bad_eosb_prompts = []
        for _tid in sorted(EOSB_TOPIC_IDS):
            for _lang in ("ar", "en"):
                _p = build_prompt(topic_by_id(_tid), _lang)
                if _tid == "labor-art85":
                    _critical_markers = (
                        ("المادة 84", "المادة 85", "المادة 86", "المادة 81",
                         "مدة إشعار العقد", "الثلثان بعد تجاوز خمس سنوات",
                         "لا تقل إن عدم الالتزام بالإشعار", "سنتين متتاليتين كحد أدنى")
                        if _lang == "ar" else
                        ("Article 84", "Article 85", "Article 86", "Article 81",
                         "contract notice requirements", "two thirds only above five",
                         "Do not claim that notice non-compliance", "two consecutive years as the minimum")
                    )
                    if any(_m not in _p for _m in _critical_markers):
                        _bad_eosb_prompts.append(f"{_tid}/{_lang}:scoped")
                    continue
                _markers = _eosb_ar_markers if _lang == "ar" else _eosb_en_markers
                if any(_m not in _p for _m in _markers):
                    _bad_eosb_prompts.append(f"{_tid}/{_lang}")
        check("EOSB: قواعد كل موضوع تصل للبرومبت بنطاق قانوني مناسب لكل لغة",
              bool(EOSB_TOPIC_IDS) and not _bad_eosb_prompts)

        # التمييز المنصوص عليه في التقرير: الأساس (84) قسم مستقل عن نِسَب
        # الاستقالة (85)، ولا تُقدَّم نِسَب الاستقالة كأنها قاعدة الحساب الأساسية.
        _p_res_ar = build_prompt(topic_by_id("eosb-resignation"), "ar")
        _p_res_en = build_prompt(topic_by_id("eosb-resignation"), "en")
        check("EOSB: التمييز بين أساس المادة 84 ونِسَب الاستقالة في المادة 85 (عربي)",
              "المادة 84" in _p_res_ar and "المادة 85" in _p_res_ar
              and "أجر نصف شهر" in _p_res_ar and "ثلث المكافأة" in _p_res_ar
              and _p_res_ar.index("المادة 84") < _p_res_ar.index("المادة 85"))
        check("EOSB: التمييز بين أساس المادة 84 ونِسَب الاستقالة في المادة 85 (إنجليزي)",
              "Article 84" in _p_res_en and "Article 85" in _p_res_en
              and "half a month's wage" in _p_res_en
              and "one third of the benefit" in _p_res_en
              and _p_res_en.index("Article 84") < _p_res_en.index("Article 85"))

        # الفصل البنيوي: بند المادة 85 (الاستقالة) يبقى بنداً مستقلاً خالياً من
        # استثناءات 87 ومن حقوق 81، وقاعدة 87 تُعرَّف صراحةً كاستثناء من 85 —
        # فلا تُدمج نِسَب الاستقالة بالنِسَب الاستثنائية ولا تُعمَّم على المادة 81.
        _seg85_ar = _p_res_ar[_p_res_ar.index("الاستحقاق عند الاستقالة (المادة 85)"):
                              _p_res_ar.index("استثناءات الاستحقاق الكامل (المادة 87)")]
        _seg85_en = _p_res_en[_p_res_en.index("Entitlement on resignation (Article 85)"):
                              _p_res_en.index("Full-entitlement exceptions (Article 87)")]
        check("EOSB: المادة 87 استثناء صريح من 85 وبند الاستقالة منفصل عن الاستثناءات",
              "87" not in _seg85_ar and "81" not in _seg85_ar
              and "استثناءً صريحًا من أحكام المادة 85" in _p_res_ar
              and "87" not in _seg85_en
              and "as an express exception to Article 85" in _p_res_en)

        # جزء السنة: النصّ المُرسل يوجب النسبة ويمنع قاعدتَي 21 يوماً ونصف اليوم.
        check("EOSB: قاعدة أجزاء السنة تناسبياً ومنع 21 يوماً ونصف اليوم (كلا اللغتين)",
              "بنسبة ماقضى العامل منها فعلاً" in _p_res_ar
              and "لا بقاعدة «21 يوماً عن كل سنة»" in _p_res_ar
              and "ولا بنصف يوم عن كل شهر غير مكتمل" in _p_res_ar
              and "in proportion to the time actually served" in _p_res_en
              and 'not by a flat "21 days per year" rule' in _p_res_en
              and "not by half a day per incomplete month" in _p_res_en)

        # سلوكي: القواعد تصل فعلاً إلى جسم طلب المزوّد (دورة حقيقية بطلبات وهمية)،
        # لا إلى build_prompt فقط — واللغة تُميَّز كما في بقية الفحوص.
        _sandbox()
        _schema_reqs.clear()
        globals()["http_request_full"] = _fake_schema_run()
        run_once(mode="draft", provider="groq", api_key=_FAKE_GROQ_KEY,
                 skip_source_check=True)
        _live_prompts = [r["messages"][-1]["content"] for r in _schema_reqs]
        check("EOSB: القواعد القانونية تصل جسم طلب المزوّد في النسختين فعلاً",
              len(_live_prompts) == 2
              and any("المادة 84" in p and "المادة 85" in p for p in _live_prompts)
              and any("Article 84" in p and "Article 85" in p for p in _live_prompts))

        # سلوكي مضبوط على موضوعَي الاستحقاق الكامل والمادة 81: كل موضوع بطلبيه
        # (ar/en)، والعلامات المستخدمة من نصّ القاعدة نفسه لا من عنوان الموضوع
        # (عنوان labor-art81 يحوي «المادة 81» أصلاً، فالعنوان لا يصلح دليلاً).
        _focus_prompts = []
        for _focus_tid in ("eosb-full-entitlement", "labor-art81"):
            _sandbox()
            _schema_reqs.clear()
            globals()["http_request_full"] = _fake_schema_run()
            run_once(mode="draft", provider="groq", api_key=_FAKE_GROQ_KEY,
                     skip_source_check=True, topic_id=_focus_tid)
            _focus_prompts.extend(r["messages"][-1]["content"]
                                  for r in _schema_reqs)
        check("EOSB: قاعدتا 87 و81 في جسم الطلب لموضوعَي eosb-full-entitlement وlabor-art81",
              len(_focus_prompts) == 4
              and sum("قوة قاهرة خارجة عن إرادته" in p
                      and "بحقوقه النظامية كلها" in p
                      and "تستحق فيه المكافأة كاملة وفق المادة 84" in p
                      for p in _focus_prompts) == 2
              and sum("force majeure beyond his control" in p
                      and "retaining all of his statutory rights" in p
                      and "payable in full under Article 84" in p
                      for p in _focus_prompts) == 2)

        # المادة 81: استحقاق كامل وفق 84 (لا استقالة ولا عتبة سنتين)، مع فصل صريح
        # عن تعويض المادة 77 كي لا يُقدَّم استحقاقه كحقيقة مؤكدة في الحالات كلها.
        _seg81_ar = EOSB_LEGAL_RULES["ar"][
            EOSB_LEGAL_RULES["ar"].index("8) ترك العمل بحالات المادة 81"):
            EOSB_LEGAL_RULES["ar"].index("9) تعويض المادة 77 (منفصل عن المكافأة)")]
        _seg81_en = EOSB_LEGAL_RULES["en"][
            EOSB_LEGAL_RULES["en"].index("8) Leaving work under Article 81"):
            EOSB_LEGAL_RULES["en"].index(
                "9) Article 77 compensation (separate from the benefit)")]
        check("EOSB: المادة 81 استحقاق كامل وفق 84 وفصل عن تعويض المادة 77 (كلا اللغتين)",
              "المكافأة كاملة وفق المادة 84" in _seg81_ar
              and "تعويض المادة 77" in _seg81_ar
              and "لا تفترض استحقاقه في جميع حالات المادة 81" in _seg81_ar
              and "is not a resignation within the meaning of Article 85" in _seg81_en
              and "payable in full under Article 84" in _seg81_en
              and "Article 77 compensation" in _seg81_en
              and "do not assume it is due in all Article 81 cases" in _seg81_en)
        check("EOSB: تعويض المادة 77 مذكور كحماية لا كاستحقاق مؤكد (كلا اللغتين)",
              "فلا تُضِف تعويضًا آخر كتعويض المادة 77" in _seg81_ar
              and "ولا تقدّمه كحقيقة مؤكدة دون سند نظامي أو قضائي موثّق" in _seg81_ar
              and "do not add any other compensation such as Article 77 compensation"
                  in _seg81_en
              and "never state it as settled without a documented statutory or "
                  "judicial basis" in _seg81_en)

        # المادة 77: قاعدة مستقلة (9) توثّق الفصل، المدخل المستقل الافتراضي False،
        # ومنع التخمين — وتُغطّى بالعلامات نفسها في اللغتين.
        _seg77_ar = EOSB_LEGAL_RULES["ar"][
            EOSB_LEGAL_RULES["ar"].index("9) تعويض المادة 77 (منفصل عن المكافأة)"):]
        _seg77_en = EOSB_LEGAL_RULES["en"][
            EOSB_LEGAL_RULES["en"].index(
                "9) Article 77 compensation (separate from the benefit)"):]
        check("EOSB: تعويض المادة 77 — فصل صريح وسياسة كاملة (كلا اللغتين)",
              "منفصل تمامًا عن مكافأة نهاية الخدمة" in _seg77_ar
              and "ولا يدخل تلقائيًا في ناتج المكافأة عند اختيار أي سبب" in _seg77_ar
              and "ولا في أي من حالات المادة 81 السبع" in _seg77_ar
              and "الاحتساب التلقائي هو سياسة للبرنامج" in _seg77_ar
              and "شرط نظامي مطلق" in _seg77_ar
              and "لا يُحتسب إلا بمدخل مستقل" not in _seg77_ar
              and "Has_Judicial_Ruling_Or_Settlement" in _seg77_ar
              and "ليست نصًّا حرفيًا من المادة 77" in _seg77_ar
              and "entirely separate from the end-of-service benefit" in _seg77_en
              and "is never added automatically to the benefit result for any reason"
                  in _seg77_en
              and "seven Article 81 cases" in _seg77_en
              and "Not computing it automatically is a program policy" in _seg77_en
              and "an absolute statutory condition" in _seg77_en
              and "is computed only from an independent" not in _seg77_en
              and "Has_Judicial_Ruling_Or_Settlement" in _seg77_en
              and "is not a literal quotation of Article 77" in _seg77_en)

        # المادة 77 ليست نصًّا منسوخًا ولا تنفي المطالبة القضائية، والقاعدة 9 مستقلة
        # عن قاعدة 8 (لا تختلط نصوصها)، واسم المدخل ثابت افتراضيًا False.
        check("EOSB: سياسة المادة 77 — مدخل مستقل افتراضيًا False ولا مبلغ مخمّن",
              ARTICLE_77_FLAG_NAME == "Has_Judicial_Ruling_Or_Settlement"
              and ARTICLE_77_FLAG_DEFAULT is False
              and article_77_missing_inputs()
                  == list(ARTICLE_77_REQUIRED_INPUTS)
              and article_77_compensation() is None
              and article_77_compensation(
                  has_judicial_ruling_or_settlement=True,
                  contract_type="unlimited",
                  contract_compensation_amount=5000) is None
              and "منفصل تمامًا عن مكافأة نهاية الخدمة" not in _seg81_ar
              and "9) تعويض المادة 77" not in _seg81_ar
              and "ترك العمل بحالات المادة 81" not in _seg77_ar
              and "entirely separate from the end-of-service benefit" not in _seg81_en
              and "9) Article 77 compensation" not in _seg81_en
              and "8) Leaving work under Article 81" not in _seg77_en)

        # لا اختلاط: مرجع المكافأة (84/85) لا يتغيّر بتفعيل مدخل المادة 77؛ فالتعويض
        # لا يُمزج بناتج المكافأة ولا بنسبة art81 (الحالات السبعة تبقى بلا تعويض).
        check("EOSB: تعويض المادة 77 لا يُخلط بمكافأة نهاية الخدمة ولا بنسبة art81",
              eosb_reference_amount(3, 10000, resigned=False) == 15000.0
              and eosb_reference_amount(1.9, 10000, resigned=True) == 0.0
              and article_77_compensation(
                  has_judicial_ruling_or_settlement=True,
                  contract_type="unlimited",
                  contract_compensation_amount=15000) is None)

        # حواجز الموضوع: غير المكافأة لا تحمل هذه القواعد إطلاقاً (بلا تعميم ضار)،
        # بما فيها تعويض المادة 77 كي لا يتسرّب إلى موضوعات لا تخصّ المكافأة.
        check("EOSB: الموضوعات غير المرتبطة بالمكافأة بلا هذه القواعد",
              all("المادة 84" not in build_prompt(t, "ar")
                  and "المادة 87" not in build_prompt(t, "ar")
                  and "المادة 81" not in build_prompt(t, "ar")
                  and "المادة 77" not in build_prompt(t, "ar")
                  and "Article 84" not in build_prompt(t, "en")
                  and "Article 87" not in build_prompt(t, "en")
                  and "Article 81" not in build_prompt(t, "en")
                  and "Article 77" not in build_prompt(t, "en")
                  for t in TOPICS if t["id"] not in EOSB_TOPIC_IDS))

        # القرارات النهائية: وثيقة النظام بلا وسوم المراجعة القديمة الخاصة بالمادة 81/77،
        # وتوثّق القاعدة الحسابية المعتمدة وإخلاء المسؤولية، ويبقى تنبيه المستخدم قائماً.
        try:
            _domain_md = (BASE_DIR / "docs" / "DOMAIN_RULES.md").read_text(
                encoding="utf-8")
        except OSError:
            _domain_md = ""
        check("DOCS: أُزيلت وسوم المراجعة القديمة بشأن المادة 81/77 من DOMAIN_RULES",
              bool(_domain_md)
              and "⚠️ يحتاج اعتمادًا واضحًا لتفسير المادة 81" not in _domain_md
              and "[مراجعة بشرية: نموذج الإدخال غير مُعرَّف]" not in _domain_md
              and "**[مراجعة بشرية]** المعالجة الحسابية أعلاه" not in _domain_md)
        check("DOCS: DOMAIN_RULES يوثّق قاعدة المادة 81 الحسابية المعتمدة وإخلاء المسؤولية",
              "قاعدة حسابية معتمدة في المنتج" in _domain_md
              and "افتراض حسابي لتقدير الحقوق" in _domain_md
              and "ليس إثباتًا قانونيًا لوقوع المخالفة" in _domain_md
              and "إقرارًا بمسؤولية صاحب العمل" in _domain_md
              and "بلا حدّ أدنى للخدمة" in _domain_md)
        check("DOCS: DOMAIN_RULES يوضّح أن عدم احتساب المادة 77 سياسة برنامج لا شرط نظامي",
              "عدم الاحتساب التلقائي سياسة للبرنامج" in _domain_md
              and "شرط نظامي مطلق" in _domain_md
              and "استحقاق التعويض وتقديره مسألة منفصلة" in _domain_md)
        check("DOCS: إخلاء المسؤولية العام للمستخدم باقٍ (نصّ عربي وإنجليزي)",
              bool(DISCLAIMER_AR) and bool(DISCLAIMER_EN)
              and "استشارة قانونية" in DISCLAIMER_AR
              and "not legal advice" in DISCLAIMER_EN)

        # التحقق الحسابي بمرجع حتمي يطابق معادلة calculateEOS() في index.html —
        # لا بحساب يقدّمه النموذج. الحدود محسوبة من النصّ: (84) نصف شهر ×5 ثم
        # شهر كامل، و(85) صفر/ثلث/ثلثان/كاملة، والخمس بالضمن تبقى ثلثاً.
        check("EOSB: مرجع المادة 84 — نصف شهر عن السنوات الخمس ثم شهر كامل بعدها",
              eosb_reference_amount(4, 10000, resigned=False) == 20000.0
              and eosb_reference_amount(5, 10000, resigned=False) == 25000.0
              and eosb_reference_amount(7, 10000, resigned=False) == 45000.0
              and eosb_reference_amount(2.5, 10000, resigned=False) == 12500.0
              and eosb_reference_amount(0.5, 10000, resigned=False) == 2500.0)
        check("EOSB: مرجع المادة 85 — نِسَب الاستقالة بحدودها الأربعة",
              eosb_reference_amount(1.9, 10000, resigned=True) == 0.0
              and abs(eosb_reference_amount(2, 9000, resigned=True) - 3000.0) < 1e-9
              and abs(eosb_reference_amount(5, 9000, resigned=True) - 7500.0) < 1e-9
              and abs(eosb_reference_amount(7.5, 12000, resigned=True) - 40000.0) < 1e-9
              and eosb_reference_amount(10, 10000, resigned=True) == 75000.0
              and eosb_reference_amount(12, 10000, resigned=True) == 95000.0)

        # المرجع الحسابي لا يُستدعى في مسار الإنتاج: legal_rules_for تُعيد نصّ
        # المواد 84-88 للمكافأة فقط، وفارغاً لكل ما عداها، ولغة غير معروفة ⇒ الإنجليزية.
        check("EOSB: legal_rules_for مقيّدة بموضوعات المكافأة وبالمادتين (ar|en)",
              set(EOSB_LEGAL_RULES) == {"ar", "en"}
              and legal_rules_for(topic_by_id("eosb-resignation"), "ar")
                  == EOSB_LEGAL_RULES["ar"]
              and legal_rules_for(topic_by_id("labor-art85"), "en")
                  == EOSB_ARTICLE85_LEGAL_RULES["en"]
              and "Article 84" in legal_rules_for(topic_by_id("labor-art85"), "en")
              and "Article 87" not in legal_rules_for(topic_by_id("labor-art85"), "en")
              and legal_rules_for(topic_by_id("cv-ats-optimization"), "ar") == ""
              and legal_rules_for(topic_by_id("daily-monthly-wage"), "en") == ""
              and legal_rules_for(topic_by_id("eosb-basics"), "fr")
                  == EOSB_LEGAL_RULES["en"])

        # البوابات لم تُضعّف: قيمها المرجعية كما هي (فحص حارس لا يعتمد على النصوص).
        check("EOSB: بوابات الجودة ومصادر الرسمية لم تُضعّف (قيم مرجعية)",
              MIN_WORDS == {"ar": 250, "en": 250} and MIN_SECTIONS == 3
              and MIN_TOTAL_CHARS == 1200 and SOURCE_MIN_BYTES == 200
              and ALLOWED_SOURCE_SUFFIXES == (".gov.sa",)
              and BLOCKED_SOURCE_HOSTS == {"mol.gov.sa", "www.mol.gov.sa"})

        # (ظ) لغة المقال: article_lang / --article-lang — عزل اللغة غير المختارة عن
        #     التوليد والكتابة وتحديث الحالة، وحماية المسودة العربية المعتمدة.
        #     كلها بمحاكاة كاملة بلا شبكة وبلا API وبمجلد مؤقّت معزول.
        def _fake_groq_record():
            """يسجّل عدد طلبات التوليد لكل لغة ويعيد ظرف Groq صالحاً للغة المطلوبة."""
            _rec = {"ar": 0, "en": 0}

            def _fn(url, **kwargs):
                prompt = _request_prompt(kwargs)
                _lang = "en" if "لغة المخرجات: English" in prompt else "ar"
                _rec[_lang] += 1
                topic_id = _topic_id_from_prompt(prompt)
                return _groq_envelope(lang=_lang, topic_id=topic_id) + (url,)

            return _fn, _rec

        def _capture(fn):
            """يشغّل fn() مع التقاط stdout ويرجع (rc, out). لا يبتلع SystemExit."""
            _saved = sys.stdout
            _cap = tempfile.TemporaryFile(mode="w+", encoding="utf-8")
            try:
                sys.stdout = _cap
                _rc = fn()
                sys.stdout = _saved
                _cap.seek(0)
                return _rc, _cap.read()
            finally:
                sys.stdout = _saved
                _cap.close()

        check("article_lang: اختياري وافتراضيه both (توافق الاستدعاءات والاختبارات السابقة)",
              run_once.__kwdefaults__.get("article_lang") == "both"
              and run_once.__kwdefaults__.get("social_lang") == "both")

        # (ظ-1) حماية المسودة العربية المعتمدة: الحالة ar=draft/en=error، وملف عربي
        #       بعلامة مميزة؛ ثم دورة en فقط ⇒ لا يُمَس الملف العربي ولا تتغيّر حالته.
        _sandbox()
        _AR_MARK = b"<!-- APPROVED_AR_DRAFT_DO_NOT_OVERWRITE -->"
        _seed = default_state()
        _seed["topics"]["labor-art81"] = {"ar": "draft", "en": "error",
                                          "published_at": None, "attempts": 1}
        atomic_write_json(STATE_JSON, _seed)
        _ar_path = DRAFTS_DIR / "ar" / "labor-art81-ar.html"
        atomic_write_text(_ar_path, _AR_MARK.decode("ascii"))
        _ar_before = _ar_path.read_bytes()
        fake, _rec = _fake_groq_record()
        globals()["http_request_full"] = fake
        rc = run_once(mode="draft", provider="groq", api_key=_FAKE_GROQ_KEY,
                      skip_source_check=True, topic_id="labor-art81",
                      article_lang="en", social_lang="ar")
        _st = load_state()["topics"]["labor-art81"]
        _en_path = DRAFTS_DIR / "en" / "labor-art81-en.html"
        check("article_lang=en: توليد إنجليزي واحد فقط (لا طلب عربي)",
              rc == 0 and _rec == {"ar": 0, "en": 1})
        check("article_lang=en: ملف المسودة العربية لم يتغيّر بايتاً واحداً",
              _ar_path.read_bytes() == _ar_before)
        check("article_lang=en: العربية بقيت draft والإنجليزية صارت draft",
              _st["ar"] == "draft" and _st["en"] == "draft")
        check("article_lang=en: المسودة الإنجليزية كُتبت في المسار المعزول فقط",
              _en_path.exists() and _en_path.parent == DRAFTS_DIR / "en")

        # (ظ-2) article_lang=ar: العربية فقط، بلا ملف إنجليزي وبلا تغيير لحالة en؛
        #       ومع social_lang=en لإثبات الاستقلال بين الخيارين.
        _sandbox()
        fake, _rec = _fake_groq_record()
        globals()["http_request_full"] = fake
        rc = run_once(mode="draft", provider="groq", api_key=_FAKE_GROQ_KEY,
                      skip_source_check=True, topic_id="labor-art81",
                      article_lang="ar", social_lang="en")
        _st = load_state()["topics"]["labor-art81"]
        check("article_lang=ar: العربية فقط ولا ملف إنجليزي ولا تغيير لحالة en",
              rc == 0 and _rec == {"ar": 1, "en": 0}
              and (DRAFTS_DIR / "ar" / "labor-art81-ar.html").exists()
              and not (DRAFTS_DIR / "en" / "labor-art81-en.html").exists()
              and _st["ar"] == "draft" and _st["en"] == "pending")

        # (ظ-3) الافتراضي both (بلا تمرير article_lang): اللغتان ومسودتان — سلوك محفوظ.
        _sandbox()
        fake, _rec = _fake_groq_record()
        globals()["http_request_full"] = fake
        rc = run_once(mode="draft", provider="groq", api_key=_FAKE_GROQ_KEY,
                      skip_source_check=True, topic_id="labor-art81")
        _st = load_state()["topics"]["labor-art81"]
        check("بلا article_lang (افتراضي both): اللغتان ومسودتان — السلوك السابق محفوظ",
              rc == 0 and _rec == {"ar": 1, "en": 1}
              and (DRAFTS_DIR / "ar" / "labor-art81-ar.html").exists()
              and (DRAFTS_DIR / "en" / "labor-art81-en.html").exists()
              and _st["ar"] == "draft" and _st["en"] == "draft")

        # (ظ-4) تجربة reasoning_effort=medium للإنجليزية فقط؛ العربية تبقى low، والتشخيص منظم.
        _sandbox_root = _sandbox()
        _effort_report = _sandbox_root / "generation_report.json"
        _saved_effort = os.environ.get("GROQ_EN_REASONING_EFFORT")
        _saved_report_path = os.environ.get("GENERATION_REPORT_PATH")
        os.environ["GROQ_EN_REASONING_EFFORT"] = "medium"
        os.environ["GENERATION_REPORT_PATH"] = str(_effort_report)
        _observed_efforts, _observed_counts = {}, {"ar": 0, "en": 0}
        def _fake_effort(url, **kwargs):
            body = json.loads(kwargs["data"].decode("utf-8"))
            prompt_text = _request_prompt(kwargs)
            chosen_lang = "en" if "لغة المخرجات: English" in prompt_text else "ar"
            _observed_efforts[chosen_lang] = body.get("reasoning_effort")
            _observed_counts[chosen_lang] += 1
            tid = _topic_id_from_prompt(prompt_text)
            return _groq_envelope(lang=chosen_lang, topic_id=tid) + (url,)
        try:
            globals()["http_request_full"] = _fake_effort
            rc = run_once(mode="draft", provider="groq", api_key=_FAKE_GROQ_KEY,
                          skip_source_check=True, topic_id="labor-art85", article_lang="both")
        finally:
            if _saved_effort is None:
                os.environ.pop("GROQ_EN_REASONING_EFFORT", None)
            else:
                os.environ["GROQ_EN_REASONING_EFFORT"] = _saved_effort
            if _saved_report_path is None:
                os.environ.pop("GENERATION_REPORT_PATH", None)
            else:
                os.environ["GENERATION_REPORT_PATH"] = _saved_report_path
        _report_data = json.loads(_effort_report.read_text(encoding="utf-8")) if _effort_report.exists() else {}
        check("Groq: medium اختياري للإنجليزية فقط مع صفوف تشخيص موحدة وحدّ استدعاءات",
              rc == 0 and _observed_efforts == {"ar": "low", "en": "medium"}
              and _observed_counts == {"ar": 1, "en": 1}
              and len(_report_data.get("results", [])) == 2
              and all("http_requests" in row and "stage" in row and "status" in row
                      and "reason" in row for row in _report_data["results"])
              and all(row.get("http_requests") == 1 for row in _report_data["results"])
              and all(row.get("token_usage_scope") == "cumulative_per_language"
                      and row.get("prompt_tokens") == 10 and row.get("completion_tokens") == 20
                      and row.get("total_tokens") == 30 and row.get("usage_responses") == 1
                      and row.get("rate_limit_hits") == 0
                      for row in _report_data["results"]))

        # (ظ-4) main() يمرّر --article-lang إلى run_once فعلاً (بمفتاح وهمي واستجابة محاكاة).
        _sandbox()
        fake, _rec = _fake_groq_record()
        globals()["http_request_full"] = fake
        _saved_gsk = os.environ.get("GROQ_API_KEY")
        os.environ["GROQ_API_KEY"] = _FAKE_GROQ_KEY
        try:
            rc_main, _out_main = _capture(lambda: main([
                "--topic", "labor-art81", "--mode", "draft", "--provider", "groq",
                "--article-lang", "en", "--skip-source-check"]))
        finally:
            if _saved_gsk is None:
                os.environ.pop("GROQ_API_KEY", None)
            else:
                os.environ["GROQ_API_KEY"] = _saved_gsk
        check("main(): --article-lang en يصل إلى run_once (إنجليزي فقط بلا طلب عربي)",
              rc_main == 0 and _rec == {"ar": 0, "en": 1}
              and (DRAFTS_DIR / "en" / "labor-art81-en.html").exists()
              and not (DRAFTS_DIR / "ar" / "labor-art81-ar.html").exists())

        # (ظ-5) --help يعرض الخيار، وargparse يرفض قيمة غير مسموحة (بلا أي توليد).
        _help_rc, _help_out = None, ""
        _saved_hout = sys.stdout
        _hcap = tempfile.TemporaryFile(mode="w+", encoding="utf-8")
        try:
            sys.stdout = _hcap
            try:
                main(["--help"])
            except SystemExit as _se:
                _help_rc = _se.code
            sys.stdout = _saved_hout
            _hcap.seek(0)
            _help_out = _hcap.read()
        finally:
            sys.stdout = _saved_hout
            _hcap.close()
        check("--help: يعرض --article-lang بخياراته {ar,en,both}",
              _help_rc == 0 and "--article-lang" in _help_out
              and "{ar,en,both}" in _help_out)

        try:
            main(["--article-lang", "fr"])
            _bad_rejected = False
        except SystemExit:
            _bad_rejected = True
        check("argparse: يرفض قيمة --article-lang غير مسموحة", _bad_rejected)
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
    parser.add_argument("--article-lang", choices=["ar", "en", "both"], default=None,
                        help="لغة المقال المولَّد (ar|en|both، الافتراضي both؛ مستقلة عن --social-lang)")
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
    article_lang = args.article_lang or "both"
    if article_lang not in ("ar", "en", "both"):
        article_lang = "both"

    try:
        return run_once(mode=mode, topic_id=args.topic, social_lang=social_lang,
                        article_lang=article_lang,
                        dry_run=args.dry_run, skip_source_check=args.skip_source_check,
                        provider=args.provider)
    except Exception as exc:  # noqa: BLE001
        log(f"[ERROR] فشل غير متوقّع: {redact(exc)}")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
