## Design around a usable contract
A duration report needs objects providing duration(); it does not need to know whether each represents audio, video or a live session. New implementations can join without adding branches to the report. This is polymorphism: the same operation invokes behavior supplied by different objects.

Duck typing means using the operations an object supports. It still requires a contract. All duration methods must agree on units and meaning. Mixing seconds with minutes produces plausible but incorrect totals. Document that each implementation returns nonnegative seconds.

## Inheritance and composition
Inheritance models a substitutable specialized kind of object. A subclass can reuse behavior and override selected methods. super() calls the next implementation in the method resolution order, supporting cooperative initialization. Avoid duplicating parent initialization in every child.

Composition puts a collaborator inside an object: a player can contain media rather than inherit from every format. Choose the design whose responsibilities and valid operations are clearest. A deeper inheritance hierarchy is not automatically better.

## Worked example: a polymorphic report
```
from abc import ABC, abstractmethod

class Media(ABC):
    @abstractmethod
    def duration(self):
        """Return duration in seconds."""
        raise NotImplementedError

class Clip(Media):
    def __init__(self, seconds):
        self.seconds = seconds

    def duration(self):
        return self.seconds

class LiveSession(Media):
    def duration(self):
        return 1800

def report_seconds(items):
    return sum(item.duration() for item in items)

print(report_seconds([Clip(120), LiveSession()]))
```

The output is 1920. Each object supplies its duration behavior without a type-specific branch. The abstract base class prevents instantiation of subclasses missing duration. It does not automatically validate units or results; this example assumes valid clip durations.

## Properties protect state through a stable interface
A property can expose salary while storing _salary. Its setter can reject negative amounts before assignment. Inside the setter, assign self._salary: assigning self.salary again recursively invokes the setter. An underscore marks an internal convention; it is not security or access control.

Properties are useful when attribute access needs validation. Avoid expensive network operations hidden in ordinary attribute reads. Callers should understand the likely cost and side effects of their operations.

## Coding workshop and design review
Implement total_duration by summing duration() results. Inputs may contain unrelated classes sharing that method. Do not filter by one concrete class or build an isinstance chain. Verify that an empty collection returns zero and a mixed collection includes every item.

Extend a salary tracker with a validating property and confirm a rejected update preserves the old salary. Create an incomplete Media subclass and explain the TypeError on construction. Distinguish rules enforced by the abstract interface from rules requiring implementation and tests.
