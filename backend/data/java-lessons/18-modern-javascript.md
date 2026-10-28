## ES6 and beyond
**ECMAScript** is the specification behind JavaScript. **ES6 (ES2015)** was a huge update, and yearly releases have added more since. Modern React and Node code uses these features everywhere, so you must read them fluently.

| Feature | Version |
| --- | --- |
| `let`/`const`, arrow functions, template literals, destructuring, spread/rest, default parameters, classes, modules, promises | ES2015 |
| `async`/`await` | ES2017 |
| Object spread/rest | ES2018 |
| Optional chaining `?.`, nullish coalescing `??` | ES2020 |
| `Array.prototype.at`, `Object.hasOwn`, top-level `await` in modules | ES2022 |

## let and const
`let` and `const` replace `var` with **block scope** and no use-before-declaration.

```javascript
for (let i = 0; i < 3; i++) {
  setTimeout(() => console.log(i), 0);   // 0 1 2 - each iteration has its own i
}
// with var the same loop prints 3 3 3

const config = { theme: "dark" };
config.theme = "light";     // allowed - the object is mutable
// config = {};             // TypeError - the binding is constant
const frozen = Object.freeze({ theme: "dark" });   // shallowly immutable
```

`const` means the **variable** cannot be reassigned, not that the value is immutable.

## Template literals
Backtick strings support interpolation and multiple lines.

```javascript
const user = { name: "Asha", courses: 3 };
const msg = `Hello ${user.name}, you have ${user.courses} course${user.courses === 1 ? "" : "s"}.`;
const html = `
  <li class="course">
    ${user.name}
  </li>`;
```

Be careful: inserting user data into HTML strings and assigning to `innerHTML` can cause XSS. Escape the data or use `textContent` (Module 20) - React escapes automatically.

## Arrow functions
```javascript
const add = (a, b) => a + b;              // implicit return
const square = x => x * x;                // one parameter - no parentheses needed
const makeUser = (name) => ({ name });    // wrap an object literal in parentheses
const log = () => { console.log("hi"); }; // block body needs explicit return
```

Differences from regular functions:
- No own `this` - they use `this` from the surrounding scope (great for callbacks inside classes).
- No `arguments` object; use rest parameters instead.
- Cannot be used as constructors with `new`.
- Not suitable as object methods that rely on `this`.

```javascript
class Timer {
  seconds = 0;
  start() {
    setInterval(() => this.seconds++, 1000);   // arrow keeps the Timer's this
  }
}
```

## Destructuring
Extract values from arrays and objects into variables.

```javascript
// Arrays - by position
const [first, second, ...others] = ["Java", "SQL", "React", "Docker"];
console.log(first, others);          // "Java" ["React", "Docker"]
let a = 1, b = 2;
[a, b] = [b, a];                     // swap

// Objects - by property name
const course = { title: "Spring Boot", fee: 7999, trainer: { name: "Kiran" } };
const { title, fee: price, level = "beginner", trainer: { name: trainerName } } = course;
console.log(title, price, level, trainerName);   // "Spring Boot" 7999 "beginner" "Kiran"

// In function parameters - very common in React props
function CourseCard({ title, fee = 0 }) {
  return `${title}: ₹${fee}`;
}
CourseCard(course);   // "Spring Boot: ₹7999"
```

## Spread operator, rest parameters and default parameters
### Spread `...` expands an iterable or object
```javascript
const base = [1, 2];
const more = [...base, 3, 4];                    // [1, 2, 3, 4]
const copy = [...base];                          // shallow copy
Math.max(...more);                               // 4

const user = { name: "Asha", role: "learner" };
const updated = { ...user, role: "trainer" };    // copy and override - immutable update
```

### Rest `...` collects remaining items
```javascript
function total(...amounts) {                       // any number of arguments
  return amounts.reduce((s, x) => s + x, 0);
}
total(100, 250, 50);                               // 400

const { password, ...safeUser } = { id: 1, name: "Asha", password: "x" };
// safeUser = { id: 1, name: "Asha" }
```

