Simulation
==========

IoT Devices with Zephyr
-----------------------

Zephyr implements an LwM2M client library [1]_ and has an LwM2M client sample
[2]_. The Zephyr works with the flownexus server out of the box e.g. with an
nRF9160 DK board.

flownexus provides a modified sample at ``endpoint_sim/lwm2m_client`` to
showcase all server features.

.. note::
   Currently, the lwm2m_client sample is a copy of the original Zephyr sample.
   Distinct features that showcase flownexus capabilities are planned for the
   upcoming releases.

LwM2M Endpoint Simulation
-------------------------

The lwm2m_client sample can run in simulation mode (``native_sim``) [3]_.
Building the sample with ``native_sim`` will generate a binary that can be
executed directly on the host machine. This allows to test all components
locally.

The native_sim simulation allows to connect the simulated Zephyr instance to
the host network [4]_. Furthermore, simulated Zephyr endpoints have access to
the internet via the host network, allowing testing of both a locally hosted
instance of flownexus as well as a remote instance.

To simulate endpoints easily, a script is provided that builds and runs the
endpoints in a docker container. Setting up the network and running the
simulation in a docker container ensures interoperability with different host
systems.

Prerequisites
.............

The simulation requires a working Docker installation.

.. code-block:: console

   host:~$ apt install docker-ce


Simulating a single Endpoint
............................

The easiest way to run the simulation is to execute the simulate.py script
without any arguments:

.. code-block:: console

  host:~/flownexus_workspace/flownexus$ python3 ./simulate
  No build/run options provided, build and run n clients with logging:
    Warning: bindir will be cleaned, do you want to continue? [y/n]
  y

  Cleaning ./lwm2m_client/endpoint_binaries/
  Building Zephyr client [1/1]
  Building image from ./Dockerfile
  Starting container
  Starting zeth [1/1]
  Starting Zephyr client [1/1]

  *** Booting Zephyr OS build v3.7.0-rc3-75-gd06e95c49b75 ***
  [..]

You should now be able see one active endoint with the registration name
``urn:imei:100000000000000`` the registered node in the Django Admin dashboard
at ``https://flownexus.org/admin/``.

Simulation Script (simulate.py)
...............................

.. code-block:: console
  :caption: Options of the simulate.py script

  host:~/flownexus_workspace/flownexus$ python3 simulate.py --help

  usage: simulate.py [-h] [-n NUM_CLIENTS] [-l] [-b] [-r] [-d DELAY]

  Zephyr Build and Run Script

  options:
    -h, --help      show this help message and exit
    -n NUM_CLIENTS  Number of client instances to start. (1 - 254) (default: 1)
    -l              Enable logging (default: False)
    -b              Build the client (default: False)
    -r              Run the client. (default: False)
    -d DELAY        Client start delay [ms] (default: 0)

Simulating Multiple Endpoints
.............................

The simulation allows to configure and start multiple Zephyr endpoints. The
script takes care of assigning individual IP addresses and gateway settings to
each endpoint. Furthermore it sets up the virtual network adapter (zeth) that
connects the endpoints to the host network. For that reason, each endpoint has
to be build before it can be started. The resulting binaries are stored in the
lwm2m_client sample (e.g. ``lwm2m_client/endpoint_binaries/ep_0.exe``). A set
of devices can be build once and started by omitting the parameter ``-b``.

.. code-block:: console
  :caption: Build and run 10 endpoints without logging

  host:~/flownexus_workspace/flownexus$ python3 simulate.py -b -r -n 10
  Cleaning ./lwm2m_client/endpoint_binaries/
  Building Zephyr client [10/10]
  Building image from ./Dockerfile
  Starting container
  Starting zeth [10/10]
  Starting Zephyr client [10/10]
  # Stop the simulation with <Ctrl+c>
  Stopping container

.. warning::
   Currently, the simulate.py script supports max. 254 clients.

Configuring the Firmware
........................

You can change the flownexus domain that you want to connect to by modifying
the ``Kconfig`` file in the lwm2m_client sample.

.. code-block:: diff
   :caption: Change the LwM2M server address to a locally hosted instance of flownexus

    ./endpoint_sim/lwm2m_client/Kconfig
    # flownexus.org -> 217.160.3.6
    config LWM2M_APP_SERVER
           string "LwM2M server address"
   -       default "coap://flownexus.org:5683" if !LWM2M_DTLS_SUPPORT
   +       default "coap://leshan:5683" if !LWM2M_DTLS_SUPPORT


If you want to modify the firmware further, check :ref:`firmware_setup` for
more details on this topic.

.. [1] https://docs.zephyrproject.org/latest/connectivity/networking/api/lwm2m.html
.. [2] https://docs.zephyrproject.org/latest/samples/net/lwm2m_client/README.html
.. [3] https://docs.zephyrproject.org/latest/boards/native/native_sim/doc/index.html.
.. [4] https://docs.zephyrproject.org/latest/connectivity/networking/networking_with_multiple_instances.html
