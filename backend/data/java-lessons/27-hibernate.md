## Hibernate introduction and ORM
Writing JDBC code (Module 13) for every table means repetitive SQL, manual mapping of result sets to objects and handling relationships yourself. **ORM (Object-Relational Mapping)** maps Java classes to database tables so you work with objects and the framework generates SQL.

| Object world | Relational world |
| --- | --- |
| Class | Table |
| Object | Row |
| Field | Column |
| Object reference / collection | Foreign key / join table |

**Hibernate** is the most popular ORM and the default implementation of **JPA (Jakarta Persistence API)**, the standard ORM specification. In Spring Boot you write JPA annotations (`jakarta.persistence.*`) and Hibernate does the work underneath.

Benefits: less boilerplate, database portability (dialects), caching, lazy loading and automatic dirty checking. Costs: you must understand the generated SQL, or you get slow queries (N+1) and surprises.

## Hibernate configuration
In plain Hibernate you configure a `hibernate.cfg.xml` or properties; in Spring Boot you use `application.properties`:

```properties
spring.datasource.url=jdbc:mysql://localhost:3306/training_db
spring.datasource.username=${DB_USER}
spring.datasource.password=${DB_PASSWORD}

spring.jpa.hibernate.ddl-auto=validate     # none | validate | update | create | create-drop
spring.jpa.show-sql=true                   # log SQL (development only)
spring.jpa.properties.hibernate.format_sql=true
spring.jpa.open-in-view=false              # do not keep sessions open during view rendering
```

`ddl-auto=create`/`update` is convenient for experiments but dangerous for real databases - use `validate` plus migration tools such as **Flyway** or **Liquibase** for schema changes.

Plain Hibernate bootstrap (for understanding):

```java
SessionFactory factory = new Configuration()
        .configure("hibernate.cfg.xml")
        .addAnnotatedClass(Course.class)
        .buildSessionFactory();
```

## Entity mapping and primary key generation
An **entity** is a class mapped to a table.

```java
import jakarta.persistence.*;

@Entity
@Table(name = "course")
public class Course {

    @Id
    @GeneratedValue(strategy = GenerationType.IDENTITY)
    private Long id;

    @Column(nullable = false, unique = true, length = 20)
    private String code;

    @Column(nullable = false, length = 150)
    private String title;

    @Column(precision = 10, scale = 2)
    private BigDecimal fee;

    @Enumerated(EnumType.STRING)          // store "BEGINNER", not 0
    private Level level;

    private LocalDate startDate;

    @Transient                            // not persisted
    private boolean selected;

    protected Course() { }                // JPA requires a no-arg constructor

    public Course(String code, String title, BigDecimal fee) {
        this.code = code; this.title = title; this.fee = fee;
    }
    // getters and setters ...
}
```

### Primary key generation strategies
| Strategy | How the ID is created | Notes |
| --- | --- | --- |
| `IDENTITY` | Database auto-increment column | Simple; MySQL default; disables JDBC insert batching |
| `SEQUENCE` | Database sequence | Best for PostgreSQL/Oracle; supports batching with allocation size |
| `TABLE` | A table simulating a sequence | Portable but slow |
| `AUTO` | Hibernate chooses for the dialect | Default |
| `UUID` | Generated UUID | Globally unique, larger keys |

## SessionFactory, Session and CRUD
- **SessionFactory** - heavyweight, thread-safe, created once per application; holds configuration and caches.
- **Session** - lightweight, **not** thread-safe, one per unit of work; represents a database conversation and the **persistence context**.
- In JPA terms: `EntityManagerFactory` ≈ `SessionFactory`, `EntityManager` ≈ `Session`.

```java
try (Session session = factory.openSession()) {
    Transaction tx = session.beginTransaction();
    try {
        Course c = new Course("JAVA101", "Java Basics", new BigDecimal("4999"));
        session.persist(c);                       // Create - INSERT at flush/commit

        Course found = session.get(Course.class, c.getId());   // Read by id
        found.setTitle("Java Fundamentals");      // Update - no explicit call needed (dirty checking)

        session.remove(found);                    // Delete
        tx.commit();
    } catch (RuntimeException e) {
        tx.rollback();
        throw e;
    }
}
```

In Spring you never manage sessions manually: inject a repository (Module 29) or an `EntityManager`, and mark service methods `@Transactional`.

## Entity lifecycle
| State | Meaning | How you get there |
| --- | --- | --- |
| **Transient** | New object, not known to Hibernate, no row | `new Course(...)` |
| **Persistent (managed)** | Associated with an open session; changes are tracked | `persist`, `get`, query results |
| **Detached** | Was persistent, but the session closed | Session closed, `detach`, `clear` |
| **Removed** | Scheduled for deletion | `remove` |

**Dirty checking:** at flush (before commit or a query), Hibernate compares managed entities with their snapshots and issues `UPDATE`s for changed fields. To reattach a detached object's changes, use `merge`, which copies its state onto a managed instance.

## HQL
**HQL (Hibernate Query Language)** - and its standard form **JPQL** - queries **entities and fields**, not tables and columns.

```java
List<Course> cheap = session.createQuery(
        "from Course c where c.fee < :max order by c.title", Course.class)
    .setParameter("max", new BigDecimal("5000"))
    .getResultList();

Long count = session.createQuery("select count(c) from Course c where c.level = :lvl", Long.class)
    .setParameter("lvl", Level.BEGINNER)
    .getSingleResult();

// Projection into a DTO
List<CourseSummary> rows = session.createQuery(
    "select new com.shimento.dto.CourseSummary(c.id, c.title) from Course c", CourseSummary.class)
    .getResultList();

// Paging
session.createQuery("from Course", Course.class).setFirstResult(20).setMaxResults(10).getResultList();
```

