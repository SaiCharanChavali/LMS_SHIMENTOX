## Build a coherent learning catalogue
The capstone supports employee upskilling: store profiles, summarize skills, search courses and process enrollment requests. Begin with input and output contracts. Choose structures from required operations rather than adding complexity merely to demonstrate terminology.

Separate validation, core logic and presentation. Validation decides whether records are acceptable. Core functions calculate from valid data. Presentation formats results. This separation makes tests clear and prevents display decisions from changing calculations.

## Count employees rather than repeated labels
The workshop receives records containing skills lists. Count an employee at most once per skill. Converting each employee's skills to a set removes duplicates within that employee. Do not deduplicate the whole dataset: that would discard contributions from other employees.

Python and python are distinct strings unless a boundary deliberately normalizes them. Keep the workshop's exact-input contract unchanged. Introduce a documented capitalization and whitespace policy in the larger project's validator.

## Worked example: aggregate a cohort
```
def skill_counts(records):
    counts = {}
    for record in records:
        for skill in set(record["skills"]):
            counts[skill] = counts.get(skill, 0) + 1
    return counts

employees = [
    {"name": "Mira", "skills": ["Python", "SQL", "Python"]},
    {"name": "Dev", "skills": ["Python", "Git"]},
]
counts = skill_counts(employees)
for skill in sorted(counts):
    print(skill, counts[skill])
print(skill_counts([]))
```

The output is Git 1, Python 2, SQL 1 and {} on separate lines. Mira contributes only one Python count. Sorting for presentation makes the report deterministic without depending on set iteration order.

## Connect structures to requirements
Use a dictionary keyed by employee ID for lookup, a set for per-profile skill deduplication and a deque for requests processed in arrival order. Binary search fits a maintained sorted title list; document how additions preserve sorting.

Use classes when state-changing operations need invariants, such as enrollment capacity. A graph can represent prerequisites; detect cycles if they would make completion impossible. Recursion and dynamic programming should address real needs rather than appear in every project.

## Deliverables and acceptance checks
Provide source, fictional sample records, run instructions and at least eight assertions. Cover empty input, duplicate skills, shared skills, missing fields, invalid field types, absent searches, queue order and rejected operations preserving state. The public validator should reject malformed records before calling core helpers.

Complete the browser's supplied skill_counts contract. Run the larger project locally in your selected environment. Include a design note explaining structures, complexity assumptions and limitations. Avoid real employee information in demonstrations.

## Review and completion
Review values, collections, exceptions, objects, algorithms, graphs and dynamic programming through project decisions. Explain why each approach fits its constraints and what its tests demonstrate.

Browser practice feedback supports learning; knowledge checks and secured assignments track assessment separately. Complete the final three-module assignment through the existing flow. Shimento records its own course completion and does not confer an external provider's certification.
