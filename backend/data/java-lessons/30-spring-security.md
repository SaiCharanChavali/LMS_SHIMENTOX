## Security basics
Every API that stores real data must answer two questions on **every request**:
- **Authentication** - *Who are you?* (login with a password, token, certificate, SSO).
- **Authorization** - *Are you allowed to do this?* (roles, permissions, record ownership).

Other core concepts:
- **Principal** - the authenticated identity (user name, ID).
- **Credentials** - proof of identity (password, token).
- **Authority / role** - a permission such as `ROLE_ADMIN` or `course:write`.
- **Defence in depth** - validate input, authenticate, authorize, encrypt in transit (HTTPS), log security events and keep secrets out of code.

Common web threats you must design against (OWASP Top 10): broken access control, injection, broken authentication, sensitive data exposure, security misconfiguration, cross-site scripting (XSS) and cross-site request forgery (CSRF).

## Spring Security setup
Add the starter:

```groovy
implementation 'org.springframework.boot:spring-boot-starter-security'
```

Immediately, every endpoint requires authentication, a default user with a generated password is logged at startup, and you get a login form, HTTP Basic, CSRF protection and security headers.

### How it works: the filter chain
Spring Security is a chain of **servlet filters** that runs **before** your controllers:

```
Request → SecurityFilterChain [CORS → CSRF → Authentication filters → ExceptionTranslation → Authorization] → DispatcherServlet → Controller
```

- An **authentication filter** extracts credentials and asks the `AuthenticationManager` to verify them (via an `AuthenticationProvider` and a `UserDetailsService`).
- On success, the `Authentication` object is stored in the **SecurityContext** (`SecurityContextHolder`) for the rest of the request.
- The **authorization filter** checks whether that authentication may access the URL.

## Authentication
Load users from your database by implementing `UserDetailsService`:

```java
@Entity
public class AppUser {
    @Id @GeneratedValue private Long id;
    @Column(unique = true, nullable = false) private String email;
    @Column(nullable = false) private String passwordHash;
    @Enumerated(EnumType.STRING) private Role role;          // EMPLOYEE, TRAINER, ADMIN
    private boolean enabled = true;
    // getters
}

@Service
public class DbUserDetailsService implements UserDetailsService {
    private final AppUserRepository users;
    public DbUserDetailsService(AppUserRepository users) { this.users = users; }

    @Override
    public UserDetails loadUserByUsername(String email) {
        AppUser u = users.findByEmail(email)
            .orElseThrow(() -> new UsernameNotFoundException("Invalid credentials"));
        return User.withUsername(u.getEmail())
                   .password(u.getPasswordHash())
                   .roles(u.getRole().name())        // becomes ROLE_EMPLOYEE etc.
                   .disabled(!u.isEnabled())
                   .build();
    }
}
```

Use the same generic error message for an unknown user and a wrong password so attackers cannot discover valid accounts. Add rate limiting or lockout against brute-force attempts.

## Password encoding and BCrypt
**Never store passwords in plain text or with reversible encryption.** Store a slow, salted, one-way **hash**. **BCrypt** is the common choice: it adds a random salt automatically and has a configurable cost factor that makes brute force expensive.

```java
@Bean
public PasswordEncoder passwordEncoder() {
    return new BCryptPasswordEncoder(12);          // strength (cost) 12
}

// Registration
String hash = passwordEncoder.encode(rawPassword);   // $2a$12$...  (different every time because of the salt)

// Login - Spring does this for you
boolean ok = passwordEncoder.matches(rawPassword, hash);
```

`PasswordEncoderFactories.createDelegatingPasswordEncoder()` stores hashes with an `{id}` prefix (`{bcrypt}$2a$...`) so you can migrate algorithms later (for example to Argon2).

## Authorization and role-based access control
Configure URL rules with a `SecurityFilterChain` bean:

