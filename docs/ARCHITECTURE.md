# ARCHITECTURE.md — بنية منصة ksatools

> مصدر الحقيقة في هذه الوثيقة: `index.html` كما هو على القرص (v2.1، 4,244 سطراً، ينتهي بـ`</html>`).
> كل معلومة هنا تحقّقت منها في الكود. ما لم يتحقّق فهو بوسم `(غير متحقق)`.

---

## 1) نظرة عامة

| الصفة | القيمة |
|---|---|
| نوع الموقع | صفحة ثابتة واحدة (SPA نصّاً) |
| ملف التطبيق | `index.html` فقط |
| الأدوات | 4، كل واحدة `<section class="tool-section">` |
| البناء / التجميع | لا يوجد — الملف يُنشر كما هو |
| الخادم / الواجهة البرمجية | لا يوجد |
| التخزين | `localStorage` (محلي، داخل المتصفّح فقط) |
| المكتبات الخارجية | لا يوجد (خطوط Google فقط) |
| لغات الواجهة | `ar` (RTL) و`en` (LTR) |

الملفات الأخرى في جذر الموقع: `privacy.html`، `404.html`، `ads.txt`، `robots.txt`، `sitemap.xml`، الأيقونات و`site.webmanifest`، و`og-image.png`. **جميعها موجودة فعلاً في المستودع** (صحّح ادعاءً سبق أن أورد "غير موجودة").

---

## 2) مسار التحميل

1. `<html lang="ar" dir="rtl" id="html-root" data-theme="light">`.
2. `<head>` بالترتيب الفعلي: `<meta charset="UTF-8">` **أول عنصر** ← `<meta name="google-site-verification">` ← الوصف والكلمات المفتاحية و`robots` ← `canonical` ← `viewport` ← `<title>` ← `theme-color` ← الأيقونات والـmanifest ← `hreflang` (ثلاث قيم) ← Open Graph ← Twitter Card ← خطوط Google (Cairo + Inter) ← JSON-LD.
3. `<body>`: `<header>` الموقع ← `<div class="ad-slot" id="ad-top">` (مخفٍ) ← `<nav class="nav-tabs" id="main-tabs" role="tablist">` ← أقسام الأدوات الأربعة ← `<footer>` (لقطات الموقع + شريط الخصوصية + إخلاء المسؤولية) ← حاوية النشرة/الشيت `<div id="share-sheet" role="dialog">` ← `<div id="toast">`.
4. `<script>` واحد (الجافاسكربت كله)، ثم **سكربت Adsterra Social Bar** في نهاية `<body>` قبل `</body>`، ثم `</body>` و`</html>`.

**سكربتان خارجيان فقط**: نصّ JSON-LD (يُتحقّق من صحته)، وسكربتَا Adsterra (`Social Bar` + `Native Banner`). لا شيء آخر.

---

## 3) خريطة CSS

داخل `<style>` واحد، مرتّبة بهذا التسلسل:

