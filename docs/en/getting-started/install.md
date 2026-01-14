# Installation

This guide explains how to install FailCore.

---

## System Requirements

- Python 3.10 or higher
- pip package manager

---

## Basic Installation

### Install with pip

```bash
pip install failcore
```

This installs FailCore's core runtime.

---

## Optional Dependencies

### Proxy Mode (Recommended)

If you want to use FailCore as a proxy for LLM SDKs:

```bash
pip install "failcore[proxy]"
```

This installs:
- FastAPI (Web server)
- Uvicorn (ASGI server)

### LangChain Integration

If you use LangChain:

```bash
pip install "failcore[langchain]"
```

This installs:
- langchain-core (>=0.3.0, <2.0.0)

### Web UI

If you want to use the Web UI to view traces and reports:

```bash
pip install "failcore[ui]"
```

This installs:
- FastAPI and Uvicorn
- Jinja2 (template engine)

### MCP Support

If you use Model Context Protocol:

```bash
pip install "failcore[mcp]"
```

This installs:
- mcp (>=1.2.0)

### OpenTelemetry Integration

If you want to export telemetry data:

```bash
pip install "failcore[otel]"
```

This installs:
- OpenTelemetry API and SDK
- OTLP HTTP exporter

---

## Verify Installation

After installation, verify FailCore is correctly installed:

```bash
failcore --version
```

Or:

```bash
python -c "import failcore; print(failcore.__version__)"
```

You should see the version number (e.g., `0.1.3`).

---

## Development Installation

If you want to install from source or contribute:

```bash
# Clone repository
git clone https://github.com/your-org/failcore.git
cd failcore

# Install with dev dependencies
pip install -e ".[dev]"
```

Dev dependencies include:
- pytest (testing framework)
- build (build tools)
- twine (publishing tools)
- ruff (code linting)

---

## Common Issues

### Installation Fails

If installation fails, check:

1. **Python Version**
   ```bash
   python --version
   ```
   Ensure it's 3.10 or higher.

2. **pip Version**
   ```bash
   pip --version
   ```
   Use the latest version of pip.

3. **Network Connection**
   Ensure you can access PyPI.

### Dependency Conflicts

If you encounter dependency conflicts:

1. Use a virtual environment:
   ```bash
   python -m venv venv
   source venv/bin/activate  # Windows: venv\Scripts\activate
   pip install failcore
   ```

2. Check existing dependencies:
   ```bash
   pip list
   ```

### Windows-Specific Issues

On Windows, some features may require additional configuration:

- Path handling: FailCore automatically handles Windows path formats
- Permissions: Ensure sufficient filesystem permissions

---

## Next Steps

After installation:

- [First Run](first-run.md) - Run your first FailCore program
- [What Just Happened](what-just-happened.md) - Understand what happened

---

## Uninstall

To uninstall FailCore if needed:

```bash
pip uninstall failcore
```

Note: This will uninstall FailCore but will not delete generated trace files.
