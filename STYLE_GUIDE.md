# Eco Kaitiaki Hub — Design Style Guide

> Visual language & component system for the Predator-Free management platform.

---

## 1. Design Philosophy

**Warm, grounded, purposeful.** The interface avoids sterile "AI-generated" neutrality by using:

- **Warm-toned surfaces** instead of cool Bootstrap grays
- **Single‑family typography** — Inter at all sizes (headings use heavier weights for contrast)
- **Intentional asymmetry** — accent borders break uniform card grids
- **Nature-inspired color** — forest green primary, earth secondary, gold accent

---

## 2. Color Palette

### Brand Colors

| Token | Hex | Usage |
|---|---|---|
| `--primary-green` | `#1a5e20` | Primary brand; `.btn-forest`, `.text-forest`, `.bg-forest` |
| `--primary-green-dark` | `#154d1a` | Hover states |
| `--soft-green` | `#f0fdf4` | Background tints, hover highlights |
| `--action-gold` | `#ffc107` | Warnings, maintenance status |
| `--surface-warm` | `#F5F2ED` | Page background, replaces `bg-light` |
| `--earth` | `#8B6B4D` | Secondary accent for variety |
| `--slate-600` | `#475569` | Body text, breadcrumbs |
| `--slate-400` | `#94a3b8` | Muted text, separators |

### Semantic Colors

| Token | Hex | Usage |
|---|---|---|
| Success | `#198754` | Active/Functional status |
| Info | `#0d6efd` | Trap markers, info icons |
| Warning | `#ffc107` | Under Repair, pending |
| Danger | `#dc3545` | Retired/Error states |
| Secondary | `#6c757d` | In Storage |

### Surface Colors

```css
/* Page background — warm, not gray */
body, #content-wrapper {
  background-color: #F5F2ED;
}

/* Card backgrounds — always white for contrast */
.card {
  background-color: #ffffff;
}

/* Accent surfaces */
.bg-surface { background-color: #F5F2ED; }
.bg-soft-green { background-color: #f0fdf4; }
```

---

## 3. Typography

### Font Stack

| Role | Font | Weights |
|---|---|---|
| **Display / Headings** | Inter (sans-serif) | 500, 600, 700, 800 |
| **Body / UI** | Inter (sans-serif) | 300, 400, 500, 600, 700 |

### Heading Styles

```css
/* Headings use heavier weights for contrast; no separate display font */
h1, .h1 { font-weight: 800; letter-spacing: -0.02em; }
h2, .h2 { font-weight: 700; letter-spacing: -0.01em; }
h3, .h3, h4, .h4 { font-weight: 600; }

/* Hero titles */
.hero-title, .display-heading {
  font-weight: 900;
  letter-spacing: -0.02em;
}

/* Body */
body {
  font-family: 'Inter', sans-serif;
}

/* Data / coordinates */
.mono-coord {
  font-family: 'JetBrains Mono', 'Fira Code', monospace;
  font-size: 0.85rem;
}
```

### Type Scale

```
Hero Title:   3.5rem / 900 weight / Inter
Page Title:   2rem   / 800 weight / Inter (h1)
Section Title: 1.5rem / 700 weight / Inter (h2)
Card Title:   1.25rem / 600 weight / Inter (h3)
Body:         0.875rem / 400 weight / Inter
Small:        0.75rem  / 500 weight / Inter, uppercase
Meta:         0.65rem  / 600 weight / Inter, uppercase, wider letter-spacing
```

---

## 4. Spacing System

Use Bootstrap spacing scale (`p-*`, `m-*`, `g-*`) with these conventions:

| Token | Rem | Usage |
|---|---|---|
| `p-3` / `g-3` | 1rem | Card body padding, default grid gap |
| `p-4` | 1.5rem | Page content padding, card body (generous) |
| `py-5` | 3rem | Section vertical spacing |
| `gap-2` | 0.5rem | Button groups, inline elements |
| `gap-3` | 1rem | Icon + text pairs |

---

## 5. Components

### Cards

**Primary card (elevated):**
```html
<div class="card border-0 shadow-sm rounded-4">
```

**Card with left accent** (use sparingly on first KPI or featured card):
```html
<div class="card border-0 shadow-sm rounded-4 card-accent">
```

