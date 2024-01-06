Hardware
--------

Pressure Sensor
...............

The pressure sensor comes encased in a waterproof housing, ensuring that the
device can reliably function even when immersed in water. This sensor connects
to a system through its cable, which facilitates communication via the I2C
protocol with the help of an SDA and an SDL line.

The table states how the pressure sensor is connected to the cable. The wires
of the 5 pin cable are named PE and numbers ranging form 1-4.

.. table:: Pinout Pressure Sensor Cable

  +---------+--------------+
  | **Pin** | **Function** |
  +=========+==============+
  | PE      | GND          |
  +---------+--------------+
  | 1       | I2C SDA      |
  +---------+--------------+
  | 2       | I2C SDL      |
  +---------+--------------+
  | 3       | Interrupt    |
  +---------+--------------+
  | 4       | VCC 1V8      |
  +---------+--------------+

.. figure:: images/pressure_sensor_housing.jpg
  :width: 25%

  Pressure Sensor with waterproof housing

.. figure:: images/pressure_sensor_cable.jpg
  :width: 25%

  Pressure Sensor cable connection

Server Software
---------------

Setup
.....

Install Virtualenv
~~~~~~~~~~~~~~~~~~

First, install the `virtualenv` package using `pip` if it's not already installed on your system:

.. code-block:: bash

   $ pip install virtualenv

Creating a Virtual Environment
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Navigate to your project directory and create a virtual environment:

.. code-block:: bash

   waterlevel_monitor$ cd server
   waterlevel_monitor/server$ virtualenv venv

*Note:* "venv" is the name of the virtual environment directory.

Activating the Venv and install packages from requirements
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

To activate the virtual environment, run:

.. code-block:: bash

   $ source venv/bin/activate

Once activated, you can install packages into the virtual environment.

.. code-block:: bash

   $ pip install -r requirements.txt

Deactivating
~~~~~~~~~~~~

When you are done, you can deactivate the virtual environment by running:

.. code-block:: bash

   $ deactivate

Start Server
............

You can start the server in a development setup by executing:

.. code-block:: bash

   $ python manage.py runserver

Unless you add new files, you can keep the server running while modifying the
server.
