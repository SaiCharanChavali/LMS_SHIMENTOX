## Streams of bytes and characters
Java I/O is built on two families of classes:

| Family | Unit | Base classes | Use for |
| --- | --- | --- | --- |
| Byte streams | 8-bit bytes | `InputStream`, `OutputStream` | Images, PDFs, ZIP files, any binary data |
| Character streams | 16-bit chars | `Reader`, `Writer` | Text files (CSV, logs, JSON) |

Character streams convert bytes to characters using an **encoding**. Always use a known encoding such as UTF-8 so a file reads the same on every operating system.

All of these classes hold operating-system resources, so open them in **try-with-resources** (Module 3) to guarantee they are closed.

## The File class
`java.io.File` represents a path - it does not open or read anything.

```java
File file = new File("reports/summary.txt");
System.out.println(file.getName());          // summary.txt
System.out.println(file.exists());           // true or false
System.out.println(file.isDirectory());      // false
System.out.println(file.length());           // size in bytes (0 if missing)

File dir = new File("reports");
if (!dir.exists()) dir.mkdirs();              // create folders
String[] children = dir.list();               // names inside the folder
boolean deleted = file.delete();
```

The newer `java.nio.file` API (`Path`, `Files`) is more capable and reports clear exceptions; you will see both in real code.

```java
Path path = Path.of("reports", "summary.txt");
Files.createDirectories(path.getParent());
Files.writeString(path, "Hello", StandardCharsets.UTF_8);
String text = Files.readString(path, StandardCharsets.UTF_8);
List<String> lines = Files.readAllLines(path);
```

## FileReader and FileWriter
`FileReader` and `FileWriter` read and write characters to a file.

```java
// Write (overwrites the file)
try (FileWriter writer = new FileWriter("notes.txt", StandardCharsets.UTF_8)) {
    writer.write("First line\n");
    writer.write("Second line\n");
}

// Append instead of overwrite: second argument true
try (FileWriter writer = new FileWriter("notes.txt", StandardCharsets.UTF_8, true)) {
    writer.write("Appended line\n");
}

// Read character by character
try (FileReader reader = new FileReader("notes.txt", StandardCharsets.UTF_8)) {
    int ch;
    while ((ch = reader.read()) != -1) {    // -1 means end of file
        System.out.print((char) ch);
    }
}
```

Reading one character at a time causes many small system calls. Wrap readers and writers in buffered versions.

## BufferedReader and BufferedWriter
Buffered classes read and write large chunks into memory, which is much faster, and add convenient methods: `readLine()` and `newLine()`.

```java
// Write a CSV report
try (BufferedWriter out = new BufferedWriter(new FileWriter("marks.csv", StandardCharsets.UTF_8))) {
    out.write("name,marks");
    out.newLine();
    out.write("Asha,88");
    out.newLine();
    out.write("Ravi,72");
    out.newLine();
}

// Read it line by line and compute the average
try (BufferedReader in = new BufferedReader(new FileReader("marks.csv", StandardCharsets.UTF_8))) {
    String header = in.readLine();            // skip header
    String line;
    int total = 0, count = 0;
    while ((line = in.readLine()) != null) {  // null means end of file
        String[] parts = line.split(",");
        total += Integer.parseInt(parts[1].trim());
        count++;
    }
    System.out.println("Average: " + (double) total / count);   // Average: 80.0
}
```

A shortcut with the NIO API: `Files.newBufferedReader(path)` and `Files.lines(path)` (a stream of lines - close it with try-with-resources).

## InputStream and OutputStream
For binary files use byte streams. `FileInputStream` / `FileOutputStream` access files; `BufferedInputStream` / `BufferedOutputStream` add buffering.

```java
// Copy any file (image, PDF, ...) using a buffer
try (InputStream in = new BufferedInputStream(new FileInputStream("logo.png"));
     OutputStream out = new BufferedOutputStream(new FileOutputStream("logo-copy.png"))) {
    byte[] buffer = new byte[8192];
    int bytesRead;
    while ((bytesRead = in.read(buffer)) != -1) {
        out.write(buffer, 0, bytesRead);      // write only the bytes actually read
    }
}
// Modern one-liner: in.transferTo(out);  or  Files.copy(source, target)
```

Other useful byte streams: `DataInputStream`/`DataOutputStream` (read/write primitives), `ObjectInputStream`/`ObjectOutputStream` (Java serialization - avoid for untrusted data), and `ByteArrayInputStream` for in-memory data. In a web application, file uploads arrive as an `InputStream` (Module 28).

## Bridging bytes and characters
`InputStreamReader` and `OutputStreamWriter` convert between the two families with an explicit charset. This is how you read text from a network socket or an uploaded file:

```java
try (BufferedReader reader = new BufferedReader(
        new InputStreamReader(uploadedStream, StandardCharsets.UTF_8))) {
    reader.lines().forEach(System.out::println);
}
```

## Safety and good practice
- Always close streams - use try-with-resources.
- Specify `StandardCharsets.UTF_8`; relying on the platform default causes garbled text across systems.
- Handle `FileNotFoundException`/`NoSuchFileException` and `IOException` with useful messages.
- Treat file paths from users as untrusted: normalise them and check they stay inside an allowed folder, otherwise `../../etc/passwd` style input can escape (path traversal).
- Write to a temporary file and then move it into place when a half-written file would be harmful.
- Do not load huge files fully into memory; stream them line by line.

## Common mistakes
- Forgetting to close a writer, so buffered data never reaches the disk.
- Using `FileWriter` without the append flag and accidentally overwriting a file.
- Writing `out.write(buffer)` instead of `out.write(buffer, 0, bytesRead)`, which copies stale bytes at the end.
- Reading binary files with a `Reader`, which corrupts them.

## Practice exercise
1. Write `ExpenseLog` that appends `date,category,amount` lines to `expenses.csv` using `BufferedWriter` in append mode.
2. Read the file with `BufferedReader` and print totals per category using a `Map<String, Double>`.
3. Skip and report malformed lines (wrong column count or non-numeric amount) with their line numbers.
4. Copy `expenses.csv` to `backup/expenses-<today>.csv` using byte streams and a buffer, creating the folder if needed.

## Key takeaways
- Byte streams handle binary data; character streams handle text with an encoding.
- `File`/`Path` describe locations; streams, readers and writers move data.
- Buffered classes are faster and provide `readLine`/`newLine`.
- Use try-with-resources and explicit UTF-8 every time.
- Validate user-supplied paths and stream large files instead of loading them whole.
