## Why asynchronous JavaScript
JavaScript in the browser runs on a **single main thread**. If it waited for a slow network call, the whole page would freeze. Instead, slow work (network, timers, file reads) runs **asynchronously**: you start it, carry on, and handle the result later. Calling your Spring Boot API from React is always asynchronous.

## JSON
**JSON (JavaScript Object Notation)** is the text format used by REST APIs to exchange data.

```json
{
  "id": 42,
  "title": "Spring Boot",
  "tags": ["java", "spring"],
  "published": true,
  "trainer": { "name": "Kiran" },
  "discount": null
}
```

Rules: keys in double quotes, strings in double quotes, no trailing commas, no comments, no functions or `undefined`. Values may be strings, numbers, booleans, `null`, arrays and objects.

```javascript
const text = JSON.stringify({ id: 1, title: "Java" });   // object -> string
const obj = JSON.parse('{"id":1,"title":"Java"}');        // string -> object
JSON.stringify(obj, null, 2);                             // pretty-printed
```

`JSON.parse` throws a `SyntaxError` on invalid input - wrap it in `try/catch` when the input is untrusted. Spring Boot converts Java objects to and from JSON automatically using Jackson.

## Call stack, event loop and microtask queue
How can a single thread handle asynchronous work? The runtime has these parts:
- **Call stack** - functions currently executing. A function is pushed when called and popped when it returns.
- **Web APIs** - the browser handles timers, network requests and events outside the JS thread.
- **Task (macrotask) queue** - callbacks from `setTimeout`, events, I/O wait here.
- **Microtask queue** - promise callbacks (`then`, `await` continuations) and `queueMicrotask` wait here.
- **Event loop** - when the call stack is empty, it runs **all** microtasks, then **one** macrotask, then repeats (rendering happens between tasks).

```javascript
console.log("1: script start");
setTimeout(() => console.log("4: timeout (macrotask)"), 0);
Promise.resolve().then(() => console.log("3: promise (microtask)"));
console.log("2: script end");
```

Output:

```
1: script start
2: script end
3: promise (microtask)
4: timeout (macrotask)
```

Even with a delay of 0, the timeout runs after the current script and after all microtasks. A long synchronous loop blocks everything - clicks, rendering and timers - so keep main-thread work short.

## Promises
A **Promise** represents a value that will be available later. It is in one of three states: **pending**, **fulfilled** (resolved with a value) or **rejected** (with an error). Once settled, it never changes.

```javascript
function wait(ms) {
  return new Promise(resolve => setTimeout(resolve, ms));
}

function loadCourse(id) {
  return new Promise((resolve, reject) => {
    setTimeout(() => {
      if (id > 0) resolve({ id, title: "Java Basics" });
      else reject(new Error("Invalid id"));
    }, 300);
  });
}

loadCourse(1)
  .then(course => course.title)            // returns a value -> next then
  .then(title => console.log(title))       // "Java Basics"
  .catch(err => console.error(err.message))
  .finally(() => console.log("done"));
```

Each `then` returns a new promise, so steps chain instead of nesting. A single `catch` at the end handles a failure in any earlier step.

### Combining promises
| Method | Resolves when | Rejects when |
| --- | --- | --- |
| `Promise.all([...])` | All fulfil (array of values) | Any rejects (fail fast) |
| `Promise.allSettled([...])` | All settle (array of status objects) | Never |
| `Promise.race([...])` | The first settles | The first settles with an error |
| `Promise.any([...])` | The first fulfils | All reject |

```javascript
const [user, courses] = await Promise.all([getUser(), getCourses()]);   // in parallel
```

## async and await
`async`/`await` is syntax over promises that reads like synchronous code.

```javascript
async function showDashboard(userId) {
  try {
    const user = await getUser(userId);              // waits without blocking the thread
    const courses = await getCourses(user.id);
    console.log(`${user.name} has ${courses.length} courses`);
  } catch (err) {
    console.error("Could not load dashboard:", err.message);
  } finally {
    hideSpinner();
  }
}
```

