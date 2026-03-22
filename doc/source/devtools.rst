Devtools & Testing
==================

Testing
-------

Compliance Checks
...................

Run code formatting, linting, and git validation::

  host:~/flownexus$ make compliance

Unit Tests
..........

Run Django unit tests::

  host:~/flownexus$ make test-django

Or directly with pytest::

  host:~/flownexus$ uv run --extra test pytest server/django/sensordata/tests/

End-to-End Tests
................

Run full E2E test suite with Zephyr simulation::

  host:~/flownexus$ make test-e2e

Requires Podman and Zephyr toolchain.

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

High-fidelity simulation using actual Zephyr OS firmware binaries.

Prerequisites::

   host:~$ apt install podman podman-compose
   host:~$ uv sync --group zephyr

**Usage:**

.. code-block:: console

  host:~/flownexus$ uv run --group zephyr python devtools/zephyr/run.py --help

**Run simulation:**

.. code-block:: console

  # Build binaries
  host:~/flownexus$ make build-sim

  # Run against local server
  host:~/flownexus$ uv run --group zephyr python devtools/zephyr/run.py --config devtools/zephyr/config.yaml --run --local

External Resources
------------------

.. seealso::
   * `Zephyr LwM2M API <https://docs.zephyrproject.org/latest/connectivity/networking/api/lwm2m.html>`_
   * `Zephyr LwM2M Client Sample <https://docs.zephyrproject.org/latest/samples/net/lwm2m_client/README.html>`_
   * `Zephyr Native Sim Board <https://docs.zephyrproject.org/latest/boards/native/native_sim/doc/index.html>`_
