Comparison and Migration Guide
==============================

This guide explains when DRF API Logger is a fit, where adjacent tools fit, and
how to migrate from common request logging approaches without losing safety
controls.

Positioning
-----------

DRF API Logger is best for teams that want Django REST Framework
request/response logging with masking, asynchronous database writes, Django
admin visibility, slow API detection, optional profiling, and retention
workflows.

It is not a hosted observability platform, metrics backend, distributed tracing
backend, SIEM, or policy engine.

Custom DRF Middleware
---------------------

Custom middleware can be useful for one narrow internal rule, but production API
logging usually grows into masking, payload limits, retention, admin visibility,
thread safety, filtering, and migration work.

Use DRF API Logger when the custom middleware stores request bodies, response
bodies, status codes, execution time, or headers.

Migration steps:

1. Add ``drf_api_logger`` to ``INSTALLED_APPS``.
2. Add ``APILoggerMiddleware`` to ``MIDDLEWARE``.
3. Enable ``DRF_API_LOGGER_DATABASE = True`` or ``DRF_API_LOGGER_SIGNAL = True``.
4. Move sensitive field names into ``DRF_API_LOGGER_EXCLUDE_KEYS``.
5. Set request and response body limits.
6. Run ``python manage.py migrate`` when database logging is enabled.
7. Remove the old middleware after comparing logs in a non-production
   environment.

drf-api-tracking
----------------

``drf-api-tracking`` is a DRF request tracking package that uses a model and
view mixin pattern. DRF API Logger uses middleware, so it can cover configured
DRF traffic without adding a mixin to each view.

Choose DRF API Logger when you want middleware-level coverage, admin charts,
masking controls, profiling, and retention commands in one package.

Migration steps:

1. Identify views using the old tracking mixin.
2. Add DRF API Logger middleware and enable database logging.
3. Confirm the same endpoints are logged in a test environment.
4. Configure method, status code, namespace, and URL-name filters to match the
   old coverage.
5. Keep both systems briefly only in a controlled test environment, then remove
   the old mixin to avoid duplicate storage.

django-requestlogs and Request Logging Middleware
-------------------------------------------------

Request logging middleware packages can capture request-response data, but the
safety and storage behavior varies by package and configuration.

Choose DRF API Logger when the primary use case is DRF API request/response
inspection through Django admin with package-managed masking, body limits,
profiling, tracing, and pruning guidance.

Migration checklist:

- Compare logged fields: URL, method, status code, headers, body, response,
  execution time, client IP, and trace ID.
- Confirm secret-bearing headers and payload keys are masked.
- Confirm health checks, metrics endpoints, and static/media paths are skipped.
- Confirm old logs remain available long enough for audit or support needs.
- Remove duplicate middleware after validation.

django-easy-audit
-----------------

``django-easy-audit`` focuses on audit events such as model changes, requests,
and authentication activity. DRF API Logger focuses on DRF API request/response
observability and admin inspection.

These tools can be complementary when a project needs both model-change audit
history and API request diagnostics.

Observability Tools
-------------------

Prometheus, OpenTelemetry, Sentry, hosted API monitoring products, and log
aggregation platforms are complementary. They are better for metrics, traces,
exceptions, uptime, and cross-service views.

DRF API Logger is useful beside them when developers need payload-aware DRF API
log inspection with masking, admin filters, profiling diagnosis, and retention
commands inside a Django project.

Migration Checklist
-------------------

Before replacing an existing logger:

- Capture the old logged fields and retention policy.
- Configure DRF API Logger masking before enabling body storage.
- Configure body size limits before sending production traffic.
- Validate output in Django admin or a signal listener.
- Run the old and new loggers together only in a limited test window to avoid
  duplicate production storage.
- Document the rollback path by keeping the previous configuration available in
  version control until the new setup is accepted.
