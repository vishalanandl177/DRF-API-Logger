# Developer Testing Guide

Use this guide when contributing to DRF API Logger.

## Setup

```bash
git clone https://github.com/vishalanandl177/DRF-API-Logger.git
cd DRF-API-Logger
python -m venv .venv
.venv\Scripts\activate  # Windows
# source .venv/bin/activate  # macOS/Linux
python -m pip install -r requirements-dev.txt
```

## Required Checks

```bash
python test_runner_simple.py
python -m django test tests --settings=tests.test_settings --verbosity=1
python -m django test tests.test_asgi_middleware --settings=tests.test_settings --verbosity=2
coverage run --source=drf_api_logger -m django test tests --settings=tests.test_settings --verbosity=1
coverage report
```

For ASGI release evidence against the demo project:

```powershell
$env:PYTHONPATH='J:\projects\DRF-API-Logger'
& 'J:\projects\drf-demo\venv\Scripts\python.exe' J:\projects\DRF-API-Logger\scripts\measure_asgi_overhead.py --settings config.settings --path /api/echo/ --requests 100 --concurrency 10
```

Run the dependency matrix for middleware, model, migration, packaging, or release changes:

```bash
tox
```

Build and validate package metadata before release-oriented changes:

```bash
python -m build --sdist --wheel
python -m twine check dist/*
```

## Test Matrix

The CI workflow tests representative supported combinations:

- Python 3.10, Django 4.2, DRF 3.16
- Python 3.11, Django 4.2, DRF 3.16
- Python 3.12, Django 5.2, DRF 3.16
- Python 3.13, Django 6.0, DRF 3.17

This matrix is representative coverage, not the complete Django 4.2+ support list.

## Areas To Cover

- Request/response middleware behavior.
- ASGI middleware behavior through direct async calls and Django `AsyncClient`.
- Sensitive data masking for bodies, headers, responses, and URL query parameters.
- Signal listener behavior and failure isolation.
- Background queue flushing, stats, shutdown, and database alias handling.
- Admin display, filters, export, and profiling diagnosis.
- Management commands such as `prune_api_logs`.
- Backward compatibility for defaults and signal/database payloads.

## Operational Checks

Use the retention command with dry-run first:

```bash
python manage.py prune_api_logs --days 30 --dry-run
python manage.py prune_api_logs --days 30 --batch-size 1000
```

Use worker stats in application health checks:

```python
from drf_api_logger.apps import LOGGER_THREAD

status = LOGGER_THREAD.get_status() if LOGGER_THREAD else {"enabled": False}
```
