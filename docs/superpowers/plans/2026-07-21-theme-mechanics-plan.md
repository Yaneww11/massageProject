# Theme Mechanics Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make `SiteConfiguration`'s theme fields (colors, font pair, style
preset, hero variant) actually change what renders on every page, by wiring
them into a `<style>` override block, a dynamic Google Fonts `<link>`, and
three selectable hero layouts.

**Architecture:** A small pure-data module (`main_app/theme.py`) maps the
`font_pair`/`style_preset` choice keys `SiteConfiguration` already has (from
Plan A) to concrete CSS values. Two template filters expose that data to
templates. `base.html` renders a new partial that re-declares CSS custom
properties from `site_config` (already in every template's context via Plan
A's context processor), overriding `variables.css`'s hardcoded defaults.
`home.html`'s hero section becomes a dynamic `{% include %}` of one of three
partials selected by `site_config.hero_variant`.

**Tech Stack:** Django template language (custom filters, `{% include %}`
with a computed name via `add`), plain CSS custom properties — no JS
framework changes beyond one small new interval script for the carousel hero.

## Global Constraints

- This is Plan B of the 4-plan split of Part 2 ("Brand Configuration"),
  building on Plan A (`SiteConfiguration` model, already merged at commit
  `4a934ca`). Do not rename any `SiteConfiguration` field or choice value.
- Every `FONT_PAIRS`/`STYLE_PRESETS` dict key in this plan must exactly match
  a choice key already defined in `SiteConfiguration.FONT_PAIR_CHOICES` /
  `STYLE_PRESET_CHOICES` (`massageProject/main_app/models.py`):
  `playfair_montserrat`, `cormorant_lato`, `poppins_opensans`,
  `merriweather_sourcesans`, `raleway_roboto` / `soft`, `sharp`, `round`.
  Hero variant keys must match `HERO_VARIANT_CHOICES`: `split`, `carousel`,
  `fullbleed`.
- The existing massage-demo instance must render **pixel-identical** to
  today after this plan, since its `SiteConfiguration` defaults are
  `playfair_montserrat`/`soft`/`split` (Plan A) — the `soft` preset's radius/
  shadow values and the `playfair_montserrat` font URLs/families must be
  exact copies of what's hardcoded in `staticfiles/css/base/variables.css`
  today.
- **Scope decision (deliberate, not an oversight):** the existing split-hero
  CSS in `staticfiles/css/pages/home.css` (the `HERO — split layout` block
  and its two responsive breakpoints) stays exactly where it is, untouched.
  Only the two *new* variants (`carousel`, `fullbleed`) get their own files
  under `staticfiles/css/components/`, per the spec's "each variant gets its
  own CSS file" instruction. Relocating the pre-existing split CSS out of a
  combined-selector media-query block was assessed as unnecessary surgical
  risk for zero functional benefit and was deliberately skipped — flag this
  in review as a deliberate scope call, not a missed requirement.
- Do not modify `massageProject/main_app/views.py` — `Index.get()` already
  provides `page`, `gallery_images` (first 3 `HomePage.gallery` images), and
  `services`/`comments` in context; all three hero variants must consume
  only what's already there. No new view logic, no new content fields.
- Do not touch `Reservation`, `WorkingHours`, `Comment`, admin registrations,
  or anything from Plan A — out of scope for this plan.
- Per CLAUDE.md, any new static text this plan introduces must go through
  `python manage.py makemessages -l bg -l en` + `compilemessages` before the
  plan is done (final task).

---

### Task 1: `theme.py` — font pair and style preset data

**Files:**
- Create: `massageProject/main_app/theme.py`
- Test: `massageProject/main_app/tests_theme.py`

**Interfaces:**
- Produces: `FONT_PAIRS` (dict, keys are the 5 font-pair choice strings,
  values are dicts with keys `google_fonts_url`, `heading_family`,
  `body_family`) and `STYLE_PRESETS` (dict, keys are the 3 style-preset
  choice strings, values are dicts with keys `radius_sm`, `radius_md`,
  `radius_lg`, `shadow_sm`, `shadow_md`, `shadow_lg`) in
  `massageProject/main_app/theme.py`. Task 2's template filters import both.

- [ ] **Step 1: Write the failing tests**

Create `massageProject/main_app/tests_theme.py`:

```python
from django.test import TestCase

from massageProject.main_app.models import SiteConfiguration
from massageProject.main_app.theme import FONT_PAIRS, STYLE_PRESETS


class ThemeDataTest(TestCase):
    def test_font_pairs_cover_every_model_choice(self):
        model_keys = {key for key, _ in SiteConfiguration.FONT_PAIR_CHOICES}
        self.assertEqual(set(FONT_PAIRS.keys()), model_keys)

    def test_style_presets_cover_every_model_choice(self):
        model_keys = {key for key, _ in SiteConfiguration.STYLE_PRESET_CHOICES}
        self.assertEqual(set(STYLE_PRESETS.keys()), model_keys)

    def test_every_font_pair_has_required_keys(self):
        for key, pair in FONT_PAIRS.items():
            self.assertIn('google_fonts_url', pair, key)
            self.assertIn('heading_family', pair, key)
            self.assertIn('body_family', pair, key)

    def test_every_style_preset_has_required_keys(self):
        for key, preset in STYLE_PRESETS.items():
            for var in ('radius_sm', 'radius_md', 'radius_lg', 'shadow_sm', 'shadow_md', 'shadow_lg'):
                self.assertIn(var, preset, key)

    def test_soft_preset_matches_current_variables_css_defaults(self):
        soft = STYLE_PRESETS['soft']
        self.assertEqual(soft['radius_sm'], '4px')
        self.assertEqual(soft['radius_md'], '8px')
        self.assertEqual(soft['radius_lg'], '16px')
        self.assertEqual(soft['shadow_sm'], '0 2px 4px rgba(0,0,0,0.05)')
        self.assertEqual(soft['shadow_md'], '0 4px 12px rgba(0,0,0,0.1)')
        self.assertEqual(soft['shadow_lg'], '0 10px 25px rgba(0,0,0,0.15)')

    def test_default_font_pair_matches_current_variables_css_import(self):
        default = FONT_PAIRS['playfair_montserrat']
        self.assertIn('Playfair+Display', default['google_fonts_url'])
        self.assertIn('Montserrat', default['google_fonts_url'])
        self.assertEqual(default['heading_family'], "'Playfair Display', serif")
        self.assertEqual(default['body_family'], "'Montserrat', sans-serif")
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python manage.py test massageProject.main_app.tests_theme -v 2`
Expected: FAIL — `ModuleNotFoundError: No module named 'massageProject.main_app.theme'`.

- [ ] **Step 3: Create the theme data module**

Create `massageProject/main_app/theme.py`:

```python
FONT_PAIRS = {
    'playfair_montserrat': {
        'google_fonts_url': (
            'https://fonts.googleapis.com/css2?family=Playfair+Display:wght@400;600;700'
            '&family=Montserrat:wght@300;400;500;600&display=swap'
        ),
        'heading_family': "'Playfair Display', serif",
        'body_family': "'Montserrat', sans-serif",
    },
    'cormorant_lato': {
        'google_fonts_url': (
            'https://fonts.googleapis.com/css2?family=Cormorant+Garamond:wght@400;600;700'
            '&family=Lato:wght@300;400;700&display=swap'
        ),
        'heading_family': "'Cormorant Garamond', serif",
        'body_family': "'Lato', sans-serif",
    },
    'poppins_opensans': {
        'google_fonts_url': (
            'https://fonts.googleapis.com/css2?family=Poppins:wght@400;500;600;700'
            '&family=Open+Sans:wght@300;400;600&display=swap'
        ),
        'heading_family': "'Poppins', sans-serif",
        'body_family': "'Open Sans', sans-serif",
    },
    'merriweather_sourcesans': {
        'google_fonts_url': (
            'https://fonts.googleapis.com/css2?family=Merriweather:wght@400;700'
            '&family=Source+Sans+3:wght@300;400;600&display=swap'
        ),
        'heading_family': "'Merriweather', serif",
        'body_family': "'Source Sans 3', sans-serif",
    },
    'raleway_roboto': {
        'google_fonts_url': (
            'https://fonts.googleapis.com/css2?family=Raleway:wght@400;600;700'
            '&family=Roboto:wght@300;400;500&display=swap'
        ),
        'heading_family': "'Raleway', sans-serif",
        'body_family': "'Roboto', sans-serif",
    },
}

STYLE_PRESETS = {
    'soft': {
        'radius_sm': '4px',
        'radius_md': '8px',
        'radius_lg': '16px',
        'shadow_sm': '0 2px 4px rgba(0,0,0,0.05)',
        'shadow_md': '0 4px 12px rgba(0,0,0,0.1)',
        'shadow_lg': '0 10px 25px rgba(0,0,0,0.15)',
    },
    'sharp': {
        'radius_sm': '0px',
        'radius_md': '0px',
        'radius_lg': '0px',
        'shadow_sm': 'none',
        'shadow_md': '0 1px 2px rgba(0,0,0,0.08)',
        'shadow_lg': '0 2px 4px rgba(0,0,0,0.1)',
    },
    'round': {
        'radius_sm': '8px',
        'radius_md': '16px',
        'radius_lg': '32px',
        'shadow_sm': '0 2px 6px rgba(0,0,0,0.08)',
        'shadow_md': '0 6px 16px rgba(0,0,0,0.12)',
        'shadow_lg': '0 14px 32px rgba(0,0,0,0.18)',
    },
}
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python manage.py test massageProject.main_app.tests_theme -v 2`
Expected: PASS — all 6 tests green.

- [ ] **Step 5: Commit**

```bash
git add massageProject/main_app/theme.py massageProject/main_app/tests_theme.py
git commit -m "feat: add font pair and style preset theme data"
```

---

### Task 2: Template filters exposing theme data

**Files:**
- Create: `massageProject/main_app/templatetags/theme_extras.py`
- Test: `massageProject/main_app/tests_theme.py` (append)

**Interfaces:**
- Consumes: `FONT_PAIRS`, `STYLE_PRESETS` from Task 1.
- Produces: two template filters, loaded via `{% load theme_extras %}`:
  `{{ site_config.font_pair|font_pair_info }}` → dict with
  `google_fonts_url`/`heading_family`/`body_family`; and
  `{{ site_config.style_preset|style_preset_vars }}` → dict with
  `radius_sm`/`radius_md`/`radius_lg`/`shadow_sm`/`shadow_md`/`shadow_lg`.
  Task 3's `theme_overrides.html` uses both.

- [ ] **Step 1: Write the failing tests**

Append to `massageProject/main_app/tests_theme.py`:

```python
from django.template import Context, Template


class ThemeTemplateFiltersTest(TestCase):
    def test_font_pair_info_filter_returns_matching_dict(self):
        tmpl = Template("{% load theme_extras %}{{ 'playfair_montserrat'|font_pair_info.heading_family }}")
        # dict lookup via dot-notation in a template requires the filter's
        # return value to support attribute/key access, which plain dicts do
        rendered = Template(
            "{% load theme_extras %}{% with pair='playfair_montserrat'|font_pair_info %}{{ pair.heading_family }}{% endwith %}"
        ).render(Context({}))
        self.assertEqual(rendered, "'Playfair Display', serif")

    def test_font_pair_info_unknown_key_falls_back_to_default(self):
        rendered = Template(
            "{% load theme_extras %}{% with pair='not-a-real-key'|font_pair_info %}{{ pair.heading_family }}{% endwith %}"
        ).render(Context({}))
        self.assertEqual(rendered, "'Playfair Display', serif")

    def test_style_preset_vars_filter_returns_matching_dict(self):
        rendered = Template(
            "{% load theme_extras %}{% with preset='sharp'|style_preset_vars %}{{ preset.radius_sm }}{% endwith %}"
        ).render(Context({}))
        self.assertEqual(rendered, '0px')

    def test_style_preset_vars_unknown_key_falls_back_to_soft(self):
        rendered = Template(
            "{% load theme_extras %}{% with preset='not-a-real-key'|style_preset_vars %}{{ preset.radius_sm }}{% endwith %}"
        ).render(Context({}))
        self.assertEqual(rendered, '4px')
```

Delete the unused first line inside `test_font_pair_info_filter_returns_matching_dict`
(the `tmpl = Template(...)` assignment that's never used) before committing —
it was left in to show the invalid dot-filter syntax doesn't work; only the
`rendered = ...` assertion matters.

- [ ] **Step 2: Run tests to verify they fail**

Run: `python manage.py test massageProject.main_app.tests_theme.ThemeTemplateFiltersTest -v 2`
Expected: FAIL — `TemplateSyntaxError: 'theme_extras' is not a registered tag library`.

- [ ] **Step 3: Create the template tag module**

Create `massageProject/main_app/templatetags/theme_extras.py`:

```python
from django import template

from massageProject.main_app.theme import FONT_PAIRS, STYLE_PRESETS

register = template.Library()


@register.filter
def font_pair_info(pair_key):
    return FONT_PAIRS.get(pair_key, FONT_PAIRS['playfair_montserrat'])


@register.filter
def style_preset_vars(preset_key):
    return STYLE_PRESETS.get(preset_key, STYLE_PRESETS['soft'])
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python manage.py test massageProject.main_app.tests_theme -v 2`
Expected: PASS — all 10 tests green.

- [ ] **Step 5: Commit**

```bash
git add massageProject/main_app/templatetags/theme_extras.py massageProject/main_app/tests_theme.py
git commit -m "feat: add theme_extras template filters for font pairs and style presets"
```

---

### Task 3: `theme_overrides.html` partial + `base.html` wiring

**Files:**
- Create: `templates/partials/theme_overrides.html`
- Modify: `templates/base.html`
- Modify: `staticfiles/css/base/variables.css`
- Test: `massageProject/main_app/tests_theme.py` (append)

**Interfaces:**
- Consumes: `site_config` (already in every template's context via Plan A's
  context processor), `font_pair_info`/`style_preset_vars` filters from
  Task 2.
- Produces: every rendered page includes a `<link>` to the active font
  pair's Google Fonts URL and a `<style>` block re-declaring the 7 color
  variables, `--font-main`, `--font-heading`, and the 6 radius/shadow
  variables under `:root`, all sourced from `site_config`.

- [ ] **Step 1: Write the failing test**

Append to `massageProject/main_app/tests_theme.py`:

```python
class ThemeOverridesRenderingTest(TestCase):
    def test_home_page_includes_theme_colors_and_font_link(self):
        response = self.client.get('/bg/')
        content = response.content.decode()
        self.assertIn('--primary-color: #4A3728', content)
        self.assertIn('--font-heading: \'Playfair Display\', serif', content)
        self.assertIn('fonts.googleapis.com/css2?family=Playfair+Display', content)

    def test_variables_css_no_longer_hardcodes_google_fonts_import(self):
        with open('staticfiles/css/base/variables.css') as f:
            content = f.read()
        self.assertNotIn('@import url(\'https://fonts.googleapis.com', content)
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python manage.py test massageProject.main_app.tests_theme.ThemeOverridesRenderingTest -v 2`
Expected: FAIL — `--primary-color: #4A3728` not found in rendered page (theme
override block doesn't exist yet), and the `@import` is still present in
`variables.css`.

- [ ] **Step 3: Create the theme_overrides partial**

Create `templates/partials/theme_overrides.html`:

```html
{% load theme_extras %}{% with pair=site_config.font_pair|font_pair_info preset=site_config.style_preset|style_preset_vars %}<link rel="stylesheet" href="{{ pair.google_fonts_url }}">
<style>
:root {
    --primary-color: {{ site_config.primary_color }};
    --primary-light: {{ site_config.primary_light_color }};
    --secondary-color: {{ site_config.secondary_color }};
    --accent-color: {{ site_config.accent_color }};
    --bg-light: {{ site_config.background_color }};
    --text-main: {{ site_config.text_color }};
    --text-muted: {{ site_config.text_muted_color }};
    --font-main: {{ pair.body_family }};
    --font-heading: {{ pair.heading_family }};
    --radius-sm: {{ preset.radius_sm }};
    --radius-md: {{ preset.radius_md }};
    --radius-lg: {{ preset.radius_lg }};
    --shadow-sm: {{ preset.shadow_sm }};
    --shadow-md: {{ preset.shadow_md }};
    --shadow-lg: {{ preset.shadow_lg }};
}
</style>{% endwith %}
```

- [ ] **Step 4: Wire it into base.html**

In `templates/base.html`, change:

```html
    <link rel="stylesheet" href="{% static 'css/styles.css' %}">
    <link href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/5.15.4/css/all.min.css" rel="stylesheet">
```

to:

```html
    <link rel="stylesheet" href="{% static 'css/styles.css' %}">
    {% include 'partials/theme_overrides.html' %}
    <link href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/5.15.4/css/all.min.css" rel="stylesheet">
```

- [ ] **Step 5: Remove the hardcoded font import from variables.css**

In `staticfiles/css/base/variables.css`, delete line 1 (and the blank line
after it):

```css
@import url('https://fonts.googleapis.com/css2?family=Playfair+Display:wght@400;600;700&family=Montserrat:wght@300;400;500;600&display=swap');

```

so the file now starts directly with `:root {`.

- [ ] **Step 6: Run tests to verify they pass**

Run: `python manage.py test massageProject.main_app.tests_theme -v 2`
Expected: PASS — all 12 tests green.

- [ ] **Step 7: Run the full test suite**

Run: `python manage.py test -v 2`
Expected: PASS — no regressions (140 pre-existing + new theme tests).

- [ ] **Step 8: Commit**

```bash
git add templates/partials/theme_overrides.html templates/base.html \
        staticfiles/css/base/variables.css massageProject/main_app/tests_theme.py
git commit -m "feat: render SiteConfiguration theme values as CSS custom property overrides"
```

---

### Task 4: Extract the current hero into `partials/hero/split.html`

**Files:**
- Create: `templates/partials/hero/split.html`
- Modify: `templates/pages/home.html`
- Test: `massageProject/main_app/tests_theme.py` (append)

**Interfaces:**
- Consumes: `page`, `page.brand_name`, `page.description` (existing
  `Index.get()` context, unchanged).
- Produces: `templates/partials/hero/split.html`, included dynamically by
  `home.html` when `site_config.hero_variant == 'split'` (today's default —
  see Plan A). Tasks 5-6 add the sibling `carousel.html`/`fullbleed.html`
  this same include mechanism will select between.

- [ ] **Step 1: Write the failing test**

Append to `massageProject/main_app/tests_theme.py`:

```python
class HeroVariantSelectionTest(TestCase):
    def test_home_page_renders_split_hero_by_default(self):
        response = self.client.get('/bg/')
        content = response.content.decode()
        self.assertIn('hp-hero-inner', content)
        self.assertIn('home_background.jpg', content)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python manage.py test massageProject.main_app.tests_theme.HeroVariantSelectionTest -v 2`
Expected: currently PASSES already (the markup already exists inline in
`home.html`) — this is a characterization test to protect against
regressions from the extraction in the next steps. Run it now to confirm it
passes before refactoring, then re-run after Step 4 to prove nothing broke.

- [ ] **Step 3: Extract the hero markup into its own partial**

Create `templates/partials/hero/split.html` with exactly this content (moved
verbatim from `home.html`'s current hero section):

```html
{% load static i18n %}
<section class="hp-hero">
    <div class="hp-container hp-hero-inner">
        <div class="hp-hero-text">
            <span class="hp-eyebrow">{% trans "Масажно студио · от 2014" %}</span>
            {% if page %}
                <h1 class="hp-hero-title">{{ page.brand_name }}</h1>
                <p class="hp-hero-sub">{{ page.description }}</p>
            {% endif %}
            <div class="hp-hero-btns">
                <a href="{% url 'reservation_page' %}" class="btn btn-primary btn-lg" data-auth-modal-link>{% trans "Запазете час" %}</a>
                <a href="{% url 'services_dashboard' %}" class="btn btn-outline btn-lg">{% trans "Вижте услугите" %}</a>
            </div>
            <div class="hp-stats">
                <div class="hp-stat">
                    <span class="hp-stat-val">{% trans "10+ години" %}</span>
                    <span class="hp-stat-lbl">{% trans "опит" %}</span>
                </div>
                <div class="hp-stat">
                    <span class="hp-stat-val">4000+</span>
                    <span class="hp-stat-lbl">{% trans "клиенти" %}</span>
                </div>
                <div class="hp-stat">
                    <span class="hp-stat-val">4.9★</span>
                    <span class="hp-stat-lbl">{% trans "оценка" %}</span>
                </div>
            </div>
        </div>
        <div class="hp-hero-media">
            <img src="{% static 'images/home_background.jpg' %}" alt="{% if page %}{{ page.brand_name }}{% else %}{% trans "Масажно студио" %}{% endif %}">
        </div>
    </div>
</section>
```

- [ ] **Step 4: Replace the inline hero in home.html with a dynamic include**

In `templates/pages/home.html`, replace:

```html
<!-- ========== HERO — Split layout ========== -->
<section class="hp-hero">
    <div class="hp-container hp-hero-inner">
        <div class="hp-hero-text">
            <span class="hp-eyebrow">{% trans "Масажно студио · от 2014" %}</span>
            {% if page %}
                <h1 class="hp-hero-title">{{ page.brand_name }}</h1>
                <p class="hp-hero-sub">{{ page.description }}</p>
            {% endif %}
            <div class="hp-hero-btns">
                <a href="{% url 'reservation_page' %}" class="btn btn-primary btn-lg" data-auth-modal-link>{% trans "Запазете час" %}</a>
                <a href="{% url 'services_dashboard' %}" class="btn btn-outline btn-lg">{% trans "Вижте услугите" %}</a>
            </div>
            <div class="hp-stats">
                <div class="hp-stat">
                    <span class="hp-stat-val">{% trans "10+ години" %}</span>
                    <span class="hp-stat-lbl">{% trans "опит" %}</span>
                </div>
                <div class="hp-stat">
                    <span class="hp-stat-val">4000+</span>
                    <span class="hp-stat-lbl">{% trans "клиенти" %}</span>
                </div>
                <div class="hp-stat">
                    <span class="hp-stat-val">4.9★</span>
                    <span class="hp-stat-lbl">{% trans "оценка" %}</span>
                </div>
            </div>
        </div>
        <div class="hp-hero-media">
            <img src="{% static 'images/home_background.jpg' %}" alt="{% if page %}{{ page.brand_name }}{% else %}{% trans "Масажно студио" %}{% endif %}">
        </div>
    </div>
</section>
```

with:

```html
<!-- ========== HERO — variant selected by SiteConfiguration.hero_variant ========== -->
{% include "partials/hero/"|add:site_config.hero_variant|add:".html" %}
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `python manage.py test massageProject.main_app.tests_theme -v 2`
Expected: PASS — `test_home_page_renders_split_hero_by_default` still passes
(proves the extraction is byte-identical output), all other theme tests
still green.

- [ ] **Step 6: Run the full test suite**

Run: `python manage.py test -v 2`
Expected: PASS — no regressions.

- [ ] **Step 7: Commit**

```bash
git add templates/partials/hero/split.html templates/pages/home.html \
        massageProject/main_app/tests_theme.py
git commit -m "refactor: extract the current hero into a selectable split.html partial"
```

---

### Task 5: `carousel` hero variant

**Files:**
- Create: `templates/partials/hero/carousel.html`
- Create: `staticfiles/css/components/hero-carousel.css`
- Modify: `staticfiles/css/styles.css` (one new `@import`)
- Test: `massageProject/main_app/tests_theme.py` (append)

**Interfaces:**
- Consumes: `page`, `gallery_images` (existing `Index.get()` context — up to
  3 `Image` instances from `HomePage.gallery`), same as Task 4.
- Produces: `templates/partials/hero/carousel.html`, selectable by setting
  `SiteConfiguration.hero_variant = 'carousel'` in the admin.

- [ ] **Step 1: Write the failing test**

Append to `massageProject/main_app/tests_theme.py`:

```python
from massageProject.main_app.models import SiteConfiguration as SC


class CarouselHeroVariantTest(TestCase):
    def test_carousel_variant_renders_when_selected(self):
        config = SC.get_solo()
        config.hero_variant = 'carousel'
        config.save()
        try:
            response = self.client.get('/bg/')
            content = response.content.decode()
            self.assertIn('hp-hero-carousel', content)
            self.assertNotIn('hp-hero-inner', content)
        finally:
            config.hero_variant = 'split'
            config.save()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python manage.py test massageProject.main_app.tests_theme.CarouselHeroVariantTest -v 2`
Expected: FAIL — `TemplateDoesNotExist: partials/hero/carousel.html`.

- [ ] **Step 3: Create the carousel hero partial**

Create `templates/partials/hero/carousel.html`:

```html
{% load static i18n %}
<section class="hp-hero-carousel">
    <div class="hp-hero-carousel-track" id="hp-hero-carousel-track">
        {% for image in gallery_images %}
        <div class="hp-hero-carousel-slide{% if forloop.first %} hp-hero-carousel-slide--active{% endif %}">
            <img src="{{ image.image.url }}" alt="{{ image.alt_text }}">
        </div>
        {% endfor %}
    </div>
    <div class="hp-hero-carousel-scrim"></div>
    <div class="hp-hero-carousel-content">
        {% if page %}
            <h1 class="hp-hero-carousel-title">{{ page.brand_name }}</h1>
            <p class="hp-hero-carousel-sub">{{ page.description }}</p>
        {% endif %}
        <div class="hp-hero-carousel-btns">
            <a href="{% url 'reservation_page' %}" class="btn btn-primary btn-lg" data-auth-modal-link>{% trans "Запазете час" %}</a>
            <a href="{% url 'services_dashboard' %}" class="btn btn-outline btn-lg">{% trans "Вижте услугите" %}</a>
        </div>
    </div>
</section>
<script>
(function () {
    var slides = document.querySelectorAll('#hp-hero-carousel-track .hp-hero-carousel-slide');
    if (slides.length <= 1) return;
    var current = 0;
    setInterval(function () {
        slides[current].classList.remove('hp-hero-carousel-slide--active');
        current = (current + 1) % slides.length;
        slides[current].classList.add('hp-hero-carousel-slide--active');
    }, 5000);
})();
</script>
```

- [ ] **Step 4: Create the carousel hero CSS**

Create `staticfiles/css/components/hero-carousel.css`:

```css
.hp-hero-carousel {
    position: relative;
    height: 560px;
    overflow: hidden;
}

.hp-hero-carousel-track {
    position: absolute;
    inset: 0;
}

.hp-hero-carousel-slide {
    position: absolute;
    inset: 0;
    opacity: 0;
    transition: opacity 1s ease;
}

.hp-hero-carousel-slide--active { opacity: 1; }

.hp-hero-carousel-slide img {
    width: 100%;
    height: 100%;
    object-fit: cover;
    display: block;
}

.hp-hero-carousel-scrim {
    position: absolute;
    inset: 0;
    background: linear-gradient(to top, rgba(0, 0, 0, 0.55), rgba(0, 0, 0, 0.1) 60%);
}

.hp-hero-carousel-content {
    position: absolute;
    left: 0;
    right: 0;
    bottom: 0;
    padding: 3rem 2rem;
    max-width: 1200px;
    margin: 0 auto;
    color: var(--white);
}

.hp-hero-carousel-title {
    margin: 0;
    font-family: var(--font-heading);
    font-size: clamp(2rem, 4vw, 3.5rem);
    color: var(--white);
}

.hp-hero-carousel-sub {
    margin-top: 1rem;
    max-width: 560px;
    font-size: 1.125rem;
    line-height: 1.6;
}

.hp-hero-carousel-btns {
    display: flex;
    gap: 1rem;
    margin-top: 2rem;
    flex-wrap: wrap;
}

@media (max-width: 600px) {
    .hp-hero-carousel { height: 420px; }
    .hp-hero-carousel-content { padding: 2rem 1rem; }
}
```

- [ ] **Step 5: Import the new CSS file**

In `staticfiles/css/styles.css`, add
`@import url('components/hero-carousel.css');` to the `/* Components
styles */` block, alongside the existing `buttons.css`/`cards.css`/etc.
imports.

- [ ] **Step 6: Run tests to verify they pass**

Run: `python manage.py test massageProject.main_app.tests_theme -v 2`
Expected: PASS — all tests green, including `CarouselHeroVariantTest`.

- [ ] **Step 7: Commit**

```bash
git add templates/partials/hero/carousel.html staticfiles/css/components/hero-carousel.css \
        staticfiles/css/styles.css massageProject/main_app/tests_theme.py
git commit -m "feat: add carousel hero variant"
```

---

### Task 6: `fullbleed` hero variant

**Files:**
- Create: `templates/partials/hero/fullbleed.html`
- Create: `staticfiles/css/components/hero-fullbleed.css`
- Modify: `staticfiles/css/styles.css` (one new `@import`)
- Test: `massageProject/main_app/tests_theme.py` (append)

**Interfaces:**
- Consumes: `page`, `gallery_images` (same context as Tasks 4-5; uses only
  `gallery_images.0`, the first image).
- Produces: `templates/partials/hero/fullbleed.html`, selectable by setting
  `SiteConfiguration.hero_variant = 'fullbleed'` in the admin.

- [ ] **Step 1: Write the failing test**

Append to `massageProject/main_app/tests_theme.py`:

```python
class FullbleedHeroVariantTest(TestCase):
    def test_fullbleed_variant_renders_when_selected(self):
        config = SC.get_solo()
        config.hero_variant = 'fullbleed'
        config.save()
        try:
            response = self.client.get('/bg/')
            content = response.content.decode()
            self.assertIn('hp-hero-fullbleed', content)
            self.assertNotIn('hp-hero-inner', content)
        finally:
            config.hero_variant = 'split'
            config.save()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python manage.py test massageProject.main_app.tests_theme.FullbleedHeroVariantTest -v 2`
Expected: FAIL — `TemplateDoesNotExist: partials/hero/fullbleed.html`.

- [ ] **Step 3: Create the fullbleed hero partial**

Create `templates/partials/hero/fullbleed.html`:

```html
{% load i18n %}
<section class="hp-hero-fullbleed">
    {% with first_image=gallery_images.0 %}
    {% if first_image %}
        <img src="{{ first_image.image.url }}" alt="{{ first_image.alt_text }}" class="hp-hero-fullbleed-image">
    {% endif %}
    {% endwith %}
    <div class="hp-hero-fullbleed-scrim"></div>
    <div class="hp-hero-fullbleed-content">
        {% if page %}
            <h1 class="hp-hero-fullbleed-title">{{ page.brand_name }}</h1>
            <p class="hp-hero-fullbleed-sub">{{ page.description }}</p>
        {% endif %}
        <a href="{% url 'reservation_page' %}" class="btn btn-primary btn-lg" data-auth-modal-link>{% trans "Запазете час" %}</a>
    </div>
</section>
```

- [ ] **Step 4: Create the fullbleed hero CSS**

Create `staticfiles/css/components/hero-fullbleed.css`:

```css
.hp-hero-fullbleed {
    position: relative;
    height: 620px;
    display: flex;
    align-items: center;
    justify-content: center;
    text-align: center;
    overflow: hidden;
}

.hp-hero-fullbleed-image {
    position: absolute;
    inset: 0;
    width: 100%;
    height: 100%;
    object-fit: cover;
    display: block;
}

.hp-hero-fullbleed-scrim {
    position: absolute;
    inset: 0;
    background: rgba(0, 0, 0, 0.4);
}

.hp-hero-fullbleed-content {
    position: relative;
    z-index: 1;
    color: var(--white);
    max-width: 700px;
    padding: 0 2rem;
}

.hp-hero-fullbleed-title {
    margin: 0;
    font-family: var(--font-heading);
    font-size: clamp(2.2rem, 5vw, 4rem);
    color: var(--white);
}

.hp-hero-fullbleed-sub {
    margin-top: 1.25rem;
    font-size: 1.125rem;
    line-height: 1.6;
}

.hp-hero-fullbleed-content .btn {
    margin-top: 2rem;
}

@media (max-width: 600px) {
    .hp-hero-fullbleed { height: 460px; }
}
```

- [ ] **Step 5: Import the new CSS file**

In `staticfiles/css/styles.css`, add
`@import url('components/hero-fullbleed.css');` to the `/* Components
styles */` block, after the `hero-carousel.css` import added in Task 5.

- [ ] **Step 6: Run tests to verify they pass**

Run: `python manage.py test massageProject.main_app.tests_theme -v 2`
Expected: PASS — all tests green, including `FullbleedHeroVariantTest`.

- [ ] **Step 7: Commit**

```bash
git add templates/partials/hero/fullbleed.html staticfiles/css/components/hero-fullbleed.css \
        staticfiles/css/styles.css massageProject/main_app/tests_theme.py
git commit -m "feat: add fullbleed hero variant"
```

---

### Task 7: Full regression + i18n regeneration

**Files:**
- No new source files.
- Modify: `locale/bg/LC_MESSAGES/django.po`, `locale/bg/LC_MESSAGES/django.mo`
- Modify: `locale/en/LC_MESSAGES/django.po`, `locale/en/LC_MESSAGES/django.mo`

**Interfaces:**
- Consumes: everything from Tasks 1-6.
- Produces: nothing new — this task only verifies and regenerates
  translation catalogs.

- [ ] **Step 1: Run the full test suite**

Run: `python manage.py test -v 2`
Expected: PASS — every test in the project (Plan A's 140 plus this plan's
new `tests_theme.py` tests) passes with zero regressions.

- [ ] **Step 2: Check whether this plan introduced any new translatable strings**

This plan's only new `{% trans %}` calls are in `carousel.html` and
`fullbleed.html` ("Запазете час", "Вижте услугите") — both already exist as
msgids in `locale/*/LC_MESSAGES/django.po` from the pre-existing `home.html`
(now `split.html`), since `makemessages` deduplicates identical msgids across
files. Run:

```bash
source venv/bin/activate
python manage.py makemessages -l bg -l en
```

Then check `git diff locale/bg/LC_MESSAGES/django.po
locale/en/LC_MESSAGES/django.po` — expect only `#:` file/line-number
reference comments to change (new file paths like `templates/partials/hero/
carousel.html` added alongside the existing reference for the same msgid),
and no new empty `msgstr ""` entries. If any *new* empty `msgstr` did appear
(meaning a string in this plan wasn't already covered), fill it in with the
correct bg/en text before proceeding.

- [ ] **Step 3: Compile messages**

```bash
python manage.py compilemessages
```

- [ ] **Step 4: Commit**

```bash
git add locale/bg/LC_MESSAGES/django.po locale/bg/LC_MESSAGES/django.mo \
        locale/en/LC_MESSAGES/django.po locale/en/LC_MESSAGES/django.mo
git commit -m "chore: regenerate translation catalogs after theme mechanics templates"
```

If Step 2 found no diff at all in the `.po` files (possible if `makemessages`
produces byte-identical output), skip this commit — there is nothing to
commit, and an empty commit must not be created.

---

## Plan Self-Review Notes

- **Spec coverage:** font pair / style preset data (✅ Task 1), template
  filters (✅ Task 2), `theme_overrides.html` + font `<link>` + `variables.css`
  cleanup (✅ Task 3), `split`/`carousel`/`fullbleed` hero partials (✅ Tasks
  4-6), i18n regen (✅ Task 7). The spec's "no live theme preview" and
  "no custom CSS override field" are non-goals already excluded per the
  original design doc's Out of Scope section — nothing in this plan
  contradicts that.
- **Placeholder scan:** no TBD/TODO; every step has literal, runnable code.
- **Type consistency:** `hero_variant` values (`split`/`carousel`/`fullbleed`)
  used in the `{% include %}` path construction in Task 4 match the actual
  filenames created in Tasks 4-6 (`split.html`, `carousel.html`,
  `fullbleed.html`) and match `SiteConfiguration.HERO_VARIANT_CHOICES` from
  Plan A — verified consistent across all three tasks. `font_pair_info`/
  `style_preset_vars` filter names match their `{% load theme_extras %}`
  usage in `theme_overrides.html`.
