## JDBC introduction
**JDBC (Java Database Connectivity)** is the standard Java API for talking to relational databases. Your code uses JDBC interfaces from `java.sql`; a database-specific **driver** implements them. Swap the driver and the same code can talk to MySQL, PostgreSQL or Oracle.

```
Java application → JDBC API (java.sql) → JDBC driver (e.g. MySQL Connector/J) → Database
```

Spring's `JdbcTemplate`, JPA and Hibernate are all built on JDBC, so understanding it explains what those frameworks do for you.

Add the MySQL driver with Gradle:

```groovy
dependencies {
    implementation 'com.mysql:mysql-connector-j:8.4.0'
}
```

## Driver types
| Type | Name | How it works | Today |
| --- | --- | --- | --- |
| Type 1 | JDBC-ODBC bridge | Translates JDBC calls to ODBC | Removed in Java 8 |
| Type 2 | Native-API | Calls the database's native client library | Rare |
| Type 3 | Network protocol | Talks to a middleware server that talks to the DB | Rare |
| Type 4 | Thin / pure Java | Speaks the database's network protocol directly | **Standard choice** (MySQL Connector/J, PostgreSQL driver) |

Modern drivers register themselves automatically (JDBC 4+), so `Class.forName("com.mysql.cj.jdbc.Driver")` is no longer required.

## Establishing a connection
A `Connection` represents a session with the database. `DriverManager.getConnection` opens one from a **JDBC URL**:

```java
import java.sql.*;

public class ConnectDemo {
    public static void main(String[] args) {
        String url = "jdbc:mysql://localhost:3306/training_db";
        String user = System.getenv("DB_USER");          // keep credentials out of code
        String password = System.getenv("DB_PASSWORD");

        try (Connection conn = DriverManager.getConnection(url, user, password)) {
            System.out.println("Connected: " + conn.getMetaData().getDatabaseProductName());
        } catch (SQLException e) {
            System.out.println("Connection failed: " + e.getMessage());
        }
    }
}
```

Steps of every JDBC program:
1. Get a `Connection`.
2. Create a `Statement`, `PreparedStatement` or `CallableStatement`.
3. Execute: `executeQuery` (SELECT → `ResultSet`), `executeUpdate` (INSERT/UPDATE/DELETE → row count) or `execute`.
4. Process the `ResultSet`.
5. Close everything - use **try-with-resources**.

## Statement, PreparedStatement and CallableStatement
### Statement
For fixed SQL with no user input:

```java
try (Statement st = conn.createStatement();
     ResultSet rs = st.executeQuery("SELECT COUNT(*) FROM course")) {
    rs.next();
    System.out.println("Courses: " + rs.getInt(1));
}
```

### The SQL injection problem
Never concatenate user input into SQL:

```java
// DANGEROUS
String sql = "SELECT * FROM users WHERE email = '" + email + "'";
// email = "' OR '1'='1"  →  returns every user
```

### PreparedStatement (use this)
`?` placeholders are sent separately from the values, so input can never change the SQL structure. The statement is also precompiled and reusable.

```java
String sql = "SELECT id, title, fee FROM course WHERE level = ? AND fee <= ?";
try (PreparedStatement ps = conn.prepareStatement(sql)) {
    ps.setString(1, "BEGINNER");     // parameter indexes start at 1
    ps.setBigDecimal(2, new BigDecimal("6000"));
    try (ResultSet rs = ps.executeQuery()) {
        while (rs.next()) {
            System.out.printf("%d %s %s%n", rs.getInt("id"), rs.getString("title"), rs.getBigDecimal("fee"));
        }
    }
}

// Insert and read the generated key
String insert = "INSERT INTO course(code, title, fee) VALUES (?, ?, ?)";
try (PreparedStatement ps = conn.prepareStatement(insert, Statement.RETURN_GENERATED_KEYS)) {
    ps.setString(1, "SQL101");
    ps.setString(2, "SQL Basics");
    ps.setBigDecimal(3, new BigDecimal("2999"));
    int rows = ps.executeUpdate();                // 1
    try (ResultSet keys = ps.getGeneratedKeys()) {
        if (keys.next()) System.out.println("New id: " + keys.getLong(1));
    }
}
```

Placeholders work for values only - not for table or column names. If those must vary, choose from a fixed allow-list.

### CallableStatement
Calls stored procedures:

```java
try (CallableStatement cs = conn.prepareCall("{call give_raise(?, ?)}")) {
    cs.setInt(1, 1);
    cs.setBigDecimal(2, new BigDecimal("5"));
    cs.execute();
}
```

OUT parameters are registered with `cs.registerOutParameter(index, Types.INTEGER)` and read after execution.

## ResultSet
A `ResultSet` is a cursor over query rows; it starts **before** the first row, so call `next()` first.

```java
List<Course> courses = new ArrayList<>();
try (PreparedStatement ps = conn.prepareStatement("SELECT id, code, title FROM course ORDER BY title");
     ResultSet rs = ps.executeQuery()) {
    while (rs.next()) {
        courses.add(new Course(rs.getLong("id"), rs.getString("code"), rs.getString("title")));
    }
}
```

