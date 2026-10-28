## Distinguish invalid syntax, invalid data and failed operations
A SyntaxError means Python could not parse the source as written. A ValueError from int("many") occurs while syntactically valid code executes. A missing file or unavailable dependency is another category. Understanding which boundary failed is more useful than adding one large catch-all handler around the whole program.

Read an exception traceback from the exception type and final message back to the relevant call path. A line number points to where a failure became visible, which may differ from where invalid data first entered the program. Preserve useful context when reporting or translating failures, but avoid logging secrets or unnecessary employee data.

## A narrow try block supports meaningful recovery
Put the operation that can fail inside try and catch the specific exception you can handle. Catching Exception indiscriminately can hide an unrelated NameError or a programming defect as if it were routine input validation. Do not use a bare except merely to keep printing success.

An else block executes when the try block finishes without an exception. A finally block executes for cleanup whether the operation succeeds or fails. For file objects, a with statement is normally clearer than manually closing in several branches. Do not put a return in finally simply to suppress every previous outcome; that can replace the result or failure the caller needed to observe.

## Conversion is not complete validation
The expression int("0") succeeds, but zero may be invalid for a number of participants. Separate syntax conversion from the business range check. Also document the accepted input types: int(None) raises TypeError rather than ValueError. A helper whose contract accepts strings can focus on invalid string syntax; a public boundary accepting arbitrary objects needs an explicit policy for other types.

None can be a documented “no valid result” marker, but it must not be confused with a valid count of zero if the domain allows zero. Another valid design raises a named validation exception. Choose one contract and keep callers consistent instead of returning strings, numbers and exceptions interchangeably without explanation.

## Worked example with explicit outcomes
```
def parse_positive(text):
    try:
        value = int(text)
    except ValueError:
        return None
    if value <= 0:
        return None
    return value

for sample in ["12", "0", "-2", "many"]:
    print(sample, parse_positive(sample))
```

The lines end in 12, None, None and None respectively. The helper assumes a string input. The conversion handles invalid numeric text, and a separate check handles values outside the positive range. No success is reported after a failed conversion.

## From simple input checks to a checksum validator
An ISBN-style exercise demonstrates layered validation. First check the required length and allowed characters. Then convert permitted symbols, calculate the weighted sum and evaluate the checksum rule. For ISBN-10, weights descend from 10 to 1 and X can represent 10 only in the last position. A checksum match does not excuse malformed input, and a plausible-looking string is not proof of a valid checksum.

## Guided practice and review
- Complete parse_count using the workshop's string-input contract and return None for invalid or nonpositive input.
- Test an accepted value, zero, a negative integer string, blank input and nonnumeric text.
- Extend a local caller to provide a useful message without mixing that message into the numeric helper's return type.
- For an additional lab, implement the layered ISBN-10 validation and distinguish format failures from checksum failures.

Explain exactly which exception is handled and which conditions are checked without exceptions. A correct solution preserves failures it cannot honestly recover from rather than hiding every defect behind a generic fallback.
