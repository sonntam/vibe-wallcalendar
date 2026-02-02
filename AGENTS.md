# AGENTS.md

This file provides context and instructions for AI agents (and human developers) working on the **Vibe Wall Calendar** repository.

## 1. Project Overview
This project is a lightweight, self-hosted wall calendar designed for older hardware (specifically Android 4.4/Firefox 64).
*   **Architecture**: Server-Side Rendered (SSR) with Python/Flask.
*   **Key Constraint**: The frontend must remain extremely lightweight (no modern JS frameworks) and compatible with older browser engines.
*   **Backend**: Python 3.11 + Flask + CalDAV.
*   **Deployment**: Docker Compose.

## 2. Environment & Commands

### Docker (Primary)
The project is designed to run in Docker.
*   **Build & Run**: `docker-compose up -d --build`
*   **Logs**: `docker-compose logs -f`
*   **Stop**: `docker-compose down`

### Local Development (Python)
If working outside Docker, ensure Python 3.11+ is installed.

1.  **Setup Virtual Environment**:
    ```bash
    python -m venv venv
    # Windows:
    .\venv\Scripts\activate
    # Linux/Mac:
    source venv/bin/activate
    pip install -r app/requirements.txt
    ```

2.  **Running the App**:
    ```bash
    export FLASK_APP=app/main.py
    flask run --debug
    ```

### Testing
*Currently, no test suite is implemented.*
*   **Agent Instruction**: When adding significant logic, **create unit tests** using `pytest`.
*   **Future Command**: `pytest`
*   **Running a Single Test**: `pytest tests/test_file.py::test_function_name`

### Linting & Formatting
Follow standard Python community guidelines.
*   **Linter**: `flake8`
*   **Formatter**: `black`
*   **Command**:
    ```bash
    pip install flake8 black
    flake8 app/
    black app/
    ```

## 3. Code Style Guidelines

### Python (Backend)
*   **Style**: Adhere to **PEP 8**.
*   **Formatting**: Use `black` with default settings (88 char line length).
*   **Imports**:
    1.  Standard Library (`os`, `datetime`, `logging`)
    2.  Third-Party (`flask`, `caldav`, `dateutil`)
    3.  Local Imports
*   **Type Hinting**: Encouraged for new function signatures (e.g., `def get_data() -> dict:`).
*   **Docstrings**: Required for all complex functions. Explain *arguments*, *return values*, and *exceptions*.
*   **Error Handling**:
    *   Use specific `try...except` blocks (avoid bare `except:`).
    *   Log errors using the configured `logger`.
    *   Fail gracefully (e.g., return cached data or an empty list) rather than crashing the page.

### HTML/CSS (Frontend)
*   **Compatibility**: **CRITICAL**. Must work on Firefox 64.
*   **CSS**: Use standard CSS3 Flexbox. Avoid Grid if possible (partial support in older browsers).
*   **JavaScript**: Minimal to none. Use `<meta http-equiv="refresh">` for auto-updates.
*   **Structure**: Keep the DOM shallow.
*   **Resolution**: Optimized for **1280x800**.

## 4. Architecture & conventions

*   **Caching**: The application uses a simple in-memory cache (`CACHE` dict in `main.py`) to prevent rate-limiting from iCloud. Respect this pattern.
*   **Timezones**: Timezones are critical. Always use `dateutil.tz` or timezone-aware datetime objects. The application defaults to `Europe/Berlin`.
*   **Secrets**: NEVER commit credentials. Use `os.environ` to access secrets (`ICLOUD_PASSWORD`, etc.).

## 5. Agent Operational Rules

1.  **Safety First**: When editing `main.py`, ensure the fallback mechanisms (e.g., serving stale cache on error) remain intact.
2.  **Verify Compatibility**: If adding CSS features, verify they were supported in 2018 (Firefox 64 era).
3.  **Dependencies**: If you import a new package, immediately add it to `app/requirements.txt`.
4.  **No "Fixes" without understanding**: Do not refactor the "old-school" frontend code into a React/Vue app. The legacy nature is a requirement.
5.  **Testing**: Since there are no current tests, if you break something, you might not know. Create a reproduction script or a small unit test before making complex changes.
