Local Zephyr E2E tests
======================

The E2E tests run a native_sim binary against a local Django, Redis, Celery,
and Leshan stack. Each pytest session gets a temporary SQLite database, a
unique endpoint, dynamically selected host ports, and an artifact directory.
The harness stops only processes and containers created by that session.

.. note::

   This harness is temporary. Flownexus has no public device API yet, so
   the tests read SQLite and post to the ingest API directly. When the API
   exists, replace ``stack.py`` with ``server/compose.yml`` and the PTY
   transport with ``pytest-twister-harness``, and use only the API in the
   tests. See plan P-006 in ``flownexus_meta``.

Prerequisites
-------------

Build the local Leshan image and the Zephyr binary before running the suite::

    podman-compose -f server/compose.yml build leshan
    make build-sim

Run the suite from the repository root. ``make test-e2e`` builds the binary
and runs the same command::

    FLOWNEXUS_RUN_E2E=1 PYTHONPATH=.:server/django \
      uv run --extra test pytest --pyargs devtools.zephyr.e2e \
      -n 0 --override-ini addopts=""

Set ``FLOWNEXUS_ZEPHYR_BINARY`` when the binary is outside the default build
path. The session writes logs and ``run.json`` below
``devtools/zephyr/e2e-artifacts`` when that directory is configured with
``FLOWNEXUS_E2E_ARTIFACT_ROOT``. The default pytest temporary directory is
used otherwise. Artifacts are retained after failures.

CI (``.github/workflows/e2e_test.yml``) always runs the fast harness tests.
The ``build-sim`` job builds ``native_sim`` in ``ci-base`` and runs the
twister tests of the client. The full-stack job builds the Leshan, Django,
and Redis images, runs ``devtools/image-smoke-test`` against them, then runs
this suite with ``FLOWNEXUS_RUN_E2E=1``. This suite runs Django from source;
the smoke test covers the Django image. On ``push`` the job publishes all
three images to GHCR.

To add a scenario, use the ``e2e_context`` fixture, drive the device with
``device.shell.command()`` and check the result with ``DjangoApi`` or
``device.logs.wait_for()``.

Device I/O
----------

The harness keeps the two output channels of the native_sim binary apart:

- **Shell:** runs on its own pseudo terminal (PTY). The harness reads the
  ``connected to pseudotty: /dev/pts/N`` line from stdout and opens the PTY.
  ``device.shell.command()`` returns only the response lines and raises an
  error on shell errors. ``zephyr-shell.log`` keeps the transcript.
- **Logs:** go to stdout (``CONFIG_SHELL_LOG_BACKEND=n``).
  ``zephyr.log`` keeps them, and ``device.logs.wait_for()`` matches them.

The scenarios drive the device with the Zephyr ``lwm2m`` shell and the
``flownexus`` application shell::

    flownexus start urn:imei:e2e-... coap://127.0.0.1:<coap-port>
    lwm2m write /3303/0/5700 -f 17.25
    lwm2m send /3303/0/5700 /3304/0/5700
    lwm2m update

The operation scenario seeds Device ``3/0/14`` (``utc_offset``) in Django,
queues a write operation and triggers a registration update, because Django
sends queued operations on registration update. The test then waits for the
device log ``write 3/0/14=<value>`` and for the operation status
``CONFIRMED``.

Fixture evaluation
------------------

Zephyr's ``pytest-twister-harness`` provides ``dut`` and ``shell`` fixtures
for a native simulator. With a prebuilt application, the documented direct
invocation is ``pytest --twister-harness --device-type=native --build-dir=...``
after adding its source directory to ``PYTHONPATH``. The fixtures launch the
binary and offer prompt-based stdin/stdout access. They do not allocate
service ports or test storage, and they do not supervise Django, Redis,
Leshan, or Celery. This harness keeps its own process transport because it
must create and correlate the complete local service run. The upstream shell
implementation remains the reference for prompt and command-echo behavior.
