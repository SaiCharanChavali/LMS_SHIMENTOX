## Dictionaries give records named fields
A dictionary maps hashable keys to values. An employee profile might contain a name and a skills list, while a lookup table maps stable employee IDs to those profiles. Keys are unique: assigning another value under an existing key replaces its previous value. Values can be mutable, so sharing the same nested list between records can create unintended changes.

Use record[key] when the key is required and missing data should be an error. Use record.get(key, default) when absence is part of the contract. A default does not validate the type of a present value. For example, a present skills field containing an integer is not repaired by get. Validate shape and types before processing externally supplied records.

Iterating over items yields key/value pairs. Dictionary insertion order is preserved by modern Python, but that is not the same as alphabetic sorting. Choose an explicit sorted view when the report requires a consistent order independent of input construction.

## Sets represent membership and uniqueness
A set contains unique hashable values and supports union, intersection and difference. Use intersection to find shared skills, union to combine distinct skills and difference to find skills missing from a requirement. A set is not a display-order contract: convert to a deliberately sorted list when the consumer expects alphabetical output.

Converting every collection to a set loses duplicate information. That is correct when counting employees who have a skill once each, but incorrect when counting repeated events. State which business question is being answered before deduplicating.

## Validate types and understand a subtle numeric case
isinstance allows a value to satisfy a type or subtype relationship. In Python, bool is a subclass of int, so isinstance(True, int) is true. If an input contract requires an integer count but excludes booleans, enforce that distinction deliberately. Similarly, a nonempty list may still contain invalid elements; validating the outer container alone is not enough.

## Modules create reusable boundaries
A module groups definitions in a Python file. import math gives access through names such as math.sqrt; from math import sqrt brings a selected name into the current namespace. Avoid naming your own file math.py or another standard-library module name unintentionally, because import resolution may load your file instead of the expected library.

Keep reusable calculation helpers separate from interactive or file-reading entry points. A module that performs unexpected work immediately on import is harder to reuse and test. For a local command-line script, an if __name__ == "__main__" boundary can separate entry-point behavior from definitions.

## Worked example and expected result
```
profile = {"name": "Mira", "skills": ["Python", "SQL", "Python"]}
required = {"Python", "Git"}
available = set(profile["skills"])
print(sorted(available & required))
print(sorted(required - available))
print(profile.get("department", "Unassigned"))
```

The output is ['Python'], then ['Git'], then Unassigned. The original profile still contains its repeated Python entry; a separate set was constructed for a membership question. The fallback is used because department is absent, not because every profile field has been validated.

## Guided practice and acceptance criteria
- Complete shared_skills, returning a sorted list of shared values without duplicates.
- Test no shared skills, empty input, repeated tags and differently ordered input lists.
- Write a profile validator for a nonblank name and a list of nonblank skill strings.
- Put that validator in a local module and import it from a small entry-point file.

Explain which information each transformation preserves or discards. A correct report has a defined input contract, an intentional uniqueness rule and an explicit output order.
