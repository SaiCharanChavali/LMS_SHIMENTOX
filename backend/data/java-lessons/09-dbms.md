## Introduction to DBMS
A **database** is an organised collection of data. A **Database Management System (DBMS)** is the software that stores that data and lets many users and applications read and change it safely. Examples: MySQL, PostgreSQL, Oracle, SQL Server (relational) and MongoDB (document).

Why not just use files?

| Plain files | DBMS |
| --- | --- |
| Duplicate data across files becomes inconsistent | Shared, centrally defined data |
| Each program writes its own search code | Declarative query language (SQL) |
| Concurrent writes overwrite each other | Concurrency control and locking |
| Crashes can leave half-written data | Transactions and recovery |
| Access control is all-or-nothing | Users, roles and privileges |

A **Relational DBMS (RDBMS)** stores data in **tables** (relations) made of **rows** (records/tuples) and **columns** (attributes). Each column has a data type and optional constraints.

### ACID transactions
Relational databases guarantee **ACID** properties for transactions:
- **Atomicity** - all statements in a transaction succeed, or none do.
- **Consistency** - a transaction moves the database from one valid state to another (constraints hold).
- **Isolation** - concurrent transactions do not see each other's partial work.
- **Durability** - once committed, data survives crashes.

## Database schema
A **schema** is the blueprint of the database: tables, columns, types, relationships and constraints. It is described with DDL (Data Definition Language, Module 10).

Levels of abstraction:
- **Physical level** - how data is stored on disk (files, pages, indexes).
- **Logical (conceptual) level** - tables, columns and relationships; what developers design.
- **View (external) level** - what particular users see, for example a view hiding salary columns.

This separation gives **data independence**: you can add an index (physical) without changing queries, or add a column (logical) without breaking existing views.

## Keys
Keys identify rows and connect tables.

| Key | Definition | Example in `employee` |
| --- | --- | --- |
| Super key | Any set of columns that uniquely identifies a row | `{emp_id, name}` |
| Candidate key | A minimal super key (no extra columns) | `emp_id`, `email` |
| Primary key | The candidate key chosen as the main identifier; unique and NOT NULL | `emp_id` |
| Alternate key | Candidate keys not chosen as primary | `email` |
| Composite key | A key made of two or more columns | `(student_id, course_id)` in enrollment |
| Foreign key | A column referencing another table's primary key | `dept_id` → `department.dept_id` |

A **surrogate key** is an artificial identifier (an auto-increment number or UUID); a **natural key** has business meaning (email, ISBN). Surrogate keys are usually preferred as primary keys because business values can change.

## ER diagrams
An **Entity-Relationship (ER) diagram** models the data before you create tables.
- **Entity** (rectangle): a thing you store data about - Student, Course.
- **Attribute** (oval): a property - name, email. Key attributes are underlined; multivalued attributes have double ovals; derived attributes (age from date of birth) have dashed ovals.
- **Relationship** (diamond): how entities relate - Student *enrolls in* Course.
- **Cardinality**: one-to-one (1:1), one-to-many (1:N), many-to-many (M:N).
- **Participation**: total (every entity must participate) or partial.

```
[Department] 1 ──< works in >── N [Employee]
[Student]    M ──< enrolls  >── N [Course]
```

### From ER to tables
- Each entity becomes a table; its key becomes the primary key.
- **1:N** - put a foreign key on the "many" side (`employee.dept_id`).
- **M:N** - create a **junction table** with both foreign keys (`enrollment(student_id, course_id, enrolled_on)`).
- **1:1** - put a unique foreign key on one side, or merge the tables.

## Database design
A good design process:
1. Collect requirements and business rules ("an employee belongs to exactly one department").
2. Identify entities, attributes and relationships; draw the ER diagram.
3. Convert the diagram to tables, keys and constraints.
4. Normalise (next section) to remove redundancy.
5. Add indexes for the queries you expect to run.
6. Review with sample data and edge cases.

Naming tips: use singular or plural consistently (`employee` or `employees`), `snake_case`, and an `id` or `<table>_id` primary key.

## Normalization
**Normalization** organises tables to reduce duplicated data and prevent **anomalies**:
- *Insert anomaly* - cannot add a department until it has an employee.
- *Update anomaly* - a department name stored in 500 rows must be changed 500 times.
- *Delete anomaly* - deleting the last employee also deletes the department's information.

Starting table:

| order_id | customer | customer_city | products |
| --- | --- | --- | --- |
| 1 | Asha | Pune | Pen, Book |
| 2 | Asha | Pune | Bag |

### First Normal Form (1NF)
Every column holds **atomic** values - no lists, no repeating groups. Split "Pen, Book" into separate rows (`order_item` table).

### Second Normal Form (2NF)
1NF, and every non-key column depends on the **whole** primary key (no partial dependency). In `order_item(order_id, product_id, product_name, qty)`, `product_name` depends only on `product_id` - move it to a `product` table.

### Third Normal Form (3NF)
2NF, and no non-key column depends on another non-key column (no **transitive** dependency). `customer_city` depends on `customer`, not on the order - move it to a `customer` table.

### BCNF
Boyce-Codd Normal Form tightens 3NF: for every functional dependency X → Y, X must be a super key.

Result:

```
customer(customer_id PK, name, city)
orders(order_id PK, customer_id FK, order_date)
product(product_id PK, name, price)
order_item(order_id FK, product_id FK, qty, PRIMARY KEY(order_id, product_id))
```

**Denormalization** deliberately adds redundancy for read performance (for example, storing an order total). Do it only with a measured reason and a plan to keep copies consistent.

## Common mistakes
- Storing comma-separated lists in a single column.
- Using a changeable natural value (email, phone) as the primary key.
- Modelling a many-to-many relationship without a junction table.
- Copying descriptive data (department name) into every row.

## Practice exercise
Design the database for a training portal:
1. Entities: Employee, Department, Course, Trainer, Enrollment.
2. Draw the ER diagram with cardinalities (an employee can enroll in many courses; a course has one trainer).
3. Convert it to tables with primary keys, foreign keys and a composite key for enrollment.
4. Take this flat table and normalise it to 3NF: `(emp_id, emp_name, dept_name, dept_head, course_code, course_title, score)`.

## Key takeaways
- A DBMS provides shared, consistent, concurrent and recoverable data access; RDBMSs guarantee ACID.
- Primary keys identify rows; foreign keys enforce relationships.
- ER diagrams capture entities, attributes and cardinalities before you write SQL.
- M:N relationships need a junction table.
- Normalise to 3NF to eliminate anomalies; denormalise only deliberately.
