## React introduction
**React** is a JavaScript library for building user interfaces from **components**. You describe what the UI should look like for the current data (**state**), and React updates the DOM efficiently when that data changes. It is the most common frontend partner for a Spring Boot REST API.

Core ideas:
- **Declarative** - you describe the result, not each DOM operation.
- **Component-based** - the UI is a tree of small, reusable functions.
- **One-way data flow** - data passes down from parent to child through props.
- **Virtual DOM / reconciliation** - React compares the new render output with the previous one and applies only the differences.

## Setting up a React project with Vite
**Vite** is a fast build tool and dev server. You need Node.js (LTS) installed.

```bash
npm create vite@latest training-ui -- --template react
cd training-ui
npm install
npm run dev          # http://localhost:5173 with hot reload
npm run build        # production files in dist/
```

## Folder structure
```
training-ui/
├── index.html              # single HTML page; loads /src/main.jsx
├── package.json            # dependencies and scripts
├── vite.config.js
├── public/                 # static files served as-is
└── src/
    ├── main.jsx            # entry: renders <App /> into #root
    ├── App.jsx             # root component
    ├── components/         # reusable UI: CourseCard.jsx, Button.jsx
    ├── pages/              # route-level screens: CoursesPage.jsx
    ├── services/           # API calls: courseApi.js
    ├── hooks/              # custom hooks: useCourses.js
    └── assets/             # images, global CSS
```

```javascript
// src/main.jsx
import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import App from "./App.jsx";
import "./index.css";

createRoot(document.getElementById("root")).render(
  <StrictMode>
    <App />
  </StrictMode>
);
```

## JSX
**JSX** lets you write HTML-like markup inside JavaScript. Vite compiles it to `React.createElement` calls.

```jsx
function Welcome() {
  const user = { name: "Asha", courses: 3 };
  const isAdmin = false;
  return (
    <section className="welcome">                {/* className, not class */}
      <h1>Hello, {user.name}!</h1>               {/* any JS expression in braces */}
      <p>You are enrolled in {user.courses} courses.</p>
      <label htmlFor="q">Search</label>         {/* htmlFor, not for */}
      <input id="q" style={{ width: "100%" }} />  {/* style takes an object */}
      {isAdmin && <button>Manage</button>}
    </section>
  );
}
```

JSX rules: return **one root element** (or a fragment `<>...</>`), close every tag (`<img />`), use camelCase attributes (`onClick`, `tabIndex`), and remember braces hold **expressions**, not statements (no `if` or `for` inside them). React escapes values in braces automatically, which protects against XSS.

## Components and props
A **component** is a function that returns JSX. Names start with a capital letter. **Props** are the inputs a parent passes to a child - they are read-only.

```jsx
function CourseCard({ title, level, fee = 0, onEnroll }) {
  return (
    <article className="card">
      <h3>{title}</h3>
      <span className="badge">{level}</span>
      <p>{fee === 0 ? "Free" : `₹${fee}`}</p>
      <button onClick={() => onEnroll(title)}>Enroll</button>
    </article>
  );
}

function App() {
  const handleEnroll = (title) => alert(`Enrolled in ${title}`);
  return (
    <main>
      <CourseCard title="Java Basics" level="Beginner" fee={4999} onEnroll={handleEnroll} />
      <CourseCard title="Git Essentials" level="Beginner" onEnroll={handleEnroll} />
    </main>
  );
}
```

`props.children` holds nested content: `<Card><p>Inside</p></Card>`. Keep components small and focused; pass data down and callbacks up.

## State and event handling
**State** is data a component owns that changes over time. `useState` returns the current value and a setter; calling the setter re-renders the component.

```jsx
import { useState } from "react";

function Counter() {
  const [count, setCount] = useState(0);
  return (
    <div>
      <p>Clicked {count} times</p>
      <button onClick={() => setCount(c => c + 1)}>+1</button>
      <button onClick={() => setCount(0)}>Reset</button>
    </div>
  );
}
```

