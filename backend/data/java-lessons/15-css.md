## CSS introduction
**CSS (Cascading Style Sheets)** controls how HTML looks: colours, fonts, spacing and layout. A CSS **rule** has a selector and declarations:

```css
h1 {                 /* selector */
  color: #1d4ed8;    /* property: value; */
  font-size: 2rem;
}
```

Three ways to add CSS:
- **External stylesheet** (best): `<link rel="stylesheet" href="styles.css">`
- **Internal**: a `<style>` block in `<head>`
- **Inline**: `<p style="color:red">` (hard to maintain; avoid)

"Cascading" means several rules can apply to one element; the browser decides by **importance** (`!important`), **specificity** and **source order** (later wins). Some properties, such as `color` and `font-family`, are **inherited** by child elements.

## Selectors
| Selector | Example | Selects |
| --- | --- | --- |
| Type | `p` | All `<p>` elements |
| Class | `.card` | Elements with `class="card"` |
| ID | `#main` | The element with `id="main"` |
| Universal | `*` | Everything |
| Descendant | `nav a` | `<a>` anywhere inside `<nav>` |
| Child | `ul > li` | Direct `<li>` children |
| Adjacent / general sibling | `h2 + p`, `h2 ~ p` | Next / following siblings |
| Attribute | `input[type="email"]` | Matching attribute |
| Pseudo-class | `a:hover`, `li:first-child`, `input:focus`, `:not(.done)` | Element state or position |
| Pseudo-element | `p::first-line`, `.req::after` | Part of an element / generated content |
| Group | `h1, h2, h3` | Several selectors |

**Specificity** (highest wins): inline styles > IDs > classes/attributes/pseudo-classes > element types. Prefer classes for styling; IDs make rules hard to override.

## Colors, fonts and backgrounds
```css
:root { color-scheme: light; }
body {
  font-family: "Inter", system-ui, sans-serif;   /* fallbacks */
  font-size: 16px;
  line-height: 1.6;
  color: #1f2937;
  background-color: #f9fafb;
}
.title { font-weight: 700; font-size: 1.5rem; text-transform: uppercase; letter-spacing: .05em; }
.hero {
  background-image: linear-gradient(135deg, #1d4ed8, #7c3aed);
  background-size: cover;
  background-position: center;
  color: white;
}
```

- Colours: names (`red`), hex (`#1d4ed8`), `rgb(29 78 216)`, `rgb(0 0 0 / 50%)` with transparency, `hsl(220 80% 50%)`.
- Ensure enough **contrast** between text and background (WCAG recommends at least 4.5:1 for body text).
- Units: `px` (fixed), `rem` (relative to root font size - good for accessibility), `em` (relative to the parent), `%`, `vw`/`vh` (viewport).
- Web fonts load with `@font-face` or a Google Fonts `<link>`.

## Box model: margin, border, padding
Every element is a rectangular box: **content → padding → border → margin** (from inside out).

```css
* { box-sizing: border-box; }          /* width includes padding and border */
.card {
  width: 300px;
  padding: 16px;                       /* space inside the border */
  border: 1px solid #e5e7eb;
  border-radius: 12px;                 /* rounded corners */
  margin: 16px auto;                   /* space outside; auto centres horizontally */
}
```

With the default `content-box`, the card above would be 300 + 32 + 2 = 334px wide; with `border-box` it is exactly 300px - which is why most projects set it globally. Shorthand order is **top, right, bottom, left** (clockwise): `margin: 10px 20px` means 10px top/bottom and 20px left/right. Vertical margins between blocks can **collapse** into the larger one.

## Display and position
### display
| Value | Behaviour |
| --- | --- |
| `block` | New line, full width, width/height apply |
| `inline` | Flows in text; width/height ignored |
| `inline-block` | Flows in text but respects width/height |
| `none` | Removed from layout (not rendered) |
| `flex` / `grid` | Turns the element into a flex or grid container |

`visibility: hidden` hides an element but keeps its space.

### position
| Value | Behaviour |
| --- | --- |
| `static` | Default; normal flow |
| `relative` | Offset from its normal place; becomes a reference for absolute children |
| `absolute` | Removed from flow; placed relative to the nearest positioned ancestor |
| `fixed` | Placed relative to the viewport; stays when scrolling |
| `sticky` | Normal until a scroll threshold, then sticks |

