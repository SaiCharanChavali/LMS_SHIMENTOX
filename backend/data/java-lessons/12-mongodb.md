## NoSQL basics
**NoSQL** ("not only SQL") databases store data in models other than relational tables. They became popular for flexible schemas, horizontal scaling and specific access patterns.

| NoSQL type | Data model | Examples | Good for |
| --- | --- | --- | --- |
| Document | JSON-like documents | MongoDB, Couchbase | Catalogues, profiles, content |
| Key-value | Key → value | Redis, DynamoDB | Caching, sessions |
| Column-family | Wide rows grouped in column families | Cassandra, HBase | Huge write volumes, time series |
| Graph | Nodes and edges | Neo4j | Social networks, recommendations |

**MongoDB** is the most popular document database. It stores data as **BSON** (binary JSON) documents inside **collections**, inside **databases**.

## SQL vs NoSQL

| | SQL (relational) | NoSQL (MongoDB) |
| --- | --- | --- |
| Structure | Tables with a fixed schema | Collections of flexible documents |
| Relationships | Joins and foreign keys | Embedding or references (`$lookup`) |
| Scaling | Usually vertical; sharding is harder | Built-in horizontal sharding |
| Transactions | Strong ACID across tables | Atomic per document; multi-document transactions available |
| Query language | SQL | MongoDB Query API (JSON-style) |
| Best for | Complex relationships, strict integrity (banking, orders) | Rapidly changing structure, nested data, high scale |

| Relational term | MongoDB term |
| --- | --- |
| Database | Database |
| Table | Collection |
| Row | Document |
| Column | Field |
| Primary key | `_id` field (auto-generated `ObjectId`) |
| Join | Embedding or `$lookup` |

Many systems use both: SQL for orders and payments, MongoDB for a product catalogue or activity feed.

## Installation
- Install **MongoDB Community Server** from the official site, or run `docker run -d --name mongo -p 27017:27017 mongo:7`.
- Install **mongosh**, the MongoDB shell, and optionally **MongoDB Compass**, the GUI.
- Cloud option: a free **MongoDB Atlas** cluster.

```bash
mongosh                               # connects to mongodb://localhost:27017
```

```javascript
show dbs
use training                          // switches (creates on first write)
db.getName()
```

## Collections and documents
A document is a set of field-value pairs, and values can be nested documents or arrays:

```javascript
{
  _id: ObjectId("..."),
  code: "JAVA101",
  title: "Java Basics",
  fee: 4999,
  tags: ["java", "beginner"],
  trainer: { name: "Kiran Rao", email: "kiran@corp.com" },
  modules: [ { no: 1, title: "Syntax" }, { no: 2, title: "OOP" } ],
  published: true
}
```

Collections are created automatically on first insert, or explicitly with validation rules - flexible does not mean "no rules":

```javascript
db.createCollection("courses", {
  validator: { $jsonSchema: {
    bsonType: "object",
    required: ["code", "title", "fee"],
    properties: {
      code:  { bsonType: "string" },
      fee:   { bsonType: ["int", "double", "decimal"], minimum: 0 }
    }
  }}
})
```