- Never mutate state directly (`count++`, `items.push(x)`) - always call the setter with a **new** value.
- Use the updater form `setCount(c => c + 1)` when the new value depends on the old one.
- Arrays and objects: `setItems([...items, newItem])`, `setUser({ ...user, name: "Ravi" })`, `setItems(items.filter(i => i.id !== id))`.
- State updates are applied on the next render, not immediately.

Event handlers receive a synthetic event: `onClick={handleClick}` (pass the function, do not call it), `onChange={e => setValue(e.target.value)}`, `onSubmit={e => { e.preventDefault(); ... }}`.

## Conditional rendering
```jsx
function CourseStatus({ loading, error, courses }) {
  if (loading) return <p>Loading...</p>;               // early return
  if (error) return <p role="alert">{error}</p>;
  return (
    <>
      {courses.length === 0 ? <p>No courses yet.</p> : <p>{courses.length} courses</p>}
      {courses.length > 10 && <a href="#more">See all</a>}
    </>
  );
}
```

Pitfall: `{count && <Badge />}` renders `0` when `count` is 0. Use `{count > 0 && <Badge />}`.

## Lists and keys
```jsx
function CourseList({ courses }) {
  return (
    <ul>
      {courses.map(course => (
        <li key={course.id}>{course.title}</li>
      ))}
    </ul>
  );
}
```

Each list item needs a **stable, unique `key`** so React can match items between renders. Use a database ID. Avoid the array index when items can be reordered, inserted or deleted - React may reuse the wrong component state - and never use random keys.

## Forms
In a **controlled component**, React state is the single source of truth for an input's value.

```jsx
import { useState } from "react";

function EnrollForm({ onSubmit }) {
  const [form, setForm] = useState({ name: "", email: "", course: "java" });
  const [errors, setErrors] = useState({});

  const handleChange = (e) => {
    const { name, value } = e.target;
    setForm(prev => ({ ...prev, [name]: value }));     // one handler for all fields
  };

  const handleSubmit = (e) => {
    e.preventDefault();
    const next = {};
    if (form.name.trim().length < 2) next.name = "Name is required";
    if (!form.email.includes("@")) next.email = "Enter a valid email";
    setErrors(next);
    if (Object.keys(next).length === 0) onSubmit(form);
  };

  return (
    <form onSubmit={handleSubmit} noValidate>
      <label htmlFor="name">Name</label>
      <input id="name" name="name" value={form.name} onChange={handleChange} />
      {errors.name && <p className="error">{errors.name}</p>}

      <label htmlFor="email">Email</label>
      <input id="email" name="email" type="email" value={form.email} onChange={handleChange} />
      {errors.email && <p className="error">{errors.email}</p>}

      <label htmlFor="course">Course</label>
      <select id="course" name="course" value={form.course} onChange={handleChange}>
        <option value="java">Java</option>
        <option value="react">React</option>
      </select>
      <button type="submit">Enroll</button>
    </form>
  );
}
```

An input with `value` but no `onChange` is read-only. For large forms, libraries such as React Hook Form reduce boilerplate.

## Common mistakes
- Mutating state (`state.items.push`) - React does not see the change.
- Calling a handler during render: `onClick={handleClick()}`.
- Missing or index-based keys in dynamic lists.
- Using `class` and `for` instead of `className` and `htmlFor`.
- Copying props into state and letting them drift apart.

## Practice exercise
Create a Vite React app "Course Catalogue":
1. `CourseCard` component with title, level, fee and an Enroll button (props + callback).
2. `CourseList` rendering an array of courses with proper keys.
3. A search input (controlled) that filters the list - derive the filtered list, do not store it in state.
4. An `EnrollForm` with validation messages.
5. Show "No courses match" when the filter returns nothing and a counter of enrolled courses in the header.

## Key takeaways
- Vite scaffolds and serves React apps; organise code into components, pages, services and hooks.
- JSX is JavaScript with markup; use `className`, `htmlFor` and braces for expressions.
- Props flow down (read-only); state is owned data changed through setters.
- Render lists with stable keys and choose UI with conditional expressions.
- Controlled forms keep input values in state.
