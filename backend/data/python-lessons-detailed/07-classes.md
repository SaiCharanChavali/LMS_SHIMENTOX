## Model state and behavior together
A class defines a kind of object. An instance holds the state of one particular object. Two inventory records share operations such as receiving stock, but their quantities must remain independent. Use a class when operations and the rules protecting state belong together; dictionaries remain useful for passive records.

Calling a class invokes __init__ to initialize the new instance. The parameter self refers to that instance. Python supplies self when you call item.receive(3), so the caller passes only the amount. Assigning self.quantity creates instance state. A mutable class attribute, such as a shared transaction list, can accidentally connect unrelated instances.

## Establish and preserve valid state
A constructor should reject invalid starting values rather than create an object that later methods must repair. __init__ initializes an instance; it must not return a replacement object. Methods should preserve the same rules after construction. Define units, accepted types and failure behavior before implementation.

## Worked example: independent inventory records
```
class StockItem:
    def __init__(self, name, quantity=0):
        if type(quantity) is not int or quantity < 0:
            raise ValueError("Use a nonnegative integer")
        self.name = name
        self.quantity = quantity

    def receive(self, amount):
        if type(amount) is not int or amount <= 0:
            raise ValueError("Receive a positive integer")
        self.quantity += amount
        return self.quantity

first = StockItem("Keyboard", 2)
second = StockItem("Mouse")
print(first.receive(3))
print(second.quantity)
```

The output is 5 followed by 0. Both instances use the same method definition, but self identifies a different object on each call. Returning the quantity supports reuse without forcing the method to print. The type check deliberately rejects booleans, which otherwise qualify as integers in isinstance checks.

## References are not independent copies
Assigning another = first creates another reference to the same object. Updating another also affects the object observed through first. Constructing another StockItem creates separate state. Draw the names and objects when debugging unexpected updates in collections of instances.

Class attributes suit shared constants or deliberately shared information. Instance attributes suit per-record state. Putting an instance's mutable list on the class merely to avoid a constructor can cause every instance to append to the same list.

## Coding workshop and acceptance checks
Complete Counter in the editor. Its constructor starts self.value at zero and increment adds one. Construct two counters, increment the first twice and the second once, and verify values of two and one. A third new counter must still start at zero.

Explain why a local variable named value does not update self.value. Keep required public names unchanged so checks can call your implementation. As an extension, add reset and document whether it returns a value or simply changes state. Test its effect on one instance while observing another.
