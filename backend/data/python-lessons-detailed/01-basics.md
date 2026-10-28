## Purpose and starting point
Python is useful for transforming employee records, validating imports and automating repeatable work. This course builds those skills through small functions whose behavior you can explain and test. Begin with the difference between writing a value, calculating a value and displaying a value; confusing these steps causes problems even in larger applications.

## Names, objects and common types
An assignment binds a name to an object. After score = 12, score refers to an integer value; assigning score = score + 3 evaluates the right-hand expression first and binds score to the new result. Assignment does not print anything. A later print(score) displays the current value.

Use int for whole-number counts, float for approximate fractional values, str for text and bool for a true/false decision. Quotation marks matter: 12 is a number, while "12" is text. Adding two numeric values performs arithmetic; adding two strings concatenates them. Do not assume that data received as text has already been validated or converted into the type the calculation needs.

None represents an explicit absence of a value. It is different from zero, an empty string and False. A function with no explicit return returns None, which is one reason printing inside a function does not substitute for returning a result.

## Expressions, division and presentation
Python follows operator precedence, so multiplication and division are evaluated before addition unless parentheses change the grouping. The / operator performs true division; // performs floor division, and % gives a remainder. Floor division rounds toward negative infinity, so it is not simply truncation toward zero for negative inputs.

Floating-point values approximate many decimal fractions. Keep the numeric result separate from presentation and format it at the display boundary. An f-string evaluates expressions inside braces, and a format such as :.2f displays two decimal places. Formatting does not change the stored result into an exact monetary representation. Business rules involving exact amounts need a deliberately chosen representation, such as integer minor units or Decimal with a defined rounding policy.

## Conditions, indentation and reusable functions
An if statement selects a branch based on a condition. Use == for an equality comparison and = for assignment. Combine conditions with and/or; parentheses can make a business rule easier to read. Indentation defines the statements belonging to a branch, loop or function, so consistent whitespace is part of the program's structure.

Define a function with def and give its parameters meaningful names. The caller supplies arguments; return sends the result back. Keep calculations independent of console output so the same function can serve a script, test or UI. Validate a precondition before performing the operation that depends on it.

## Worked example and trace
Run this complete example in the browser editor or a local Python file.

```
def price_after_discount(price, percent):
    if not 0 <= percent <= 100:
        raise ValueError("Percentage must be between 0 and 100")
    return price * (1 - percent / 100)

amount = price_after_discount(120, 15)
print(f"Amount due: {amount:.2f}")
```

The output is Amount due: 102.00. The condition accepts 15, division produces 0.15, and the remaining fraction is 0.85. Multiplying by 120 produces the numeric result, which the caller formats. Passing 150 as the percentage raises the validation exception before a price is returned. This teaching helper assumes an otherwise valid numeric price; a real input boundary must define and enforce the full contract.

## Guided browser practice
- Complete discounted_price in the workshop below using the same separation between calculation and printing.
- Predict the results for a zero discount and a full discount before running the checks.
- Experiment with print(2 + 3) and print("2 + 3") and explain the different outputs.
- Change only indentation in a small if example and observe why a line's block membership matters.

## Acceptance criteria and common mistakes
Return the calculated number; do not return the result of print, which is None. Show why a percentage of 25 means a remaining fraction of 0.75. Keep expected output separate from source code when copying examples. A successful submission passes the visible checks and includes an explanation of the boundary cases rather than only a screenshot of one result.
