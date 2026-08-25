Release Checklist
=================

Use this checklist for every DRF API Logger release. It keeps package
metadata, compatibility claims, documentation, and public learning resources
aligned with the code being shipped.

Version and Compatibility
-------------------------

* Update the version in ``setup.py`` before publishing a new distribution.
* Confirm ``python_requires``, Django requirements, DRF requirements, Trove
  classifiers, the README, and the documentation all describe the same
  supported versions.
* Run the supported framework matrix with ``tox`` when middleware, models,
  migrations, packaging, or compatibility changes.
* Record database-specific migration or operational warnings in the release
  notes and the relevant documentation page.

Documentation and Links
-----------------------

* Update the README and ``docs/`` together for settings or behavior changes.
* Verify the documentation, source, issue tracker, operations guide, AI
  guidance, and maintainer tutorial entries in ``project_urls``.
* Check that the `CodersSecret production guide
  <https://coderssecret.com/blog/drf-api-logger-django-rest-framework>`_ still
  uses the current stable version, compatibility range, commands, and bounded
  performance language.
* Describe the Django REST Framework third-party package listing precisely;
  do not imply endorsement, certification, or official package status.

Safety and Operations
---------------------

* Review masking defaults, example payloads, body limits, retention commands,
  and endpoint policies for safe production guidance.
* Keep performance claims bounded: capture, masking, serialization, and queue
  work still occur on the request path even when database writes are batched in
  the background.
* Do not describe request logs as an immutable audit trail, a compliance
  guarantee, or a replacement for a WAF, SIEM, IDS, APM, or tracing backend.

Build and Publish
-----------------

.. code-block:: bash

   python test_runner_simple.py
   python -m django test tests --settings=tests.test_settings --verbosity=1
   python -m build --sdist --wheel
   python -m twine check dist/*

* Inspect the wheel and source distribution before upload.
* Confirm the GitHub Actions matrix passes for the release commit.
* Verify the new version on PyPI, the generated GitHub release, and the
  published documentation after the workflow completes.
* Recheck every public link from the PyPI project page; ``project_urls`` changes
  appear there only after a new package version is published.