```java
@Configuration
@EnableWebSecurity
@EnableMethodSecurity
public class SecurityConfig {

    @Bean
    SecurityFilterChain api(HttpSecurity http) throws Exception {
        http
            .authorizeHttpRequests(auth -> auth
                .requestMatchers("/api/auth/**", "/actuator/health").permitAll()
                .requestMatchers(HttpMethod.GET, "/api/courses/**").authenticated()
                .requestMatchers(HttpMethod.POST, "/api/courses/**").hasAnyRole("TRAINER", "ADMIN")
                .requestMatchers("/api/admin/**").hasRole("ADMIN")
                .anyRequest().authenticated())                 // deny-by-default mindset
            .httpBasic(Customizer.withDefaults());
        return http.build();
    }
}
```

Rules are evaluated **in order** - put specific matchers before general ones. **RBAC (Role-Based Access Control)** assigns permissions to roles and roles to users; `hasRole("ADMIN")` checks the authority `ROLE_ADMIN`, while `hasAuthority("course:write")` checks a fine-grained permission.

## Method security
URL rules are coarse. **Method security** protects service methods directly - including **record-level ownership checks**, which prevent users from accessing other users' data by changing an ID in the URL (an *IDOR* vulnerability, the most common access-control bug).

```java
@Service
public class EnrollmentService {

    @PreAuthorize("hasRole('ADMIN') or #employeeId == authentication.principal.id")
    public List<EnrollmentDto> forEmployee(Long employeeId) { ... }

    @PreAuthorize("hasRole('TRAINER')")
    public void gradeSubmission(Long submissionId, int score) { ... }

    @PostAuthorize("returnObject.ownerEmail == authentication.name or hasRole('ADMIN')")
    public CertificateDto certificate(Long id) { ... }
}
```

Or check in code:

```java
Course course = courses.findById(id).orElseThrow();
if (!course.getOwnerId().equals(currentUser.id()) && !currentUser.isAdmin()) {
    throw new AccessDeniedException("Not your course");
}
```

Get the current user with `@AuthenticationPrincipal` in a controller or `SecurityContextHolder.getContext().getAuthentication()`. **Never trust a user ID sent in the request body.**

## CORS
Browsers block JavaScript from reading responses from a **different origin** (scheme + host + port) unless the server allows it via **CORS (Cross-Origin Resource Sharing)** headers. A React app on `http://localhost:5173` calling an API on `http://localhost:8080` is cross-origin.

```java
@Bean
CorsConfigurationSource corsConfigurationSource() {
    CorsConfiguration config = new CorsConfiguration();
    config.setAllowedOrigins(List.of("http://localhost:5173", "https://app.example.com"));
    config.setAllowedMethods(List.of("GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"));
    config.setAllowedHeaders(List.of("Authorization", "Content-Type", "X-XSRF-TOKEN"));
    config.setAllowCredentials(true);                 // only if cookies are used
    UrlBasedCorsConfigurationSource source = new UrlBasedCorsConfigurationSource();
    source.registerCorsConfiguration("/api/**", config);
    return source;
}
// and in the filter chain: http.cors(Customizer.withDefaults())
```

CORS is a **browser** relaxation, not a security barrier: tools like curl ignore it. Never combine `allowCredentials(true)` with a wildcard origin.

## CSRF
**Cross-Site Request Forgery** tricks a logged-in user's browser into sending a state-changing request to your site (the browser attaches cookies automatically). Spring Security enables CSRF protection by default: state-changing requests must include a secret token that a malicious site cannot read.

- **Cookie/session-based** apps: keep CSRF on. For SPAs, use `CookieCsrfTokenRepository.withHttpOnlyFalse()` so the frontend can read the `XSRF-TOKEN` cookie and send it back in an `X-XSRF-TOKEN` header (Axios does this automatically).
- **Stateless APIs with bearer tokens in the `Authorization` header** (not cookies): browsers do not attach the header automatically, so CSRF protection can be disabled - only because of that credential model.

```java
http.csrf(csrf -> csrf.disable())        // ONLY for stateless bearer-token APIs
    .sessionManagement(s -> s.sessionCreationPolicy(SessionCreationPolicy.STATELESS));
```

