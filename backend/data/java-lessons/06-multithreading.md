## Why multithreading
A **thread** is an independent path of execution inside a program. Every Java program starts with the `main` thread. Additional threads let a server handle many requests at once, keep a UI responsive while work runs in the background, and use all CPU cores. The price is complexity: threads share memory, so unsynchronised access to shared data produces bugs that appear only occasionally.

## Creating threads: Thread and Runnable
### Extending Thread
```java
class Downloader extends Thread {
    @Override
    public void run() {
        System.out.println("Downloading on " + Thread.currentThread().getName());
    }
}
new Downloader().start();
```

### Implementing Runnable (preferred)
`Runnable` separates the *task* from the *thread*, and your class remains free to extend something else. Because `Runnable` has a single method, a lambda works.

```java
Runnable task = () -> System.out.println("Report on " + Thread.currentThread().getName());
Thread t = new Thread(task, "report-worker");
t.start();      // starts a new thread which calls run()
t.join();       // main waits for it to finish
```

Always call **`start()`**, not `run()`. Calling `run()` directly executes the code on the current thread - no new thread is created.

## Thread lifecycle
| State | Meaning |
| --- | --- |
| NEW | Created, `start()` not yet called |
| RUNNABLE | Running or ready to run when the scheduler picks it |
| BLOCKED | Waiting to acquire a monitor lock |
| WAITING | Waiting indefinitely (`wait()`, `join()`) |
| TIMED_WAITING | Waiting with a timeout (`sleep(ms)`, `wait(ms)`, `join(ms)`) |
| TERMINATED | `run()` finished or threw an exception |

Useful methods: `Thread.sleep(ms)` pauses the current thread, `join()` waits for another thread, `interrupt()` politely asks a thread to stop (the thread must check `isInterrupted()` or handle `InterruptedException`), and `setDaemon(true)` marks a background thread that does not keep the JVM alive.

## Synchronization
When two threads perform a read-modify-write on the same variable, updates can be lost (a **race condition**).

```java
class Counter {
    private int count = 0;
    public void increment() { count++; }   // NOT atomic: read, add, write
    public int get() { return count; }
}

Counter c = new Counter();
Thread a = new Thread(() -> { for (int i = 0; i < 10_000; i++) c.increment(); });
Thread b = new Thread(() -> { for (int i = 0; i < 10_000; i++) c.increment(); });
a.start(); b.start(); a.join(); b.join();
System.out.println(c.get());   // often less than 20000!
```

Fixes:

```java
public synchronized void increment() { count++; }     // one thread at a time per object

// or a synchronized block on a lock object
private final Object lock = new Object();
public void increment() { synchronized (lock) { count++; } }

// or an atomic class - lock-free and simplest for counters
private final AtomicInteger count = new AtomicInteger();
public void increment() { count.incrementAndGet(); }
```

`synchronized` guarantees **mutual exclusion** and **visibility** (changes made inside are seen by the next thread that takes the lock). The `volatile` keyword guarantees visibility only - fine for a stop flag, not for `count++`. For advanced needs use `ReentrantLock` from `java.util.concurrent.locks` (supports `tryLock` with timeouts).

## Inter-thread communication
Threads can coordinate with `wait()`, `notify()` and `notifyAll()`, which must be called while holding the object's lock. `wait()` releases the lock and sleeps until notified.

```java
class Mailbox {
    private String message;
    public synchronized void put(String m) throws InterruptedException {
        while (message != null) wait();      // always wait in a loop
        message = m;
        notifyAll();
    }
    public synchronized String take() throws InterruptedException {
        while (message == null) wait();
        String m = message;
        message = null;
        notifyAll();
        return m;
    }
}
```

In real code, prefer a **`BlockingQueue`**, which implements this producer-consumer pattern for you:

```java
BlockingQueue<String> queue = new LinkedBlockingQueue<>(10);
new Thread(() -> { try { queue.put("order-1"); } catch (InterruptedException e) { } }).start();
System.out.println(queue.take());   // blocks until an item arrives: order-1
```

## Deadlock
A **deadlock** happens when threads wait for each other forever. Thread 1 holds lock A and waits for B; thread 2 holds B and waits for A.