- Read by column label (`rs.getString("title")`) or 1-based index.
- `getInt` returns `0` for SQL NULL; call `rs.wasNull()` or use `rs.getObject("col", Integer.class)`.
- Default result sets are forward-only and read-only; scrollable/updatable ones are requested with `createStatement(ResultSet.TYPE_SCROLL_INSENSITIVE, ResultSet.CONCUR_READ_ONLY)`.
- `ResultSetMetaData` describes column names and types.

## Transactions
By default each statement auto-commits. To make several changes atomic, turn auto-commit off:

```java
public void transfer(Connection conn, long from, long to, BigDecimal amount) throws SQLException {
    String debit = "UPDATE account SET balance = balance - ? WHERE id = ? AND balance >= ?";
    String credit = "UPDATE account SET balance = balance + ? WHERE id = ?";
    boolean oldAutoCommit = conn.getAutoCommit();
    conn.setAutoCommit(false);
    try (PreparedStatement d = conn.prepareStatement(debit);
         PreparedStatement c = conn.prepareStatement(credit)) {
        d.setBigDecimal(1, amount); d.setLong(2, from); d.setBigDecimal(3, amount);
        if (d.executeUpdate() != 1) throw new SQLException("Insufficient funds or missing account");
        c.setBigDecimal(1, amount); c.setLong(2, to);
        if (c.executeUpdate() != 1) throw new SQLException("Target account missing");
        conn.commit();
    } catch (SQLException e) {
        conn.rollback();          // undo the debit too
        throw e;
    } finally {
        conn.setAutoCommit(oldAutoCommit);   // restore state (important with pools)
    }
}
```

Use `conn.setSavepoint()` for partial rollbacks and `conn.setTransactionIsolation(...)` to choose an isolation level.

## Batch processing
Sending many statements one by one costs a network round trip each. **Batching** groups them:

```java
String sql = "INSERT INTO enrollment(employee_id, course_id) VALUES (?, ?)";
conn.setAutoCommit(false);
try (PreparedStatement ps = conn.prepareStatement(sql)) {
    for (long employeeId : employeeIds) {
        ps.setLong(1, employeeId);
        ps.setLong(2, courseId);
        ps.addBatch();
    }
    int[] counts = ps.executeBatch();
    conn.commit();
    System.out.println("Inserted " + counts.length + " rows");
}
```

For MySQL, add `rewriteBatchedStatements=true` to the JDBC URL for a large speed-up. For very large imports, execute the batch every 500-1000 rows.

## RowSet
A **RowSet** (`javax.sql.rowset`) is a `ResultSet` that is also a JavaBean and can be configured with properties.
- `JdbcRowSet` - connected; a scrollable, updatable wrapper around a result set.
- `CachedRowSet` - **disconnected**; loads rows into memory, closes the connection, can be modified offline and synced back.
- `WebRowSet`, `FilteredRowSet`, `JoinRowSet` - add XML export, filtering and joins.

```java
CachedRowSet rs = RowSetProvider.newFactory().createCachedRowSet();
rs.setUrl(url); rs.setUsername(user); rs.setPassword(password);
rs.setCommand("SELECT code, title FROM course");
rs.execute();                 // connection is closed after loading
while (rs.next()) System.out.println(rs.getString("code"));
```

RowSets are rarely used in new Spring applications, but they appear in older enterprise code.

## Connection pooling
Opening a database connection is slow (network handshake, authentication). A **connection pool** keeps a set of open connections and lends them out. Calling `close()` on a pooled connection returns it to the pool instead of closing it.

```java
HikariConfig config = new HikariConfig();
config.setJdbcUrl("jdbc:mysql://localhost:3306/training_db");
config.setUsername(System.getenv("DB_USER"));
config.setPassword(System.getenv("DB_PASSWORD"));
config.setMaximumPoolSize(10);
config.setConnectionTimeout(3000);           // ms to wait for a free connection

try (HikariDataSource ds = new HikariDataSource(config);
     Connection conn = ds.getConnection()) {   // borrowed from the pool
    // use conn
}                                               // returned to the pool
```

**HikariCP** is the default pool in Spring Boot - you just set `spring.datasource.*` properties. Size pools modestly: more connections than the database can serve makes things slower. Always restore connection state (auto-commit, isolation) before returning a connection.

## Common mistakes
- Building SQL with string concatenation (SQL injection).
- Not closing `ResultSet`/`Statement`/`Connection`, leaking resources until the pool is exhausted.
- Forgetting `rs.next()` before reading.
- Leaving auto-commit off or a transaction open after an error.
- Hard-coding passwords in source code.

## Practice exercise
Build a console `CourseDao` for the MySQL `training_db`:
1. `save(Course)` returning the generated id, `findById(long)` returning `Optional<Course>`, `findByLevel(String)`, `updateFee(long, BigDecimal)` and `delete(long)` - all with `PreparedStatement`.
2. `enrollAll(long courseId, List<Long> employeeIds)` using batching inside one transaction.
3. A `transferEnrollment` method that removes one enrollment and adds another atomically; prove rollback by forcing the second step to fail.
4. Replace `DriverManager` with a HikariCP `DataSource`.

## Key takeaways
- JDBC = standard interfaces + vendor driver; Type 4 thin drivers are the norm.
- Always use `PreparedStatement` for input values - it prevents SQL injection.
- `ResultSet` starts before the first row; close all JDBC objects with try-with-resources.
- Disable auto-commit and commit/rollback to make multi-statement work atomic.
- Use batching for bulk writes and a connection pool (HikariCP) in real applications.
