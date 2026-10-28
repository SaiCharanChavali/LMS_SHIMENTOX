## Translate a budget into transactions
A ledger records transactions instead of repeatedly overwriting a balance. Deposits are positive integer-cent amounts and withdrawals are negative amounts. The balance is their sum. Keeping transactions explains how a balance arose, which a single balance field cannot do alone.

Here, 1250 means 12.50 currency units. Integer cents avoid binary floating-point surprises in decimal currency arithmetic. Real financial systems also require currency codes, rounding policies, durable storage and audit controls. This project focuses on arithmetic and valid state changes.

## Validate before changing the ledger
A withdrawal succeeds only when its amount is positive and the current balance covers it. Check both conditions before appending. A rejected request must leave the ledger unchanged. Returning False after modifying the list violates the contract even if later code repairs the balance.

Computing the balance from transactions avoids maintaining two values that can disagree. This is clear for a small ledger. A large system might cache balances, but must then keep the cache and transactions consistent.

## Worked example: a controlled budget category
```
class Budget:
    def __init__(self):
        self.ledger = []

    def deposit(self, cents):
        if type(cents) is not int or cents <= 0:
            raise ValueError("Deposit positive integer cents")
        self.ledger.append(cents)

    def balance(self):
        return sum(self.ledger)

    def withdraw(self, cents):
        if type(cents) is not int or cents <= 0:
            return False
        if cents > self.balance():
            return False
        self.ledger.append(-cents)
        return True

training = Budget()
training.deposit(5000)
print(training.withdraw(1250))
print(training.withdraw(4000))
print(training.ledger)
print(training.balance())
```

The output is True, False, [5000, -1250] and 3750 on separate lines. The second withdrawal cannot be covered and creates no transaction. The remaining amount represents 37.50 units; convert only for display.

## Transfers form a complete operation
A transfer withdraws from one category and deposits into another. Validate the amount and destination before starting. In a shared persistent application, both changes belong in one database transaction so a failure cannot debit one account without crediting the other. This classroom list does not provide that persistence guarantee.

Keep descriptions separate from numeric amounts if you extend transactions into dictionaries. Never calculate a balance by adding display strings such as "12.50 spent". Report success only after completing the operation.

## Coding workshop and acceptance checks
Implement withdraw(ledger, cents) using the supplied list contract. Return a boolean and append a negative amount only on success. Test exact balance, overdraw, zero, negative requests and an empty ledger. Save a copy before a rejected call and assert equality afterwards.

Extend the project with two categories and a transfer. Their combined balance must remain constant. Then attempt an invalid transfer and verify both ledgers remain unchanged. Explain why checking failure paths is as important as checking successful balances.
