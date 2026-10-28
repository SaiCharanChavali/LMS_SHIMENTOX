## Hooks
**Hooks** are functions that let components use React features. Rules of hooks: call them only at the **top level** of a component or custom hook (not in loops, conditions or nested functions) and only from React functions.

| Hook | Purpose |
| --- | --- |
| `useState` | Local state |
| `useEffect` | Synchronise with external systems: fetching, subscriptions, timers |
| `useContext` | Read a context value |
| `useRef` | Hold a mutable value or a DOM element reference without re-rendering |
| `useMemo` | Cache an expensive calculation between renders |
| `useCallback` | Cache a function reference between renders |
| `useReducer` | Complex state transitions with a reducer function |

### useEffect
```jsx
import { useEffect, useState } from "react";

function CourseList() {
  const [courses, setCourses] = useState([]);
  const [error, setError] = useState(null);

  useEffect(() => {
    const controller = new AbortController();
    fetch("/api/courses", { signal: controller.signal })
      .then(r => { if (!r.ok) throw new Error(`HTTP ${r.status}`); return r.json(); })
      .then(setCourses)
      .catch(e => { if (e.name !== "AbortError") setError(e.message); });
    return () => controller.abort();          // cleanup when unmounting or re-running
  }, []);                                      // [] = run once after the first render

  if (error) return <p role="alert">{error}</p>;
  return <ul>{courses.map(c => <li key={c.id}>{c.title}</li>)}</ul>;
}
```

The **dependency array** controls when the effect re-runs: no array = after every render, `[]` = once, `[userId]` = whenever `userId` changes. Include every value from the component that the effect uses. In development, `StrictMode` runs effects twice to expose missing cleanup.

### useRef, useMemo and useCallback
```jsx
const inputRef = useRef(null);
useEffect(() => inputRef.current.focus(), []);          // <input ref={inputRef} />

const total = useMemo(() => items.reduce((s, i) => s + i.price * i.qty, 0), [items]);
const handleDelete = useCallback(id => setItems(prev => prev.filter(i => i.id !== id)), []);
```

Use `useMemo`/`useCallback` when profiling shows a real cost - not by default.

## Routing with React Router
**React Router** maps URLs to components in a single-page app.

```bash
npm install react-router-dom
```

```jsx
import { BrowserRouter, Routes, Route, Link, NavLink, useParams, useNavigate } from "react-router-dom";

function App() {
  return (
    <BrowserRouter>
      <nav>
        <NavLink to="/">Home</NavLink> <NavLink to="/courses">Courses</NavLink>
      </nav>
      <Routes>
        <Route path="/" element={<Home />} />
        <Route path="/courses" element={<CourseList />} />
        <Route path="/courses/:id" element={<CourseDetail />} />
        <Route path="*" element={<NotFound />} />
      </Routes>
    </BrowserRouter>
  );
}

function CourseDetail() {
  const { id } = useParams();                 // from /courses/42
  const navigate = useNavigate();
  return <button onClick={() => navigate("/courses")}>Back to course {id} list</button>;
}
```

`Link` changes the URL without reloading the page. Nested routes with `<Outlet />` share layouts. When deploying, configure the server to return `index.html` for unknown paths so deep links work.

## Axios for HTTP requests
**Axios** is an HTTP client with conveniences over `fetch`: automatic JSON, rejection on HTTP error statuses, interceptors and timeouts.

```bash
npm install axios
```

```javascript
// src/services/api.js
import axios from "axios";

export const api = axios.create({
  baseURL: import.meta.env.VITE_API_URL,       // e.g. http://localhost:8080/api
  timeout: 10000
});

export const getCourses = (page = 0) => api.get("/courses", { params: { page, size: 10 } }).then(r => r.data);
export const createCourse = (course) => api.post("/courses", course).then(r => r.data);
export const deleteCourse = (id) => api.delete(`/courses/${id}`);
```

Errors: `error.response` holds the server response (status, body), `error.request` means no response arrived.

## Context API
**Context** shares values with many components without passing props through every level ("prop drilling") - for example the signed-in user or the theme.