```css
.badge-wrapper { position: relative; }
.badge { position: absolute; top: 8px; right: 8px; }
.site-header { position: sticky; top: 0; z-index: 10; }
```

`z-index` controls stacking order for positioned elements.

## Flexbox
**Flexbox** lays items out in one dimension - a row or a column.

```css
.toolbar {
  display: flex;
  flex-direction: row;          /* or column */
  justify-content: space-between;   /* main axis: start | center | end | space-between | space-around */
  align-items: center;          /* cross axis */
  gap: 12px;
  flex-wrap: wrap;
}
.toolbar .search { flex: 1; }   /* grow to fill remaining space */
```

Perfect centring: `display: flex; justify-content: center; align-items: center;`. Use flexbox for navbars, toolbars, card footers and aligning items in a row.

## Grid
**CSS Grid** lays items out in two dimensions - rows and columns.

```css
.course-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(250px, 1fr));   /* responsive with no media query */
  gap: 20px;
}

.page {
  display: grid;
  grid-template-columns: 240px 1fr;
  grid-template-areas:
    "header header"
    "sidebar main"
    "footer footer";
}
.page header { grid-area: header; }
.page aside  { grid-area: sidebar; }
```

`fr` is a fraction of the free space. Rule of thumb: **Grid for page layout, Flexbox for components**.

## Media queries and responsive design
**Responsive design** makes one page work on phones, tablets and desktops.

```css
/* Mobile-first: base styles target small screens */
.course-grid { display: grid; grid-template-columns: 1fr; gap: 16px; }

@media (min-width: 768px) {            /* tablets and up */
  .course-grid { grid-template-columns: repeat(2, 1fr); }
}
@media (min-width: 1200px) {           /* desktops */
  .course-grid { grid-template-columns: repeat(3, 1fr); }
}
@media (prefers-color-scheme: dark) {
  body { background: #111827; color: #f9fafb; }
}
img { max-width: 100%; height: auto; }   /* images never overflow */
```

Principles: include the viewport meta tag, design **mobile-first**, use fluid units (`%`, `fr`, `rem`, `clamp(1rem, 2vw, 1.5rem)`), avoid fixed widths and test with browser DevTools device mode.

## CSS variables
**Custom properties** store reusable values and can change at runtime (for theming).

```css
:root {
  --brand: #1d4ed8;
  --radius: 12px;
  --space: 16px;
}
.button { background: var(--brand); border-radius: var(--radius); padding: calc(var(--space) / 2) var(--space); }
[data-theme="dark"] { --brand: #60a5fa; }
```

## Transitions and animations
**Transitions** animate a property change between two states:

```css
.button { transition: background-color .2s ease, transform .2s ease; }
.button:hover { background-color: #1e40af; transform: translateY(-2px); }
```

**Animations** use `@keyframes` for multi-step motion:

```css
@keyframes spin { from { transform: rotate(0); } to { transform: rotate(360deg); } }
.loader { animation: spin 1s linear infinite; }

@media (prefers-reduced-motion: reduce) {
  * { animation: none !important; transition: none !important; }
}
```

Animate `transform` and `opacity` for smooth performance, and respect users who prefer reduced motion.

## Common mistakes
- Fixed pixel widths that overflow on phones.
- Overusing `!important` and IDs, causing specificity wars.
- Forgetting `box-sizing: border-box`.
- Low-contrast text and removing focus outlines without a visible replacement.
- Using absolute positioning for whole layouts instead of flex/grid.

## Practice exercise
Style the `course.html` page from Module 14:
1. Define colours, spacing and radius as CSS variables.
2. Build a sticky header with a flexbox navbar.
3. Lay out course cards with Grid: 1 column on phones, 2 on tablets, 3 on desktops.
4. Push each card's "Enroll" button to the bottom with flexbox.
5. Add hover transitions, a visible `:focus-visible` style and a dark-mode media query.

## Key takeaways
- The cascade resolves conflicts by importance, specificity and order.
- Box model: content, padding, border, margin; use `border-box`.
- Flexbox for one dimension, Grid for two.
- Build mobile-first with media queries and fluid units.
- Use variables for themes and animate transform/opacity responsibly.