- **الهوية الأساسية** — `--primary`، `--primary-dark`، `--primary-light`، `--accent` (لون الهوية لا يُغيَّر أبداً).
- **المحايدات** — `--bg`، `--card`، `--border`، `--text`، `--muted`، `--primary-soft`، `--primary-text`، `--primary-border`، `--accent-soft`، `--accent-deep`، `--surface-1/2`، `--danger*`، `--gold`… إلخ.
- **الوضع الليلي** — عبر `html[data-theme="dark"]` (يُعاد فيه تعريف **مجموعة محددة فقط**: `--primary-soft`، `--primary-text`، `--primary-border`، `--primary-gradient`، `--accent`، `--dark`، `--bg`، `--card`، `--border`، `--surface-*`). **لا يُعاد تعريف** `--primary`، `--primary-dark`، `--gold`، ولا أي متغيّر من مجموعة `--paper-*`.
- **بطاقات النتيجة** — `--primary-light`/`--accent-deep`/`--border` (محسوبة تبايناً ضد الخلفية).
- **قالب السيرة `--paper-*`** — تظلّ بيضاء في الوضعين لأنها مجموعة منفصلة لا تعاد تعريفها ليلياً.
- **إطار الورقة** — `--cv-frame-border` و`--cv-frame-shadow`، بقيمتين: نهارية وليلية.
- **الترويسة/التذييل** — القواعد **مقيّدة على `body > header` و`body > footer`**.
- **الأحجام وشبكة** — الحاويات بـ`max-width: 1080px`، والشبكة `.grid-2` بـ`repeat(2, minmax(0, 1fr))`.
- **المتصفّح (Responsive)** — `min-width: 901px` (عمودان، و`.cv-side` **بلا** قيد `sticky`/`max-height` كي لا تُقصّ معاينة السيرة)، `max-width: 900px` (عمود واحد)، `max-width: 560px`، `max-width: 860px`.
- **معاينة/طباعة الكشف** — `.cv-doc` وأصناف `cvd-*`.

### 3.1 نظام الألوان (بيئة عمل يجب عدم تغييرها)
`--primary` / `--primary-dark` / `--primary-light` / `--accent` → الهوية.
مجموعة `--paper-*` (`--paper`، `--paper-text`، `--paper-ink`، `--paper-sub`، `--paper-muted`، `--paper-accent`، `--paper-line`، `--paper-border`…) → ورقة السيرة الدائمة البيضاء.
مجموعة `--cv-frame-*` → إطار الورقة وظلالها فقط، مع `background-clip: padding-box` حتى لا يظهر إطار على الحواف.

### 3.2 مستند السيرة `.cv-doc`
- الخلفية بيضاء في الوضعين نهائياً عبر `--paper` (وليس `!important` على الألوان).
- الحدّ الخارجي من `--cv-frame-border` والظل من `--cv-frame-shadow`.
- أصناف `cvd-*` تلوّن عبر `--paper-accent` / `--paper-sub` / `--paper-ink` / `--paper-line` فقط.
- `.cvd-ltr` يعزل الاتجاه (`direction: ltr; unicode-bidi: isolate`) حتى لا تنقلب `+966`.
- `cvd-contact` يُبنى بـ`display: flex` ليمنع المتصفّح من إعادة ترتيب العناصر.

### 3.3 الطباعة
يوجد **كتلتا `@media print`**: الأولى (تُخفي الترويسة/التذييل/التبويبات/الإعلانات/الشارات/الـtoast/الشيت وتُحوي `.grid-2` والـ`.ats-panel`) والثانية (الكتلة الأكبر للمستند). مزامنة التلوين في الكتلة الثانية جرت بقيمة لونية مضمّنة داخل القالب. الحالة الحالية: **كتلتان، لم تُدمجا بعد** (Backlog).

---

## 4) خريطة الجافاسكربت

السكربت كله في وسم `<script>` واحد. الترتيب كالتالي:

### 4.1 الثوابت والأدوات الأساسية
| الاسم | الدور |
|---|---|
| `store` | غلاف آمن لـ`localStorage` (`store.get` / `store.set`) بمعالجة أخطاء |
| `CONFIG` | `GOSI_CAP: 45000`، `DBR: 1 / 3`، `RATES_UPDATED: '2026-07'`، وجدول `GOSI` |
| `gosiScheme(cat, d)` | تُرجع نسبة المساهمة حسب الفئة **وتاريخ التنفيذ** |
| `urlLang` / `currentLang` | اختيار اللغة من `?lang=` ثم `store.get('seh_lang')` ثم افتراضي `ar` |
| `i18n` | كائن عملاق `ar` / `en` |
| `t(key)` | جلب نصّ متغيّر، وإن لم يوجد يرجع المفتاح نفسه |
| `$`, `clamp`, `numVal`, `debounce`, `formatSAR`, `showToast` | أدوات عامة |

