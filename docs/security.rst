Security
========

DRF API Logger handles sensitive data by default and provides controls for
compliance-conscious deployments.

Automatic Data Masking
----------------------

By default, these fields are recursively masked with ``***FILTERED***`` in both
request and response bodies:

- ``password``
- ``token``
- ``access``
- ``refresh``

Masking works on:

- Top-level dictionary keys
- Nested dictionaries (recursive)
- Lists of dictionaries
- URL query parameters (e.g., ``?token=abc`` becomes ``?token=***FILTERED***``)

Extend the default list:

.. code-block:: python

   DRF_API_LOGGER_EXCLUDE_KEYS = [
       'password', 'token', 'access', 'refresh',
       'secret', 'api_key', 'credit_card', 'ssn',
       'authorization', 'cookie', 'session_id',
   ]

What Is NOT Logged
------------------

- Django Admin panel requests (always excluded)
- Static and media file requests (always excluded)
- Request/response bodies exceeding size limits (logged with empty body)

No Sensitive Data in the Database
---------------------------------

The masking happens **before** data reaches the database or signal system.
The original unmasked data never touches storage.

.. code-block:: python

   # Input: {"username": "john", "password": "secret123"}
   # Stored: {"username": "john", "password": "***FILTERED***"}

Database Access Control
-----------------------

Use a dedicated database with restricted access for log storage:

.. code-block:: python

   DRF_API_LOGGER_DEFAULT_DATABASE = 'logs_db'

Admin Permissions
-----------------

The API Logs admin is read-only by default:

- ``has_add_permission`` returns ``False``
- ``has_change_permission`` returns ``False``

Logs can only be viewed and deleted (not created or modified) through the admin.

Data Retention
--------------

Implement periodic cleanup to comply with data retention policies:

.. code-block:: python

   from drf_api_logger.models import APILogsModel
   from django.utils import timezone
   from datetime import timedelta

   # Delete logs older than 30 days
   APILogsModel.objects.filter(
       added_on__lt=timezone.now() - timedelta(days=30)
   ).delete()

Profiling Data
--------------

Profiling data contains only timing information and query counts — no actual
SQL queries, request bodies, or response data. It is safe to store alongside
logs without additional masking.

OpenTelemetry
-------------

When OTel export is enabled, span attributes contain:

- HTTP metadata (method, URL, status code, IP)
- Timing data (execution time, profiling breakdown)
- Query counts (not query contents)

No request/response bodies or sensitive data are exported to OTel backends.
