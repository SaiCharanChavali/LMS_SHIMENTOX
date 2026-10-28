## Project brief and scope
Create a small configuration manager for harmless training preferences such as theme or page size. It supports adding, updating, deleting and displaying settings. The important lesson is a predictable API over shared mutable state, not merely making several dictionary operations print messages. Do not use classroom sample code to store real credentials.

Write the operation contracts before implementation. Add succeeds only when a normalized key is absent. Update succeeds only when it exists. Delete removes an existing key without creating a new one. Display returns a stable representation. Decide how empty keys and invalid values are rejected, then apply the same policy at every operation boundary.

## Normalization is part of identity
If Theme, theme and surrounding-whitespace variants represent the same setting, normalize before both membership checks and writes. Otherwise one function can look up a different key from another function. For this exercise, strip surrounding whitespace and lowercase the key. This is a narrow classroom policy; arbitrary user-facing identifiers may require a different internationalization and case policy.

Normalization does not validate the remaining content. A string of spaces becomes an empty key, which still needs a decision. Likewise, receiving a non-string key should not accidentally produce a confusing attribute error if the public API is intended to reject that input explicitly.

## Mutations and return values serve different roles
The settings dictionary is a shared object passed to a helper. Mutating it changes the caller's dictionary. Returning True or False describes the result without requiring every caller to parse a console message. Keep user-facing wording in the presentation layer so another script or test can reuse the same operation.

A failed operation should leave the dictionary unchanged. Check preconditions before writing. This principle matters later in transactions and service APIs too: failure must not quietly apply half of a requested change. Returning a success flag is useful only when it accurately reflects the resulting state.

## Worked example: add without replacing
```
def add_setting(settings, key, value):
    normalized = key.strip().lower()
    if not normalized:
        raise ValueError("A setting key is required")
    if normalized in settings:
        return False
    settings[normalized] = value
    return True

preferences = {}
print(add_setting(preferences, " Theme ", "dark"))
print(add_setting(preferences, "theme", "light"))
print(preferences)
```

The output is True, False and {'theme': 'dark'}. The second call recognizes the normalized existing key and does not overwrite it. The example assumes a string key; extend the input validation deliberately if the function is exposed to less controlled callers.

## Guided browser practice
The workshop asks you to implement update_setting, which differs from add_setting: a missing key must not be inserted. Normalize the key, check presence and only then update its value. Verify the returned flag and the actual dictionary after both success and failure. A function that always returns True without checking state does not satisfy the contract.

## Local extension and acceptance criteria
- Implement delete_setting with a documented missing-key result.
- Return a title-sorted or key-sorted display without relying on the order settings happened to be inserted.
- Test empty settings, an existing key, a missing key, whitespace normalization and a rejected empty key.
- Verify failed updates and deletions preserve every other setting.
- Keep calculation/mutation helpers separate from a command-line menu or browser messages.

Prepare a short operation table listing preconditions, resulting state and returned value. Another employee should be able to use the manager without guessing whether an update silently creates new preferences or whether a failed call has already changed data.