## JWT
A **JSON Web Token** is a signed, compact token: `header.payload.signature` (Base64URL-encoded). The payload carries **claims** - `sub` (user), `roles`, `iat` (issued at), `exp` (expiry). The signature proves the server issued it and it was not modified. The payload is **encoded, not encrypted** - never put secrets in it.

Typical flow:
1. `POST /api/auth/login` with email/password → server verifies → returns a short-lived **access token** (e.g. 15 minutes) and a longer-lived **refresh token**.
2. Client sends `Authorization: Bearer <access token>` on each request.
3. Server validates signature and expiry on every request - no session lookup needed (stateless).

Spring Security's **resource server** support validates JWTs for you:

```groovy
implementation 'org.springframework.boot:spring-boot-starter-oauth2-resource-server'
```

```java
http.oauth2ResourceServer(oauth -> oauth.jwt(Customizer.withDefaults()));
```

Configure the signing key (`spring.security.oauth2.resourceserver.jwt.secret-key` / public key / issuer URI). Plan the full **lifecycle**: expiry, refresh-token rotation, revocation on logout or password change, and where the client stores tokens.

## OAuth2
**OAuth 2.0** is a delegation framework: a user lets an application access resources on their behalf without sharing their password. **OpenID Connect (OIDC)** adds a standard identity layer on top, which enables "Sign in with Google/Microsoft/GitHub" and corporate SSO (Okta, Keycloak, Azure AD).

Roles: **resource owner** (user), **client** (your app), **authorization server** (issues tokens), **resource server** (your API). The recommended flow for web and mobile apps is **Authorization Code with PKCE**.

```properties
spring.security.oauth2.client.registration.google.client-id=${GOOGLE_CLIENT_ID}
spring.security.oauth2.client.registration.google.client-secret=${GOOGLE_CLIENT_SECRET}
```

```java
http.oauth2Login(Customizer.withDefaults());     // login with an external provider
```

Using an identity provider means you do not store passwords at all.

## Security exception handling
Spring Security distinguishes:
- **401 Unauthorized** - not authenticated (missing/invalid/expired credentials) → `AuthenticationEntryPoint`.
- **403 Forbidden** - authenticated but not allowed → `AccessDeniedHandler`.

```java
http.exceptionHandling(ex -> ex
    .authenticationEntryPoint((req, res, e) -> {
        res.setStatus(401);
        res.setContentType("application/json");
        res.getWriter().write("{\"title\":\"Unauthorized\",\"detail\":\"Please sign in\"}");
    })
    .accessDeniedHandler((req, res, e) -> {
        res.setStatus(403);
        res.setContentType("application/json");
        res.getWriter().write("{\"title\":\"Forbidden\",\"detail\":\"You do not have permission\"}");
    }));
```

Return generic messages; log details (user, path, reason) on the server for auditing.

## Common mistakes
- Hiding buttons in the UI but leaving the API open.
- Missing ownership checks - users read others' records by changing IDs.
- Storing plain or MD5/SHA-1 password hashes.
- Disabling CSRF in a cookie-based app because a tutorial did.
- `allowedOrigins("*")` with credentials, or treating CORS as authentication.
- Long-lived JWTs with no revocation plan; secrets inside JWT payloads.

## Practice exercise
Secure `training-api`:
1. Users in the database with BCrypt hashes and roles EMPLOYEE, TRAINER, ADMIN.
2. URL rules: public login, authenticated reads, trainer/admin writes, admin-only user management.
3. `@PreAuthorize` ownership check so employees only see their own enrollments.
4. JWT login endpoint and resource-server validation (stateless), with 15-minute expiry.
5. CORS for your React dev server; JSON 401/403 responses.
6. Test four cases for each sensitive endpoint: anonymous, wrong role, another user's record, valid user.

## Key takeaways
- Authentication proves identity; authorization decides access - on the server, every request.
- Spring Security is a filter chain; configure it with a `SecurityFilterChain` bean.
- Hash passwords with BCrypt (or another adaptive encoder).
- Combine URL rules, RBAC and method security with record-ownership checks.
- CORS relaxes browser restrictions; CSRF protects cookie-based sessions; JWT and OAuth2 need a full lifecycle design.
