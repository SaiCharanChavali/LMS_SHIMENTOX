## Introduction to Spring Data JPA
Even with Hibernate, you would still write a DAO class with `EntityManager` calls for every entity. **Spring Data JPA** removes that boilerplate: you declare a **repository interface**, and Spring generates the implementation at runtime - CRUD, paging, sorting and queries derived from method names.

Add the starter:

```groovy
implementation 'org.springframework.boot:spring-boot-starter-data-jpa'
runtimeOnly 'com.mysql:mysql-connector-j'
```

## JPA architecture
```
Your service → Spring Data repository (interface) → JPA API (EntityManager)
            → JPA provider (Hibernate) → JDBC → Database
```

| JPA component | Role |
| --- | --- |
| `Entity` | Class mapped to a table |
| `EntityManagerFactory` | Created once; builds EntityManagers (like Hibernate's SessionFactory) |
| `EntityManager` | Manages the persistence context for a unit of work (like a Session) |
| `Persistence context` | Set of managed entities; first-level cache and dirty checking |
| `EntityTransaction` / `@Transactional` | Transaction boundary |
| `JPQL` | Object-oriented query language |

JPA is the **specification**; Hibernate is the **implementation**; Spring Data JPA is a **layer on top** that generates repositories.

## Entity mapping
Entity mapping is the same as in Module 27. A typical pair:

```java
@Entity
public class Course {
    @Id @GeneratedValue(strategy = GenerationType.IDENTITY)
    private Long id;

    @Column(nullable = false, unique = true)
    private String code;

    @Column(nullable = false)
    private String title;

    private BigDecimal fee;

    @Enumerated(EnumType.STRING)
    private Level level;

    @ManyToOne(fetch = FetchType.LAZY)
    private Trainer trainer;

    protected Course() { }
    // constructor, getters, setters
}
```

## JpaRepository
```java
public interface CourseRepository extends JpaRepository<Course, Long> { }
```

That single line gives you:

| Method | Purpose |
| --- | --- |
| `save(entity)` / `saveAll` | Insert or update |
| `findById(id)` | `Optional<Course>` |
| `findAll()`, `findAll(Sort)`, `findAll(Pageable)` | Read all / sorted / paged |
| `existsById(id)`, `count()` | Checks |
| `deleteById(id)`, `delete(entity)` | Delete |
| `flush()`, `saveAndFlush()` | Force SQL now |

Repository hierarchy: `Repository` → `CrudRepository` → `ListCrudRepository` → `PagingAndSortingRepository` → `JpaRepository`. Repository methods are transactional by default (read-only for reads).

## CRUD operations in a service
```java
@Service
@Transactional(readOnly = true)
public class CourseService {
    private final CourseRepository courses;
    public CourseService(CourseRepository courses) { this.courses = courses; }

    @Transactional
    public CourseResponse create(CourseRequest r) {
        if (courses.existsByCode(r.code())) throw new DuplicateCodeException(r.code());
        Course saved = courses.save(new Course(r.code(), r.title(), r.fee()));
        return CourseResponse.from(saved);
    }

    public CourseResponse get(Long id) {
        return courses.findById(id)
            .map(CourseResponse::from)
            .orElseThrow(() -> new ResourceNotFoundException("Course " + id + " not found"));
    }

    @Transactional
    public CourseResponse update(Long id, CourseRequest r) {
        Course c = courses.findById(id).orElseThrow(() -> new ResourceNotFoundException("Course " + id));
        c.setTitle(r.title());           // dirty checking - no save() call required
        c.setFee(r.fee());
        return CourseResponse.from(c);
    }

    @Transactional
    public void delete(Long id) {
        if (!courses.existsById(id)) throw new ResourceNotFoundException("Course " + id);
        courses.deleteById(id);
    }
}
```

Put `@Transactional` on **service** methods that represent one business operation, so several repository calls commit or roll back together.

## Query methods
Spring Data derives queries from method names: `find…By`, `count…By`, `exists…By`, `delete…By` followed by property conditions.

```java
public interface CourseRepository extends JpaRepository<Course, Long> {
    Optional<Course> findByCode(String code);
    boolean existsByCode(String code);
    List<Course> findByLevel(Level level);
    List<Course> findByTitleContainingIgnoreCase(String text);
    List<Course> findByFeeBetween(BigDecimal min, BigDecimal max);
    List<Course> findByLevelAndFeeLessThanOrderByTitleAsc(Level level, BigDecimal max);
    List<Course> findTop5ByOrderByFeeDesc();
    List<Course> findByTrainerName(String name);          // traverses trainer.name
    long countByLevel(Level level);
}
```

Keywords: `And`, `Or`, `Between`, `LessThan`, `GreaterThanEqual`, `Like`, `Containing`, `StartingWith`, `In`, `IsNull`, `True`, `IgnoreCase`, `OrderBy…Asc/Desc`, `First`/`Top`. A misspelled property fails at **startup**, which catches mistakes early. When names get long, switch to `@Query`.

## Relationships in repositories
Relationships are mapped on entities (Module 27). In repositories you can query across them and control fetching:

```java
public interface CourseRepository extends JpaRepository<Course, Long> {

    @EntityGraph(attributePaths = "trainer")             // fetch trainer in the same query (avoid N+1)
    List<Course> findByLevel(Level level);

    @Query("select c from Course c join fetch c.trainer where c.id = :id")
    Optional<Course> findWithTrainer(@Param("id") Long id);
}

public interface EnrollmentRepository extends JpaRepository<Enrollment, Long> {
    List<Enrollment> findByEmployeeIdOrderByEnrolledOnDesc(Long employeeId);
    boolean existsByEmployeeIdAndCourseId(Long employeeId, Long courseId);
}
```

## JPQL and native queries
### JPQL with @Query
```java
@Query("select c from Course c where c.fee <= :max and c.level = :level")
List<Course> affordable(@Param("max") BigDecimal max, @Param("level") Level level);

// DTO projection - select only what the screen needs
@Query("select new com.shimento.training.course.CourseSummary(c.id, c.title, t.name) " +
       "from Course c left join c.trainer t")
List<CourseSummary> summaries();

@Modifying
@Transactional
@Query("update Course c set c.fee = c.fee * :factor where c.level = :level")
int reprice(@Param("factor") BigDecimal factor, @Param("level") Level level);
```

Interface-based projections also work: `interface CourseTitle { String getTitle(); }` and `List<CourseTitle> findByLevel(Level l)`.

### Native queries
```java
@Query(value = "SELECT * FROM course WHERE MATCH(title) AGAINST (:q)", nativeQuery = true)
List<Course> fullTextSearch(@Param("q") String q);
```

Use native SQL for database-specific features (full-text search, window functions). It is not portable and bypasses some JPA checks. In both JPQL and native queries, **always bind parameters** - never concatenate input.

## Pagination and sorting
```java
// Controller
@GetMapping
public Page<CourseResponse> list(@RequestParam(defaultValue = "0") int page,
                                 @RequestParam(defaultValue = "10") int size,
                                 @RequestParam(defaultValue = "title") String sort) {
    if (!Set.of("title", "fee", "id").contains(sort)) throw new IllegalArgumentException("Bad sort field");
    size = Math.min(size, 50);                                         // enforce a maximum
    Pageable pageable = PageRequest.of(page, size, Sort.by(sort).and(Sort.by("id")));   // stable tiebreak
    return courses.findAll(pageable).map(CourseResponse::from);
}
```

A `Page` contains `content`, `totalElements`, `totalPages`, `number` and `size`; it runs an extra count query. Use `Slice` when you only need "is there a next page" (cheaper). Page numbers start at **0**. Always cap the page size and whitelist sort fields.

## Specifications
**Specifications** build dynamic queries from optional filters (search screens with many optional fields) using the JPA Criteria API in a type-safe, composable way.

```java
public interface CourseRepository extends JpaRepository<Course, Long>, JpaSpecificationExecutor<Course> { }

public final class CourseSpecs {
    public static Specification<Course> titleContains(String q) {
        return (root, query, cb) -> q == null ? null
            : cb.like(cb.lower(root.get("title")), "%" + q.toLowerCase() + "%");
    }
    public static Specification<Course> levelIs(Level level) {
        return (root, query, cb) -> level == null ? null : cb.equal(root.get("level"), level);
    }
    public static Specification<Course> feeAtMost(BigDecimal max) {
        return (root, query, cb) -> max == null ? null : cb.lessThanOrEqualTo(root.get("fee"), max);
    }
}

// Usage: null specifications are ignored
Page<Course> result = courses.findAll(
    Specification.where(titleContains(q)).and(levelIs(level)).and(feeAtMost(maxFee)), pageable);
```

## Auditing (optional)
Spring Data can fill in who created/changed a record and when.

```java
@Configuration
@EnableJpaAuditing
public class AuditConfig {
    @Bean
    AuditorAware<String> auditorAware() {
        return () -> Optional.ofNullable(SecurityContextHolder.getContext().getAuthentication())
                             .map(Authentication::getName);          // from the authenticated user
    }
}

@MappedSuperclass
@EntityListeners(AuditingEntityListener.class)
public abstract class Auditable {
    @CreatedDate  @Column(updatable = false) private Instant createdAt;
    @LastModifiedDate                        private Instant updatedAt;
    @CreatedBy    @Column(updatable = false) private String createdBy;
    @LastModifiedBy                          private String updatedBy;
}

@Entity
public class Course extends Auditable { /* ... */ }
```

The auditor must come from the **authenticated security context**, never from a field the client sends.

## Common mistakes
- Putting `@Transactional` on controllers or forgetting it on multi-step service operations.
- Calling `findAll()` on large tables without paging.
- Unbounded `size` parameters and unvalidated sort fields.
- N+1 queries when mapping lazy relationships to DTOs - use `@EntityGraph` or fetch joins.
- Concatenating strings into `@Query`.

## Practice exercise
Extend `training-api`:
1. `CourseRepository` with derived queries: by code, by level, title contains, fee between, top 5 by fee.
2. A JPQL DTO projection `CourseSummary(id, title, trainerName)` without N+1.
3. Paged and sorted `GET /api/courses` with a 50-item maximum and a whitelist of sort fields.
4. A search endpoint using Specifications for optional `q`, `level` and `maxFee` filters.
5. `@Modifying` bulk repricing for a level inside a transaction.
6. Auditing fields filled from the authenticated user (use a fixed user until Module 30).

## Key takeaways
- Spring Data JPA generates repository implementations from interfaces.
- `JpaRepository` gives CRUD, paging and sorting; derived query names express simple queries.
- Use `@Query` (JPQL or native) and projections for complex or optimised reads.
- Paginate with `Pageable`, cap sizes, whitelist sorts and add a stable tiebreaker.
- Specifications compose dynamic filters; auditing records actors from the security context.