Same syntax, opposite jobs: **spread** in calls and literals, **rest** in parameters and destructuring patterns.

### Default parameters
```javascript
function paginate(items, page = 1, size = 10) {
  return items.slice((page - 1) * size, page * size);
}
paginate([...Array(25).keys()], 3);   // [20, 21, 22, 23, 24]
```

Defaults apply when the argument is `undefined` (not when it is `null`).

## Modules
**ES modules** split code into files with explicit imports and exports.

```javascript
// mathUtils.js
export const TAX = 0.18;
export function withTax(amount) { return amount * (1 + TAX); }
export default function formatINR(n) { return `₹${n.toFixed(2)}`; }

// app.js
import formatINR, { withTax, TAX as GST } from "./mathUtils.js";
import * as utils from "./mathUtils.js";
console.log(formatINR(withTax(1000)));   // ₹1180.00
```

- A file can have many **named** exports and at most one **default** export.
- In the browser, load with `<script type="module" src="app.js">`.
- Modules are strict by default and have their own scope - no accidental globals.
- Dynamic `import("./chart.js")` loads code on demand (used for code splitting in Module 22).

## Closures
A **closure** is a function that remembers the variables of the scope where it was created, even after that scope has finished.

```javascript
function createCounter() {
  let count = 0;                    // private to this closure
  return {
    increment: () => ++count,
    current: () => count
  };
}
const counter = createCounter();
counter.increment();
counter.increment();
console.log(counter.current());     // 2
// count is not accessible directly - data privacy
```

Closures power private state, function factories (`const add5 = makeAdder(5)`), event handlers and React hooks.

## Higher-order functions and callbacks
A **higher-order function** takes a function as an argument or returns one. A **callback** is the function passed in.

```javascript
// Takes a function
const prices = [100, 250, 400];
const discounted = prices.map(p => p * 0.9);

// Returns a function
function makeDiscount(percent) {
  return price => price * (1 - percent / 100);
}
const festive = makeDiscount(20);
festive(500);                         // 400

// Callback
function fetchCourses(onSuccess) {
  setTimeout(() => onSuccess(["Java", "React"]), 500);
}
fetchCourses(list => console.log("Loaded", list));

// Composing functions
const compose = (...fns) => x => fns.reduceRight((v, f) => f(v), x);
const slugify = compose(s => s.replaceAll(" ", "-"), s => s.toLowerCase(), s => s.trim());
slugify("  Java Full Stack ");        // "java-full-stack"
```

Deeply nested callbacks ("callback hell") are hard to read and handle errors poorly - promises and `async/await` (Module 19) fix this.

## Common mistakes
- Thinking `const` objects cannot be changed.
- Using an arrow function as an object method that needs `this`.
- Forgetting parentheses when an arrow function returns an object literal.
- Confusing spread and rest.
- Mixing default and named imports incorrectly (`import { formatINR }` when it is a default export).

## Practice exercise
Refactor a shopping-cart script using modern JavaScript:
1. Split it into `cart.js` (named exports `addItem`, `removeItem`, `total`) and `format.js` (default export `formatINR`).
2. Represent the cart as an array of `{ id, name, price, qty }` and update it immutably with spread.
3. Use destructuring in every function parameter.
4. Write `createDiscount(percent)` that returns a function (closure), and apply it with `map`.
5. Write `sum(...numbers)` with rest parameters and a `paginate` function with default parameters.

## Key takeaways
- `let`/`const` are block-scoped; `const` prevents reassignment, not mutation.
- Template literals interpolate; arrow functions are concise and inherit `this`.
- Destructuring, spread and rest make data handling short and immutable-friendly.
- ES modules give each file its own scope with explicit imports and exports.
- Closures and higher-order functions are the foundation of functional JavaScript and React.