```java
// Thread 1: synchronized(accountA) { synchronized(accountB) { transfer } }
// Thread 2: synchronized(accountB) { synchronized(accountA) { transfer } }   -> deadlock risk
```

Prevention:
- **Always acquire locks in the same global order** (for example by account ID).
- Hold locks for as short a time as possible and never call unknown code while holding one.
- Use `tryLock(timeout)` so a thread can back off.
- Use higher-level concurrency utilities instead of nested locks.

## Executor framework and thread pools
Creating a new thread per task is expensive and unbounded. An **ExecutorService** manages a **thread pool** and a task queue.

```java
ExecutorService pool = Executors.newFixedThreadPool(4);
List<Future<Integer>> results = new ArrayList<>();
for (int i = 1; i <= 5; i++) {
    int n = i;
    results.add(pool.submit(() -> n * n));      // Callable returns a value
}
for (Future<Integer> f : results) {
    System.out.print(f.get() + " ");            // 1 4 9 16 25
}
pool.shutdown();                                 // stop accepting tasks
pool.awaitTermination(5, TimeUnit.SECONDS);
```

- `Runnable` returns nothing; `Callable<V>` returns a value and may throw a checked exception.
- `Future.get()` blocks until the result is ready; `get(timeout, unit)` avoids waiting forever.
- Pool types: `newFixedThreadPool(n)`, `newCachedThreadPool()`, `newSingleThreadExecutor()`, `newScheduledThreadPool(n)`, and since Java 21 `newVirtualThreadPerTaskExecutor()` for lightweight virtual threads.
- Always `shutdown()` a pool you create, or use try-with-resources on Java 19+.

## Concurrent collections
Ordinary collections are not thread-safe. Use the `java.util.concurrent` versions:

| Collection | Use |
| --- | --- |
| `ConcurrentHashMap` | Thread-safe map with atomic `merge`, `compute`, `putIfAbsent` |
| `CopyOnWriteArrayList` | Lists that are read often and written rarely (listeners) |
| `BlockingQueue` (`LinkedBlockingQueue`, `ArrayBlockingQueue`) | Producer-consumer pipelines |
| `ConcurrentLinkedQueue` | Non-blocking queue |

```java
ConcurrentHashMap<String, Integer> hits = new ConcurrentHashMap<>();
hits.merge("/home", 1, Integer::sum);   // atomic even with many threads
```

## CompletableFuture
`CompletableFuture` composes asynchronous steps without blocking, similar to JavaScript promises.

```java
CompletableFuture<String> user = CompletableFuture.supplyAsync(() -> "Asha");
CompletableFuture<Integer> orders = CompletableFuture.supplyAsync(() -> 3);

String summary = user
    .thenCombine(orders, (name, count) -> name + " has " + count + " orders")
    .exceptionally(ex -> "Could not load summary")
    .get();
System.out.println(summary);   // Asha has 3 orders
```

Key methods: `supplyAsync`/`runAsync` start work, `thenApply` transforms, `thenCompose` chains another async call, `thenCombine` joins two results, `allOf` waits for many, `exceptionally`/`handle` recover from errors, and `orTimeout` bounds waiting time.

## Common mistakes
- Calling `run()` instead of `start()`.
- Sharing a mutable `ArrayList` or `HashMap` across threads.
- Using `volatile` for compound operations like `count++`.
- Forgetting to shut down an executor, which keeps the JVM alive.
- Calling `wait()` outside a loop or outside `synchronized`.
- Testing concurrency by "it worked once" - races are timing-dependent.

## Practice exercise
1. Reproduce the lost-update counter bug with two threads, then fix it three ways: `synchronized`, `ReentrantLock` and `AtomicInteger`.
2. Build a producer-consumer pipeline with `BlockingQueue`: one thread reads order IDs, two worker threads "process" them.
3. Use a fixed thread pool to compute the sum of squares for 1..1000 in four chunks, collecting `Future` results.
4. Use `CompletableFuture` to load a user and their orders in parallel and combine the results, with a fallback on error.

## Key takeaways
- Prefer `Runnable`/`Callable` with an `ExecutorService` over raw threads.
- Shared mutable state needs synchronization, locks or atomic classes.
- Avoid deadlock by acquiring locks in a consistent order.
- Use concurrent collections and `BlockingQueue` for shared data.
- `CompletableFuture` composes asynchronous work with explicit error handling.
