## Introduction to JavaScript
**JavaScript (JS)** is the programming language of the browser. HTML provides structure, CSS provides style, and JavaScript provides **behaviour**: reacting to clicks, validating forms, calling your Spring Boot API and updating the page. With Node.js it also runs on servers and powers tools such as Vite and npm.

Unlike Java, JavaScript is **dynamically typed** (types belong to values, not variables), interpreted/JIT-compiled in the browser, and single-threaded with an event loop (Module 19). Despite the name, it is unrelated to Java.

Add it to a page with `<script src="app.js" defer></script>` and experiment in the browser **DevTools Console** (F12).

```javascript
console.log("Hello, JavaScript!");
```

## Variables and data types
```javascript
let count = 0;            // can be reassigned, block-scoped
const PI = 3.14159;       // cannot be reassigned, block-scoped
var legacy = "avoid";     // function-scoped, hoisted - avoid in modern code
```

Use `const` by default and `let` when the value must change.

| Type | Example | Notes |
| --- | --- | --- |
| `number` | `42`, `3.14`, `NaN`, `Infinity` | One numeric type for integers and decimals |
| `bigint` | `9007199254740993n` | Arbitrarily large integers |
| `string` | `"text"`, `'text'`, backtick template literals | Immutable |
| `boolean` | `true`, `false` | |
| `undefined` | `let x;` | Declared but not assigned |
| `null` | `let y = null;` | Intentionally empty |
| `symbol` | `Symbol("id")` | Unique identifiers |
| `object` | `{}`, `[]`, functions, dates | Everything that is not a primitive |

```javascript
typeof 42;          // "number"
typeof "hi";        // "string"
typeof undefined;   // "undefined"
typeof null;        // "object"  (a historic quirk)
Array.isArray([]);  // true
```

`0.1 + 0.2` gives `0.30000000000000004` (floating point) - round money carefully or work in paise/cents.

## Operators
Arithmetic `+ - * / % **`, assignment `= += -=`, comparison `< > <= >=`, logical `&& || !`, and:

```javascript
5 == "5";     // true  - loose equality converts types
5 === "5";    // false - strict equality, no conversion
"5" + 1;      // "51"  - + concatenates when a string is involved
"5" - 1;      // 4     - other operators convert to number
null ?? "default";   // "default" - nullish coalescing (only null/undefined)
0 || "default";      // "default" - || treats 0, "", false, NaN as falsy
user?.address?.city; // optional chaining: undefined instead of an error
```

**Always use `===` and `!==`.** Falsy values are `false`, `0`, `""`, `null`, `undefined` and `NaN`; everything else is truthy.

## Conditionals and loops
```javascript
const score = 82;
if (score >= 90) console.log("A");
else if (score >= 75) console.log("B");
else console.log("C");

const label = score >= 50 ? "Pass" : "Fail";

switch (new Date().getDay()) {
  case 0:
  case 6: console.log("Weekend"); break;
  default: console.log("Weekday");
}

for (let i = 0; i < 3; i++) console.log(i);          // 0 1 2
const skills = ["Java", "SQL", "React"];
for (const skill of skills) console.log(skill);       // values of an iterable
const course = { title: "Java", hours: 40 };
for (const key in course) console.log(key, course[key]);   // keys of an object
let n = 3;
while (n > 0) n--;
```

## Functions
```javascript
// Declaration - hoisted
function add(a, b) {
  return a + b;
}

// Expression
const multiply = function (a, b) { return a * b; };

// Arrow function (Module 18)
const square = x => x * x;

// Default parameters
function greet(name = "learner") { return `Hello, ${name}`; }

console.log(add(2, 3), square(4), greet());   // 5 16 "Hello, learner"
```

Functions are **first-class values**: they can be stored in variables, passed as arguments and returned from other functions.

## Hoisting and scope
### Scope
- **Global scope** - declared outside any function or block.
- **Function scope** - `var` is visible throughout the function.
- **Block scope** - `let` and `const` are visible only inside `{ }`.

```javascript
if (true) {
  var a = 1;
  let b = 2;
}
console.log(a);   // 1
// console.log(b); // ReferenceError: b is not defined
```

Inner functions can read variables of outer functions (**lexical scope**) - the basis of closures in Module 18.

### Hoisting
Before running code, JavaScript registers declarations in their scope.
- Function declarations are hoisted with their body - callable before the line they appear on.
- `var` is hoisted and initialised to `undefined`.
- `let`/`const` are hoisted but **not initialised**; accessing them before the declaration throws a ReferenceError (the "temporal dead zone").

```javascript
sayHi();                 // works
function sayHi() { console.log("hi"); }

console.log(x);          // undefined
var x = 5;

// console.log(y);       // ReferenceError
let y = 5;
```