```jsx
import { createContext, useContext, useState } from "react";

const AuthContext = createContext(null);

export function AuthProvider({ children }) {
  const [user, setUser] = useState(null);
  const login = (u) => setUser(u);
  const logout = () => setUser(null);
  return <AuthContext.Provider value={{ user, login, logout }}>{children}</AuthContext.Provider>;
}

export const useAuth = () => useContext(AuthContext);

// anywhere below the provider:
function Header() {
  const { user, logout } = useAuth();
  return user ? <button onClick={logout}>Sign out {user.name}</button> : <a href="/login">Sign in</a>;
}
```

Every consumer re-renders when the context value changes, so keep contexts focused (auth, theme) rather than putting all app state in one.

## Custom hooks
A **custom hook** is a function starting with `use` that combines other hooks so logic can be reused.

```jsx
function useFetch(url) {
  const [state, setState] = useState({ data: null, loading: true, error: null });
  useEffect(() => {
    const controller = new AbortController();
    setState({ data: null, loading: true, error: null });
    fetch(url, { signal: controller.signal })
      .then(r => { if (!r.ok) throw new Error(`HTTP ${r.status}`); return r.json(); })
      .then(data => setState({ data, loading: false, error: null }))
      .catch(e => { if (e.name !== "AbortError") setState({ data: null, loading: false, error: e.message }); });
    return () => controller.abort();
  }, [url]);
  return state;
}

function CourseDetail({ id }) {
  const { data, loading, error } = useFetch(`/api/courses/${id}`);
  if (loading) return <p>Loading...</p>;
  if (error) return <p role="alert">{error}</p>;
  return <h2>{data.title}</h2>;
}
```

## Error boundaries, lazy loading and code splitting
### Error boundaries
An **error boundary** catches rendering errors in its child tree and shows a fallback instead of a blank screen. It must be a class component (or use the `react-error-boundary` package):

```jsx
class ErrorBoundary extends React.Component {
  state = { hasError: false };
  static getDerivedStateFromError() { return { hasError: true }; }
  componentDidCatch(error, info) { console.error(error, info); }   // report to logging
  render() { return this.state.hasError ? <p>Something went wrong.</p> : this.props.children; }
}
```

They do not catch errors in event handlers or async code - handle those with `try/catch`.

### Lazy loading and code splitting
By default the bundler ships one large JavaScript file. **Code splitting** creates separate chunks loaded on demand.

```jsx
import { lazy, Suspense } from "react";
const AdminPage = lazy(() => import("./pages/AdminPage.jsx"));   // separate chunk

<Suspense fallback={<p>Loading admin...</p>}>
  <Routes>
    <Route path="/admin" element={<AdminPage />} />
  </Routes>
</Suspense>
```

Split by route first; it gives the biggest win for initial load time.

## Redux Toolkit
For large apps with complex shared state, **Redux Toolkit (RTK)** provides a single store, predictable updates and great DevTools.

```javascript
// cartSlice.js
import { createSlice, configureStore } from "@reduxjs/toolkit";

const cartSlice = createSlice({
  name: "cart",
  initialState: { items: [] },
  reducers: {
    addItem: (state, action) => { state.items.push(action.payload); },  // Immer makes this immutable
    removeItem: (state, action) => { state.items = state.items.filter(i => i.id !== action.payload); }
  }
});
export const { addItem, removeItem } = cartSlice.actions;
export const store = configureStore({ reducer: { cart: cartSlice.reducer } });
```

```jsx
import { Provider, useSelector, useDispatch } from "react-redux";
// <Provider store={store}><App /></Provider>
const items = useSelector(state => state.cart.items);
const dispatch = useDispatch();
dispatch(addItem({ id: 1, title: "Java" }));
```

RTK Query (part of RTK) also handles API caching. Use Context for simple global values and Redux when many components read and update complex shared state.

## JWT authentication and protected routes
With token-based auth, the client sends credentials to `/api/auth/login`, the server returns a **JWT** (JSON Web Token), and the client attaches it to later requests.