**تنبيه**: `formatSAR()` تنشئ `new Intl.NumberFormat(...)` **في كل استدعاء** (تيقّن: `Intl.NumberFormat` لا تُحجز في ثابت) — Backlog.

### 4.2 الطباعة والتواريخ
- `refreshPrintDate()` — يعبّئ التاريخ المطبوع **الجريجوري + الهجري** (`toLocaleDateString('ar-SA-u-ca-gregory')`).
- `printDoc(id)` — يضبط `data-print-tool` ثم `window.print()`. مستخدَم عبر أزرار `eos-print` / `sal-print` و`data-print-tool` في قوالب الطباعة.
- `localDateStr(date)` — يرجع تاريخاً بصيغة **ISO `YYYY-MM-DD`** (وليس صيغة عربية مختصرة).

### 4.3 المشاركة (المهم للسير)
| الاسم | الدور |
|---|---|
| `buildShareLink(tool, params)` | يبني الرابط من السؤال الحالي (يحافظ على الـquery الموجود) |
| `eosSharePayload()` | يبني `{ tool, s, y, m, d, ld, lb, bs }` **+** نصّ المشاركة. **لا يضع `r`** (سبب الاستقالة) |
| `salSharePayload()` | يبني `{ tool, b, h, l, o, c }` |
| `applyShareParams()` | يقرأ السؤال ويطبّق القيم، ثم **ينتهي بـ`saveInputs()`** |
| `buildShareText(what)` / `initShareSheet()` / `shareTo(w)` / `closeShareSheet()` | نصّ المشاركة وشريط المشاركة (`#share-sheet`) |

**مسار الرابط**: `?tool=eos|sal|…&s=…#tool-id` + أهداف `#tool` مثل `#eos-tool`.

### 4.4 الحفظ المحلي
- `PERSIST_KEY = 'seh_inputs_v2'`.
- `saveInputs()` — **دالة مؤجَّلة `debounce` 300ms** تحفظ `value` لكل عنصر يحمل `data-persist`.
- `restoreInputs()` — تُعيد القيم. **تستخدم `localStorage.getItem` مباشرة** (أي عكس `store.get`) — Backlog.
- مفاتيح التخزين كاملة: **`seh_inputs_v2`**، **`seh_theme`**، **`seh_lang`**.
- `data-persist` موجود على: كل مدخلات وقوائم `eos-*`، وكل `sal-*`، وكل `let-*`، و`cv-doc-lang`، و**`cv-data`** (حقل مخفي يحمل حالة السيرة كاملة JSON).

