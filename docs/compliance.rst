Compliance Readiness
====================

DRF API Logger can support compliance programs, but installing the package is
not a compliance certification. Your application owner remains responsible for
lawful collection, retention, access control, encryption, and breach response.

The guidance below maps common audit expectations to package controls and the
operational controls you still need to configure.

What Is Covered by the Package
------------------------------

.. list-table::
   :header-rows: 1
   :widths: 30 35 35

   * - Control Area
     - Package Support
     - Operator Responsibility
   * - Secret masking
     - Masks sensitive body, header, and query keys case-insensitively before database or signal delivery.
     - Add domain-specific keys via ``DRF_API_LOGGER_EXCLUDE_KEYS``.
   * - Data minimization
     - Request and response body capture is bounded by default and records truncation markers when limits are exceeded.
     - Set body limits to ``0`` for marker-only body logging on regulated endpoints.
   * - Log processing isolation
     - Request threads enqueue log objects; database writes happen in the background worker.
     - Use a dedicated log database and a restricted database user.
   * - Failure isolation
     - Signal listener failures are contained and database writer failures are counted.
     - Alert on queue backlog, dropped logs, and failed inserts.
   * - Observability
     - Prometheus-style metrics include process identity, queue backlog, dropped logs, inserted logs, and failed inserts.
     - Scrape every worker process or aggregate through your APM/OpenTelemetry pipeline.
   * - Retention
     - Logs include timestamps and can be filtered or deleted by age.
     - Implement retention jobs that match your data policy.

Recommended Compliance Settings
-------------------------------

Use these settings as a starting point for privacy-sensitive environments:

.. code-block:: python

   DRF_API_LOGGER_DATABASE = True
   DRF_API_LOGGER_DEFAULT_DATABASE = 'logs_db'

   # Minimize captured payloads. Use 0 for marker-only body logging.
   DRF_API_LOGGER_MAX_REQUEST_BODY_SIZE = 0
   DRF_API_LOGGER_MAX_RESPONSE_BODY_SIZE = 0

   DRF_API_LOGGER_EXCLUDE_KEYS = [
       'password', 'token', 'access', 'refresh',
       'authorization', 'proxy_authorization',
       'cookie', 'set_cookie', 'x_api_key', 'api_key',
       'secret', 'client_secret', 'private_key',
       'email', 'phone', 'ssn', 'credit_card',
   ]

   DRF_API_LOGGER_SKIP_URL_NAME = [
       'health-check',
       'readiness',
       'metrics',
   ]

   DRF_API_LOGGER_ENABLE_METRICS = True
   DRF_API_LOGGER_ENABLE_PROFILING = True
   DRF_API_LOGGER_PROFILING_SAMPLE_RATE = 0.05

Retention Example
-----------------

Run retention outside the request path, for example from Celery beat, cron, or
your platform scheduler:

.. code-block:: python

   from datetime import timedelta
   from django.utils import timezone
   from drf_api_logger.models import APILogsModel

   def delete_old_api_logs(days=30, using='logs_db'):
       cutoff = timezone.now() - timedelta(days=days)
       return APILogsModel.objects.using(using).filter(
           added_on__lt=cutoff
       ).delete()

Operational Controls Still Required
-----------------------------------

- Encrypt the log database at rest when log entries may contain personal data.
- Use TLS for database, OpenTelemetry, and monitoring transport.
- Restrict Django admin and database access to personnel with a business need.
- Review export permissions because CSV exports can contain personal data.
- Record and monitor access to log storage through your database or platform audit logs.
- Configure backups and restores so log data follows the same retention and access policy.
- Document the lawful basis and purpose for collecting API request logs.
- Run periodic tests for masking, retention, logging failures, and queue backlog alerts.

Standards Alignment Notes
-------------------------

The implementation aligns with OWASP Logging Cheat Sheet themes by masking or
excluding secrets, bounding payload capture, isolating log-write failures from
the application request path, and exposing health signals for verification.

For GDPR-like environments, the package helps with data minimization and
confidentiality controls, but encryption, retention policy, access controls,
lawful basis, and processor/controller obligations must be handled by the
deploying organization.

References
----------

- OWASP Logging Cheat Sheet:
  https://cheatsheetseries.owasp.org/cheatsheets/Logging_Cheat_Sheet.html
- GDPR Article 32 security of processing:
  https://gdpr-info.eu/art-32-gdpr/
