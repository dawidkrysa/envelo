# Envelo Brandbook

Design language for the Envelo frontend. This document is the source of truth
for visual decisions; its values are implemented in
[`frontend/src/theme.py`](../frontend/src/theme.py). If the two ever disagree,
fix `theme.py` to match this file.

This brandbook transcribes the Claude Design import "Envelo budget app
design" (`Envelo.dc.html`) - a calm, editorial envelope-budgeting UI in IBM
Plex Sans with an oklch-authored palette.

## 1. Brand concept

**Envelo = calm control over money.**

The visual language is quiet and editorial: soft near-white surfaces, a deep
forest-green brand mark, hairline borders instead of shadows, and generous
whitespace. State is communicated by three accent hues - never by decoration.

| Pillar | Meaning | Visual consequence |
|---|---|---|
| **Calm & editorial** | Money should not feel alarming to look at | Soft green-gray canvas, white cards, 1px hairline borders, no shadows on content (only the modal sheet and toast lift off the page) |
| **Green means go** | Money under control is the default state | Emerald for "on track"; the same green family drives the brand mark and buttons |
| **Warn early, never scold** | Alerts arrive *before* overspending | Amber for approaching a limit, red reserved strictly for actual overspend |

## 2. Color

Every token below is a literal sRGB conversion of the design's OKLCH custom
property of the same name (`--brand`, `--ok`, `--warn`, ...), so the hex
values match the source exactly rather than approximating with a fixed
Material role. See `theme.Palette`, `theme.LIGHT` and `theme.DARK`.

### 2.1 Light palette

| Token | Hex | Role |
|---|---|---|
| `sf` | `#FFFFFF` | Card / surface fill |
| `sf2` | `#F6F8F6` | Table header fill, subtle panel tint |
| `sf3` | `#ECF0EE` | Progress track, row dividers |
| `canvas` | `#EDF1EE` | Page background |
| `ink` | `#19221D` | Primary text |
| `ink2` | `#46504A` | Secondary text |
| `ink3` | `#585F5B` | Metadata / tertiary text |
| `line` | `#DAE0DC` | Default 1px border |
| `line2` | `#C8D0CB` | Stronger border (buttons) |
| `brand` / `brandHover` | `#1D3A2A` / `#0E2B1B` | Primary action fill |
| `link` | `#2E5740` | Text links, row-level actions |
| `ok` / `okInk` / `okFill` / `okBorder` | `#14874E` / `#00582C` / `#DBF4E3` / `#BEE2C9` | Healthy envelope state |
| `warn` / `warnInk` / `warnFill` / `warnBorder` | `#CD9219` / `#784500` / `#FFF1C8` / `#EBCD95` | Approaching-limit state |
| `over` / `overInk` / `overFill` / `overBorder` | `#C53637` / `#A51E24` / `#FFE8E4` / `#FFBDB7` | Overspent state |
| `ruleFill` / `ruleInk` | `#DDF3E5` / `#00502F` | "Rule" transaction-source badge |
| `mlFill` / `mlInk` | `#EEE6FF` / `#5D408A` | "ML" transaction-source badge |
| `toast` | `#17221C` | Toast background |

### 2.2 Dark palette