### 4.5 المظهر واللغة والتبويبات
- `applyTheme(theme)` — يضبط `data-theme` وأيقونة الزر. **يستخدم `localStorage.setItem` مباشرة**، **ولا يضبط `aria-label`**.
- `toggleLanguage()` — **يستخدم `localStorage.setItem` مباشرة**.
- `applyI18n()` — يطابق `data-i18n` (نصّ) و`data-i18n-ph` (placeholder). **لا يوجد `data-i18n-html`**، لذا يُستبدل `<strong>` داخل `disclaimer` بنصّ خام.
- `TOOL_IDS = ['eos-tool', 'salary-tool', 'letter-tool', 'cv-tool']`.
- `switchTool(toolId, setHash)` — يبدّل التبويب ويضبط `aria-selected`/`tabindex`، ثم `history.replaceState(null, '', '#' + toolId)` مع **الحفاظ على الـquery**.
- `initTabs()` — يبني **أسهماً راجعة وأمامية تراعي `document.documentElement.dir === 'rtl'`** و**`Home` / `End`**.
- **لا يوجد مستمع `hashchange`** — أزرار الواجهة والفوتر (#tool) لا تعمل بعد التبويب.

### 4.6 الحاسبات
**`calculateEOS()`** (مكافأة نهاية الخدمة) — راجع `docs/DOMAIN_RULES.md`. تلخّص: `#eos-basic` تدخل فقط عند `leaveBasis === 'basic'`، وإلا الاستناد `salary × 0.75`. تُغطّي الناتج في بطاقات `eos-*`.

**`calculateSalary()`** (الراتب) — `sal-category` (سعودي/وافد/نظام جديد)، الحقول `sal-basic` / `sal-housing` (فارغ ⇒ `basic × 0.25`) / `sal-transport` / `sal-obligations`. تُنفّذ سلم الرواتب، استقطاع `DBR`، سقف `GOSI_CAP`، وتُرجّع قدرة تمويلية.

**`generateLetter()`** — 6 أنواع خطابات (`let-type`)، بلغة `let-doc-lang`. التاريخ المطبع يأخذ `let-date` وإن غاب فـ`localDateStr(new Date())` (**صيغة ISO**)، ويُضاف التاريخ الهجري في العربية عبر `hijriToday()`.

### 4.7 السيرة الذاتية
| الاسم | الدور |
|---|---|
| `cvState` | كائن حالة السيرة (`p` لبيانات الشخص، `summary`، `exp[]`، `edu[]`، `skills`، `certs`، `langs`) |
| `cvHydrate()` / `cvSave()` / `cvSync()` | قراءة/حفظ/مزامنة الحالة مع `#cv-data` |
| `cvRenderAll()` / `cvRender()` / `cvRenderTags()` / `cvRenderTagsAll()` | رسم اللوح + العارض |
| `cvSecHTML()`, `cvPlainHTML()`, `cvDocHTML()`, `buildCV()` | بناء `innerHTML` للمستند |
| `cvDocHTML(lang, L, s)` | **يُنتج `<header class="cvd-head">`** (وليس `<div>`) مع `cvd-name`/`cvd-role`/`cvd-contact` |
| `CV_RULES` | `email`, `phone`, `metrics`, `verbs`, `bad`, `ats` — قواعد الفحص |
| `CV_SECTIONS`, `CV_STATUS_TEXT`, `CV_DEMO` | قواميس اللغة + بيانات تجريبية |
| `cvOpenStep()`, `cvStepDone()`, `cvUpdateStatus()`, `cvSetNavActive()` | الخطوات/التنقّل |
| `cvLoadDemo()`, `cvReset()`, `cvInit()` | الاستعادة والتصفير |
| `cvYearsSpan()`, `cvAutoSummary()`, `normalizeDigits()`, `cvEsc()`, `cvSplitTags()`, `cvDuties()` | مساعدات |
| `cvAfterInput()`, `cvAfterStruct()`, `updateCountHint()` | بعد التعديل |

**فحص "المقاييس"**: نصّ `metricsText = normalizeDigits(sumText + ' ' + dutiesAll)` **ثم `.replace(/\b(19|20)\d{2}\b/g, ' ')`** — هذه القاعدة تحذف أي سنة، ولذلك تُسقط عبارة مثل «2000 ريال» قبل اختبار `CV_RULES.metrics`. القاعدة نفسها في `CV_RULES` **تتضمن تفرعاً للعملة** (انتبه: الإصلاح نصف منجز) — Backlog.

---

## 5) تدفّق البيانات

```
مدخل المستخدم  (input/select)  ← data-persist
      │
      ├── change / input  →  bindCalc(...)  →  debounce(150ms)  →  calculateX()  ─┐
      │                                                                    │
      │                                                                    ├─→  كتابة النتيجة في DOM
      │                                                                    └─→  saveInputs()  (debounce 300ms)
      │                                                                            └─→  store.set('seh_inputs_v2', …)
      │
      └── تحميل الصفحة  →  restoreInputs()  →  applyShareParams()  →  (قد يتجاوز الحفظ)
```

ملاحظات متحقّق منها:
- الزر `#eos-calc-btn` / `#sal-calc-btn` يخوّل `calculateEOS()` / `calculateSalary()` أيضاً.
- `applyShareParams()` يُنفَّذ **بعد** `restoreInputs()`، لذا تغلب قيم المشاركة المُستعادة.
- التبويب يُستعاد عبر `switchTool` مع `history.replaceState` (لا `pushState`)، فما فوقه في الـhistory.

---

## 6) الاستعادة عبر الرابط (التحقق)

| التحقق | الحالة |
|---|---|
| إنشاء رابط من كشف EOS ثم فتحه في نافذة جديدة يعيد `s/y/m/d/ld/lb` | متحقّق يدوياً |
| `#eos-basic` + معامل `bs` يُقرأ ويُستعاد | متحقّق (يوجد في `eosSharePayload` وفي `applyShareParams`) |
| سبب الاستقالة `r` يُستعاد | متحقّق (يوجد في `applyShareParams`) |
| سبب الاستقالة `r` **يُنشَأ** في الرابط | **غير متحقق / كسر** (يغيب في `eosSharePayload`) — Backlog |
| التصفّح بروابط الفوتر `#tool` أثناء عمل التبويب | **غير متحقق** (لا `hashchange`) |

---

## 7) ملاحظات نشر داخل الملف

`index.html` يحتله **علقاً** `<!-- ============================================================ ملاحظات النشر ... -->` في رأس الملف (بند المهام: نقله إلى `DEPLOY_NOTES.md`). محتواه: إرشاد `ads.txt`، رابط `privacy.html` النسبي، خيار النشر على `/ar/` و`/en/`، وتأكيد عدم إرسال بيانات للخادم.

> لا تنسخ أي معرّف ناشر أو كود تحقق إلى هذه الوثيقة.

---

## 8) نظام التسويق/SEO الآلي (مضاف 2026-10-15)

### 8.1 `auto_marketing.py` — خط الأنابيب الكامل (stdlib فقط)

| الرمز | الدور |
|---|---|
| `TOPICS` | مصفوفة ≥30 موضوع (معرف + عناوين ar/en + مصادفة مصدر رسمي) |
| `run_once(*, mode, topic_id=None, social_lang="both", dry_run=False, skip_source_check=False, api_key=None, model=None)` | نقطة الدخول الوحيدة. `mode="draft"` (افتراضي) يكتب المسودات إلى `DRAFT_DIR`، لا يلمس `articles.json`/`sitemap.xml`. `mode="auto"` ينشر فقط بعد **كل** البوابات: طول/ترميز، مصدر رسمي (نطاقان مسموحان)، لا HTML/JS في الحقول، تحقق شبكة (اختياري)، فحص تقاطع `articles.json`/`sitemap.xml`. |
| `gemini_generate_json(prompt, *, api_key, model, timeout=90, retries=2)` | استدعاء Gemini REST، يعيد JSON منظَّم. النموذج الافتراضي `gemini-3.8-flash` (موثق رسمياً). |
| `validate_article(data, *, topic, lang, published_at)` | بوابة الجودة: يرفض HTML/JS في الحقول، يطالب بـ`meta_description`/`excerpt`/`sections`/`faq`/`official_sources`، يطيل النص لمتطلبات عدد الكلمات، يبني `slug` (معرف-اللغة)، يحسب `word_count`، يعيد كائن مقال كامل. |
| `duplicate_check(article, existing_records)` | يمنع تكرار الرابط أو العنوان (طبيعي بعد تطبيع المسافات). |
| `check_sources(sources, *, timeout=None)` | فحص شبكي للمصادر الرسمية: `GET` مع ترويسات طلب عادية (`SOURCE_REQUEST_HEADERS` = `User-Agent`/`Accept`/`Accept-Language`)، ويقبل `200` + جسم أكبر من `SOURCE_MIN_BYTES` فقط (رفض `403`/`404` فشلٌ لا يُتجاوز). يرجع قائمة مشاكل نصّية (فارغة = نجاح). |
| `is_allowed_source_url(url)` | بوابة ساكنة: `https` فقط، والنطاق `*.gov.sa` + `qiwa.sa` فقط (لا توسيع). `is_blocked_source_host` يحجب `mol.gov.sa` **وكل نطاقاته الفرعية**، ويُستعمل `parts.hostname` فلا تنطلي بيانات المستخدم/المنفذ أو لاحقة مضلّلة. |
| `probe_source(url, *, timeout=None) -> (ok, code, note)` | فحص مصدر واحد وتصنيف الفشل: `ok` · `dns` · `timeout` · `network` · `http_<status>` · `empty` (رسائل عربية واضحة بلا كشف أسرار). |
| `probe_sources(sources, *, timeout=None) -> list` | يفحص كل مصدر مرة واحدة ويرجع نتائج منظّمة `[{title,url,ok,code,note}]` — تُستعمل في `run_once` لسجل واضح بلا طلب مزدوج. |
| `normalize_source_url(url)` | تطبيع رابط المصدر: حذف المسافات، ترميز المسارات العربية UTF-8 (`%`)، وإسقاط `#fragment` — كي تنجح الروابط العربية في الطلب والنشر. |
| `official_sources_for(topic)` | المصادر الرسمية المفضّلة لموضوع من `OFFICIAL_SOURCE_LIBRARY`: مصدر أساسي ثم بديل رسمي لنفس الجهة؛ تُضمَّن في `build_prompt` لمنع اختراع روابط (مثل `mol.gov.sa`). |
| `render_article_html(article, *, published: bool)` | **قالب ثابت + تهريب** (`esc`) — **لا HTML خام من النموذج**. المنشور: `index,follow`، canonical، hreflang متبادل، JSON-LD، Social Bar + Native Banner مرة واحدة. المسودة: `noindex,nofollow`، لا canonical. |
| `write_article_files(article, *, published: bool) -> Path` | يكتب `articles/{lang}/{slug}.html` (ذرّي). |
| `merge_articles(existing, new_records)` | يدمج السجلات المنشورة، يحتفظ بأول `published_at`، يحتفظ بأحدث `updated_at`. |
| `article_record(art)` | يستخرج سجلاً للـ`articles.json` (بدون `content_hash`، بدون `sections`/`faq`/`official_sources`/`word_count`/`slug`). |
| `add_sitemap_entries(xml_text, entries)` | يُدرج قبل `</urlset>`، **يزيل التكرار داخل `entries` نفسها** (حارس انحدار: `article_sitemap_entries` يُرجع زوج اللغتين لكل مقال، قد يُمرّر مرتين). |
| `verify_outputs() -> list` | فحص غير متصل: `articles.json`/`sitemap.xml`/`index.html` + تقاطع (كل مقال منشور له ملف + سطر في sitemap). |
| `--selftest` / `--dry-run` / `--verify` / `--mode auto|draft` | واجهات سطر أوامر، **بلا شبكة** (إلا `auto` مع مفتاح). `dry-run` لا يلمس ملفات. |

**ملفات الحالة:**
- `articles.json` — مصفوفة سجلات منشورة (ثنائية اللغة، `translation_id` مشترك).
- `sitemap.xml` — الرئيسية + الخصوصية + مقالات (كل مقالة: ar + en + x-default).
- `latest_social_post.txt` — نص مشاركة لآخر مقال (ar/en، رابطين، وسم العلامة).
- `marketing_state.json` — `{ version, topics: { topic_id: { ar, en, attempts, published_at } }, last_run }`.
- `drafts/` — `ar/`, `en/` (خارج المستودع في Workflow: `$RUNNER_TEMP/drafts`).

### 8.2 `.github/workflows/ai_marketing.yml`

| ميزة | التفصيل |
|---|---|
| `on.schedule` | `cron: "0 9 * * *"` مع `timezone: "Asia/Riyadh"` (مدعوم رسمياً GitHub، لا تحويل UTC). |
| `workflow_dispatch` | `mode` (`auto`/`draft`)، `topic_id` اختياري، `social_lang`. |
| Jobs | `content` (تشغيل `auto_marketing.py`) + `deploy` (مشروط بـ`vars.PAGES_VIA_ACTIONS == 'true'`). |
| Secrets | `GEMINI_API_KEY`, `GEMINI_MODEL`, `TELEGRAM_BOT_TOKEN`, `TELEGRAM_CHAT_ID`. |
| Env | `PUBLISH_MODE` (افتراضي `draft`)، `SOCIAL_LANGUAGE` (افتراضي `both`)، `DRAFT_DIR` (`$RUNNER_TEMP/drafts`). |
| Permissions | `contents: read` (افتراضي)، `pages: write` + `id-token: write` فقط في `deploy`. |
| Concurrency | `group: ai-marketing`, `cancel-in-progress: true`. |
| Preflight | `python -m py_compile auto_marketing.py`، `--selftest`، `--verify` — **يفشل العمل قبل أي API**. |
| Drafts artefact | المسودات تُرفع كـ artefact (`drafts/`) للمراجعة البشرية، لا تُلتزم. |
| Deploy | افتراضي: `git push origin HEAD:<branch>` (Pages بفرع). اختياري: `actions/deploy-pages` عند `vars.PAGES_VIA_ACTIONS == 'true'`. |

### 8.3 `index.html` — قسم "أحدث الأدلة العمالية" (`section#guides`)

| العنصر | التفصيل |
|---|---|
| الموقع | مباشرة بعد `</main>`، قبل(Native Banner السفلية). |
| المفاتيح i18n | `guidesHeading`, `guidesIntro`, `guidesLoading`, `guidesEmpty`, `guidesError`, `guidesUpdated`, `guidesOther` (ar/en). |
| JS | `safeGuideUrl(raw)` — يقبل: مسار داخلي مطلق ينتهي بـ`.html`، أو رابط مطلق على `https://ksatools.github.io` (نفس الأصل أو النطاق الرسمي). يرفض: `javascript:`، `data:`، `vbscript:`، `//`، نطاقات خارجية، `..`. `guidesCard(item)` يبني `<article class="guide-card">` بـ`textContent` فقط. `renderGuides()` يفلتر `status === 'published' && lang === currentLang`، يرتّب تنازلياً، يقطع بـ`GUIDES_LIMIT=6`. `loadGuides()` يقرأ `articles.json` عبر `fetch` (حراس: `typeof fetch`، `location.protocol === 'file:'` → حالة خطأ صامتة بلا كونسول). |
| استدعاء | `loadGuides()` في `DOMContentLoaded` (بعد `initShareSheet()`)، و`renderGuides()` في `toggleLanguage()`. |

### 8.4 إصلاح خصوصية السيرة (`cvSharePayload`)

- **قبل:** `#cv-share` كان يستدعي `textSharePayload('shareCvTitle')` التي تشمل `#cv-output` (اسم، جوال، بريد، نص السيرة كاملاً).
- **بعد:** `cvSharePayload()` تُرجع نصاً مُصمّماً للمشاركة: `t('shareCvPrivacy')` + درجة ATS + التغذية الراجعة + وسم العلامة + رابط العلامة التجارية. لا بيانات شخصية.
- `#cv-share` يستدعي `cvSharePayload()` بدلاً من `textSharePayload()`.
- التحقق: `tests/smoke_test.py` يملأ السيرة بـ`cv-demo`، يفتح المشاركة، يتحقق `leaked=[]` ودرجة ATS موجودة.

### 8.5 سياسة المصادر الرسمية والتحقّق الشبكي (بعد تشغيل Groq #7 — 2026-10-16)

**المشكلة المرصودة:** الدورة #7 ولّدت المقالين بنجاح، لكن النموذج استشهد بـ`mol.gov.sa` (الاسم السابق لوزارة العمل) وهو نطاق لا يُترجَم عبر DNS (NXDOMAIN)، فرفض `check_sources` المقالين ورفعهما مسودتين غير متحقَّق منهما — بلا نشر (السلوك الآمن صحيح، لكن الجذر يجب إصلاحه).

**الإصلاح (بلا تجاوز أي بوابة):**
1. **منع النطاق الميت من البوابة الساكنة**: `BLOCKED_SOURCE_HOSTS = {"mol.gov.sa", "www.mol.gov.sa"}`، و`is_blocked_source_host(host)` يحجب النطاق **وكل نطاقاته الفرعية** (`portal.mol.gov.sa`) كي لا يمرّ نطاق ميت بدعوى لاحقة `.gov.sa`؛ فالمقال الذي يستشهد به يُرفض في `validate_article` بلا أي طلب شبكة. يستخدم `is_allowed_source_url` كذلك `parts.hostname` (يحذف المنفذ/بيانات المستخدم) فلا تنطلي حيل مثل `https://www.hrsd.gov.sa@evil.com/` أو `https://www.hrsd.gov.sa.evil.com/`.
2. **روابط رسمية معتمدة في البرومبت**: `OFFICIAL_SOURCE_LIBRARY` (hrsd.gov.sa، gosi.gov.sa، qiwa.sa) و`official_sources_for(topic)` تكتب قائمة صريحة بأسماء الجهات والروابط، وتحظر النطاق المنتهي — فلا يحتاج النموذج لتخمين رابط.
3. **بديل رسمي لكل موضوع**: لكل موضوع مصدر أساسي وبدائل معتمدة لنفس الجهة (`TOPIC_SOURCE_KEYS`)، فيبقى مصدر ثانٍ سليم متاح إذا فقد الأول.
4. **تصنيف فشل واضح**: `probe_source` يميّز `dns` · `timeout` · `network` · `http_<status>` · `empty`، ورسالة عربية واضحة لكل حالة بلا كشف أسرار، والسجل يطبع كل مصدر بـ`[OK]`/`[FAIL]`.
5. **ترويسات طلب عادية**: `SOURCE_REQUEST_HEADERS` (`User-Agent` + `Accept` + `Accept-Language`) لأن `hrsd.gov.sa` يردّ `403` بلا هذه الترويسات و`200` معها (تحقّق فعلي) — طلب HTTP عادي لا تجاوز، ورفض `403`/`404` يبقى فشلاً.
6. **تطبيع الروابط العربية**: `normalize_source_url` يرمّز المسار العربي `UTF-8` ويُسقط الـfragment كي يعمل الرابط في الطلب وفي صفحة المقال.
7. **الفحص يشمل النسختين**: `run_once` يفحص **اتّحاد** مصادر `ar`+`en` بلا تكرار وبتنفيذ واحد لكل رابط.

**الثابت (لم يتغيّر):** تعذّر التحقّق من أي مصدر ⇒ `draft_unverified` فقط، ولا يُلمس `articles.json`/`sitemap.xml`، و`PUBLISH_MODE=draft` يبقى الافتراضي. `--skip-source-check` يبقى للاستخدام اليدوي فقط ويُسجَّل `[WARN]`.

**تحقّق فعلي عبر الشبكة (بلا مزوّدي AI):** `probe_source` على المصادر المعتمدة السبع ⇒ `ok` (200 · 4KB–478KB). `www.mol.gov.sa` و`portal.mol.gov.sa` ⇒ `dns` (والاثنان مرفوضان أيضاً ساكنياً). الروابط المرشّحة: `/علاقات-العمل` ⇒ `ok` (200)؛ `/ministry-services/services/end-service-benefit-calculator?s=09` ⇒ `http_404`؛ `prod.hrsd.gov.sa/...` ⇒ `dns` (المضيف لا يُترجَم). واعتُمد البديل الرسمي `/media-center/media/leendofservice` ⇒ `ok`.

**حدود البوابة:** `*.gov.sa` + `qiwa.sa` فقط — لا يُقبل نطاق لمجرد أنّ اسمه يبدو حكومياً، ولا يُضاف استثناء فردي.
