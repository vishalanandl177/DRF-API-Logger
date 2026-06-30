# Contributing to DRF API Logger

Thanks for helping improve DRF API Logger. The package is used inside real Django REST Framework applications, so changes should preserve compatibility, protect sensitive data, and keep request-path overhead low.

## Development Setup

```bash
git clone https://github.com/vishalanandl177/DRF-API-Logger.git
cd DRF-API-Logger
python -m venv .venv
.venv\Scripts\activate  # Windows
# source .venv/bin/activate  # macOS/Linux
python -m pip install -r requirements-dev.txt
```

## Test Commands

Run the fast core tests first:

```bash
python test_runner_simple.py
```

Run the full Django test suite before opening a pull request:

```bash
python -m django test tests --settings=tests.test_settings --verbosity=1
```

Run the supported framework matrix when changing middleware, models, migrations, packaging, or release behavior:

```bash
tox
```

## Package Checks

Before release-oriented changes:

```bash
python -m build --sdist --wheel
python -m twine check dist/*
```

## Contribution Guidelines

- Add tests for behavior changes and bug fixes.
- Keep masking and privacy behavior conservative by default.
- Avoid synchronous database writes in request handling.
- Preserve existing settings, signal payloads, database schema, and admin behavior unless a breaking change is intentional and documented.
- Update README and `docs/` together when behavior, configuration, supported versions, or operational guidance changes.
- Keep generated artifacts such as `build/`, `dist/`, `.tox/`, coverage output, virtual environments, and profiling files out of commits.
