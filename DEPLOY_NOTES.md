# DEPLOY_NOTES.md — ملاحظات النشر

> المنصّة موقع ثابت بملف واحد (`index.html`) يُنشر على GitHub Pages:
> `https://ksatools.github.io/`
> **لا يوجد خادم ولا إرسال بيانات.** كل الحساب يجري في متصفّح المستخدم.

> هذا الملف نُسخ من تعليق \"ملاحظات النشر\" أعلى `index.html`، مع تصحيحات وتنبيهات.
> البند المقابل في `docs/BACKLOG.md` هو نقل التعليق من داخل الملف إلى هنا وحذفه.
> **⚠️ لا تُدرج أي معرّف ناشر أو كود تحقق في هذا الملف.**

---

## 1) `ads.txt`

**المُصلَح (2026-10-15):** سطر واحد صحيح بصيغة IAB:
```
adsterra.com, <publisher-id>, DIRECT
```
(القيمة الفعلية في `ads.txt`، ولا تُنسخ هنا.)

**⚠️ درس مستفاد:** كان الملف يحوي سطراً إضافياً بصيغة `adsterra.com, ksatools.github.io, DIRECT` — أي وضع **نطاق الموقع** في خانة **معرّف الناشر**، وهو غير مطابق للصيغة. الحقل الثاني يجب أن يكون معرّف الناشر من لوحة Adsterra. (ملاحظة موثّقة: بعض المواقع مثل `anotepad.com` تستخدم صيغة النطاق فعلاً؛ لكن المعتمد هو ما تسلّمه لوحة حسابك.) البند مُغلق في `docs/BACKLOG.md`.

---

## 2) صفحة الخصوصية

- موجودة: `privacy.html` في جذر المستودع (ملف مستقل، ~30 كيلوبايت).
- مرتبطة من تذييل الصفحة الرئيسة **بروابط نسبية**: `privacy.html` و`privacy.html#ads`.
- **مهم:** استخدم روابط نسبية لا مطلقة (`privacy.html` لا `/privacy.html`) لتعمل على GitHub Pages حتى لو نُشر الموقع على مسار فرعي مثل `username.github.io/repo/`.
- مراجعة الصياغة القانونية بشرية — انظر قائمة المراجعة في `docs/DOMAIN_RULES.md`.

---

## 3) الفهرسة (SEO) والنطاقات

- `robots.txt` و`sitemap.xml` و`404.html` موجودة في الجذر.
- لتحسين الفهرسة: يُنصح بنشر الصفحة على مسارين `/ar/` و`/en/` مع تعديل اللغة الافتراضية عند التهيئة.
- توجد `canonical` وثلاث قيم `hreflang` في `<head>`.
- موجودة أيضاً: `og-image.png` (صورة المشاركة)، `site.webmanifest`، ومجموعة أيقونات (`favicon.svg/ico/16/32/48`، `apple-touch-icon.png`، `icon-192.png`، `icon-512.png`).
- توجد وسمة `google-site-verification` لإثبات الملكية في Search Console — **لا تُنسخ قيمتها في أي ملف**.

---

## 4) الإعلانات

