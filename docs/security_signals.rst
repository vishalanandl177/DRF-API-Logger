Security Signals
================

DRF API Logger can emit optional, detect-only security metrics for suspicious
API activity. Security signals are disabled by default and do not block
requests.

The feature is not a WAF, IDS, SIEM, API gateway, rate limiter, or fraud engine.
It provides privacy-safe API-level signals that can feed systems your team
already operates.

Enable Detect-Only Signals
--------------------------

.. code-block:: python

   DRF_API_LOGGER_METRICS_ENABLED = True
   DRF_API_LOGGER_SECURITY_METRICS_ENABLED = True
   DRF_API_LOGGER_SECURITY_MODE = "detect"

Only ``detect`` mode is supported. Detection errors are isolated and must not
break customer API responses.

Body Inspection
---------------

Payload inspection is bounded. The default request sample limit is 8192 bytes,
and response-body inspection is off:

.. code-block:: python

   DRF_API_LOGGER_SECURITY_BODY_INSPECTION = {
       "enabled": True,
       "max_body_bytes": 8192,
       "inspect_request_body": True,
       "inspect_response_body": False,
   }

Security signals never place sampled body content in metric labels or signal
objects. Samples are used only inside the request path for bounded pattern
matching.

Rule Coverage
-------------

The implementation registers rule IDs ``DRFSEC-001`` through ``DRFSEC-016``.
Rules are low-cost and detect-only. Some rules are stateless, and correlation
rules use bounded in-memory TTL state per process:

- authentication failures;
- success after repeated authentication failures;
- token/auth endpoint failures;
- authorization failures;
- admin/debug probing;
- suspicious payload patterns;
- rate-limit pressure;
- route scanning hints;
- object ID enumeration hints;
- log injection control characters;
- suspected sensitive field exposure in response samples when response
  inspection is explicitly enabled;
- pagination sweep hints;
- bulk export hints;
- high response volume hints;
- customer-provided sensitive-route context.
- repeated customer-provided business-flow actions.

Actor correlation uses an internal HMAC fingerprint derived from configured
actor signals such as authenticated user id, IP address, or user-agent family.
The fingerprint is used only inside the process-local rolling state and is not
emitted as a metric label.

Business Context Hook
---------------------

Applications can provide safe, low-cardinality business context:

.. code-block:: python

   DRF_API_LOGGER_SECURITY_CONTEXT_GETTER = "myapp.security.get_context"

The callable receives ``request``, ``response``, and ``exception`` keyword
arguments and may return keys such as ``actor_type``, ``business_action``,
``resource_type``, ``flow_name``, and ``is_sensitive_route``. Values are
sanitized before rule evaluation. Do not return raw user IDs, object IDs,
tenant IDs, emails, tokens, or payload content.

Safe Labels
-----------

Security metrics use only low-cardinality labels:

- ``rule_id``
- ``event_type``
- ``category``
- ``severity``
- ``route``
- ``method``
- ``status_class``
- ``outcome``

Raw users, IPs, object IDs, tokens, request IDs, trace IDs, request bodies,
response bodies, exception messages, and SQL queries are never labels.

False Positives
---------------

Security signals are probabilistic. Treat them as triage and dashboard inputs,
not as proof of an attack. Tune alerts by route, severity, and sustained rate,
and investigate with your normal logs, traces, SIEM, WAF, gateway, or incident
workflow.

Operational Pattern
-------------------

Start conservatively:

1. Enable logger and pipeline metrics.
2. Enable security metrics in a non-production environment.
3. Review rule counts and false positives.
4. Enable bounded request-body inspection only where acceptable.
5. Keep blocking, enforcement, and incident response in dedicated security
   tooling.

For regulated environments, keep response inspection disabled unless there is a
documented operational need and the sampled content is covered by your privacy
and retention policy.