```javascript
// Attach the token to every request
api.interceptors.request.use(config => {
  const token = getAccessToken();            // from memory / auth context
  if (token) config.headers.Authorization = `Bearer ${token}`;
  return config;
});

// React to expired sessions
api.interceptors.response.use(
  r => r,
  error => {
    if (error.response?.status === 401) logoutAndRedirect();
    return Promise.reject(error);
  }
);
```

```jsx
import { Navigate, Outlet, useLocation } from "react-router-dom";

function ProtectedRoute({ roles }) {
  const { user } = useAuth();
  const location = useLocation();
  if (!user) return <Navigate to="/login" replace state={{ from: location }} />;
  if (roles && !roles.includes(user.role)) return <Navigate to="/forbidden" replace />;
  return <Outlet />;
}

<Route element={<ProtectedRoute roles={["ADMIN"]} />}>
  <Route path="/admin" element={<AdminPage />} />
</Route>
```

A protected route only improves the **user experience**. The Spring Boot API must still check authentication and authorisation on every request (Module 30). Token storage trade-offs: memory is safest against XSS but is lost on reload; `localStorage` survives reloads but is readable by scripts; HttpOnly cookies are not readable by scripts but need CSRF protection.

## Environment variables, API integration, CRUD and deployment
### Environment variables
Vite exposes variables that start with `VITE_`:

```bash
# .env.development
VITE_API_URL=http://localhost:8080/api
# .env.production
VITE_API_URL=https://api.example.com/api
```

Read them with `import.meta.env.VITE_API_URL`. They are embedded into the public bundle at build time, so **never put secrets** (database passwords, private API keys) in them.

### A CRUD screen
```jsx
function CourseAdmin() {
  const [courses, setCourses] = useState([]);
  const [title, setTitle] = useState("");
  const [busy, setBusy] = useState(false);

  useEffect(() => { getCourses().then(page => setCourses(page.content)); }, []);

  const add = async (e) => {
    e.preventDefault();
    setBusy(true);
    try {
      const saved = await createCourse({ title });
      setCourses(prev => [...prev, saved]);
      setTitle("");
    } finally { setBusy(false); }
  };

  const remove = async (id) => {
    await deleteCourse(id);
    setCourses(prev => prev.filter(c => c.id !== id));
  };

  return (
    <>
      <form onSubmit={add}>
        <input value={title} onChange={e => setTitle(e.target.value)} required aria-label="Course title" />
        <button disabled={busy}>Add</button>
      </form>
      <ul>{courses.map(c => <li key={c.id}>{c.title} <button onClick={() => remove(c.id)}>Delete</button></li>)}</ul>
    </>
  );
}
```

### Deployment (optional)
`npm run build` produces static files in `dist/`. Host them on Netlify, Vercel, AWS S3 + CloudFront, Nginx, or serve them from Spring Boot's `static` folder. Configure a fallback to `index.html` for client-side routes and set the production `VITE_API_URL`.

## Common mistakes
- Missing effect dependencies or cleanup, causing stale data or memory leaks.
- Treating a hidden route as security.
- Putting secrets in `VITE_` variables.
- Using Redux for state that is local to one component.
- Shipping one huge bundle instead of splitting by route.

## Practice exercise
Extend the Course Catalogue from Module 21:
1. Add React Router with list, detail (`/courses/:id`), login and admin pages.
2. Create an Axios instance with base URL from `VITE_API_URL` and a token interceptor.
3. Store the user in an `AuthContext`; protect `/admin` for the ADMIN role.
4. Write a `useCourses(page)` custom hook with loading and error states.
5. Lazy-load the admin page and wrap the app in an error boundary.
6. Implement create/edit/delete for courses against a mock API (json-server) or your Spring Boot API.

## Key takeaways
- `useEffect` synchronises with the outside world and needs correct dependencies and cleanup.
- React Router maps URLs to components; Axios simplifies HTTP calls.
- Context and custom hooks share state and logic; Redux Toolkit handles complex global state.
- Error boundaries, lazy loading and code splitting improve resilience and performance.
- JWT and protected routes shape the UX, but the server enforces security; `VITE_` variables are public.
