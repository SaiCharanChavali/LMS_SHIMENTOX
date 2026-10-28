## Introduction and installation
**Bootstrap** is a popular CSS (and small JavaScript) framework of ready-made, responsive components and utility classes. Instead of writing CSS for every button and grid, you compose classes such as `btn btn-primary` or `col-md-6`. It is ideal for admin panels, dashboards and prototypes that need to look consistent quickly.

What Bootstrap provides:
- A responsive 12-column **grid system** built on flexbox.
- Styled **components**: buttons, cards, forms, navbars, modals, alerts, carousels.
- **Utility classes** for spacing, colours, display and flex.
- JavaScript plugins for interactive components (modal, dropdown, collapse, carousel).

## How to add Bootstrap to a project
### Option 1: CDN (fastest to start)
```html
<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.3/dist/css/bootstrap.min.css" rel="stylesheet">
  <title>Bootstrap demo</title>
</head>
<body>
  <h1 class="text-primary">Hello, Bootstrap!</h1>
  <script src="https://cdn.jsdelivr.net/npm/bootstrap@5.3.3/dist/js/bootstrap.bundle.min.js"></script>
</body>
</html>
```

The `bundle` script includes Popper, which dropdowns and tooltips need. Pin an exact version so your site does not change unexpectedly.

### Option 2: npm (for React/Vite projects)
```bash
npm install bootstrap
```

```javascript
// main.jsx
import 'bootstrap/dist/css/bootstrap.min.css';
import 'bootstrap/dist/js/bootstrap.bundle.min.js';   // only if you need JS components
```

React projects can also use **React-Bootstrap**, which wraps the components as React components (`<Button variant="primary">`).

## The grid system
The grid has three levels: **container → row → columns**. Each row has 12 columns.

```html
<div class="container">
  <div class="row g-4">
    <div class="col-12 col-md-6 col-lg-4">Card 1</div>
    <div class="col-12 col-md-6 col-lg-4">Card 2</div>
    <div class="col-12 col-md-6 col-lg-4">Card 3</div>
  </div>
</div>
```

| Breakpoint | Class infix | Min width |
| --- | --- | --- |
| Extra small | (none) `col-` | < 576px |
| Small | `sm` | ≥ 576px |
| Medium | `md` | ≥ 768px |
| Large | `lg` | ≥ 992px |
| Extra large | `xl` | ≥ 1200px |
| XXL | `xxl` | ≥ 1400px |

The example shows full-width cards on phones, two per row on tablets and three per row on laptops. Classes apply from their breakpoint **upward** (mobile-first). `container` has fixed max-widths per breakpoint; `container-fluid` is always full width. `g-*` sets gutters; `offset-md-2` shifts a column; `col` (no number) shares space equally.

## Typography
```html
<h1 class="display-4">Learn Java Full Stack</h1>
<p class="lead">From core Java to cloud deployment.</p>
<p class="text-muted small">Updated October 2026</p>
<p class="fw-bold text-uppercase text-center">Bold, uppercase, centred</p>
<p class="text-truncate" style="max-width: 200px;">A very long course title that will be truncated</p>
```

Bootstrap resets browser defaults (Reboot) and offers `display-1` to `display-6`, `lead`, `fw-*` (font weight), `fs-*` (font size), `text-start/center/end` and text colour classes.

## Buttons
```html
<button type="button" class="btn btn-primary">Enroll</button>
<button type="button" class="btn btn-outline-secondary">Preview</button>
<button type="button" class="btn btn-danger btn-sm">Delete</button>
<button type="button" class="btn btn-success btn-lg" disabled>Completed</button>
<a href="/courses" class="btn btn-link">Browse courses</a>
<div class="btn-group" role="group" aria-label="View">
  <button class="btn btn-outline-primary active">Grid</button>
  <button class="btn btn-outline-primary">List</button>
</div>
```

Variants: `primary`, `secondary`, `success`, `danger`, `warning`, `info`, `light`, `dark`, `link`, each also as `btn-outline-*`. Sizes: `btn-sm`, `btn-lg`.

## Cards
```html
<div class="card h-100 shadow-sm">
  <img src="/img/spring.png" class="card-img-top" alt="Spring Boot logo">
  <div class="card-body d-flex flex-column">
    <span class="badge text-bg-info mb-2 align-self-start">Intermediate</span>
    <h5 class="card-title">Spring Boot</h5>
    <p class="card-text">Build REST APIs with validation and security.</p>
    <a href="/courses/spr201" class="btn btn-primary mt-auto">View course</a>
  </div>
</div>
```

`h-100` makes cards in a row equal height; `d-flex flex-column` plus `mt-auto` pins the button to the bottom.

## Forms
```html
<form class="row g-3 needs-validation" novalidate>
  <div class="col-md-6">
    <label for="name" class="form-label">Full name</label>
    <input type="text" class="form-control" id="name" required>
    <div class="invalid-feedback">Please enter your name.</div>
  </div>
  <div class="col-md-6">
    <label for="course" class="form-label">Course</label>
    <select class="form-select" id="course" required>
      <option value="">Choose...</option>
      <option>Java Basics</option>
    </select>
  </div>
  <div class="col-12 form-check">
    <input class="form-check-input" type="checkbox" id="terms" required>
    <label class="form-check-label" for="terms">I agree to the terms</label>
  </div>
  <div class="col-12"><button class="btn btn-primary" type="submit">Submit</button></div>
</form>
```

