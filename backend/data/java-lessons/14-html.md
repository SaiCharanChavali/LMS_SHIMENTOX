## HTML introduction
**HTML (HyperText Markup Language)** describes the structure and meaning of web content. The browser reads HTML, builds the **DOM** (Document Object Model), applies CSS for presentation and runs JavaScript for behaviour. In a full-stack Java application, HTML is what React (Module 21) ultimately renders, and what Spring Boot can serve directly.

Every page starts from this skeleton:

```html
<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Training Portal</title>
  <link rel="stylesheet" href="styles.css">
</head>
<body>
  <h1>Welcome to the Training Portal</h1>
  <script src="app.js" defer></script>
</body>
</html>
```

- `<!DOCTYPE html>` switches the browser to standards mode.
- `<head>` holds metadata: character set, viewport (essential for mobile), title, stylesheets.
- `<body>` holds the visible content.

## Elements and attributes
An **element** is a start tag, content and an end tag: `<p>Hello</p>`. Some elements are **void** (no content, no end tag): `<img>`, `<br>`, `<input>`, `<meta>`, `<link>`.

Elements are either **block-level** (start on a new line, take full width: `div`, `p`, `h1`, `ul`, `section`) or **inline** (flow within text: `span`, `a`, `strong`, `em`, `img`).

**Attributes** add information to an element in the start tag as `name="value"`:

| Attribute | Purpose |
| --- | --- |
| `id` | Unique identifier on the page |
| `class` | One or more reusable names for CSS/JS |
| `href`, `src` | Link destination, resource location |
| `alt` | Text alternative for an image |
| `title` | Advisory tooltip text |
| `lang` | Language of the content |
| `data-*` | Custom data for scripts, e.g. `data-course-id="42"` |
| `hidden`, `disabled`, `required` | Boolean attributes - presence means true |

## Headings, paragraphs and text
```html
<h1>Java Full Stack</h1>
<h2>Module 1: Java Basics</h2>
<p>Java is a <strong>statically typed</strong> language. Read the <em>setup guide</em> first.</p>
<p>Line one<br>Line two</p>
<hr>
<blockquote>Write once, run anywhere.</blockquote>
<pre><code>System.out.println("Hi");</code></pre>
```

Use **one `h1`** per page and do not skip levels (h2 then h3). Headings create the outline that screen-reader users navigate by - choose them for structure, not for font size. `<strong>` means importance and `<em>` emphasis; for purely visual styling use CSS.

## Links and images
```html
<a href="/courses">All courses</a>                                   <!-- relative -->
<a href="https://dev.java" target="_blank" rel="noopener noreferrer">Dev.java</a>
<a href="#syllabus">Jump to syllabus</a>                            <!-- same page -->
<a href="mailto:training@corp.com">Email us</a>
<a href="/files/guide.pdf" download>Download guide</a>

<img src="/img/java-logo.png" alt="Java logo" width="120" height="120" loading="lazy">
```

- Link text should make sense out of context ("Download the syllabus", not "click here").
- Add `rel="noopener noreferrer"` with `target="_blank"`.
- Every informative image needs meaningful `alt` text; a decorative image uses `alt=""`.
- Set `width` and `height` to prevent layout shift; `loading="lazy"` defers off-screen images.
- `<picture>` and `srcset` serve different image sizes to different screens.

## Lists and tables
```html
<ul>                       <!-- unordered -->
  <li>Java</li>
  <li>Spring Boot</li>
</ul>
<ol start="1">             <!-- ordered -->
  <li>Install JDK</li>
  <li>Write code</li>
</ol>
<dl>                       <!-- description list -->
  <dt>JVM</dt><dd>Executes bytecode</dd>
</dl>

<table>
  <caption>Course fees</caption>
  <thead>
    <tr><th scope="col">Course</th><th scope="col">Fee</th></tr>
  </thead>
  <tbody>
    <tr><td>Java Basics</td><td>₹4,999</td></tr>
    <tr><td>Spring Boot</td><td>₹7,999</td></tr>
  </tbody>
</table>
```

Use tables only for tabular data, never for page layout. `<caption>` and `<th scope>` make tables understandable to assistive technology; `colspan`/`rowspan` merge cells.

## Forms
Forms collect user input and submit it to a server.

