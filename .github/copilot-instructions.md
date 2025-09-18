# copilot-instructions.md

## Coding Standards

### General Principles
- **Target Framework:** All projects use **Python 3.12** (or the version defined in the project). Ensure compatibility with this version.
- **Language:** Use Python for all code unless otherwise specified.
- **Readability:** Write clear, self-explanatory code. Use meaningful variable, function, class, and module names.
- **Consistency:** Follow consistent naming conventions (PEP 8/PEP 257) and code formatting throughout the solution.
- **Comments:** Add inline comments only where necessary to clarify complex logic; prefer self-explanatory code.
- **Docstrings:** Use docstrings for modules, classes, functions, and methods, following a consistent style (Google or NumPy).
- **Error Handling:** Use structured exception handling. Avoid swallowing exceptions; log or re-raise as appropriate. Create custom exceptions when useful.
- **Design Principles:** Follow SOLID-inspired principles adapted for Python (cohesion, low coupling, ABCs/protocols).
- **Dependency Injection:** Prefer constructor or parameter injection for dependencies.
- **Async/Await:** Use asynchronous programming patterns where appropriate, especially for I/O-bound operations. Do not block the event loop.
- **Magic Numbers:** Avoid magic numbers; use named constants or enums.
- **File Organization:** Prefer one concept per file/module. Organize files into appropriate folders by feature or layer.
- **Static Typing:** Use type hints and validate with mypy (or pyright).

### Naming Conventions
- **Packages & Modules:** snake_case (e.g., `user_service.py`)
- **Classes & Exceptions:** PascalCase (e.g., `UserService`, `UserNotFoundError`)
- **Functions & Methods:** snake_case (e.g., `get_user_by_id`)
- **Variables & Parameters:** snake_case (e.g., `user_id`)
- **Constants:** UPPER_CASE (e.g., `DEFAULT_TIMEOUT`)
- **Unit Test Functions:** Use descriptive names indicating the scenario and expected outcome (e.g., `test_get_user_by_id_returns_user_when_user_exists`)

### Code Style
- **Formatting:** Use Black for code formatting. Do not manually override its output.
- **Indentation:** Use 4 spaces per indentation level.
- **Line Length:** Limit lines to 120 characters.
- **Imports:** Group imports (stdlib, third-party, local) with blank lines between. Use isort. Avoid `import *`.
- **Strings:** Prefer f-strings. Declare UTF-8 encoding explicitly if necessary.
- **Comparisons:** Use `is`/`is not` for `None`. Avoid ambiguous truthiness checks.
- **Context Managers:** Use `with` for resources (files, connections).
- **Linting:** Use ruff (or flake8 with plugins). Resolve relevant warnings.

---

## Copilot Usage

- **Adhere to these standards** when generating or modifying Python code.
- **Prefer existing patterns** and conventions found in the solution.
- **Generate code that is ready to use** and fits seamlessly into the current structure, including type hints, docstrings, and tests when applicable.
- **Ensure style compatibility** with automated tools (Black, isort, ruff).
- **Document any deviations** from these standards in pull requests or code reviews.
- **For async code**, provide examples of async tests (`pytest.mark.asyncio`) and ensure non-blocking behavior.
- **For external I/O**, abstract logic behind interfaces/protocols (ABCs or typing.Protocol) for easier testing and mocking.


## Unit Test Standards

### General Principles
- **Test Framework:** Use **pytest** as the default test framework. Use `pytest-mock` or `unittest.mock` for mocking when appropriate.
- **Test Naming:** Use descriptive function names in the format: `function_name_state_under_test_expected_behavior`.
- **Test Structure:** Follow the Arrange-Act-Assert (AAA) pattern in all tests.
- **Isolation:** Each test must be independent and not rely on the outcome of other tests.
- **Mocking:** Use mocks or fakes for external dependencies (e.g., APIs, databases, file systems) to ensure tests are deterministic and reliable.