Available accent variants:
- `card-accent` — green left border
- `card-accent card-accent-gold` — gold left border (pending/warning)
- `card-accent card-accent-earth` — earth left border (secondary info)

### Buttons

| Class | Style | Use |
|---|---|---|
| `.btn-forest` | Solid green | Primary actions |
| `.btn-outline-forest` | Green outline | Secondary actions |
| `.btn-success` | Blue (branded) | Approve, confirm |
| `.btn-light` | Light | Tertiary, cancel |
| `.btn-danger` | Red | Delete, reject |

All buttons should use `rounded-pill` for primary actions, `rounded-3` for secondary.

### KPI Cards

```
┌─────────────────────────┐
│ [icon]  LABEL           │
│         VALUE           │
└─────────────────────────┘
```

- Icon box: `44x44px`, `border-radius: 12px`, centered
- Label: `0.7rem`, uppercase, `600` weight, `text-muted`
- Value: `h4` / `fw-black`

### Badges / Status Pills

- Use `rounded-pill` for all status badges
- Always pair icon + text for status (e.g., `bi-check-circle + "Functional"`)
- Background colors correspond to status:
  - Green (`--primary-green`): Functional, Active, Deployed
  - Gold (`--action-gold`): Under Repair, Pending
  - Gray (`--slate-400`): In Storage
  - Red (`#dc3545`): Retired, Unknown

### Breadcrumbs

Two patterns:

**Pattern A — Premium (custom):**
```html
<div class="premium-breadcrumb">
    <a href="...">Home</a>
    <span class="breadcrumb-sep">·</span>
    <span class="text-forest fw-bold">Current Page</span>
</div>
```

**Pattern B — Bootstrap (standard):**
```html
<nav aria-label="breadcrumb">
    <ol class="breadcrumb small text-uppercase ls-1">
        <li class="breadcrumb-item"><a href="..." class="text-muted">Section</a></li>
        <li class="breadcrumb-item active text-forest fw-bold">Page</li>
    </ol>
</nav>
```

---

## 6. Layout Patterns

### Dashboard Grid

```
┌──────┬──────┬──────┬──────┐  ← 4-col (global) or 3-col (scoped)
│ KPI  │ KPI  │ KPI  │ KPI  │     First card uses card-accent
├──────┴──────┴──────┴──────┤
│       MAP / TABLE          │
├────────────────────────────┤
│    Quick Actions           │
└────────────────────────────┘
```

### Detail / Form Pages

```
┌──────────────────────────────────────┐
│  Breadcrumb (text-forest active)     │
├──────────────────────────────────────┤
│  [icon-circle]  Page Title           │
├─────────────────────┬────────────────┤
│  Form / Config      │  Map / Preview │  (asymmetric: 5/7)
└─────────────────────┴────────────────┘
```

### Line Card List

Each line card has:
- Left: Line name + type badge (Trap/Bait) + status pill
- Right: Chevron indicator
- Selected state: `border-left: 4px solid var(--primary-green)`

---

## 7. Interaction Patterns

### Hover States

| Element | Effect | Timing |
|---|---|---|
| Card | `translateY(-2px)`, shadow deepens | 0.25s |
| KPI card | Cursor pointer, subtle lift | 0.2s |
| Button | Darken bg, slight lift (`translateY(-1px)`) | 0.2s |
| Nav link | Color transition + underline scale | 0.2s |
| Table row | Left border highlight (`3px` green) | 0.15s |
| Dropdown item | Green tint bg (`#f0fdf4`) | 0.15s |

### Active / Focus

- Nav active: 3px underline, `border-radius: 2px`, forest green
- Form focus: `border-color: #1a5e20` + `box-shadow: 0 0 0 4px rgba(26,94,32,0.1)`
- Button active (click): Inner shadow for press effect

---

## 8. Shadow System

| Level | Value | Use |
|---|---|---|
| Flat | None | Cards on dark/warm surfaces |
| Subtle | `0 2px 12px rgba(0,0,0,0.06)` | Default card state |
| Raised | `0 10px 30px rgba(0,0,0,0.08)` | Dropdowns, hovered cards |
| Prominent | `0 16px 40px rgba(22,163,74,0.15)` | Featured cards on hover |
| Deep | `0 20px 40px rgba(0,0,0,0.08)` | Login card, modals |

