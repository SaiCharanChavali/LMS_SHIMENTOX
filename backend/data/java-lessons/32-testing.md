## Why testing matters
Automated tests prove your code works, catch regressions when you change it, document expected behaviour and make refactoring safe. A balanced strategy follows the **testing pyramid**:

```
            /  E2E  \          few, slow, high confidence in user journeys
           /---------\
          / Integration\       some: database, HTTP, wiring
         /-------------\
        /     Unit      \      many, fast, focused business rules
```

A good test is **fast, isolated, repeatable, self-checking and readable**. Structure each test as **Arrange - Act - Assert** (or Given - When - Then).

## JUnit
**JUnit 5 (Jupiter)** is the standard Java testing framework.

```java
class FeeCalculatorTest {

    private FeeCalculator calculator;

    @BeforeEach
    void setUp() { calculator = new FeeCalculator(); }

    @Test
    @DisplayName("applies 10% discount for early enrollment")
    void earlyDiscount() {
        BigDecimal fee = calculator.fee(new BigDecimal("1000"), true);   // Act
        assertEquals(new BigDecimal("900.00"), fee);                        // Assert
    }

    @Test
    void rejectsNegativeFee() {
        assertThrows(IllegalArgumentException.class,
            () -> calculator.fee(new BigDecimal("-1"), false));
    }

    @ParameterizedTest
    @CsvSource({ "95, A", "80, B", "60, C", "10, F" })
    void grades(int marks, String expected) {
        assertEquals(expected, Grades.of(marks));
    }
}
```

Key annotations: `@Test`, `@BeforeEach`/`@AfterEach`, `@BeforeAll`/`@AfterAll`, `@DisplayName`, `@Disabled`, `@Nested`, `@ParameterizedTest` with `@ValueSource`/`@CsvSource`/`@MethodSource`. Assertions: `assertEquals`, `assertTrue`, `assertNotNull`, `assertThrows`, `assertAll`, `assertTimeout`. **AssertJ** offers fluent assertions: `assertThat(list).hasSize(3).contains("Java")`.

Run with `./gradlew test` (with `useJUnitPlatform()`).

## Mockito
A unit test should not hit a real database or network. **Mockito** creates **mocks** - fake objects whose behaviour you program and whose interactions you can verify.

```java
@ExtendWith(MockitoExtension.class)
class EnrollmentServiceTest {

    @Mock EnrollmentRepository enrollments;
    @Mock CourseRepository courses;
    @InjectMocks EnrollmentService service;

    @Test
    void enrollsWhenSeatsAvailable() {
        Course course = new Course("JAVA101", "Java", 30);
        when(courses.findById(1L)).thenReturn(Optional.of(course));               // stub
        when(enrollments.countByCourseId(1L)).thenReturn(10L);

        service.enroll(7L, 1L);

        verify(enrollments).save(argThat(e -> e.getEmployeeId().equals(7L)));     // verify interaction
    }

    @Test
    void rejectsWhenCourseFull() {
        when(courses.findById(1L)).thenReturn(Optional.of(new Course("JAVA101", "Java", 30)));
        when(enrollments.countByCourseId(1L)).thenReturn(30L);

        assertThrows(CourseFullException.class, () -> service.enroll(7L, 1L));
        verify(enrollments, never()).save(any());
    }
}
```

- **Stub** return values with `when(...).thenReturn(...)` or `thenThrow(...)`.
- **Verify** calls with `verify(mock).method(...)`, `times(n)`, `never()`.
- `ArgumentCaptor` captures arguments for detailed assertions.
- Mock only **boundaries you own** (repositories, gateways) and assert on **outcomes**, not just "method was called".

## Spring Boot testing
`spring-boot-starter-test` bundles JUnit 5, Mockito, AssertJ, MockMvc and more. **Test slices** load only part of the application, making tests faster:

| Annotation | Loads | Use for |
| --- | --- | --- |
| `@SpringBootTest` | Full application context | End-to-end within the app |
| `@WebMvcTest(CourseController.class)` | MVC layer only (controllers, advice, filters) | Request mapping, validation, JSON, status codes |
| `@DataJpaTest` | JPA, repositories, embedded/test DB, transactions rolled back | Repository queries |
| `@JsonTest` | Jackson | Serialisation |

```java
@WebMvcTest(CourseController.class)
class CourseControllerTest {

    @Autowired MockMvc mvc;
    @MockitoBean CourseService service;      // replaces the bean with a mock (Spring Boot 3.4+; older: @MockBean)

    @Test
    void returns404WhenMissing() throws Exception {
        when(service.get(99L)).thenThrow(new ResourceNotFoundException("Course 99 not found"));
        mvc.perform(get("/api/courses/99"))
           .andExpect(status().isNotFound())
           .andExpect(jsonPath("$.detail").value("Course 99 not found"));
    }

    @Test
    void rejectsBlankTitle() throws Exception {
        mvc.perform(post("/api/courses")
                .contentType(MediaType.APPLICATION_JSON)
                .content("{\"title\":\"\",\"code\":\"JAVA101\",\"fee\":100}"))
           .andExpect(status().isBadRequest())
           .andExpect(jsonPath("$.errors.title").exists());
    }
}
```

With Spring Security on the classpath, use `@WithMockUser(roles = "ADMIN")` and `.with(csrf())` to test access rules: anonymous → 401, wrong role → 403, right role → 200.

## Integration testing
**Integration tests** check that components work together with real infrastructure: SQL queries, constraints, transactions, JSON mapping and security.

```java
@DataJpaTest
class CourseRepositoryTest {
    @Autowired CourseRepository repo;

    @Test
    void findsByTitleIgnoringCase() {
        repo.save(new Course("JAVA101", "Java Basics", new BigDecimal("4999")));
        assertThat(repo.findByTitleContainingIgnoreCase("java")).hasSize(1);
    }

    @Test
    void enforcesUniqueCode() {
        repo.saveAndFlush(new Course("JAVA101", "A", BigDecimal.ONE));
        assertThrows(DataIntegrityViolationException.class,
            () -> repo.saveAndFlush(new Course("JAVA101", "B", BigDecimal.ONE)));
    }
}
```

An in-memory H2 database behaves differently from MySQL (SQL dialect, constraints, functions), so tests can pass on H2 and fail in production. That is what Testcontainers solves.

## Testcontainers
**Testcontainers** starts real dependencies (MySQL, PostgreSQL, Kafka, Redis) in disposable Docker containers for your tests.

```groovy
testImplementation 'org.springframework.boot:spring-boot-testcontainers'
testImplementation 'org.testcontainers:junit-jupiter'
testImplementation 'org.testcontainers:mysql'
```

```java
@SpringBootTest(webEnvironment = SpringBootTest.WebEnvironment.RANDOM_PORT)
@Testcontainers
class CourseApiIntegrationTest {

    @Container
    @ServiceConnection                                  // Boot wires the datasource to the container
    static MySQLContainer<?> mysql = new MySQLContainer<>("mysql:8.4");

    @Autowired TestRestTemplate rest;

    @Test
    void createThenFetch() {
        var created = rest.postForEntity("/api/courses",
            Map.of("title", "Docker", "code", "DKR101", "fee", 100), CourseResponse.class);
        assertThat(created.getStatusCode()).isEqualTo(HttpStatus.CREATED);
        var fetched = rest.getForObject("/api/courses/" + created.getBody().id(), CourseResponse.class);
        assertThat(fetched.title()).isEqualTo("Docker");
    }
}
```

Docker must be available on the developer machine and CI runner. Containers can be reused across test classes to keep suites fast.

## Postman API testing
**Postman** is a tool for exploring and testing APIs manually and with scripts.
- Organise requests in **collections** (Courses → List, Create, Get, Update, Delete).
- Use **environments** with variables (`{{baseUrl}}`, `{{token}}`) for local, staging and production.
- Write **test scripts** that run after each response:

