## Introduction to Gradle
A real Java project has hundreds of source files and dozens of libraries. Compiling with `javac` by hand does not scale. A **build tool** automates compiling, downloading dependencies, running tests, packaging JARs and publishing artifacts - the same way on every machine and on the CI server.

**Gradle** is a modern build tool used by Spring Boot, Android and many enterprise projects. Builds are written in a **Groovy** (`build.gradle`) or **Kotlin** (`build.gradle.kts`) DSL. Its main alternative is **Maven** (XML `pom.xml`); both use the same Maven Central repository.

| | Gradle | Maven |
| --- | --- | --- |
| Build script | Groovy/Kotlin DSL | XML |
| Flexibility | Very flexible, custom tasks are easy | Convention-driven, fixed lifecycle |
| Speed | Incremental builds, build cache, daemon | Generally slower on large builds |

## Installation and the Gradle Wrapper
Install Gradle (from gradle.org, SDKMAN `sdk install gradle`, or Homebrew), then check:

```bash
gradle --version
```

In practice you rarely use a global Gradle. Projects include the **Gradle Wrapper** - scripts that download and run the exact Gradle version the project expects:

```bash
gradle wrapper              # generate wrapper files once
./gradlew build             # macOS/Linux
gradlew.bat build           # Windows
```

Commit `gradlew`, `gradlew.bat` and the `gradle/wrapper/` folder so every developer and CI server uses the same version. Spring Initializr projects already include the wrapper.

Create a new project interactively with `gradle init` (choose application, Java, Groovy DSL, JUnit Jupiter).

### Standard project layout
```
my-app/
├── settings.gradle            # project name, included subprojects
├── build.gradle               # build logic for this project
├── gradlew, gradlew.bat, gradle/wrapper/
└── src/
    ├── main/java/             # application code
    ├── main/resources/        # config files (application.properties)
    ├── test/java/             # tests
    └── test/resources/
```

Build output goes to `build/` - add it to `.gitignore`.

## build.gradle explained
```groovy
plugins {
    id 'java'
    id 'application'
}

group = 'com.shimento'
version = '1.0.0'

java {
    toolchain {
        languageVersion = JavaLanguageVersion.of(21)   // Gradle provisions/uses JDK 21
    }
}

repositories {
    mavenCentral()                                     // where dependencies come from
}

dependencies {
    implementation 'com.google.guava:guava:33.2.1-jre'
    implementation 'com.mysql:mysql-connector-j:8.4.0'
    testImplementation 'org.junit.jupiter:junit-jupiter:5.10.3'
    testRuntimeOnly 'org.junit.platform:junit-platform-launcher'
}

application {
    mainClass = 'com.shimento.App'
}

test {
    useJUnitPlatform()                                 // run JUnit 5 tests
}
```

Reading it top to bottom: **plugins** add capabilities, `group`/`version` identify the artifact, the **toolchain** fixes the Java version, **repositories** say where to download libraries, **dependencies** list them, and the `application` and `test` blocks configure tasks. A misspelled block or property fails the build with an error naming the line - read Gradle's messages carefully.

## Dependencies
A dependency is written as `group:name:version` (its Maven coordinates). The **configuration** controls where it is visible:

| Configuration | Available at | Example |
| --- | --- | --- |
| `implementation` | Compile + runtime of main code | Spring Web, Guava |
| `api` (`java-library` plugin) | Like implementation, but exposed to consumers of your library | Shared model types |
| `compileOnly` | Compile time only | Lombok annotations |
| `runtimeOnly` | Runtime only | JDBC driver |
| `annotationProcessor` | Compile-time processing | Lombok, MapStruct |
| `testImplementation` | Test compile + runtime | JUnit, Mockito |
| `testRuntimeOnly` | Test runtime only | JUnit platform launcher |

Gradle also downloads **transitive dependencies** (dependencies of your dependencies). Inspect them with:

```bash
./gradlew dependencies --configuration runtimeClasspath
./gradlew dependencyInsight --dependency jackson-databind
```

A **BOM (bill of materials)** aligns versions of related libraries: `implementation platform('org.springframework.boot:spring-boot-dependencies:3.3.4')`. The Spring Boot plugin manages these versions for you, so you can omit them.

