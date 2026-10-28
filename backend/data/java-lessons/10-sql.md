## SQL overview
**SQL (Structured Query Language)** is the standard language for relational databases. Its statements fall into groups:

| Group | Purpose | Statements |
| --- | --- | --- |
| DDL - Data Definition | Define structure | `CREATE`, `ALTER`, `DROP`, `TRUNCATE` |
| DML - Data Manipulation | Change data | `INSERT`, `UPDATE`, `DELETE` |
| DQL - Data Query | Read data | `SELECT` |
| DCL - Data Control | Permissions | `GRANT`, `REVOKE` |
| TCL - Transaction Control | Transactions | `COMMIT`, `ROLLBACK`, `SAVEPOINT` |

The examples in this module use this schema:

```sql
CREATE TABLE department (
    dept_id   INT PRIMARY KEY,
    name      VARCHAR(50) NOT NULL UNIQUE
);

CREATE TABLE employee (
    emp_id    INT PRIMARY KEY,
    name      VARCHAR(100) NOT NULL,
    email     VARCHAR(150) UNIQUE,
    salary    DECIMAL(10,2) CHECK (salary > 0),
    dept_id   INT,
    joined_on DATE DEFAULT (CURRENT_DATE),
    FOREIGN KEY (dept_id) REFERENCES department(dept_id)
);
```

## CRUD operations
**C**reate, **R**ead, **U**pdate, **D**elete - the four basic operations behind every application screen.

```sql
-- Create
INSERT INTO department (dept_id, name) VALUES (1, 'Engineering'), (2, 'Sales'), (3, 'HR');
INSERT INTO employee (emp_id, name, email, salary, dept_id)
VALUES (101, 'Asha', 'asha@corp.com', 90000, 1),
       (102, 'Ravi', 'ravi@corp.com', 50000, 2),
       (103, 'Mei',  'mei@corp.com', 120000, 1),
       (104, 'Omar', 'omar@corp.com', 65000, NULL);

-- Read
SELECT name, salary FROM employee WHERE salary > 60000 ORDER BY salary DESC;
SELECT * FROM employee WHERE name LIKE 'A%';           -- starts with A
SELECT * FROM employee WHERE dept_id IN (1, 2);
SELECT * FROM employee WHERE dept_id IS NULL;           -- never "= NULL"
SELECT name FROM employee ORDER BY name LIMIT 2 OFFSET 0;

-- Update (always with WHERE!)
UPDATE employee SET salary = salary * 1.10 WHERE dept_id = 1;

-- Delete (always with WHERE!)
DELETE FROM employee WHERE emp_id = 104;
```

`DELETE` removes chosen rows and can be rolled back; `TRUNCATE` removes all rows quickly; `DROP` removes the table itself.

## Constraints
Constraints let the database enforce business rules no matter which application writes the data.

| Constraint | Rule |
| --- | --- |
| `PRIMARY KEY` | Unique and not null; identifies each row |
| `FOREIGN KEY` | Value must exist in the referenced table (or be NULL) |
| `UNIQUE` | No two rows share the value |
| `NOT NULL` | A value is required |
| `CHECK` | A boolean condition must hold (`salary > 0`) |
| `DEFAULT` | Value used when none is supplied |

Foreign keys can specify what happens when the parent row changes: `ON DELETE CASCADE` (delete children), `ON DELETE SET NULL`, or the default `RESTRICT` (refuse).

## Joins
Joins combine rows from related tables.

```sql
-- INNER JOIN: only employees that have a matching department
SELECT e.name, d.name AS department
FROM employee e
INNER JOIN department d ON e.dept_id = d.dept_id;
-- Asha | Engineering, Ravi | Sales, Mei | Engineering

-- LEFT JOIN: all employees, department or NULL
SELECT e.name, d.name AS department
FROM employee e
LEFT JOIN department d ON e.dept_id = d.dept_id;
-- ... plus Omar | NULL

-- Departments with no employees
SELECT d.name
FROM department d
LEFT JOIN employee e ON e.dept_id = d.dept_id
WHERE e.emp_id IS NULL;            -- HR
```

| Join | Returns |
| --- | --- |
| `INNER JOIN` | Rows with a match in both tables |
| `LEFT JOIN` | All rows from the left table, matches or NULL from the right |
| `RIGHT JOIN` | All rows from the right table |
| `FULL OUTER JOIN` | All rows from both (not in MySQL; emulate with `UNION`) |
| `CROSS JOIN` | Every combination (Cartesian product) |
| Self join | A table joined to itself, e.g. employee and manager |

## Aggregation and functions
```sql
SELECT d.name, COUNT(e.emp_id) AS headcount, AVG(e.salary) AS avg_salary
FROM department d
LEFT JOIN employee e ON e.dept_id = d.dept_id
GROUP BY d.dept_id, d.name
HAVING COUNT(e.emp_id) > 0
ORDER BY avg_salary DESC;
```

- **Aggregate functions**: `COUNT`, `SUM`, `AVG`, `MIN`, `MAX`.
- `WHERE` filters rows **before** grouping; `HAVING` filters groups **after** aggregation.
- **Scalar functions**: `UPPER`, `LOWER`, `CONCAT`, `LENGTH`, `SUBSTRING`, `ROUND`, `COALESCE(x, default)`, `NOW()`, `DATEDIFF`.
- **Window functions** (`OVER`) compute values across related rows without collapsing them: `RANK() OVER (PARTITION BY dept_id ORDER BY salary DESC)`.

