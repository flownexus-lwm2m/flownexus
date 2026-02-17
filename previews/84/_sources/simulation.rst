Simulation
==========

flownexus provides a modular simulation platform located in the ``simulation/``
directory. This platform allows you to simulate IoT devices at different levels
of fidelity, from lightweight API mocks to full-stack Zephyr firmware
simulations.

Simulation Backends
-------------------

The platform supports two primary backends:

1.  **Mock Backend**: A lightweight Python-based simulator that interacts
    directly with the Django Ingestion API. It is ideal for frontend development
    and load testing.
2.  **Zephyr Backend**: A high-fidelity simulator that builds and runs actual
    Zephyr OS binaries (``native_sim``) inside a containerized network
    environment.

Simulation Dispatcher (simulate.py)
-----------------------------------

The ``simulate.py`` script is the central entry point for all simulations. It
uses YAML configuration files to define the simulation behavior.

.. code-block:: console
  :caption: Usage of simulate.py

  host:~/flownexus/simulation$ python3 simulate.py --help
  usage: simulate.py [-h] --config CONFIG [--build] [--run]
                     [--type {mock,zephyr}] [--count DEVICE_COUNT]

  Flownexus Device Simulation Dispatcher

  options:
    -h, --help            show this help message and exit
    --config CONFIG       Path to simulation YAML config file (Required)
    --build               Build binaries (Zephyr only)
    --run                 Run simulation
    --type {mock,zephyr}  Override simulation type
    --count DEVICE_COUNT  Override number of devices

Mock Simulation
---------------

The Mock backend is designed for rapid development of the flownexus frontend.
It provides a high-level abstraction of IoT devices, allowing you to test
dashboards, data ingestion, and firmware updates without a real device.

Features
........

*   **Sine-wave Data**: Generates smooth temperature and humidity curves,
    making it easy to verify frontend charts.
*   **Integrated FOTA Support**: Simulates the LwM2M firmware update lifecycle,
    including state transitions (Downloading, Downloaded, Updating) and
    actual binary download verification.
*   **Mock Leshan API**: Provides a built-in REST API on port 8081 that mimics
    the Leshan LwM2M server, allowing Django to send commands to mock devices.
*   **Zero Dependencies**: Does not require Docker, Podman (for the simulation itself),
    or Zephyr toolchains.

Automated Environment (make run-mock)
.....................................

The recommended way to develop for flownexus is using the integrated mock environment.
Running a single command sets up the entire stack:

.. code-block:: console

  host:~/flownexus$ make run-mock

This command orchestrates:
1.  **Redis**: Starts the message broker (via Podman).
2.  **Django**: Starts the development server at http://localhost:8000.
3.  **Celery**: Starts a worker to process background tasks (like FOTA commands).
4.  **Mock Simulation**: Starts the device simulator and the Mock Leshan API.

The script ensures all processes are synchronized and provides a clean shutdown
(via Ctrl+C) by killing all spawned process groups.

Manual Control
..............

If you prefer to run the simulation manually alongside an existing server:

.. code-block:: console

  host:~/flownexus/simulation$ python3 simulate.py --config sim_mock.yaml

.. note::
   When running manually, ensure your Django server is configured to talk to
   the mock API by setting ``LESHAN_URI=http://localhost:8081`` in your environment.

Zephyr Simulation
-----------------

The Zephyr backend runs actual firmware binaries. This is used for
end-to-end (E2E) testing and verifying LwM2M protocol compliance.

Prerequisites
.............

The Zephyr simulation requires a working Podman installation and the
Python ``docker`` and ``PyYAML`` libraries.

.. code-block:: console

   host:~$ apt install podman podman-compose
   host:~$ pip install docker PyYAML

Furthermore, the flownexus server stack should be running. The script expects
the network ``server_mynetwork`` to be available.

Running the Zephyr Simulation
.............................

The easiest way to build and run the Zephyr simulation is via the project
``Makefile``:

.. code-block:: console

  # Build the binaries (Required once or after code changes)
  host:~/flownexus$ make build-sim

  # Run the E2E test suite
  host:~/flownexus$ make test-e2e

Manual Control
..............

You can also use ``simulate.py`` directly with the Zephyr configuration:

.. code-block:: console

  # Build 5 devices
  host:~/flownexus/simulation$ python3 simulate.py --config sim_zephyr.yaml --build --count 5

  # Run the simulation and connect to the local server
  host:~/flownexus/simulation$ python3 simulate.py --config sim_zephyr.yaml --run --local

Configuration (YAML)
--------------------

Simulations are configured via YAML files. This allows you to check in specific
test scenarios into version control.

.. code-block:: yaml
  :caption: Example sim_mock.yaml

  type: mock
  url: "http://localhost:8000/flownexus/ingest"
  device_count: 5
  interval: 2.0  # Seconds between updates
  duration: 0    # 0 = Run forever
  run: true      # Automatically start simulation

.. code-block:: yaml
  :caption: Example sim_zephyr.yaml

  type: zephyr
  device_count: 1
  local_leshan: true  # Connect to the Leshan container
  verbose: false
  delay: 0            # Startup delay between instances (ms)
  build: false
  run: false

Integration Testing
-------------------

The mock simulation is integrated into the Django test suite. You can run
automated ingestion tests using:

.. code-block:: console

  host:~/flownexus/server/django$ python manage.py test sensordata.tests.test_mock_simulation

This test uses Django's ``LiveServerTestCase`` to spin up a real HTTP server
and verify that the simulation backend can successfully register devices and
ingest data.

External Resources
------------------

.. seealso::
   * `Zephyr LwM2M API <https://docs.zephyrproject.org/latest/connectivity/networking/api/lwm2m.html>`_
   * `Zephyr LwM2M Client Sample <https://docs.zephyrproject.org/latest/samples/net/lwm2m_client/README.html>`_
   * `Zephyr Native Sim Board <https://docs.zephyrproject.org/latest/boards/native/native_sim/doc/index.html>`_
   * `Zephyr Networking with Multiple Instances <https://docs.zephyrproject.org/latest/connectivity/networking/networking_with_multiple_instances.html>`_