- An `async` function always returns a promise.
- `await` pauses only that function until the promise settles; a rejection becomes a thrown error.
- Independent calls should run in parallel: `await Promise.all([a(), b()])` rather than two sequential `await`s.
- `await` inside `forEach` does not wait - use `for...of` or `Promise.all(items.map(...))`.

## The Fetch API
`fetch` makes HTTP requests and returns a promise of a `Response`.

```javascript
async function getCourses() {
  const response = await fetch("/api/courses?page=0&size=10");
  if (!response.ok) {                                // fetch does NOT reject on 404/500
    throw new Error(`HTTP ${response.status}`);
  }
  return response.json();                            // parse body (also a promise)
}

async function createCourse(course, token) {
  const response = await fetch("/api/courses", {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      "Authorization": `Bearer ${token}`
    },
    body: JSON.stringify(course)
  });
  const data = await response.json();
  if (!response.ok) throw new Error(data.message || "Create failed");
  return data;
}
```

Important facts:
- `fetch` rejects only on **network failure**; HTTP errors resolve normally - always check `response.ok` or `response.status`.
- Send JSON with `Content-Type: application/json` and `JSON.stringify`.
- Cancel requests with an `AbortController` (`fetch(url, { signal })`), for example when the user navigates away.
- Cookies for another origin require `credentials: "include"` and a matching CORS configuration on the server (Module 31).

## Local storage and session storage
The **Web Storage API** stores string key/value pairs in the browser.

```javascript
localStorage.setItem("theme", "dark");
localStorage.getItem("theme");            // "dark"
localStorage.removeItem("theme");

// Objects must be serialised
const prefs = { pageSize: 20, view: "grid" };
localStorage.setItem("prefs", JSON.stringify(prefs));
const saved = JSON.parse(localStorage.getItem("prefs") ?? "{}");

sessionStorage.setItem("draft", "unsent message");
```

| | `localStorage` | `sessionStorage` | Cookies |
| --- | --- | --- | --- |
| Lifetime | Until cleared | Until the tab closes | Until expiry |
| Scope | Origin, all tabs | Origin, one tab | Domain/path, sent to server |
| Size | ~5-10 MB | ~5 MB | ~4 KB |
| Sent with requests | No | No | Yes, automatically |

Security: any script on the page can read Web Storage, so an XSS bug can steal what is stored there. Do not store passwords or sensitive personal data; think carefully before storing auth tokens (Module 22 and 31 discuss the trade-offs). Never trust stored values for authorisation - the server decides.

## Common mistakes
- Assuming `fetch` throws on a 404 or 500.
- Forgetting `await`, so you get a pending promise instead of data.
- Sequential `await`s for independent requests (slow).
- Not handling rejections - "Uncaught (in promise)" errors.
- Storing secrets in `localStorage`.

## Practice exercise
Use the free test API `https://jsonplaceholder.typicode.com` (or a local mock):
1. Write `async function loadUsers()` that fetches `/users`, checks `response.ok` and returns JSON.
2. Show "Loading...", then the list, or a friendly error message; always hide the spinner in `finally`.
3. Load a user and their posts in parallel with `Promise.all`.
4. Add a search box; cancel the previous request with `AbortController` when a new search starts.
5. Remember the last search term in `localStorage` and restore it on reload.
6. Predict the output order of a snippet mixing `console.log`, `setTimeout` and `Promise.then`, then verify it.

## Key takeaways
- JSON is the data format of REST APIs; `JSON.parse`/`stringify` convert it.
- The event loop runs microtasks (promises) before the next macrotask (timers, events).
- Promises chain with `then/catch`; `async/await` makes them read sequentially.
- `fetch` needs an explicit `response.ok` check.
- Web Storage is convenient but readable by any script - never store secrets there.
