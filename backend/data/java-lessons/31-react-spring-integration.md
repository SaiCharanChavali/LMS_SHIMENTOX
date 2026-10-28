## Introduction to React + Spring Boot integration
A full-stack application has two parts that communicate over HTTP:
- **Frontend** - React (Vite) running in the browser, responsible for UI and user interaction.
- **Backend** - Spring Boot REST API, responsible for business rules, security and data.

They agree on an **API contract**: URLs, HTTP methods, request/response JSON, status codes and error format. Document it with OpenAPI (Module 28) so both sides build against the same specification.

```
Browser (React :5173)  ── HTTP/JSON ──>  Spring Boot API (:8080)  ──>  MySQL
```

## Connecting React with Spring Boot
In development the two run on different ports. Two options:

**Option 1 - Vite proxy (simplest in development).** Requests to `/api` are forwarded to Spring Boot, so the browser sees a single origin and CORS is not needed:

```javascript
// vite.config.js
export default defineConfig({
  plugins: [react()],
  server: {
    proxy: { "/api": "http://localhost:8080" }
  }
});
```

**Option 2 - direct cross-origin calls** to `http://localhost:8080/api`, which require CORS configuration on the server.

In production you can serve the React build from the same domain (Nginx or Spring Boot's `static` folder) or host it separately with an allowed origin.

## CORS configuration
For a separate frontend origin, configure CORS in Spring Security (Module 30) or, without security, with `WebMvcConfigurer`:

```java
@Configuration
public class WebConfig implements WebMvcConfigurer {
    @Value("${app.frontend-origin}")
    private String frontendOrigin;           // http://localhost:5173 in dev

    @Override
    public void addCorsMappings(CorsRegistry registry) {
        registry.addMapping("/api/**")
                .allowedOrigins(frontendOrigin)
                .allowedMethods("GET", "POST", "PUT", "PATCH", "DELETE")
                .allowedHeaders("*")
                .allowCredentials(true);
    }
}
```

A CORS error appears in the browser console, not in Spring logs - check the `Origin` header and the response's `Access-Control-Allow-Origin`.

## Axios for HTTP requests and REST API integration
Keep all HTTP code in a service layer, not inside components.

```javascript
// src/services/http.js
import axios from "axios";
export const http = axios.create({ baseURL: import.meta.env.VITE_API_URL ?? "/api", timeout: 10000 });

// src/services/courseApi.js
import { http } from "./http";
export const courseApi = {
  list: (params) => http.get("/courses", { params }).then(r => r.data),
  get: (id) => http.get(`/courses/${id}`).then(r => r.data),
  create: (body) => http.post("/courses", body).then(r => r.data),
  update: (id, body) => http.put(`/courses/${id}`, body).then(r => r.data),
  remove: (id) => http.delete(`/courses/${id}`)
};
```

## CRUD operations
```jsx
function CoursesPage() {
  const [page, setPage] = useState({ content: [], totalPages: 0, number: 0 });
  const [status, setStatus] = useState("loading");      // loading | ready | error

  const load = useCallback((p = 0) => {
    setStatus("loading");
    courseApi.list({ page: p, size: 10, sort: "title" })
      .then(data => { setPage(data); setStatus("ready"); })
      .catch(() => setStatus("error"));
  }, []);

  useEffect(() => { load(0); }, [load]);

  const remove = async (id) => {
    if (!confirm("Delete this course?")) return;
    await courseApi.remove(id);
    load(page.number);                                  // refresh current page
  };

  if (status === "loading") return <p>Loading courses...</p>;
  if (status === "error") return <p role="alert">Could not load courses. <button onClick={() => load(0)}>Retry</button></p>;
  if (page.content.length === 0) return <p>No courses yet.</p>;
  return (
    <ul>{page.content.map(c => (
      <li key={c.id}>{c.title} <Link to={`/courses/${c.id}/edit`}>Edit</Link> <button onClick={() => remove(c.id)}>Delete</button></li>
    ))}</ul>
  );
}
```

Every screen needs four states: **loading, empty, error and success**.

## Form handling and validation
Validate on the client for fast feedback, and show the **server's** validation errors too - the server is authoritative.

```jsx
function CourseForm({ initial = { title: "", code: "", fee: 0 }, onSaved }) {
  const [form, setForm] = useState(initial);
  const [errors, setErrors] = useState({});
  const [submitting, setSubmitting] = useState(false);

  const submit = async (e) => {
    e.preventDefault();
    if (submitting) return;                            // prevent double submit
    setSubmitting(true);
    setErrors({});
    try {
      const saved = initial.id ? await courseApi.update(initial.id, form) : await courseApi.create(form);
      onSaved(saved);
    } catch (err) {
      if (err.response?.status === 400) setErrors(err.response.data.errors ?? {});   // field errors from ProblemDetail
      else setErrors({ form: "Save failed. Please try again." });
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <form onSubmit={submit} noValidate>
      <label htmlFor="title">Title</label>
      <input id="title" value={form.title} onChange={e => setForm({ ...form, title: e.target.value })} aria-describedby="title-err" />
      {errors.title && <p id="title-err" className="error">{errors.title}</p>}
      {errors.form && <p role="alert">{errors.form}</p>}
      <button disabled={submitting}>{submitting ? "Saving..." : "Save"}</button>
    </form>
  );
}
```

Server side, return field errors in a predictable shape (the `GlobalExceptionHandler` from Module 28 adds an `errors` map). On create, protect against duplicates from retries with unique constraints or an idempotency key.

## Search, filtering, pagination and sorting
Keep search state in the URL so links and the back button work:

```jsx
const [params, setParams] = useSearchParams();
const q = params.get("q") ?? "";
const pageNo = Number(params.get("page") ?? 0);
const sort = params.get("sort") ?? "title";

useEffect(() => {
  const controller = new AbortController();
  http.get("/courses", { params: { q, page: pageNo, size: 10, sort }, signal: controller.signal })
      .then(r => setPage(r.data))
      .catch(e => { if (!axios.isCancel(e)) setError("Search failed"); });
  return () => controller.abort();                 // ignore stale responses
}, [q, pageNo, sort]);

// Debounce the input (Module 20) before calling setParams({ q: value, page: 0, sort })
```

Server: `GET /api/courses?q=java&page=0&size=10&sort=title` returning a `Page` (Module 29) with `totalPages` so the UI can render page buttons. Reset to page 0 when the filter changes.

## File upload and download
```jsx
async function uploadMaterial(courseId, file) {
  const data = new FormData();
  data.append("file", file);                        // name matches @RequestParam("file")
  return http.post(`/courses/${courseId}/materials`, data, {
    onUploadProgress: e => setProgress(Math.round((e.loaded * 100) / e.total))
  });
}

async function downloadMaterial(name) {
  const response = await http.get(`/courses/materials/${name}`, { responseType: "blob" });
  const url = URL.createObjectURL(response.data);
  const a = document.createElement("a");
  a.href = url;
  a.download = name;
  a.click();
  URL.revokeObjectURL(url);
}
```

Do not set `Content-Type` manually for `FormData` - the browser adds the multipart boundary. Validate size and type on the server.

## User registration and login
```java
@PostMapping("/api/auth/register")
@ResponseStatus(HttpStatus.CREATED)
public void register(@Valid @RequestBody RegisterRequest r) {
    if (users.existsByEmail(r.email())) throw new ConflictException("Email already registered");
    users.save(new AppUser(r.email(), passwordEncoder.encode(r.password()), Role.EMPLOYEE));
}

@PostMapping("/api/auth/login")
public TokenResponse login(@Valid @RequestBody LoginRequest r) {
    Authentication auth = authenticationManager.authenticate(
        new UsernamePasswordAuthenticationToken(r.email(), r.password()));
    return tokenService.issue(auth);                 // access + refresh token
}
```

The server assigns the role - never accept a `role` field from the registration form.

## JWT authentication and refresh tokens
React side:

```javascript
let accessToken = null;                              // kept in memory
export const setAccessToken = (t) => { accessToken = t; };

http.interceptors.request.use(config => {
  if (accessToken) config.headers.Authorization = `Bearer ${accessToken}`;
  return config;
});

let refreshing = null;
http.interceptors.response.use(r => r, async error => {
  const original = error.config;
  if (error.response?.status === 401 && !original._retry) {
    original._retry = true;
    refreshing ??= http.post("/auth/refresh").finally(() => { refreshing = null; });   // one refresh for many 401s
    const { data } = await refreshing;
    setAccessToken(data.accessToken);
    return http(original);                           // replay the request
  }
  return Promise.reject(error);
});
```

A common, safer pattern keeps the **refresh token in an HttpOnly, Secure, SameSite cookie** (unreadable by JavaScript) and the short-lived access token in memory. The server **rotates** refresh tokens on each use and revokes them on logout, so a stolen refresh token stops working.

## Protected routes, role-based authorization and logout
```jsx
<Route element={<ProtectedRoute />}>                       {/* any signed-in user */}
  <Route path="/my-courses" element={<MyCourses />} />
</Route>
<Route element={<ProtectedRoute roles={["TRAINER", "ADMIN"]} />}>
  <Route path="/courses/new" element={<CourseForm />} />
</Route>

{user?.role === "ADMIN" && <NavLink to="/admin">Admin</NavLink>}   // hide links the user cannot use
```

The backend enforces the same rules (Module 30); the UI just avoids showing dead ends. Handle **403** by showing "You don't have permission", not a broken page.

Logout:

```javascript
async function logout() {
  try { await http.post("/auth/logout"); }           // server revokes refresh token, clears cookie
  finally {
    setAccessToken(null);
    authContext.clear();
    navigate("/login");
  }
}
```

## Error handling
Centralise error handling so every screen behaves consistently:

| Status | UI behaviour |
| --- | --- |
| 400 | Show field errors next to inputs |
| 401 | Try refresh once, then send to login |
| 403 | "You don't have permission" message |
| 404 | Not-found page or message |
| 409 | Conflict message ("Code already exists") |
| 5xx / network | Friendly retry message; log details |

Never display raw stack traces or server internals to users, and never report success when the request failed.

## Deployment
Two common topologies:
1. **Same origin** - build React (`npm run build`), copy `dist/` into Spring Boot's `src/main/resources/static`, package one JAR; or put Nginx in front serving `dist/` and proxying `/api` to Spring Boot. No CORS needed; cookies are simple.
2. **Separate hosting** - React on Netlify/Vercel/S3+CloudFront, API on a VM/container/App Service. Configure `VITE_API_URL`, CORS for the exact frontend origin and HTTPS on both.

Either way: use HTTPS, production profiles, environment-based secrets and a client-side routing fallback to `index.html`.

## Common mistakes
- Hard-coding `http://localhost:8080` in components.
- No loading/empty/error states.
- Trusting role or user ID values sent by the client.
- Double-submit creating duplicate records.
- Stale search responses overwriting newer ones.
- Storing long-lived tokens in `localStorage`.

## Practice exercise
Connect your React Course Catalogue to `training-api`:
1. Vite proxy for development; `VITE_API_URL` for production.
2. Full CRUD with server-side validation errors shown per field.
3. Search + filter + pagination + sorting stored in the URL.
4. Upload and download course material PDFs with a progress bar.
5. Register/login with JWT access token in memory and refresh token in an HttpOnly cookie; automatic refresh on 401; logout.
6. Protected and role-based routes; 403 handling; deploy both parts and test the whole journey.

## Key takeaways
- React and Spring Boot integrate through a documented REST contract.
- Use a Vite proxy or explicit CORS; keep API calls in a service layer with Axios.
- Handle loading, empty, error and validation states, and prevent duplicate submissions.
- JWT with refresh-token rotation and HttpOnly cookies balances usability and security.
- The UI hides what users cannot do; the API enforces it.
