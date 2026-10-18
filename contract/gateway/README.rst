Gateway contract golden files
=============================

The files in ``ingest/`` record what the Leshan gateway sends to the Django
ingest API for a set of device scenarios. Both sides check against them:

- **Producer:** ``devtools/zephyr/e2e/test_contract.py`` drives a native_sim
  device against the Leshan image. The gateway posts to a recording sink
  instead of Django. The recorded requests must equal the golden file.
- **Consumer:** ``server/django/sensordata/tests/test_gateway_contract.py``
  posts the same requests to the ingest API and checks the database.

A contract change shows up as a diff of these files. Do not edit them by
hand. Re-record them from the repository root after building the Leshan
image and the native_sim binary::

    FLOWNEXUS_RUN_E2E=1 FLOWNEXUS_UPDATE_GOLDEN=1 PYTHONPATH=.:server/django \
      uv run --extra test pytest --pyargs devtools.zephyr.e2e.test_contract \
      -n 0 --override-ini addopts=""

Format
------

Each file holds one scenario:

``setup``
  Device shell commands that run before recording, usually the start of the
  client.
``steps``
  A list of steps. ``device`` lists the shell commands of the step, and
  ``requests`` lists the HTTP requests (``method``, ``path``, ``body``) the
  gateway sent after them, in order. A ``sleep <seconds>`` command waits on
  the host.

The recorder replaces volatile values with placeholders:

=================  ==========================================================
Placeholder        Replaces
=================  ==========================================================
``<endpoint>``     The endpoint name of the test device.
``<time>``         The value of a resource of type ``TIME``.
``<timestamp>``    An ISO 8601 timestamp key of a timestamped Send.
=================  ==========================================================

The Django tests substitute fixed values for the placeholders. To add a
scenario, add it to ``SCENARIOS`` in ``test_contract.py``, record it, and
add database checks to ``test_gateway_contract.py``.
