Communication, Interfaces
==========================

The communication between IoT devices and Leshan is specified by the OMA LwM2M
standard:

- `LwM2M core specification v1.1.1`_
- `LwM2M transport binding v1.1.1`_

.. _LwM2M core specification v1.1.1: https://www.openmobilealliance.org/release/LightweightM2M/V1_1_1-20190617-A/OMA-TS-LightweightM2M_Core-V1_1_1-20190617-A.pdf
.. _LwM2M transport binding v1.1.1: https://www.openmobilealliance.org/release/LightweightM2M/V1_1_1-20190617-A/OMA-TS-LightweightM2M_Transport-V1_1_1-20190617-A.pdf

The standard describes how the LwM2M server (Leshan) works, however, it does
not describe how to connect a backend server to Leshan. The backend is
responsible for storing the data in a database and implementing application
logic. A frontend can access the data in the database and visualize outward
facing user interfaces. Leshan acts as a gateway between Endpoints and the
backend. There should be no application specific logic implemented in Leshan.

In order to communicate and exchange data, both components (Leshan LwM2M Server
and Django) send requests to each other's ReST APIs. Communication is typically
triggered by IoT devices sending data or the user/application requesting data
from devices.

Data Flow: Endpoint -> Backend
------------------------------

All communication from Endpoints to the server flows through Leshan. Leshan
interprets this data according to the LwM2M protocol and generates a ReST API
call to the backend server. The backend server then stores the data in the
database.

Django hosts the ReST API that Leshan posts to. Serializers, a part of Django,
deserialize the incoming data and store it in the database according to the
database model.

The gateway forwards registration events and LwM2M Send data. Chapter
:doc:`gateway_contract` describes the requests and links to the golden files.

Registration Updates
....................

Leshan maintains registrations of endpoints. An endpoint can be registered or
unregistered. To maintain its registration, an endpoint must send an update to
Leshan regularly. If an endpoint does not send an update within the specified
duration, it is considered offline and will be unregistered by Leshan.

Leshan forwards those registration events to the backend server. The backend
server stores the registration events in the database. This allows to use the
generic database model for the registration events as well. All received
registration events are stored in the database and can be used for statistics.

.. _data-flow-backend-to-endpoint-label:

Data Flow: Backend -> Endpoint
------------------------------

:term:`Endpoints <endpoint>` often operate in queue mode, meaning they are not
always online. The LwM2M Server is aware of the current status of a device
(Online/Offline) and communicates this status to the backend server. Leshan
does not queue pending data that should be sent to the device when it comes
online. The backend server must handle this by itself so it has to have a
representation of the current status of each device as well as the data to be
send. The resource table ``EndpointOperation`` is used to store pending
operations that should be sent to the endpoint while it is online.

Once an endpoint updates it's registration (LwM2M Update Operation) Leshan
notifies the backend. The backend checks the ``EndpointOperation`` table for
pending operations and sends them to the device through the command API that
Leshan hosts (see :doc:`gateway_contract`). Leshan keeps the HTTP request open
until the device answers or a timeout is generated. Endpoints can be slow to respond (several
Seconds), so the backend has to handle the ReST API call in an asynchronous
manner. By only sending data to endpoints while they are online, the backend
can be sure that the ReST API calls are not open for a long time.

Asynchronous Communication
..........................

Given that endpoints are comparably slow to respond, handling communication
asynchronously is essential for efficient operation. This can be effectively
managed using Celery, a distributed task queue. When Leshan notifies the
backend of an endpoint status update, Celery can be used to handle the
long-running API calls, ensuring that the backend remains responsive and
scalable. As the backend communicates with many endpoints simultaneously, an
efficient queing mechanism is essential to ensure that the system remains
responsive and scalable.

Before the backend executes the API call, it updates the endpointOperation
status to ``SENDING``, indicating an ongoing operation.

Once the API call is complete the database will be updated with the result
(e.g. ``CONFIRMED``, ``FAILED``, ``QUEUED``) depending on the result of the
request. The ``FAILED`` status is assigned at once if the endpoint rejects the
operation, else after 3 attempts. Retransmissions are triggered when the
endpoint updates it's registration the next time.

Example Communication
.....................

The following example shows how the backend server can send a firmware download
link resource ``Package URI 5/0/1`` to an endpoint:

#. User creates new ``EndpointOperation``: resource path ``5/0/1``, value
   ``https://url.com/fw.bin``.
#. Backend checks endpoint online status.
#. If endpoint is offline, no further action is taken right away.
#. Endoint comes online, Leshan sends update to the backend.
#. Backend checks ``EndpointOperation`` table for pending operations for the
   endpoint.
#. Finds pending operation, send resource to endpoint via the Leshan ReST API.
#. Pending operation is marked ``CONFIRMED`` if the endpoint acknowledges the
   operation.
