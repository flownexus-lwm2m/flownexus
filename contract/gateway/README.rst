Gateway contract golden files
=============================

The files record the behavior of the Leshan gateway for a set of device
scenarios:

- ``ingest/``: the requests the gateway sends to the Django ingest API.
- ``command/``: the gateway's responses to Django's command requests, and
  any ingest requests they cause.

Both sides check against them:

- **Producer:** ``devtools/zephyr/e2e/test_contract.py`` drives a native_sim
  device against the Leshan image. The gateway posts to a recording sink
  instead of Django. The recorded requests and responses must equal the
  golden file.
- **Consumer:** ``server/django/sensordata/tests/test_gateway_contract.py``
  posts the ingest requests to the ingest API, answers ``send_operation``
  and the read of ``/3`` with the recorded responses, and checks the
  database.

``doc/source/architecture/gateway_contract.rst`` describes the contract that
these files record.

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
  A list of steps. ``device`` lists the commands of the step, and
  ``requests`` lists the HTTP requests (``method``, ``path``, ``body``) the
  gateway sent after them, in order. A command is a device shell command,
  ``sleep <seconds>`` on the host, or ``http <METHOD> <path> [json]``
  against the gateway command API. ``responses`` lists the ``status`` and
  ``body`` of each ``http`` command.

The recorder replaces volatile values with placeholders:

=================  ==========================================================
Placeholder        Replaces
=================  ==========================================================
``<endpoint>``     The endpoint name of the test device.
``<time>``         The value of a resource of type ``TIME``.
``<timestamp>``    An ISO 8601 timestamp, as a value or as the key of a
                   timestamped Send.
=================  ==========================================================

The Django tests substitute fixed values for the placeholders. To add a
scenario, add it to ``SCENARIOS`` in ``test_contract.py``, record it, and
add database checks to ``test_gateway_contract.py``.
