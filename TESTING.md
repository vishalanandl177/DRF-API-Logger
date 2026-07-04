# Testing Guide for DRF API Logger

This guide covers package development and user integration checks for DRF API Logger.

## Supported Test Matrix

The release workflow tests representative combinations:

- Python 3.10 with Django 4.2 and DRF 3.16
- Python 3.11 with Django 4.2 and DRF 3.16
- Python 3.12 with Django 5.2 and DRF 3.16
- Python 3.13 with Django 6.0 and DRF 3.17

Package metadata requires Python 3.10+, Django 4.2+, and Django REST Framework 3.16+.
The matrix is representative coverage, not the complete Django 4.2+ support list.

## Development Setup

```bash
git clone https://github.com/vishalanandl177/DRF-API-Logger.git
cd DRF-API-Logger
python -m venv .venv
.venv\Scripts\activate  # Windows
# source .venv/bin/activate  # macOS/Linux
python -m pip install -r requirements-dev.txt
```

## Core Commands

```bash
# Fast core smoke tests
python test_runner_simple.py

# Full Django test suite
python -m django test tests --settings=tests.test_settings --verbosity=1

# Coverage
coverage run --source=drf_api_logger -m django test tests --settings=tests.test_settings --verbosity=1
coverage report

# Supported dependency matrix
tox

# Package build and metadata checks
python -m build --sdist --wheel
python -m twine check dist/*
```

If `make` is available, the same flows are exposed as:

```bash
make install-dev
make test-core
make test
make coverage
make build
make check-package
```

## Test Organization

- `tests/test_utils.py`: headers, client IP detection, masking, and settings helpers.
- `tests/test_middleware.py`: request/response logging, filtering, tracing, body limits, and content types.
- `tests/test_models.py`: model fields, admin display, filters, and CSV export.
- `tests/test_signals.py`: event listeners, background queue behavior, app startup, and worker stats.
- `tests/test_observability.py`: dependency-free Prometheus, OpenTelemetry, and Sentry helper behavior.
- `tests/test_profiling.py`: profiling settings, SQL tracking, admin diagnosis, and nullable profiling fields.
- `tests/test_backward_compat.py`: default behavior when profiling is disabled.
- `tests/test_integration.py`: end-to-end middleware, signal, database, and workflow coverage.
- `tests/test_management_commands.py`: retention command validation, dry-run behavior, and batched deletion.

## User Integration Test

Applications can verify signal-based logging without waiting for background database writes:

```python
from django.test import TestCase
from django.test.utils import override_settings
from rest_framework.test import APIClient

from drf_api_logger import API_LOGGER_SIGNAL


class APILoggingTestCase(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.api_logs = []

        def listener(**kwargs):
            self.api_logs.append(kwargs)

        self.listener = listener

    @override_settings(DRF_API_LOGGER_SIGNAL=True, DRF_API_LOGGER_DATABASE=False)
    def test_get_request_logged(self):
        API_LOGGER_SIGNAL.listen += self.listener
        try:
            response = self.client.get('/api/users/')

            self.assertEqual(len(self.api_logs), 1)
            log = self.api_logs[0]
            self.assertEqual(log['method'], 'GET')
            self.assertEqual(log['status_code'], response.status_code)
            self.assertIn('/api/users/', log['api'])
        finally:
            API_LOGGER_SIGNAL.listen -= self.listener
```

## Production Operations Checks

Retention command:

```bash
python manage.py prune_api_logs --days 30 --dry-run
python manage.py prune_api_logs --days 30 --batch-size 1000
```

Queue health check:

```python
from drf_api_logger.apps import LOGGER_THREAD

status = LOGGER_THREAD.get_status() if LOGGER_THREAD else {"enabled": False}
```

Monitor `queue_backlog`, `dropped_count`, and `failed_insert_count` in production.

## Contribution Expectations

- Add or update tests for every behavior change.
- Watch new tests fail before implementing behavior.
- Observability integrations must keep optional third-party packages out of install requirements and must not export headers, bodies, secrets, or high-cardinality IDs as metrics labels.
- Keep tests deterministic and isolated.
- Clean up signal listeners in `finally` blocks.
- Use real Django/DRF behavior where practical.
- Update README and `docs/` when settings, support policy, security posture, or operational behavior changes.