Add the class `was-validated` to the form (from JavaScript) to show `invalid-feedback` messages. Other helpers: `input-group`, `form-floating` (floating labels), `form-switch`, `form-range`.

## Navbar
```html
<nav class="navbar navbar-expand-lg bg-dark" data-bs-theme="dark">
  <div class="container">
    <a class="navbar-brand" href="/">Shimento LMS</a>
    <button class="navbar-toggler" type="button" data-bs-toggle="collapse"
            data-bs-target="#mainNav" aria-controls="mainNav" aria-expanded="false" aria-label="Toggle navigation">
      <span class="navbar-toggler-icon"></span>
    </button>
    <div class="collapse navbar-collapse" id="mainNav">
      <ul class="navbar-nav ms-auto">
        <li class="nav-item"><a class="nav-link active" aria-current="page" href="/">Home</a></li>
        <li class="nav-item"><a class="nav-link" href="/courses">Courses</a></li>
      </ul>
    </div>
  </div>
</nav>
```

`navbar-expand-lg` shows the full menu from the `lg` breakpoint and a hamburger toggle below it.

## Carousel, modal and alerts
### Carousel
```html
<div id="promo" class="carousel slide" data-bs-ride="carousel">
  <div class="carousel-inner">
    <div class="carousel-item active"><img src="/img/s1.jpg" class="d-block w-100" alt="New Spring course"></div>
    <div class="carousel-item"><img src="/img/s2.jpg" class="d-block w-100" alt="React workshop"></div>
  </div>
  <button class="carousel-control-prev" type="button" data-bs-target="#promo" data-bs-slide="prev">
    <span class="carousel-control-prev-icon" aria-hidden="true"></span><span class="visually-hidden">Previous</span>
  </button>
  <button class="carousel-control-next" type="button" data-bs-target="#promo" data-bs-slide="next">
    <span class="carousel-control-next-icon" aria-hidden="true"></span><span class="visually-hidden">Next</span>
  </button>
</div>
```

### Modal
```html
<button class="btn btn-danger" data-bs-toggle="modal" data-bs-target="#confirmDelete">Delete course</button>

<div class="modal fade" id="confirmDelete" tabindex="-1" aria-labelledby="confirmTitle" aria-hidden="true">
  <div class="modal-dialog modal-dialog-centered">
    <div class="modal-content">
      <div class="modal-header">
        <h1 class="modal-title fs-5" id="confirmTitle">Delete course?</h1>
        <button type="button" class="btn-close" data-bs-dismiss="modal" aria-label="Close"></button>
      </div>
      <div class="modal-body">This cannot be undone.</div>
      <div class="modal-footer">
        <button class="btn btn-secondary" data-bs-dismiss="modal">Cancel</button>
        <button class="btn btn-danger" id="confirmBtn">Delete</button>
      </div>
    </div>
  </div>
</div>
```

### Alerts
```html
<div class="alert alert-success alert-dismissible fade show" role="alert">
  Enrollment saved!
  <button type="button" class="btn-close" data-bs-dismiss="alert" aria-label="Close"></button>
</div>
```

## Responsive utilities
Utility classes follow the pattern `{property}{sides}-{breakpoint}-{size}`:

| Utility | Example | Effect |
| --- | --- | --- |
| Spacing | `mt-3`, `px-md-5`, `mb-0` | margin top 3, padding x 5 from md, margin bottom 0 |
| Display | `d-none d-md-block` | Hidden on phones, visible from md |
| Flex | `d-flex justify-content-between align-items-center gap-2` | Flex layout in classes |
| Sizing | `w-100`, `h-100`, `mw-100` | Width/height percentages |
| Text | `text-center text-md-start` | Alignment per breakpoint |
| Colours | `bg-light`, `text-danger`, `border-primary` | Theme colours |

Spacing sizes run from 0 to 5 (0 to 3rem). Customise the theme (colours, fonts, radius) by overriding Bootstrap's Sass variables or CSS variables such as `--bs-primary`.

## Common mistakes
- Putting columns directly in a container without a `row`.
- Column numbers in a row adding up to more than 12 unexpectedly.
- Forgetting the JS bundle, so the navbar toggler and modals do nothing.
- Overriding Bootstrap with many `!important` rules instead of theming.
- Removing labels because the design "looks cleaner".

## Practice exercise
Rebuild the training portal with Bootstrap:
1. Responsive navbar with a collapse menu.
2. Hero section with `display` heading and a call-to-action button.
3. Course card grid: 1/2/3 columns at xs/md/lg, equal heights, buttons at the bottom.
4. Enrollment form with validation feedback.
5. A delete-confirmation modal and a dismissible success alert.
6. Hide the sidebar on phones with display utilities.

## Key takeaways
- Add Bootstrap by CDN or npm; include the JS bundle for interactive components.
- Grid = container → row → 12 columns, with mobile-first breakpoints.
- Components (buttons, cards, forms, navbar, modal, alerts, carousel) are composed from classes.
- Utilities handle spacing, display and flex without custom CSS.
- Keep markup accessible: labels, alt text and ARIA attributes still matter.