## Objects
```javascript
const employee = {
  name: "Asha",
  dept: "Engineering",
  skills: ["Java", "SQL"],
  greet() { return `Hi, I'm ${this.name}`; }
};

console.log(employee.name);          // dot notation
console.log(employee["dept"]);       // bracket notation
employee.salary = 90000;             // add a property
delete employee.dept;                // remove it
console.log("salary" in employee);   // true
console.log(Object.keys(employee));  // ["name", "skills", "greet", "salary"]
console.log(JSON.stringify({ a: 1 }));   // '{"a":1}'
```

Objects are passed by reference: assigning `const copy = employee` does not copy it. Use `{ ...employee }` for a shallow copy or `structuredClone(employee)` for a deep copy.

## Arrays
```javascript
const marks = [72, 88, 95, 60];
marks.push(81);                 // add at end
marks.pop();                    // remove from end
marks.unshift(50);              // add at start
marks.includes(88);             // true
marks.indexOf(95);              // 3

const passed = marks.filter(m => m >= 70);        // [72, 88, 95]
const curved = marks.map(m => m + 5);              // new array
const total = marks.reduce((sum, m) => sum + m, 0);
const top = [...marks].sort((a, b) => b - a)[0];  // copy, sort numerically desc
marks.forEach((m, i) => console.log(i, m));
const firstFail = marks.find(m => m < 60);         // 50
```

Default `sort()` compares strings - `[10, 9, 1].sort()` gives `[1, 10, 9]` - so always pass a comparator for numbers.

## Strings
```javascript
const title = "  Java Full Stack  ";
title.trim();                    // "Java Full Stack"
title.trim().toUpperCase();      // "JAVA FULL STACK"
"java,sql,react".split(",");      // ["java", "sql", "react"]
"Spring".includes("ring");       // true
"Spring".slice(0, 3);            // "Spr"
"a-b-c".replaceAll("-", "/");   // "a/b/c"
"5".padStart(3, "0");            // "005"
const name = "Ravi";
`Welcome, ${name}! You have ${2 + 3} courses.`;   // template literal
```

## Error handling
```javascript
function parseAge(text) {
  const age = Number(text);
  if (!Number.isInteger(age) || age < 0) {
    throw new Error(`Invalid age: ${text}`);
  }
  return age;
}

try {
  parseAge("abc");
} catch (err) {
  console.error(err.message);    // Invalid age: abc
} finally {
  console.log("done");
}

try { JSON.parse("{bad json}"); } catch (e) { console.log(e.name); }   // SyntaxError
```

Built-in error types include `Error`, `TypeError`, `ReferenceError`, `SyntaxError` and `RangeError`. Create your own by extending `Error`.

## Object-oriented JavaScript
JavaScript objects inherit through **prototypes**; the `class` syntax is a cleaner way to write the same thing.

```javascript
class Course {
  #enrolled = 0;                         // private field
  static count = 0;

  constructor(title, capacity) {
    this.title = title;
    this.capacity = capacity;
    Course.count++;
  }
  enroll() {
    if (this.#enrolled >= this.capacity) throw new Error("Course full");
    this.#enrolled++;
  }
  get seatsLeft() { return this.capacity - this.#enrolled; }
}

class PaidCourse extends Course {
  constructor(title, capacity, fee) {
    super(title, capacity);
    this.fee = fee;
  }
  toString() { return `${this.title} (₹${this.fee})`; }
}

const c = new PaidCourse("Spring Boot", 2, 7999);
c.enroll();
console.log(c.seatsLeft, String(c), Course.count);   // 1 "Spring Boot (₹7999)" 1
```

`this` depends on **how** a function is called; arrow functions do not have their own `this` (they use the surrounding one).

## Common mistakes
- Using `==` and getting surprising type conversions.
- Declaring with `var` and leaking variables out of blocks.
- Sorting numbers without a comparator.
- Mutating a shared object or array accidentally.
- Swallowing errors in an empty `catch`.

## Practice exercise
Create `grades.js` and run it with Node or the browser console:
1. Store students as an array of objects `{ name, marks: [] }`.
2. Write functions `average(marks)`, `grade(avg)` and `report(students)`.
3. Use `filter`, `map`, `reduce` and `sort` to print the class topper and the list of students below 50.
4. Throw an error for invalid marks (negative or above 100) and handle it with `try/catch`.
5. Convert the students into a `Student` class with a `get average()` getter.

## Key takeaways
- Prefer `const`, then `let`; avoid `var`.
- Use `===`; know which values are falsy.
- `let`/`const` are block-scoped; function declarations are hoisted.
- Arrays have powerful methods: `map`, `filter`, `reduce`, `find`, `sort` (with a comparator).
- Handle errors with `try/catch/finally` and model data with objects and classes.