- **Social Bar** (Adsterra): سكربت متزامن في نهاية `<body>` قبل `</body>`.
- **Native Banner** (Adsterra): سكربت + حاوية قرب نهاية الصفحة.
- **تحذير:** لا تُكرِّر السكربت ولا تحذفه؛ التكرار يخالف شروط الشبكة ويسبّب أخطاء.
- توجد حاوية `#ad-top` **مخفية** وأزرار `.btn-ad` غير مستخدمة (بند تنظيف في `docs/BACKLOG.md` #19).
- أثناء اختبار الدخان تُحجب الطلبات الخارجية، فلا تُحمَّل سكربتات الإعلان — وهذا متوقّع.

---

## 5) الخصوصية والبيانات

- لا يوجد أي إرسال لبيانات المستخدم إلى أي خادم.
- الحفظ محلي فقط عبر `localStorage` بالمفاتيح: `seh_inputs_v2` (المدخلات)، `seh_theme` (المظهر)، `seh_lang` (اللغة).
- **⚠️ ملاحظة للمراجعة:** وجود سكربتات Adsterra يعني أن المتصفّح يُجري طلبات إلى نطاقات خارجية عند التحميل؛ يجب أن تكون صياغة الخصوصية دقيقة بهذا الشأن.

---

## 6) نظام التسويق/SEO الآلي (مضاف 2026-10-15)

### 6.1 ما يُنشر تلقائياً
- **مقالات ثنائية اللغة** (ar/en) في `articles/ar/*.html` و`articles/en/*.html`.
- **`articles.json`** — مصفوفة سجلات منشورة (ثنائية اللغة، `translation_id` مشترك، `status: "published"` فقط).
- **`sitemap.xml`** — الرئيسية + الخصوصية + مقالات (كل مقالة: ar + en + x-default).
- **`latest_social_post.txt`** — نص مشاركة لآخر مقال (ar/en، رابطين، وسم العلامة).

> **المسودات لا تُنشر:** `drafts/` تُكتب خارج المستودع (في Workflow: `$RUNNER_TEMP/drafts`)، وترفع كـ artefact للمراجعة البشرية. `robots.txt` يحمل `Disallow: /drafts/` كإجراء احتياطي ثانوي فقط.

### 6.2 GitHub Actions — `.github/workflows/ai_marketing.yml`
| المطلوب | كيف تضيفه |
|---|---|
| **Secrets** (إلزامي لـ `auto`) | Settings → Secrets → Actions → New repository secret: `GEMINI_API_KEY`، `GEMINI_MODEL` (اختياري، افتراضي `gemini-3.8-flash`)، `TELEGRAM_BOT_TOKEN` (اختياري)، `TELEGRAM_CHAT_ID` (اختياري). |
| **Variables** (اختياري) | Settings → Variables → Actions: `PUBLISH_MODE` (افتراضي `draft`)، `SOCIAL_LANGUAGE` (افتراضي `both`)، `PAGES_VIA_ACTIONS` (إن `true` يستخدم `actions/deploy-pages` بدل `git push`). |
| **Pages Source** | Settings → Pages → Source: `Deploy from a branch`، الفرع `main` (أو `gh-pages`)، مجلد `/ (root)`. **هذا هو المسار الافتراضي (دفع `git push` من الـworkflow).** إن فضلت `actions/deploy-pages` فعّل `vars.PAGES_VIA_ACTIONS = 'true'` وأضف صلاحيات `pages: write` و`id-token: write` للـworkflow. |

### 6.3 التحقّق قبل النشر (محدث)
- [ ] `index.html` ينتهي بـ`</html>` ويحتوي `gosiScheme`.
- [ ] `python tests/smoke_test.py` ⇒ `FAIL=0` (حالياً `PASS=57 · FAIL=0 · FAIL(known)=13`).
- [ ] `python auto_marketing.py --selftest` ⇒ 28/28 PASS.
- [ ] `python auto_marketing.py --verify` ⇒ لا مشاكل.
- [ ] صيغة `ads.txt` صحيحة (معرّف الناشر في خانته).
- [ ] الروابط نسبية (`privacy.html` لا `/privacy.html`).
- [ ] لا معرّفات ناشرين/أكواد تحقق مكتوبة في ملفات التوثيق.
- [ ] فحص طباعة PDF لورقة السيرة (بيضاء بلا شريط ملوّن).
- [ ] **ملفات الجذر:** راجع أن `index.backup.html` و`index - Copy.html` **ليستا** في الجذر (تُنشر تلقائياً على Pages وتسبب محتوى مكرراً — أزلهما من المستودع بـ`git rm --cached "index - Copy.html" index.backup.html` إن كانتا موجودتين على الفرع البعيد).

---

## 7) قائمة تحقّق قبل النشر (القديمة — محفوظة للمرجع)

- [ ] `index.html` ينتهي بـ`</html>` ويحتوي `gosiScheme`.
- [ ] `python tests/smoke_test.py` ⇒ `FAIL=0`.
- [ ] صيغة `ads.txt` صحيحة (معرّف الناشر في خانته).
- [ ] الروابط نسبية (`privacy.html` لا `/privacy.html`).
- [ ] لا معرّفات ناشرين/أكواد تحقق مكتوبة في ملفات التوثيق.
- [ ] فحص طباعة PDF لورقة السيرة (بيضاء بلا شريط ملوّن).
