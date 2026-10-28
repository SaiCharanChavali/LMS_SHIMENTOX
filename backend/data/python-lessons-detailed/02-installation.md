## Browser Python and local Python are different environments
The Shimento workshop already provides a Python interpreter in the browser. You can execute Python source there without installing a local interpreter. Local automation, files and application projects still need a local development environment. A script that works in the browser has not automatically been installed as a scheduled program on your computer.

An interpreter executes Python instructions. A terminal starts processes and passes arguments. An editor helps you write files. The interactive Python prompt evaluates Python statements, not arbitrary operating-system commands. Knowing which environment expects a command prevents a large class of avoidable setup errors.

## Check the interpreter you are actually using
On Windows, the py launcher can select an installed interpreter. On many macOS and Linux installations, python3 is the intended command. The names and available versions depend on your installation. Check the version from the same terminal you will use to run the project. Do not infer it from an IDE label or from a different shell session.

Use sys.version for interpreter-version information, sys.executable for the local executable path where applicable, and sys.implementation.name for the implementation name. In the browser, executable paths and the available filesystem differ from your local machine. The course's portable examples use standard language features; record the actual version when investigating a version-specific failure.

## Isolate dependencies with a virtual environment
A virtual environment gives a project its own package-installation context. It prevents unrelated projects from relying on accidental global package installations, but it is not a security sandbox. Code in a local virtual environment still runs with the permissions of the user who launched it.

Create the environment in the project directory. Activation modifies shell environment settings for convenience; it is not required when you invoke the environment's interpreter by its explicit path. Using python -m pip through the intended interpreter helps avoid installing into a different Python environment from the one running the script. Recreate environments from documented dependencies rather than committing the environment directory as project source.

## Local setup walkthrough
Run the following in a Windows terminal, not in the Python browser editor. The .venv directory is a project-specific convention.

```
py --version
py -m venv .venv
.venv\Scripts\python.exe -m pip --version
.venv\Scripts\python.exe greeting.py
```

Before the last command, create greeting.py containing print("Welcome to Shimento"). The expected script output is Welcome to Shimento. On macOS/Linux, the corresponding environment interpreter is commonly .venv/bin/python after creating the environment with python3 -m venv .venv. If a launcher command is unavailable, fix or select the installation rather than pasting terminal commands into a Python source file.

## Worked example for the browser workshop
This is Python source and can run in the browser. It does not launch or install a local environment.

```
import sys

def runtime_details():
    return {
        "implementation": sys.implementation.name,
        "major": sys.version_info.major,
    }

details = runtime_details()
print(details["implementation"])
print(details["major"])
```

In the packaged course runtime, the implementation name is cpython and the major version is 3. The exact minor version is an environment fact, not a value to assume when writing every program. The workshop asks for a simpler function returning the implementation name as a string.

## Guided practice and troubleshooting
- Complete interpreter_name in the browser and verify its returned type.
- Locally, run the greeting file through the environment's explicit interpreter path.
- Record the executable and pip context used by that local project.
- Distinguish command-not-found, a missing script path and a Python syntax error.

Your setup evidence should let another employee reproduce the commands without guessing your IDE configuration. Do not store credentials or machine-specific environment directories in the training repository.