```javascript
pm.test("status is 201", () => pm.response.to.have.status(201));
pm.test("returns an id", () => pm.expect(pm.response.json().id).to.be.a("number"));
pm.environment.set("courseId", pm.response.json().id);   // chain into the next request
```

- Run whole collections with the Collection Runner or in CI with **Newman** (`newman run courses.postman_collection.json -e staging.json`).

Alternatives: Insomnia, Bruno, IntelliJ HTTP Client, curl.

## React testing
**Vitest** (or Jest) with **React Testing Library** tests components the way users use them - by visible text, labels and roles, not implementation details.

```jsx
// CourseForm.test.jsx
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { vi, test, expect } from "vitest";
import CourseForm from "./CourseForm";

test("shows an error when the title is empty", async () => {
  const onSaved = vi.fn();
  render(<CourseForm onSaved={onSaved} />);

  await userEvent.click(screen.getByRole("button", { name: /save/i }));

  expect(await screen.findByText(/title is required/i)).toBeInTheDocument();
  expect(onSaved).not.toHaveBeenCalled();
});
```

Mock network calls with **MSW (Mock Service Worker)** so components exercise real fetch/Axios code against fake responses, including errors and slow responses.

## End-to-end testing
**E2E tests** drive a real browser through complete user journeys against a running frontend and backend. Tools: **Playwright**, Cypress, Selenium.

```javascript
// e2e/enroll.spec.js (Playwright)
import { test, expect } from "@playwright/test";

test("employee can sign in and enroll in a course", async ({ page }) => {
  await page.goto("/login");
  await page.getByLabel("Email").fill("asha@corp.com");
  await page.getByLabel("Password").fill(process.env.E2E_PASSWORD);
  await page.getByRole("button", { name: "Sign in" }).click();

  await page.getByRole("link", { name: "Java Basics" }).click();
  await page.getByRole("button", { name: "Enroll" }).click();
  await expect(page.getByText("You are enrolled")).toBeVisible();
});
```

Keep E2E tests few and focused on critical journeys (sign-in, checkout, enrollment), seed known test data, and avoid fixed `sleep`s - use auto-waiting assertions.

## What to test and coverage
- Business rules and edge cases: empty, zero, maximum, invalid, duplicate.
- Failure paths: not found, validation errors, exceptions from dependencies.
- **Security**: anonymous, wrong role, other user's record, valid user.
- Concurrency and retries where they matter (double submit, idempotency).

**Code coverage** (JaCoCo) shows which lines ran during tests - not whether behaviour is correct. Use it to find untested areas, not as the goal.

## Common mistakes
- Tests that depend on execution order or shared mutable data.
- Mocking everything, so tests only repeat the implementation.
- Only testing the happy path.
- H2 tests hiding MySQL-specific failures.
- Brittle UI tests that select by CSS class instead of role/label.

## Practice exercise
For `training-api` and the React app:
1. JUnit + Mockito unit tests for `EnrollmentService` (seat limit, duplicate enrollment, missing course).
2. `@WebMvcTest` for `CourseController`: 200, 201, 400, 404, and 401/403 with security.
3. `@DataJpaTest` for custom queries, then a Testcontainers MySQL integration test for create-then-fetch.
4. A Postman collection with environment variables and test scripts, run with Newman.
5. React Testing Library tests for the course form (validation and server error).
6. One Playwright E2E test for sign-in and enrollment.

## Key takeaways
- Follow the pyramid: many unit tests, some integration tests, few E2E tests.
- JUnit 5 structures tests; Mockito isolates dependencies.
- Spring test slices (`@WebMvcTest`, `@DataJpaTest`) speed up focused tests.
- Testcontainers runs integration tests against real databases.
- Postman, React Testing Library and Playwright cover APIs, components and full journeys; coverage is a guide, not proof.