---

## 9. Do's and Don'ts

### Do
- Use `card-accent` on the **first/primary** KPI card only (not all)
- Use `--surface-warm` for page backgrounds instead of `bg-light`
- Keep headings in heavier Inter weights (no separate display font)
- Use asymmetric column splits (5/7, 4/8) for form pages
- Add icons to all badges and status pills

### Don't
- Don't use Bootstrap's default blue `#0d6efd` focus ring — use forest green
- Don't stack every card with `shadow-sm` — mix flat and raised
- Don't use `bg-light` (`#f8f9fa`) for large surface areas — use `--surface-warm`
- Don't apply `card-accent` to every card in a row — it loses impact
- Don't use generic "gray" for empty states — use warm-toned treatment

---

## 10. Component Quick Reference

```
Page bg:     #F5F2ED
Cards:       white + shadow-sm + rounded-4
KPI icons:   44px box, rounded-3, centered
Buttons:     rounded-pill or rounded-3
Badges:      rounded-pill + icon prefix
Breadcrumbs: uppercase + small + text-muted links
Headings:    Inter, 600–900 weight, -0.02em tracking
Body:        Inter, 0.875rem
```

---

*Maintain this guide as new patterns are introduced.*

---

## Appendix: Patterns from DESIGN_SPEC (archived)

These patterns are stable but less frequently used. Kept here for reference.

### Dashed CTA — `.btn-dashed`
Dashed forest-green border, transparent fill. Signature CTA style for "Apply" / "Join" prompts.
```html
<a class="btn btn-dashed px-4 fw-bold">Apply for New Group</a>
```

### Empty State Card
```html
<div class="card border-0 shadow-sm rounded-4 p-5 text-center bg-light">
    <div class="mb-3"><i class="bi bi-search fs-1 text-muted opacity-25"></i></div>
    <h5 class="fw-bold text-dark">No items found</h5>
    <p class="text-muted small">...</p>
    <a class="btn btn-forest rounded-pill px-4 fw-bold btn-sm">Action</a>
</div>
```

### Section Heading (green circle icon)
```html
<div class="mb-3 d-flex align-items-center gap-2">
    <div class="bg-forest text-white rounded-circle d-flex align-items-center justify-content-center"
         style="width: 28px; height: 28px;">
        <i class="bi bi-icon" style="font-size: 0.75rem;"></i>
    </div>
    <h5 class="fw-bold text-dark mb-0 ls-1 text-uppercase small">Section Name</h5>
</div>
```

### Forms
```html
<label class="form-label small fw-bold text-secondary text-uppercase ls-1">Field Name</label>
```
Input groups with icons:
```html
<div class="input-group">
    <span class="input-group-text bg-light text-muted border-end-0"><i class="bi bi-envelope"></i></span>
    <input type="text" class="form-control border-start-0" ...>
</div>
```
Required fields: `<span class="text-danger">*</span>` after the label.

### Modals
```html
<div class="modal-dialog modal-dialog-centered modal-lg modal-dialog-scrollable">
    <div class="modal-content border-0 shadow-lg rounded-4">
```

### User Avatars (circular initials)
```html
<div class="bg-forest text-white rounded-circle d-flex align-items-center justify-content-center fw-bold"
     style="width: 28px; height: 28px; font-size: 0.65rem;">
    {{ name[0]|upper }}
</div>
```

### Search Bars
| Location | Classes | Sizing |
|---|---|---|
| Navbar (global) | `form-control bg-light border-0 small rounded-start-pill px-2` | Width: 160px |
| Page-level | `input-group shadow-sm rounded-pill overflow-hidden border` | `py-1` on input, `px-3` on button |
| Admin dashboard | `input-group shadow-sm rounded-3 overflow-hidden` | `.small` on input |
| Sidebar | `form-control border-0 bg-light rounded-3 py-1 ps-3` | Compact |

### Card Grid Layouts
```html
<!-- 4-column grid (XL) -->
<div class="row row-cols-1 row-cols-sm-2 row-cols-lg-3 row-cols-xl-4 g-3">

<!-- Two-column layout -->
<div class="row g-4">
    <div class="col-md-6">...</div>
    <div class="col-md-6">...</div>
</div>
```
