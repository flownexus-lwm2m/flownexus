Django
======

The Django server hosts the REST API, manages the database, and provides a web interface
for data visualization and user management. This server acts as the backend
infrastructure that supports the entire IoT ecosystem by:

* **REST API**: Facilitates communication between the IoT devices and the server.
  The API endpoints handle requests for data uploads from devices, send control commands,
  and provide access to stored telemetry data.

* **Database Management**: Stores all the telemetry data, device information, user
  accounts, and configuration settings. The database ensures that data is organized,
  searchable, and retrievable in an efficient manner.

* **Web Interface**: Offers a user-friendly interface for data visualization and
  management. Through this interface, users can monitor device status, visualize
  telemetry data in real-time, manage user accounts, and configure device settings.


Build and Run
-------------

The Django server can also run locally, without the need of a docker container.
Make sure to create a virtual environment and install the requirements:

.. code-block:: console

  host:~$ source venv/bin/activate
  host:~$ cd flownexus_workspace/lwm2m_server/server/django
  host:lwm2m_server/server/django$ pip install -r requirements.txt
  host:lwm2m_server/server/django$ ./django_start.sh

The Django server should now be up and running under the following URL:
``http://localhost:8000/admin``. The admin login is ``admin`` and the password


Run Unit Tests
..............

There are unit tests, that test the deserializer, which parses the Json payload
from the ReST API. You can run the unit tests with the following command:

.. code-block:: console

  host:~/flownexus_workspace/lwm2m_server/server/django$ python manage.py test sensordata
  Found 2 test(s).
  Creating test database for alias 'default'...
  ----------------------------------------------------------------------
  Ran 2 tests in 0.008s

  OK
  Destroying test database for alias 'default'...


Database Model
--------------

The database model is the core of the Django server. It aims to store
information according to the LwM2M resource model. The advantage is that data
can be stored in a generic way and the server can be extended with new
resources without changing the database schema.

The server application logic only has to handle higher level events. Those
events are situations where multiple resources are associated (e.g.
Temperature, Pressure, Humidity, Acceleration). Those multiple resources are
linked in the event, together with a timestamp. The event itself is represented
by the database model in a generic way, several custom event types can be
created by the application logic.

An Entity Relationship Diagram (ERD) is a visual representation of the database
schema. It is automatically generated from the Django models. ``sensordata`` is
the Django app that contains the application logic.

.. figure:: ../images/erd.svg

  Entity Relationship Diagram generated from Django models

.. glossary::

  Endpoint
    IoT devices using the LwM2M protocol in the network, identifiable by a
    unique name, e.g. ``urn:imei:123456789012345``.

  ResourceType
    Defines resource data points comprehensively, annotating each with a unique
    object-resource ID combination, a descriptive name, and specifying the
    expected data type.

  Resource
    A specific piece of data or functionality within an LwM2M Object. Resources
    represent attributes or actions and are identified by Resource IDs within
    an Object.

    In the database Model a Resource represents an individual data value from one
    IoT device, annotated with timestamps, applicable data types, and linked
    to both the device and resource type for which the data is relevant.

  Event
    A collection for significant occurrences reported by endpoints. Events and
    Resources are linked to each other via EventResource table.

  EventResource
    Acts as a junction table forming a many-to-many relationship between events
    and their constituent resources, enabling flexible association without
    direct modification to the core events or resources tables.

  EndpointOperation
    Represents actionable commands or processes targeted at endpoints, tracking
    the operation type, status, and scheduling through timestamps, also
    detailing the transmission attempts and last action.

  Firmware
    Stores metadata about firmware binaries that are available for devices to
    download and install. Each record includes a version identifier, the name
    of the file, a URL from where the device can retrieve the firmware, and
    timestamps for tracking when each firmware record was created and last
    updated.
