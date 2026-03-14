Devtools & Testing
==================

flownexus provides development and testing tools in the ``devtools/``
directory. The documentation is organized by test level, from fast unit tests
to comprehensive end-to-end testing.

Testing
-------

The project provides several Makefile targets for testing. These commands can
be run from the repository root and ensure consistent test environments.

Compliance Checks
................

Run static analysis and formatting checks:

.. code-block:: console

  host:~/flownexus$ make compliance

This performs:

*   Code formatting validation (black, isort)
*   Linting (flake8, ruff)
*   Git history validation (signed commits)

All checks must pass before submitting changes.

Unit Tests
.........

Run Django unit tests in an isolated Tox environment:

.. code-block:: console

  host:~/flownexus$ make test-django

This executes all unit tests using tox, which ensures tests run in a clean,
reproducible environment with proper dependencies. Unit tests cover:

*   REST API endpoint validation
*   Data deserializer functionality
*   Model relationships and constraints
*   Permission and RBAC logic

You can also run tests directly (without tox) for faster iteration during
development:

.. code-block:: console

  host:~/flownexus/server/django$ python manage.py test sensordata

Integration Testing
..................

The ``make test-django`` command also runs integration tests, including the
mock simulation integration test:

.. code-block:: console

  host:~/flownexus/server/django$ python manage.py test sensordata.tests.integration.test_mock_simulation

This test uses Django's ``LiveServerTestCase`` to spin up a real HTTP server
and verify that the simulation backend can successfully register devices and
ingest data.

End-to-End Tests
...............

Run the full E2E test suite including Zephyr simulation:

.. code-block:: console

  host:~/flownexus$ make test-e2e

This builds Zephyr binaries, starts the server stack, runs the simulation,
and verifies data ingestion. Requires Podman and Zephyr toolchain.

Run All Tests
............

Execute the complete test suite:

.. code-block:: console

  host:~/flownexus$ make test-all

This runs compliance checks, unit tests, and E2E tests in sequence.

Development Tools
-----------------

For iterative development and debugging, flownexus provides simulation tools
that emulate IoT devices at different fidelity levels.

Mock Simulation
..............

The Mock backend is a lightweight Python-based simulator that interacts
directly with the Django Ingestion API. It generates synthetic device data
(temperature, humidity) with sine-wave patterns for easy visualization testing
and simulates the complete FOTA lifecycle.

Key features:

*   **Zero Dependencies**: No Docker, Podman, or Zephyr toolchains required
*   **Mock Leshan API**: Built-in REST API on port 8081 mimics the Leshan server
*   **Sine-wave Data**: Smooth curves make frontend chart verification easy
*   **Integrated FOTA**: Simulates firmware update state transitions

The recommended way to use the Mock backend is via the integrated development
environment:

.. code-block:: console

  host:~/flownexus$ make run-mock

This command orchestrates Redis, Django, Celery, and the Mock Simulation in a
single step. The environment uses a temporary database in ``/tmp/`` that is
deleted on shutdown. Use ``-v`` for verbose output.

Alternatively, run the simulator standalone against an existing server:

.. code-block:: console

  host:~/flownexus$ python3 devtools/mock/run.py --config devtools/mock/config.yaml

**Scenario-Based Configuration**

The mock environment supports YAML-based scenarios for testing different features.
Scenarios are stored in ``devtools/mock/scenarios/``:

*   **default**: 5 devices, 1 site, single admin user (``make run-mock``)
*   **multi-site**: 15 devices, multiple sites/users with RBAC (``make run-mock-multi-site``)

Create custom scenarios by adding YAML files. Each scenario defines devices,
sites, and users for reproducible test environments.

**Example Mock Configuration** (``devtools/mock/config.yaml``):

.. code-block:: yaml

  type: mock
  url: "http://localhost:8000/flownexus/ingest"
  device_count: 5
  interval: 2.0  # Seconds between updates
  duration: 0    # 0 = Run forever
  run: true      # Automatically start simulation

Zephyr Simulation
................

The Zephyr backend runs actual Zephyr OS firmware binaries in a containerized
network environment. This provides high-fidelity simulation for end-to-end
testing and LwM2M protocol compliance verification.

Prerequisites: Podman, Python ``docker``/``PyYAML`` libraries, and Zephyr toolchain.

.. code-block:: console

   host:~$ apt install podman podman-compose
   host:~$ pip install docker PyYAML

The script expects the ``server_mynetwork`` Docker network to be available
(from the running server stack).

**CLI Usage:**

.. code-block:: console
  :caption: Usage of devtools/zephyr/run.py

  host:~/flownexus$ python3 devtools/zephyr/run.py --help
  usage: run.py [-h] --config CONFIG [--build] [--run] [--local]

  Flownexus Zephyr Device Simulator

  options:
    -h, --help       show this help message and exit
    --config CONFIG  Path to simulation YAML config file (Required)
    --build          Build Zephyr binaries
    --run            Run simulation
    --local          Use local Leshan server

**Example Zephyr Configuration** (``devtools/zephyr/config.yaml``):

.. code-block:: yaml

  type: zephyr
  device_count: 1
  local_leshan: true  # Connect to the Leshan container
  verbose: false
  delay: 0            # Startup delay between instances (ms)
  build: false
  run: false

**Running the Simulation:**

.. code-block:: console

  # Build binaries (required once or after code changes)
  host:~/flownexus$ make build-sim

  # Run simulation against local server
  host:~/flownexus$ python3 devtools/zephyr/run.py --config devtools/zephyr/config.yaml --run --local

External Resources
------------------

.. seealso::
   * `Zephyr LwM2M API <https://docs.zephyrproject.org/latest/connectivity/networking/api/lwm2m.html>`_
   * `Zephyr LwM2M Client Sample <https://docs.zephyrproject.org/latest/samples/net/lwm2m_client/README.html>`_
   * `Zephyr Native Sim Board <https://docs.zephyrproject.org/latest/boards/native/native_sim/doc/index.html>`_
   * `Zephyr Networking with Multiple Instances <https://docs.zephyrproject.org/latest/connectivity/networking/networking_with_multiple_instances.html>`_
