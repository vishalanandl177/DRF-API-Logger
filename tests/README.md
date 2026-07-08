# Test Suite for DRF API Logger

This directory contains the package test suite.

## Structure

- `test_utils.py`: utility helpers, masking, headers, and settings.
- `test_middleware.py`: middleware configuration, filtering, tracing, content handling, and body limits.
- `test_asgi_middleware.py`: ASGI middleware capability, AsyncClient integration, async logging, and context isolation.
- `test_models.py`: database model and Django admin behavior.
- `test_signals.py`: event listeners, background queue processing, app startup, and worker stats.
- `test_metrics.py`: optional metrics settings, safe labels, no-op recorder, system checks, middleware hooks, queue metrics, security signals, and endpoint safety.
- `test_profiling.py`: profiling settings, SQL tracking, admin display, and diagnosis rules.
- `test_backward_compat.py`: default behavior and payload compatibility.
- `test_integration.py`: end-to-end middleware, signal, and database flows.
- `test_management_commands.py`: retention command validation and batched deletion.
- `test_settings.py`: Django settings for the test suite.
- `urls.py`: test URLs and DRF views.

## Running Tests

```bash
python test_runner_simple.py
python -m django test tests --settings=tests.test_settings --verbosity=1
python -m django test tests.test_management_commands --settings=tests.test_settings --verbosity=2
```

Run coverage:

```bash
coverage run --source=drf_api_logger -m django test tests --settings=tests.test_settings --verbosity=1
coverage report
```

Run the supported framework matrix:

```bash
tox
```
