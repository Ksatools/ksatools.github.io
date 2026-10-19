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
from datetime import datetime, timezone
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
    r"(?P<seconds>\d+(?:\.\d+)?)\s*(?:s|sec(?:ond|onds)?|m|min(?:ute|utes)?)\b",
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


def fixture_data(lang: str, topic_id: str = "eosb-basics") -> dict:
    """نموذج اختباري داخلي؛ يتضمن مثال مكافأة مضبوطاً للموضوعات القانونية فقط."""
    is_eosb = topic_id in EOSB_TOPIC_IDS
    scenario = (
        "resignation" if topic_id in {"labor-art85", "eosb-resignation", "contract-end-vs-resignation"}
        else "article81" if topic_id == "labor-art81"
        else "base"
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


def _has_numeric_retry_after(value) -> bool:
    """True عند وجود Retry-After رقمي صالح بالثواني (تُدعَم الأرقام فقط حالياً)."""
    if value is None:
        return False
    try:
        seconds = float(str(value).strip())
    except (TypeError, ValueError):
        return False
    return seconds >= 0 and seconds == seconds


def classify_failure(status, raw, *, retry_after=None) -> tuple:
    """يصنّف استجابة فشل من مزوّد المحتوى إلى (retryable, code, note).

    - auth  : 401/403 (مفتاح ناقص/غير صالح/بلا صلاحية) — لا يُعاد.
    - model : 404 أو رسالة تدلّ على نموذج غير متاح — لا يُعاد (العِلاج تغيير النموذج).
    - quota : 429 مع دلالة حصة يومية صريحة — لا يُعاد (تكراره بلا فائدة).
    - rate_limit : 429 مؤقّت، ومنها TPM أو Retry-After أو مهلة مذكورة في النص.
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
                or _has_numeric_retry_after(retry_after)):
            return True, "rate_limit", "تجاوز معدّل مؤقّت"
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
    ولا تحدث إطلاقاً عند 401/403 أو نموذج غير متاح أو حصة يومية صريحة، ويُحترم
    Retry-After ومهلة النص عند 429. `retries=0` في http_request_full يمنع تضاعف المحاولات.
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

        retry_after = header_get(resp_headers, "Retry-After")
        retryable, _code, _note = classify_failure(status, raw, retry_after=retry_after)
        if retryable and attempt + 1 < tries:
            # بعض استجابات Groq تذكر مهلة في نص الخطأ من دون ترويسة Retry-After.
            if not retry_after:
                response_text = raw.decode("utf-8", "replace") if isinstance(
                    raw, (bytes, bytearray)) else str(raw or "")
                wait_match = RETRY_DELAY_RE.search(response_text)
                if wait_match:
                    retry_after = wait_match.group("seconds")
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
        "2) الاستحقاق عند الاستقالة (المادة 85): الاستقالة لا تستلزم مدة ثلاثة أشهر؛ "
        "فحدّ الأدنى للاستحقاق هو خدمة متتالية لا تقل عن سنتين. فمن خدم سنتين إلى "
        "خمس سنوات فله ثلث المكافأة، وما زاد على خمس سنوات ولم يبلغ عشر سنوات "
        "ثلثاها، وما بلغ عشر سنوات فأكثر فالمكافأة كاملة. ومدة الإشعار بثلاثين "
        "يوماً أو حسم طلب الاستقالة بعد ثلاثين يوماً (المادتان 75 و79 مكرر) ليسا "
        "شرطاً للاستحقاق.\n"
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
        "2) Entitlement on resignation (Article 85): resignation does not require "
        "three months; the minimum threshold for entitlement is two consecutive "
        "years of service. From two to five years the entitlement is one third of "
        "the benefit; above five but below ten years it is two thirds; at ten "
        "years or more it is the full benefit. The thirty-day notice period, or a "
        "resignation request deemed accepted after thirty days (Articles 75 and "
        "79-bis), is not an entitlement threshold.\n"
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


def legal_rules_for(topic, lang: str) -> str:
    """قواعد المواد 80 و81 و84–88 لبرومبت الموضوع — لموضوعات المكافأة فقط وبلا تعميم."""
    if topic.get("id") not in EOSB_TOPIC_IDS:
        return ""
    return EOSB_LEGAL_RULES["ar" if lang == "ar" else "en"]


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


def validate_eosb_calculation_example(raw, *, topic, article_text: str, example_text: str) -> None:
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
                       sleep=None):
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
        # GPT-OSS supports low|medium|high reasoning_effort in Chat Completions.
        # Low effort reduces reasoning-token overhead; strict JSON schema and all
        # downstream validation gates remain enabled.
        "reasoning_effort": "low",
        "max_tokens": 12000,
        "response_format": groq_response_format(),
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


def validate_article(data, *, topic, lang, published_at) -> dict:
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

    body_text = " ".join(s["body"] + " " + " ".join(s["bullets"]) for s in sections)
    faq_text = " ".join(f"{f['q']} {f['a']}" for f in faq)
    audit_text = " ".join((title, meta_description, excerpt, body_text, faq_text))
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
    for lang in lang_order:
        if (topic["id"], lang) in published_pairs:
            log(f"[SKIP] النسخة {lang} منشورة سابقاً — لا إعادة إنشاء.")
            continue
        attempted = True
        log(f"توليد النسخة {lang}…")
        if dry_run:
            ok, data, msg = True, fixture_data(lang, topic_id=topic["id"]), "fixture"
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

    if topic["id"] in EOSB_TOPIC_IDS and results.get("ar") and results.get("en"):
        pair_problems = validate_eosb_translation_pair(results["ar"], results["en"])
        if pair_problems:
            reason = "; ".join(pair_problems)
            log("[REJECT] مثال المكافأة مختلف بين النسختين؛ لن تُحفظ أي منهما: " + reason)
            for lang in ("ar", "en"):
                state["topics"][topic["id"]][lang] = "rejected"
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

    eosb_pair_bad = fixture_data("en", topic_id="labor-art85")
    eosb_pair_bad["calculation_example"].update({
        "monthly_wage": "10000", "full_benefit": "35000", "payable_benefit": "23333.33",
    })
    eosb_pair_bad["sections"][3]["body"] = (
        eosb_pair_bad["sections"][3]["body"]
        .replace("SAR 12,000", "SAR 10,000")
        .replace("SAR 42,000", "SAR 35,000")
        .replace("SAR 28,000", "SAR 23,333.33")
    )
    eosb_pair_bad_article = validate_article(
        eosb_pair_bad, topic=eosb_topic, lang="en", published_at="2026-01-01")
    check("تدقيق EOSB: يرفض اختلاف المثال الحسابي بين اللغتين رغم صحة كل نسخة منفردة",
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

        # 5) فشل المزوّد كما في التشغيل 38946220138 (http_400 json_validate_failed):
        #    لا نشر ولا مسودة ولا أي كتابة في ملفات عامة، وبلا رجوع إلى وضع أضعف
        #    وبلا إعادة لهذا الخطأ (غير قابل لإعادة المحاولة: محاولة واحدة لكل نسخة).
        _fail_reqs, _fail_calls = [], {"ar": 0, "en": 0}

        def _schema_400(url, **kwargs):
            _fail_reqs.append(json.loads(kwargs["data"].decode("utf-8")))
            prompt = _request_prompt(kwargs)
            _fail_calls["en" if "لغة المخرجات: English" in prompt else "ar"] += 1
            return (400, {},
                    b'{"error":{"message":"Failed to validate JSON",'
                    b'"code":"json_validate_failed"}}', url)

        _sandbox()
        before = (ARTICLES_JSON.read_bytes(), SITEMAP_XML.read_bytes())
        globals()["http_request_full"] = _schema_400
        rc, out = _capture_run(mode="auto", provider="groq", api_key=_FAKE_GROQ_KEY)
        st = load_state()["topics"][TOPICS[0]["id"]]
        check("فشل المزوّد (http_400 json_validate_failed): لا نشر ولا أي كتابة في ملفات عامة",
              rc == EXIT_GENERATION_FAILED and st.get("ar") == "error"
              and st.get("en") == "error" and not DRAFTS_DIR.exists()
              and not ARTICLES_DIR.exists() and not SOCIAL_TXT.exists()
              and (ARTICLES_JSON.read_bytes(), SITEMAP_XML.read_bytes()) == before)
        check("فشل المزوّد: يبقى الطلب صارماً بلا رجوع إلى وضع أضعف وبلا إعادة",
              _fail_calls == {"ar": 1, "en": 1} and len(_fail_reqs) == 2
              and all(r.get("reasoning_effort") == "low"
                      and (r.get("response_format") or {}).get("type") == "json_schema"
                      and ((r.get("response_format") or {}).get("json_schema") or {}
                           ).get("strict") is True
                      for r in _fail_reqs)
              and "json_validate_failed" in out
              and "غير قابل لإعادة المحاولة" in out
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
            "الاستقالة لا تستلزم مدة ثلاثة أشهر",
            "خدمة متتالية لا تقل عن سنتين",
            "فالمكافأة كاملة",
            "المادتان 75 و79 مكرر",
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
            "resignation does not require three months",
            "two consecutive years of service",
            "one third of the benefit",
            "two thirds",
            "the full benefit",
            "Articles 75 and 79-bis",
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
                _markers = _eosb_ar_markers if _lang == "ar" else _eosb_en_markers
                if any(_m not in _p for _m in _markers):
                    _bad_eosb_prompts.append(f"{_tid}/{_lang}")
        check("EOSB: قواعد المواد 84-88 تصل بروموت كل موضوعات المكافأة في اللغتين",
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
                  == EOSB_LEGAL_RULES["en"]
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
