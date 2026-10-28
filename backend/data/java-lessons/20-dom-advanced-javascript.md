## The DOM
When the browser loads HTML, it builds the **Document Object Model (DOM)**: a tree of objects representing every element, attribute and text node. JavaScript reads and changes this tree, and the browser re-renders the page. React (Module 21) manages the DOM for you, but understanding it explains what React does and helps you debug.

```
document
└── html
    ├── head → title
    └── body
        ├── h1 "Courses"
        └── ul#course-list
            ├── li "Java"
            └── li "SQL"
```

## DOM manipulation
### Selecting elements
```javascript
const title = document.getElementById("page-title");
const firstCard = document.querySelector(".course-card");        // first match (CSS selector)
const allCards = document.querySelectorAll(".course-card");      // static NodeList
allCards.forEach(card => console.log(card.dataset.courseId));    // data-course-id attribute
```

### Changing content, attributes and styles
```javascript
title.textContent = "All courses";              // safe: treats the value as text
title.classList.add("highlight");               // add / remove / toggle / contains
title.setAttribute("aria-live", "polite");
title.style.color = "#1d4ed8";                  // prefer toggling classes over inline styles
const input = document.querySelector("#search");
console.log(input.value);
```

### Creating and removing elements
```javascript
const list = document.querySelector("#course-list");
function addCourse(name) {
  const li = document.createElement("li");
  li.textContent = name;                 // never innerHTML with user data
  li.className = "course";
  list.append(li);
}
addCourse("Spring Boot");
list.firstElementChild?.remove();
```

**Security:** `element.innerHTML = userInput` executes injected markup (XSS: `<img src=x onerror=alert(1)>`). Use `textContent` for text, or sanitise trusted HTML. Building many elements? Create them in a `DocumentFragment` and append once to reduce re-layouts.

Traversal properties: `parentElement`, `children`, `firstElementChild`, `nextElementSibling`, `closest(".card")`.

## Events
Events are signals such as clicks, key presses, form submissions and page loads.

```javascript
const button = document.querySelector("#enroll");
function handleEnroll(event) {
  console.log("Clicked", event.target);
}
button.addEventListener("click", handleEnroll);
button.removeEventListener("click", handleEnroll);   // needs the same function reference

document.addEventListener("keydown", e => {
  if (e.key === "Escape") closeModal();
});

document.querySelector("#enroll-form").addEventListener("submit", e => {
  e.preventDefault();                // stop the full-page form submission
  // send data with fetch instead
});
```

Common events: `click`, `dblclick`, `input` (every change), `change` (committed change), `submit`, `keydown`, `focus`/`blur`, `mouseenter`, `scroll`, `resize`, `DOMContentLoaded`, `load`.

### Propagation
An event travels in three phases: **capturing** (window → target), **target**, then **bubbling** (target → window). Listeners run during bubbling by default. `event.stopPropagation()` stops the journey; `event.preventDefault()` cancels the browser's default action (following a link, submitting a form). `event.target` is the element that was actually clicked; `event.currentTarget` is the element the listener is attached to.

## Event delegation
Instead of attaching a listener to each item, attach **one** listener to a common parent and use bubbling to find which child was clicked. It uses less memory and works for items added later.

```html
<ul id="course-list">
  <li data-id="1">Java <button class="delete">Delete</button></li>
  <li data-id="2">SQL <button class="delete">Delete</button></li>
</ul>
```

```javascript
document.querySelector("#course-list").addEventListener("click", event => {
  const button = event.target.closest(".delete");
  if (!button) return;                         // click was somewhere else
  const item = button.closest("li");
  console.log("Delete course", item.dataset.id);
  item.remove();
});
```

## Form validation
Combine HTML attributes, the Constraint Validation API and custom checks - and remember the server validates again.

```javascript
const form = document.querySelector("#signup");
const email = form.elements.email;
const password = form.elements.password;
const error = document.querySelector("#password-error");

password.addEventListener("input", () => {
  const strong = /^(?=.*[A-Z])(?=.*\d).{8,}$/.test(password.value);
  password.setCustomValidity(strong ? "" : "At least 8 characters, one capital letter and one digit");
  error.textContent = password.validationMessage;
});

form.addEventListener("submit", event => {
  event.preventDefault();
  if (!form.checkValidity()) {          // runs required/type/pattern checks
    form.reportValidity();              // shows browser messages
    return;
  }
  const data = Object.fromEntries(new FormData(form));   // { email: "...", password: "..." }
  submitToApi(data);
});
```

Good UX: validate on `blur` or after the first submit, show messages next to the field, link them with `aria-describedby`, and keep the user's input when a server error comes back.

## Debouncing
**Debouncing** delays a function until events stop arriving for a set time. Typical use: search-as-you-type, so you call the API once the user pauses instead of on every keystroke.

```javascript
function debounce(fn, delay) {
  let timer;
  return (...args) => {
    clearTimeout(timer);                        // cancel the previous scheduled call
    timer = setTimeout(() => fn(...args), delay);
  };
}

const search = debounce(term => {
  console.log("Searching for", term);           // fetch(`/api/courses?q=${encodeURIComponent(term)}`)
}, 400);

document.querySelector("#search").addEventListener("input", e => search(e.target.value));
```

Typing "spring" quickly triggers six input events but only one search, 400 ms after the last key.

## Throttling
**Throttling** runs a function at most once per time interval, no matter how often the event fires. Typical use: scroll, resize and mousemove handlers.

```javascript
function throttle(fn, interval) {
  let last = 0;
  return (...args) => {
    const now = Date.now();
    if (now - last >= interval) {
      last = now;
      fn(...args);
    }
  };
}

window.addEventListener("scroll", throttle(() => {
  const nearBottom = window.innerHeight + window.scrollY >= document.body.offsetHeight - 200;
  if (nearBottom) loadMoreCourses();              // infinite scroll
}, 300));
```

| | Debounce | Throttle |
| --- | --- | --- |
| Runs | After events stop for N ms | At most once every N ms |
| Use for | Search input, auto-save, resize end | Scroll position, drag, analytics |

## Common mistakes
- Using `innerHTML` with user-provided data.
- Forgetting `preventDefault()` on form submit, so the page reloads.
- Adding listeners inside loops for every item instead of delegating.
- Passing a new anonymous function to `removeEventListener` (it never matches).
- Calling the API on every keystroke without debouncing.

## Practice exercise
Build a "course manager" page without any framework:
1. Render a list of courses from an array using `createElement` and `textContent`.
2. Add a form to create a course with validation (title required, fee ≥ 0) and inline error messages.
3. Delete and "mark complete" buttons handled by a **single** delegated listener.
4. A debounced search box that filters the list.
5. A throttled scroll handler that shows a "back to top" button after scrolling 500px.

## Key takeaways
- The DOM is a live tree you query with `querySelector` and update with `textContent`, `classList` and `append`.
- Use `addEventListener`; understand bubbling, `preventDefault` and `stopPropagation`.
- Event delegation handles many (and future) children with one listener.
- Validate forms with the Constraint Validation API, but trust only server validation.
- Debounce waits for a pause; throttle limits frequency.