### Embedding vs referencing
- **Embed** data that is read together and bounded in size (a course's modules, an order's line items).
- **Reference** (store another document's `_id`) when data is shared, changes independently or can grow without limit (all enrollments of a popular course).

## CRUD operations
```javascript
// Create
db.courses.insertOne({ code: "JAVA101", title: "Java Basics", fee: 4999, tags: ["java"], published: true })
db.courses.insertMany([
  { code: "SPR201", title: "Spring Boot", fee: 7999, tags: ["java", "spring"], published: true },
  { code: "RCT101", title: "React", fee: 5999, tags: ["javascript"], published: false }
])

// Read
db.courses.find()                                          // all
db.courses.find({ published: true })                       // equality
db.courses.find({ fee: { $gt: 5000 } })                    // fee > 5000
db.courses.find({ tags: "java" })                          // array contains
db.courses.find({ $or: [{ fee: { $lt: 5000 } }, { tags: "spring" }] })
db.courses.find({}, { title: 1, fee: 1, _id: 0 })          // projection
db.courses.find().sort({ fee: -1 }).limit(2)               // top 2 by fee
db.courses.findOne({ code: "JAVA101" })
db.courses.countDocuments({ published: true })

// Update
db.courses.updateOne({ code: "RCT101" }, { $set: { published: true } })
db.courses.updateMany({ tags: "java" }, { $inc: { fee: 500 } })
db.courses.updateOne({ code: "JAVA101" }, { $push: { tags: "core" } })
db.courses.updateOne({ code: "NEW1" }, { $set: { title: "New" } }, { upsert: true })

// Delete
db.courses.deleteOne({ code: "NEW1" })
db.courses.deleteMany({ published: false })
```

Common operators: comparison `$eq $ne $gt $gte $lt $lte $in $nin`; logical `$and $or $not`; element `$exists $type`; update `$set $unset $inc $push $pull $addToSet`.

## Aggregation
The **aggregation pipeline** processes documents through stages, similar to Java streams or SQL `GROUP BY`.

```javascript
db.enrollments.aggregate([
  { $match: { status: "COMPLETED" } },                       // WHERE
  { $group: { _id: "$courseCode",                            // GROUP BY
              learners: { $sum: 1 },
              avgScore: { $avg: "$score" } } },
  { $sort: { learners: -1 } },                               // ORDER BY
  { $limit: 5 },                                             // LIMIT
  { $lookup: { from: "courses", localField: "_id",           // JOIN
               foreignField: "code", as: "course" } },
  { $project: { _id: 0, code: "$_id", learners: 1,
                avgScore: { $round: ["$avgScore", 1] },
                title: { $first: "$course.title" } } }
])
```

Other useful stages: `$unwind` (one document per array element), `$addFields`, `$count`, `$facet`, `$bucket`.

## Indexing
Without an index, MongoDB scans every document (a **COLLSCAN**).

```javascript
db.courses.createIndex({ code: 1 }, { unique: true })        // unique single-field
db.courses.createIndex({ published: 1, fee: -1 })            // compound
db.courses.createIndex({ title: "text" })                    // text search
db.sessions.createIndex({ createdAt: 1 }, { expireAfterSeconds: 3600 })  // TTL
db.courses.getIndexes()
db.courses.find({ published: true }).sort({ fee: -1 }).explain("executionStats")
```

Look for `IXSCAN` in the plan and compare `totalDocsExamined` to `nReturned`. Like SQL, compound indexes follow a prefix rule and every index costs write time and memory.

## Using MongoDB from Java
Spring Boot projects use **Spring Data MongoDB**: annotate a class with `@Document`, extend `MongoRepository<Course, String>`, and get CRUD methods plus derived queries such as `findByTagsContaining(String tag)`. Never build a filter from raw client JSON - accept specific, validated fields to avoid operator injection (for example a user sending `{"$ne": null}` as a password).

## Common mistakes
- Treating MongoDB as schemaless and storing inconsistent shapes.
- Embedding arrays that grow forever (16 MB document limit).
- Querying without indexes on large collections.
- Designing MongoDB collections like normalised SQL tables and then joining everything with `$lookup`.

## Practice exercise
1. Create a `training` database and a `courses` collection with schema validation.
2. Insert 8 courses with tags, an embedded trainer and embedded modules.
3. Query: published courses under 6000 sorted by fee; courses tagged "java"; titles only.
4. Add a `$push` of a new module and a `$inc` of fees for one tag.
5. Create an `enrollments` collection and write an aggregation for learners and average score per course.
6. Add indexes, run `explain("executionStats")` and confirm `IXSCAN`.

## Key takeaways
- NoSQL covers document, key-value, column-family and graph models.
- MongoDB stores BSON documents in collections; `_id` is the primary key.
- Embed bounded data read together; reference shared or unbounded data.
- Use `find`/`update`/`delete` operators for CRUD and pipelines for aggregation.
- Index according to your filters and sorts, and validate document shape.