Logical order of evaluation: `FROM/JOIN → WHERE → GROUP BY → HAVING → SELECT → ORDER BY → LIMIT`.

## Subqueries
A subquery is a query nested inside another.

```sql
-- Employees earning more than the company average
SELECT name, salary FROM employee
WHERE salary > (SELECT AVG(salary) FROM employee);

-- Employees in departments named 'Engineering' or 'Sales'
SELECT name FROM employee
WHERE dept_id IN (SELECT dept_id FROM department WHERE name IN ('Engineering', 'Sales'));

-- Correlated subquery: earns more than their own department's average
SELECT e.name FROM employee e
WHERE e.salary > (SELECT AVG(x.salary) FROM employee x WHERE x.dept_id = e.dept_id);

-- EXISTS: departments that have at least one employee
SELECT d.name FROM department d
WHERE EXISTS (SELECT 1 FROM employee e WHERE e.dept_id = d.dept_id);
```

## Views, stored procedures and triggers
### Views
A **view** is a saved query that behaves like a virtual table. Use it to simplify complex joins or hide sensitive columns.

```sql
CREATE VIEW employee_directory AS
SELECT e.name, e.email, d.name AS department
FROM employee e LEFT JOIN department d ON d.dept_id = e.dept_id;

SELECT * FROM employee_directory WHERE department = 'Sales';
```

### Stored procedures
A **stored procedure** is named SQL logic stored in the database and called with parameters (MySQL syntax):

```sql
DELIMITER //
CREATE PROCEDURE give_raise(IN p_dept INT, IN p_percent DECIMAL(5,2))
BEGIN
    UPDATE employee SET salary = salary * (1 + p_percent / 100) WHERE dept_id = p_dept;
END //
DELIMITER ;

CALL give_raise(1, 5);
```

### Triggers
A **trigger** runs automatically before or after `INSERT`, `UPDATE` or `DELETE` on a table - for example, an audit log:

```sql
CREATE TRIGGER salary_audit
AFTER UPDATE ON employee
FOR EACH ROW
INSERT INTO salary_log(emp_id, old_salary, new_salary, changed_at)
VALUES (OLD.emp_id, OLD.salary, NEW.salary, NOW());
```

Keep most business logic in the application where it is easier to test and version; use procedures and triggers for focused database-level needs.

## Indexing
An **index** is a separate data structure (usually a B-tree) that lets the database find rows without scanning the whole table - like the index at the back of a book.

```sql
CREATE INDEX idx_employee_dept ON employee(dept_id);
CREATE UNIQUE INDEX idx_employee_email ON employee(email);
CREATE INDEX idx_emp_dept_salary ON employee(dept_id, salary);   -- composite
EXPLAIN SELECT * FROM employee WHERE dept_id = 1;                -- shows the plan
```

- Index columns used in `WHERE`, `JOIN` and `ORDER BY`.
- A composite index `(a, b)` helps queries on `a` or on `a and b`, but not on `b` alone (leftmost-prefix rule).
- Indexes speed up reads but slow down writes and use storage - do not index everything.
- Primary keys and unique constraints are indexed automatically.

## Transactions
A **transaction** groups statements into one all-or-nothing unit.

```sql
START TRANSACTION;
UPDATE account SET balance = balance - 500 WHERE id = 1;
UPDATE account SET balance = balance + 500 WHERE id = 2;
COMMIT;            -- both changes become permanent
-- If anything fails: ROLLBACK;  -- undo both
```

`SAVEPOINT name` marks a point you can `ROLLBACK TO`. **Isolation levels** control what concurrent transactions see: `READ UNCOMMITTED` (dirty reads possible), `READ COMMITTED`, `REPEATABLE READ` (MySQL InnoDB default) and `SERIALIZABLE` (strictest, slowest).

## Common mistakes
- `UPDATE` or `DELETE` without `WHERE`.
- Comparing with `= NULL` instead of `IS NULL`.
- Selecting non-aggregated columns that are not in `GROUP BY`.
- Using `WHERE` to filter aggregates (use `HAVING`).
- Building SQL by concatenating user input (SQL injection - Module 13 shows the fix).

## Practice exercise
Using the employee/department schema:
1. List each department with its headcount, including departments with zero employees.
2. Find the second-highest salary (two ways: subquery and `LIMIT/OFFSET`).
3. Create a view `high_earners` for salaries above the company average.
4. Write a transaction that moves an employee to another department and logs the move; roll it back if the department does not exist.
5. Add an index that helps `WHERE dept_id = ? ORDER BY salary DESC` and check it with `EXPLAIN`.

## Key takeaways
- SQL is grouped into DDL, DML, DQL, DCL and TCL.
- Constraints enforce rules in the database itself.
- `INNER JOIN` keeps matches; `LEFT JOIN` keeps every left row.
- `WHERE` filters rows, `HAVING` filters groups.
- Indexes speed reads at a write cost; transactions make multi-step changes atomic.
