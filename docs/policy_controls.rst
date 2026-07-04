Policy Controls
===============

Use policy controls when different endpoints need different logging, masking,
persistence, or signal/export behavior. Policies are optional. When no policy
is configured, DRF API Logger keeps its current defaults.

Endpoint Skip
-------------

Skip noisy or sensitive endpoints before a log entry or signal export is
produced:

.. code-block:: python

   DRF_API_LOGGER_POLICY = {
       "rules": [
           {
               "url_name": "health_check",
               "log": False,
               "reason": "skip_health_check",
           },
       ],
   }

When ``log`` is ``False``, the middleware still returns the normal API response
but does not queue a database row and does not emit ``API_LOGGER_SIGNAL`` for
that request.

Payload Minimization
--------------------

Keep request metadata while removing headers and bodies for sensitive routes:

.. code-block:: python

   DRF_API_LOGGER_POLICY = {
       "rules": [
           {
               "route": "api/payments/",
               "headers": False,
               "request_body": False,
               "response_body": False,
               "reason": "payment_metadata_only",
           },
       ],
   }

This preserves method, URL, status code, client IP, execution time, and
timestamp while storing empty header/body/response fields.

Endpoint-Specific Masking
-------------------------

Add extra mask keys for one endpoint without changing global settings:

.. code-block:: python

   DRF_API_LOGGER_POLICY = {
       "rules": [
           {
               "url_name": "payment_create",
               "mask_keys": ["card_number", "payment_token"],
               "reason": "payment_masking",
           },
       ],
   }

Policy mask keys are applied before database persistence and before signal
emission. They do not mutate ``DRF_API_LOGGER_EXCLUDE_KEYS``.

Signal And Export Gate
----------------------

Signal listeners are commonly used as export hooks. Disable signal emission for
events that should remain local to database logging:

.. code-block:: python

   DRF_API_LOGGER_POLICY = {
       "rules": [
           {
               "namespace": "internal",
               "methods": ["POST"],
               "status_classes": ["2xx"],
               "signal": False,
               "reason": "do_not_export_internal_success",
           },
       ],
   }

When ``signal`` is ``False``, ``API_LOGGER_SIGNAL.listen`` is not called for the
matching request.

Callable Policy
---------------

Use a callable when declarative rules are not enough:

.. code-block:: python

   DRF_API_LOGGER_POLICY_FUNC = "myapp.logging.api_logger_policy"

   def api_logger_policy(context):
       if context["url_name"] == "health_check":
           return {"log": False, "reason": "skip_health_check"}
       if context["status_class"] == "5xx":
           return {"signal": True, "reason": "export_errors"}
       return {"log": True}

The context includes ``path``, ``method``, ``status_code``, ``status_class``,
``route``, ``url_name``, ``namespace``, ``app_name``, ``view_name``,
``correlation``, and ``low_cardinality``.

Safe Failure Behavior
---------------------

If policy evaluation raises an exception, DRF API Logger fails closed for
payloads:

- Headers, request body, and response body are stripped.
- The stored ``api`` value uses the request path instead of the full URL with
  query string.
- Signal emission is disabled for that event.
- Database logging may continue with safe metadata when database logging is
  enabled.
- Exception text is not stored or emitted.

Safety Rules
------------

- Do not put secrets, credentials, cookies, tokens, direct user identities, or
  regulated identifiers in policy reasons.
- Prefer ``url_name``, ``route``, ``namespace``, ``method``, ``status_code``,
  and ``status_class`` for deterministic matching.
- Use ``mask_keys`` for endpoint-specific identifiers that should not be stored
  or exported.
- Use ``signal: False`` when signal listeners export to external systems and a
  request should remain local.
- Keep policy callables bounded; they run on the request path.
