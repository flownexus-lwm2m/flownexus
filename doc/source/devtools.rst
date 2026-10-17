Devtools & Testing
==================

Testing
-------

Compliance Checks
...................

Run code formatting, linting, and git validation::

  host:~/flownexus$ make compliance

Run Zephyr checkpatch on the native_sim client (needs the Zephyr tree in
``../zephyr``)::

  host:~/flownexus$ make checkpatch

Unit Tests
..........

Run Django unit tests::

  host:~/flownexus$ make test-django

Or directly with pytest::

  host:~/flownexus$ uv run --extra test pytest server/django/sensordata/tests/

End-to-End Tests
................

Run the local Zephyr E2E suite (native_sim plus isolated Django, Redis,
Celery, and Leshan)::

  host:~/flownexus$ make test-e2e

Requires a container runtime (Podman or Docker), a built Leshan image, and
the Zephyr toolchain. Fast harness tests run without ``FLOWNEXUS_RUN_E2E``;
the three stack workflows need that flag, which ``make test-e2e`` sets.

Run the native_sim twister tests (shell test and overlay builds) without the
server stack::

  host:~/flownexus$ make test-sim

Development Tools
-----------------

Mock Simulation
...............

Lightweight Python-based device simulator for development and testing.

Run integrated development environment::

  host:~/flownexus$ make run-mock

This starts Redis, Django, Celery, and Mock Simulation with a temporary database.

Standalone simulator::

  host:~/flownexus$ uv run --group mock python devtools/mock/run.py --config devtools/mock/config.yaml

**Scenarios:**

*   **default**: 5 devices, 1 site (``make run-mock``)
*   **multi-site**: 15 devices, RBAC testing (``make run-mock-multi-site``)

Scenario files are in ``devtools/mock/scenarios/``.

Zephyr Simulation
..................

The LwM2M client in ``devtools/zephyr/client`` runs as a ``native_sim``
binary with host sockets, so no TAP setup is required. It is driven through
the Zephyr ``lwm2m`` shell, see ``devtools/zephyr/client/README.rst``.

.. code-block:: console

  # Build the binary
  host:~/flownexus$ make build-sim

  # Run it against a local Leshan on coap://127.0.0.1:5683
  host:~/flownexus$ devtools/zephyr/client/build/zephyr/zephyr.exe --uart_stdinout
  uart:~$ flownexus start my-device

External Resources
------------------

.. seealso::
   * `Zephyr LwM2M API <https://docs.zephyrproject.org/latest/connectivity/networking/api/lwm2m.html>`_
   * `Zephyr LwM2M Client Sample <https://docs.zephyrproject.org/latest/samples/net/lwm2m_client/README.html>`_
   * `Zephyr Native Sim Board <https://docs.zephyrproject.org/latest/boards/native/native_sim/doc/index.html>`_