Always use **named parameters** (`:max`) - never concatenate input into HQL. Native SQL is available with `createNativeQuery` when you need database-specific features.

## Relationships
```java
@Entity
public class Trainer {
    @Id @GeneratedValue private Long id;
    private String name;

    @OneToMany(mappedBy = "trainer", cascade = CascadeType.ALL, orphanRemoval = true)
    private List<Course> courses = new ArrayList<>();

    public void addCourse(Course c) {        // keep both sides in sync
        courses.add(c);
        c.setTrainer(this);
    }
}

@Entity
public class Course {
    @Id @GeneratedValue private Long id;

    @ManyToOne(fetch = FetchType.LAZY)
    @JoinColumn(name = "trainer_id")        // foreign key column - the owning side
    private Trainer trainer;

    @ManyToMany
    @JoinTable(name = "course_tag",
               joinColumns = @JoinColumn(name = "course_id"),
               inverseJoinColumns = @JoinColumn(name = "tag_id"))
    private Set<Tag> tags = new HashSet<>();
}

@Entity
public class Employee {
    @Id @GeneratedValue private Long id;
    @OneToOne(cascade = CascadeType.ALL)
    @JoinColumn(name = "profile_id")
    private Profile profile;
}
```

- The side with `@JoinColumn` (the foreign key) is the **owning side**; `mappedBy` marks the inverse side.
- For many-to-many relationships with extra data (enrollment date, score), use an explicit `Enrollment` entity with two `@ManyToOne` fields instead of `@ManyToMany`.

## Fetching strategies: lazy vs eager
| | LAZY | EAGER |
| --- | --- | --- |
| When loaded | On first access (via a proxy) | Immediately with the parent |
| Defaults | `@OneToMany`, `@ManyToMany` | `@ManyToOne`, `@OneToOne` |
| Risk | `LazyInitializationException` outside a session | Loading far more data than needed |

Recommended: make **all associations LAZY** (`@ManyToOne(fetch = FetchType.LAZY)`) and fetch what each use case needs explicitly.

### The N+1 problem
```java
List<Course> courses = session.createQuery("from Course", Course.class).getResultList(); // 1 query
for (Course c : courses) {
    System.out.println(c.getTrainer().getName());   // +1 query per course!
}
```

Fixes: `join fetch` in the query, an `@EntityGraph`, batch fetching (`hibernate.default_batch_fetch_size`) or a DTO projection.

```java
"select c from Course c join fetch c.trainer"       // 1 query with a join
```

## Cascade types
**Cascading** propagates an operation from a parent entity to its associated entities.

| Cascade | Propagates |
| --- | --- |
| `PERSIST` | Saving the parent saves new children |
| `MERGE` | Merging the parent merges children |
| `REMOVE` | Deleting the parent deletes children |
| `REFRESH` / `DETACH` | Refresh / detach children |
| `ALL` | All of the above |

`orphanRemoval = true` deletes a child row when it is removed from the parent's collection. Use cascades for true parent-child **composition** (Order → OrderItems). Never cascade `REMOVE` from a child to a shared parent (deleting a Course must not delete its Trainer).

## Caching
- **First-level cache** - the persistence context of each `Session`. It is always on: loading the same entity twice in one session hits the database once and returns the **same object instance**.

```java
Course a = session.get(Course.class, 1L);   // SELECT
Course b = session.get(Course.class, 1L);   // no SQL - from first-level cache
System.out.println(a == b);                  // true
```

- **Second-level cache** - optional, shared across sessions (`SessionFactory` scope), provided by Ehcache, Caffeine, Hazelcast etc. Enable per entity with `@Cacheable` and a cache region; good for read-mostly reference data.
- **Query cache** - caches query result IDs; useful only for repeated identical queries on rarely changing data.

## Common mistakes
- `ddl-auto=update` against a production database.
- EAGER fetching everywhere, loading the whole database.
- N+1 queries hidden in loops - always watch the SQL log.
- Returning entities directly from REST controllers (lazy proxies, cycles, leaked fields) - map to DTOs.
- Using `CascadeType.ALL` on `@ManyToOne`.
- Forgetting the protected no-arg constructor or putting `equals`/`hashCode` on a generated ID carelessly.

## Practice exercise
Model a training domain with Hibernate/JPA:
1. Entities `Trainer`, `Course`, `Employee` and `Enrollment` (with `enrolledOn` and `score`).
2. `Trainer` 1:N `Course` with cascade and orphan removal; `Enrollment` as an explicit entity between `Employee` and `Course`.
3. Write CRUD operations and observe the SQL log.
4. Reproduce the N+1 problem listing courses with trainer names, then fix it with `join fetch`.
5. Demonstrate first-level caching and dirty checking in one transaction.
6. Write HQL for "average score per course" returning a DTO.

## Key takeaways
- ORM maps classes to tables; Hibernate is the leading JPA implementation.
- Entities need `@Entity`, `@Id` and a generation strategy; prefer `validate` + migrations.
- Entities move between transient, persistent, detached and removed states; dirty checking writes changes.
- Map relationships carefully: owning side, LAZY fetching, explicit fetch joins to avoid N+1.
- Cascade only within true aggregates; the first-level cache is per session.
