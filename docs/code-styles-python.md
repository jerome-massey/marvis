# Copilot Instructions for Python Project

This project is a **\[brief description, e.g., "web API for user data", "data pipeline", "CLI tool"]** built with **\[main libraries/frameworks, e.g., "Flask", "Pandas", "Typer"]**, and may interact with **\[key services, e.g., "PostgreSQL", "AWS S3"]**.

## Coding Standards

### Naming

* `snake_case` for variables, functions, and modules.
* `PascalCase` for classes.
* `UPPER_CASE_WITH_UNDERSCORES` for constants.

### Style

* 4-space indentation (no tabs).
* Max line length: 88 characters.
* Double quotes for strings; use f-strings for interpolation.

### Functions & Methods

* Use `self` for instance methods, `cls` for class methods.
* Prefer explicit naming and clear purpose.

### Asynchronous Code

* Use `async`/`await` where appropriate (e.g., `asyncio`).

### Data Structures

* Use unpacking when useful (e.g., `a, b = x` or `**kwargs`).

### Imports

* Group: standard library, third-party, local. Separate with blank lines.
* Prefer absolute imports.

### Comments & Docstrings

* Use docstrings for all public modules, classes, and functions (Google or reStructuredText style).
* Keep comments concise and purposeful.

### Type Hints

* Use PEP 484 type hints in function signatures and key variables.

### Error Handling

* Catch specific exceptions (avoid bare `except:`).
