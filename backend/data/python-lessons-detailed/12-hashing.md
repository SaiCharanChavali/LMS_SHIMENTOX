## Map keys into buckets
A hash table uses a hash function to choose where a key might be stored. Taking a hash modulo bucket count produces a valid bucket index. Different keys can select the same bucket. This collision is an expected condition rather than an exceptional failure.

Separate chaining stores multiple key-value entries in each bucket. A lookup first selects the bucket, then compares original keys inside it. Equal hashes do not establish equal keys. Updating an existing key must replace its value rather than create contradictory duplicate records.

## Separate table lookup from bucket updates
The editor focuses on bucket_put(bucket, key, value). Its caller has already selected a bucket. Search the entries, replace the tuple when its key matches and otherwise append a new tuple. Distinct keys must coexist even in one bucket.

For a full table, create independent bucket lists with a comprehension. Writing [[]] * 5 repeats references to the same list. An insertion then appears in every bucket because they share one object. This is the aliasing issue from mutable sequences in another form.

## Worked example: deliberately colliding keys
```
def index_for(key, size):
    return sum(ord(char) for char in key) % size

def put(buckets, key, value):
    bucket = buckets[index_for(key, len(buckets))]
    for index, (stored_key, _) in enumerate(bucket):
        if stored_key == key:
            bucket[index] = (key, value)
            return
    bucket.append((key, value))

buckets = [[] for _ in range(5)]
put(buckets, "ab", 10)
put(buckets, "ba", 20)
put(buckets, "ab", 15)
print(index_for("ab", 5) == index_for("ba", 5))
print(buckets[index_for("ab", 5)])
```

Output is True followed by [('ab', 15), ('ba', 20)]. Both strings have the same character sum. Updating ab preserves ba and does not append a second ab entry.

## Performance and security boundaries
Expected near-constant lookup assumes a suitable hash distribution and controlled load factor: entries divided by buckets. A heavily populated bucket requires a linear scan. Resizing requires redistributing entries, not merely extending the outer list, because the modulo calculation changes.

This character-sum hash is educational. It is unsuitable for passwords, integrity checks or defending against adversarial keys. Use Python dict for ordinary application storage. Built-in hash values are not persistent business identifiers and can vary between processes for types such as strings.

## Coding workshop and acceptance checks
Implement bucket_put and test insertion, replacement and distinct colliding keys. Assert that replacement keeps the bucket length unchanged and preserves other entries. Do not compare hashes in place of keys.

Extend the full table with get and remove, using KeyError for missing keys. Test removal from the start and end of a chain. Explain why independent lists matter and what happens to lookup time when every key selects the same bucket.