## Plugins
**Plugins** add tasks and conventions.

```groovy
plugins {
    id 'java'                                              // compile, test, jar tasks
    id 'org.springframework.boot' version '3.3.4'          // bootRun, bootJar
    id 'io.spring.dependency-management' version '1.1.6'   // version management
    id 'jacoco'                                            // test coverage reports
}
```

Core plugins (`java`, `application`, `java-library`, `jacoco`) need no version; community plugins come from the Gradle Plugin Portal and need one.

## Build lifecycle and tasks
Gradle runs a build in three phases:
1. **Initialization** - reads `settings.gradle` and decides which projects take part.
2. **Configuration** - evaluates every `build.gradle` and builds a graph of tasks.
3. **Execution** - runs the requested tasks and their dependencies in order.

Common tasks from the Java plugin:

```bash
./gradlew tasks           # list available tasks
./gradlew compileJava     # compile main code
./gradlew test            # run tests (report: build/reports/tests/test/index.html)
./gradlew jar             # package a JAR
./gradlew build           # compile + test + package (assemble + check)
./gradlew clean           # delete build/
./gradlew run             # run the application plugin's main class
./gradlew bootRun         # run a Spring Boot app
./gradlew build --scan    # detailed online build report
```

Tasks are **incremental**: if inputs have not changed, Gradle reports them as `UP-TO-DATE` and skips them. A custom task:

```groovy
tasks.register('hello') {
    group = 'custom'
    description = 'Prints a greeting'
    doLast { println "Building ${project.name} ${version}" }
}
```

## Build profiles
Gradle has no built-in "profiles" like Maven, but you can vary a build with **properties**:

```groovy
// build.gradle
def env = project.findProperty('env') ?: 'dev'

tasks.named('processResources') {
    filesMatching('application.properties') {
        expand(environment: env)
    }
}

if (env == 'prod') {
    tasks.named('test') { maxParallelForks = 4 }
}
```

```bash
./gradlew build -Penv=prod
```

Properties can also live in `gradle.properties` (project or user home). In Spring Boot, runtime environments are usually selected with **Spring profiles** (`spring.profiles.active=prod`, Module 28) rather than different builds - build one artifact and configure it per environment.

## Multi-project builds
Larger systems split code into modules that build together:

```
lms/
├── settings.gradle
├── build.gradle            # shared configuration
├── common/                 # shared DTOs and utilities
├── api/                    # Spring Boot REST service
└── worker/                 # background job service
```

```groovy
// settings.gradle
rootProject.name = 'lms'
include 'common', 'api', 'worker'

// build.gradle (root)
subprojects {
    apply plugin: 'java'
    repositories { mavenCentral() }
    java { toolchain { languageVersion = JavaLanguageVersion.of(21) } }
}

// api/build.gradle
dependencies {
    implementation project(':common')        // depend on another module
}
```

```bash
./gradlew :api:test       # run one subproject's task
./gradlew build           # build everything in dependency order
```

## Common mistakes
- Using a different local Gradle instead of the committed wrapper.
- Hard-coding dependency versions that conflict with the Spring Boot BOM.
- Using `implementation` for a JDBC driver needed only at runtime (works, but `runtimeOnly` is clearer).
- Forgetting `useJUnitPlatform()`, so JUnit 5 tests do not run.
- Committing the `build/` folder.

## Practice exercise
1. Run `gradle init` to create a Java application with JUnit 5.
2. Configure a Java 21 toolchain, add Guava and a JUnit test, and run `./gradlew build`.
3. Add a custom task `printVersion` and run it.
4. Inspect transitive dependencies of one library.
5. Convert the project to a multi-project build with `common` and `app` subprojects where `app` uses a class from `common`.

## Key takeaways
- Gradle automates compile, test, package and dependency management.
- Always use the committed wrapper (`./gradlew`).
- `build.gradle` declares plugins, repositories, dependencies and task configuration.
- Configurations (`implementation`, `runtimeOnly`, `testImplementation`) control dependency visibility.
- Builds run in initialization, configuration and execution phases; multi-project builds share configuration.