| Token | Hex | Role |
|---|---|---|
| `sf` / `sf2` / `sf3` | `#1C221E` / `#252C28` / `#2F3632` | Card / panel / track fills |
| `canvas` | `#0D1310` | Page background |
| `ink` / `ink2` / `ink3` | `#F1F4F2` / `#D2D7D4` / `#A4ABA7` | Text hierarchy |
| `line` / `line2` | `#353D38` / `#505753` | Borders |
| `brand` / `brandHover` | `#5EC386` / `#72D699` | Primary action fill (mint, not the light mode's deep forest) |
| `link` | `#7BDCA6` | Links |
| `ok` / `okInk` / `okFill` / `okBorder` | `#4EBE7D` / `#87E2A8` / `#183525` / `#2E5740` | Healthy |
| `warn` / `warnInk` / `warnFill` / `warnBorder` | `#E7B140` / `#FCCD73` / `#47340D` / `#72551F` | Approaching limit |
| `over` / `overInk` / `overFill` / `overBorder` | `#EF6661` / `#FFA8A0` / `#542523` / `#8A423D` | Overspent |

### 2.3 Semantic mapping

- **Green (`ok`)** - envelope on track, healthy balance.
- **Amber (`warn`)** - envelope at/above 80% used with money left, or a
  forecast trending over.
- **Red (`over`)** - spent more than assigned. Never used for emphasis alone.
- Transaction provenance gets its own quiet palette: green-tinted "Rule",
  violet-tinted "ML", neutral gray "Manual" - these are metadata, not state,
  so they stay out of the ok/warn/over family.

## 3. Typography

**Font: IBM Plex Sans**, weights 400/500/600/700, each registered as its own
Flutter font-family alias (`theme.FONT_FILES`) since Flutter does not
synthesize missing weight files. Numbers are always tabular
(`font-variant-numeric: tabular-nums`).

| Role | Size / weight | Usage |
|---|---|---|
| Hero number | 46-52 / 600, `letter-spacing:-0.022em` | Safe to spend, Left this month |
| Page title | 26 / 600, `letter-spacing:-0.015em` | `page_header` title |
| Section heading | 15 / 600 | Card / table section titles |
| Body | 13.5 / 400 | Default text |
| Eyebrow / table label | 10.5-11.5 / 500, uppercase, `letter-spacing:0.06-0.1em` | Metadata above titles, table headers |

Money formatting: `1.234,56 €` (EU style - period thousands, comma decimal,
non-breaking-ish trailing " €"), negative amounts prefixed with `−` and
colored by state, never flat red. See `mock_data.format_money`.

## 4. Spacing, radius, shape

- The design uses many exact one-off pixel values rather than a strict base
  scale; `theme.py` keeps only the handful that genuinely repeat
  (`SPACE_XS`...`SPACE_XXXL`), and components hardcode the rest as literals
  so fidelity isn't lost to rounding.
- **Corner radius:** 16px for the login card and largest panels
  (`RADIUS_CARD_LG`), 14px for stat cards and table panels (`RADIUS_CARD`),
  13px for compact rows (`RADIUS_CARD_SM`), 9px for buttons/inputs/selects
  (`RADIUS_BUTTON`), 8px for nav items (`RADIUS_TILE`), full pill for
  progress bars and toggle tracks (`RADIUS_PILL`).
- **Progress bars** are thick data lines - 7-16px depending on context (thin
  in table rows, thick in the Flow variant with a target tick mark) - fully
  rounded, colored fill on a `sf3` neutral track.
- **Elevation:** flat everywhere except the modal sheet and toast, which lift
  off the canvas with a soft shadow.

## 5. Motion

- **Route transitions: none** - screens swap instantly
  (`page_transitions = NONE` on every platform).
- Local component state (tab switching, group collapse/expand, the
  light/dark toggle) re-renders instantly with no transition, matching the
  design's own snappy `fadeup` being reserved for full-page mounts only.

## 6. Components

Implemented as a one-file-per-component library under
[`frontend/src/components/`](../frontend/src/components/):

- **Buttons** (`button.py`) - Primary (brand fill), Secondary (outlined),
  Ghost (borderless), Danger (red text/border), and a borderless Link button
  for row-level actions (Assign, Edit, Delete, ...).
- **Badges** (`badge.py`) - uppercase pills for transaction source
  (Rule/ML/Manual) and envelope state (On track/85%/Over).
- **Progress bar** (`progress_bar.py`) - thin/thick rounded fill with an
  optional target tick.
- **Nav rail** (`nav_rail.py`) - left sidebar (desktop: full labels; tablet:
  icon-only) or bottom bar (mobile), with grouped sections, a category-groups
  quick-jump list and the user footer.
- **Envelope row/card/flow row** - the three ways one envelope renders
  (Ledger table row, Cards grid tile, Flow bar with quick actions).
- **Transaction row/card** - table row (desktop/tablet) and stacked card
  (mobile).
- **Modal dialog** (`modal_dialog.py`) - the Assign/Move/Add-* sheet: title +
  close, a field list (select or input, each with an optional hint), an
  optional preview banner, Cancel/Confirm footer.
- **Toast** (`toast.py`) - bottom-center confirmation pill.

## 7. Microcopy tone

- **Calm, concrete, second person.** "Groceries is at 85% with 9 days left" -
  never "WARNING: budget exceeded!!".
- **Warn early, never scold.** Alerts state facts and give a next step.
- **Numbers first.** Lead with the amount or percentage; explanation follows.
- Buttons are verbs: "Import statement", "Add rule", "Move money".

## 8. Logo & assets

The nav/login brand mark is a flat **"E" glyph tile**: a `brand`-colored
rounded-8px square holding a white "E", followed by the "Envelo" wordmark at
600 weight. This replaces the previous envelope-shaped SVG mark
(`frontend/src/assets/logo.svg`) as the primary in-app mark; the SVG and PNG
exports remain available as alternate assets (app icon, favicon) but are not
required for the in-app brand lockup itself.