```html
<form action="/api/enrollments" method="post">
  <label for="name">Full name</label>
  <input id="name" name="name" type="text" required minlength="2" autocomplete="name">

  <label for="email">Work email</label>
  <input id="email" name="email" type="email" required>

  <label for="course">Course</label>
  <select id="course" name="courseId" required>
    <option value="">Choose a course</option>
    <option value="1">Java Basics</option>
    <option value="2">Spring Boot</option>
  </select>

  <fieldset>
    <legend>Preferred mode</legend>
    <label><input type="radio" name="mode" value="online" checked> Online</label>
    <label><input type="radio" name="mode" value="classroom"> Classroom</label>
  </fieldset>

  <label><input type="checkbox" name="terms" required> I accept the terms</label>

  <label for="notes">Notes</label>
  <textarea id="notes" name="notes" rows="3" maxlength="500"></textarea>

  <button type="submit">Enroll</button>
</form>
```

- Every input needs a `<label>` linked by `for`/`id` (or wrapping the input).
- The `name` attribute is the key sent to the server.
- Input types: `text`, `email`, `password`, `number`, `date`, `tel`, `url`, `file`, `checkbox`, `radio`, `range`, `hidden`.
- Validation attributes: `required`, `min`, `max`, `minlength`, `maxlength`, `pattern`.
- `method="get"` puts data in the URL (searches); `method="post"` sends it in the body (changes, sensitive data).
- Browser validation is only a convenience - **the server must validate again**, because anyone can send requests directly.

## Semantic HTML
Semantic elements describe their meaning, which helps accessibility, SEO and maintainability.

```html
<header>
  <nav aria-label="Main">
    <a href="/">Home</a> <a href="/courses">Courses</a>
  </nav>
</header>
<main>
  <article>
    <h1>Spring Boot Essentials</h1>
    <section>
      <h2>What you will learn</h2>
      <p>...</p>
    </section>
    <aside>Related: Hibernate</aside>
  </article>
</main>
<footer>© 2026 Shimento Training</footer>
```

| Element | Meaning |
| --- | --- |
| `header` / `footer` | Introductory / closing content of a page or section |
| `nav` | Major navigation links |
| `main` | The unique main content (one per page) |
| `article` | Self-contained content (post, course card) |
| `section` | A thematic group with a heading |
| `aside` | Related, secondary content |
| `figure` / `figcaption` | Illustration with caption |
| `time` | A date/time: `<time datetime="2026-10-27">27 Oct</time>` |

Prefer native elements (`button`, `a`, `select`) over clickable `div`s: they come with keyboard support and correct roles for free.

## Audio and video
```html
<video controls width="640" poster="/img/intro.jpg" preload="metadata">
  <source src="/media/intro.webm" type="video/webm">
  <source src="/media/intro.mp4" type="video/mp4">
  <track kind="captions" src="/media/intro.vtt" srclang="en" label="English" default>
  Your browser does not support video.
</video>

<audio controls>
  <source src="/media/podcast.mp3" type="audio/mpeg">
</audio>
```

The browser plays the first `<source>` it supports. `controls` shows the player UI; `autoplay` generally requires `muted`; captions (`<track>`) make media accessible. Embed YouTube or other services with an `<iframe>`.

## Common mistakes
- Inputs without labels, images without `alt`.
- Using `<div onclick>` instead of `<button>`.
- Choosing headings for their size and skipping levels.
- Forgetting the viewport meta tag, so mobile pages render zoomed out.
- Trusting browser validation as security.

## Practice exercise
Build `course.html` for a training portal:
1. A semantic layout with `header`, `nav`, `main`, `article`, `aside` and `footer`.
2. A course description with headings, lists and a fees table with caption.
3. An image with alt text and a captioned introduction video.
4. An enrollment form with name, email, course select, mode radios, terms checkbox and submit button, all labelled.
5. Navigate the page using only the Tab key and check that every control is reachable.

## Key takeaways
- HTML gives content structure; CSS styles it; JavaScript adds behaviour.
- Use attributes such as `alt`, `for`, `name` and `type` correctly.
- Headings form an outline; tables are for data.
- Forms need labels, names and server-side validation.
- Semantic elements improve accessibility and maintainability.
