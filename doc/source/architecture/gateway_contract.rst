Gateway Contract
================

The Leshan gateway and Django communicate over two internal HTTP APIs. The
golden files in ``contract/gateway/`` record the exact requests and responses
and are the reference for both sides. ``contract/gateway/README.rst`` describes
their format and how to re-record them.

.. list-table::
   :header-rows: 1
   :widths: 20 40 40

   * - API
     - Direction and base URI
     - Configuration
   * - Ingest API
     - Gateway to Django, ``/flownexus/ingest/``
     - ``DATA_SENDER_URI`` on the gateway (default ``http://0.0.0.0:8000``)
   * - Command API
     - Django to gateway, ``/api/clients/``
     - ``LESHAN_URI`` on Django (default ``http://0.0.0.0:8080``); the gateway
       listens on port 8080

Both APIs have no authentication. Run them on an internal network only.

Ingest API
----------

The gateway sends only two types of requests. Both are ``POST`` requests with
a JSON body. The gateway does not observe resources, so device values reach
Django only with an LwM2M Send or a read through the command API.

Registration Events
...................

The gateway posts each registration change to
``/flownexus/ingest/registration`` with the body
``{"ep": <endpoint>, "event": <event>, "time": <ISO 8601>}``. Golden file:
``contract/gateway/ingest/registration_lifecycle.json``.

.. list-table::
   :header-rows: 1
   :widths: 16 30 54

   * - ``event``
     - Cause and ``time``
     - Django action
   * - ``registered``
     - LwM2M Register; registration time
     - Sets the endpoint registered, reads ``/3`` (see below) and sends pending
       operations.
   * - ``updated``
     - LwM2M Update; time of the update
     - Sends pending operations.
   * - ``unregistered``
     - LwM2M De-register or expired registration; gateway time of the event.
       Not sent when a new registration replaces the old one (device reboot).
     - Sets the endpoint not registered.

Django creates an unknown endpoint on the first event. It stores each event as
a resource of the internal object ``10240`` (``0`` registered, ``1``
unregistered, ``2`` updated) with the event time in epoch milliseconds as
value, so the database model and the frontend need no separate event table.
Object ``10240`` exists only in Django and is not part of the wire format.
An event older than the newest stored event of the endpoint, for example a
late retry, is stored but does not change the registration state.

After a ``registered`` event, the Celery task ``read_device_object`` reads
``/3`` through the command API and stores the content with the composite
resource serializer. Django, not the gateway, decides which objects to read
after a registration.

LwM2M Send
..........

The gateway posts each LwM2M Send to ``/flownexus/ingest/resource/timestamped``
with the body ``{"ep": <endpoint>, "val": [{<timestamp>: {"nodes": {<path>:
<node>}}}]}``. ``val`` has one entry per timestamp. The key is an ISO 8601
timestamp, or ``"null"`` if the device sent no timestamp; Django then uses the
time of reception. A node is the Leshan JSON form of an LwM2M node (``kind``,
``id``, ``type``, ``value``, ``values``, ``instances``, ``resources``).

.. list-table::
   :header-rows: 1
   :widths: 45 55

   * - Golden file in ``contract/gateway/ingest/``
     - Device input
   * - ``send_single_resource.json``
     - Send of one resource
   * - ``send_multiple_resources.json``
     - Send of resources from two objects
   * - ``send_object_instance.json``
     - Send of a whole object instance
   * - ``send_cached_timeseries.json``
     - Send of cached values, each with its own timestamp

Django creates an :term:`Event` when a Send contains more than one path or
more than one timestamp. Django skips a resource that has no ``ResourceType``
row.

Leshan rejects a Send that contains two values of one path with the same
timestamp, and the device receives ``4.00``. The Zephyr data cache stores
timestamps in seconds, so if a device writes a cached resource more often than
once per second, the device loses the whole Send.

Single and Composite Resources
..............................

Django also accepts ``/flownexus/ingest/resource/single``
(``{"ep", "obj_id", "val": <node>}``) and
``/flownexus/ingest/resource/composite`` (``{"ep", "val": {"/<obj>":
<object node>}}``). The gateway does not send these requests. The mock device
simulator in ``devtools/mock`` uses the single resource format, and
``read_device_object`` uses the composite resource serializer directly. No
golden files exist for these formats.

Responses and Delivery
......................

Django answers ``201`` for a stored request and ``400`` for an invalid body.
The gateway handles the result as follows:

- ``2xx``: the request is complete.
- ``4xx``: the gateway logs the error and drops the request.
- ``5xx`` or connection error: the gateway retries the request with
  exponential backoff (2 s, then doubled), 6 attempts in total. The last
  attempt starts about 62 s after the first one. After that, the gateway drops
  the request.

Each attempt has an HTTP timeout of 10 s. The gateway keeps pending retries in
memory only, at most 10000 at a time, so a gateway restart loses them. The order of requests is not
guaranteed: a retried request can arrive after later requests.

Command API
-----------

Django sends commands to ``/api/clients/{endpoint}/{path}`` on the gateway.
``{path}`` is an LwM2M path such as ``3``, ``3/0`` or ``5/0/1``.

.. list-table::
   :header-rows: 1
   :widths: 12 30 58

   * - Method
     - LwM2M operation
     - Path and body
   * - ``GET``
     - Read
     - Any path. No body.
   * - ``PUT``
     - Write (replace)
     - Resource path. The body is one LwM2M node of kind ``singleResource``,
       for example ``{"id": 14, "kind": "singleResource", "value": "+02:00",
       "type": "STRING"}``. ``type`` is ``STRING``, ``INTEGER``,
       ``UNSIGNED_INTEGER``, ``FLOAT``, ``BOOLEAN`` (``true``, ``false``, ``0``
       or ``1``), ``OPAQUE`` (hex string) or ``TIME`` (epoch milliseconds).
   * - ``POST``
     - Execute
     - Resource path. An optional plain text body holds the execute arguments.

Query parameters:

- ``timeout``: seconds the gateway waits for the device response, a positive
  integer. The default is 5 s.
- ``format``: content format name for the downlink request, for example
  ``CBOR``. Without it, Leshan selects the content format.

An invalid ``timeout``, an unknown ``format``, or a written resource whose
``id`` differs from the resource ID in the path is answered with ``400``.

The response body is JSON. If the device answers, the body contains
``status`` (Leshan response code name), ``code`` (CoAP code, for example
``2.05``), ``content`` (the read node, for a successful read only) and
``error`` (the device error message, if the device sent one).

.. list-table::
   :header-rows: 1
   :widths: 10 50 40

   * - Status
     - Meaning
     - Body
   * - ``200``
     - The device answered with success (CoAP ``2.xx``).
     - ``status``, ``code``, ``content``
   * - ``400``
     - Invalid path, body, query parameter or request.
     - ``error``
   * - ``404``
     - No registered client with this endpoint name.
     - ``error``
   * - ``502``
     - The device answered with an error (CoAP ``4.xx`` or ``5.xx``).
     - ``status``, ``code``, ``error``
   * - ``502``
     - The device response is invalid.
     - ``error`` (no ``code``)
   * - ``503``
     - The client sleeps, or Leshan rejected or cancelled the request.
     - ``error``
   * - ``504``
     - The device did not answer within ``timeout``.
     - ``error``

.. list-table::
   :header-rows: 1
   :widths: 45 55

   * - Golden file in ``contract/gateway/command/``
     - Case
   * - ``read_device_object.json``
     - Read of ``/3``, ``200``
   * - ``write_resource.json``
     - Accepted write, ``200``
   * - ``execute_resource.json``
     - Execute without arguments, ``200``
   * - ``write_rejected.json``
     - Write of a read-only resource, ``502`` with code ``4.05``
   * - ``device_timeout.json``
     - Write to an offline device, ``504``
   * - ``unknown_endpoint.json``
     - Command for an unregistered endpoint, ``404``
   * - ``invalid_request.json``
     - Unknown format and mismatched resource ID, ``400``

Use of the Command API in Django
................................

The Celery task ``send_operation`` sends an ``EndpointOperation`` to
``{object}/{instance_id}/{resource}``. ``instance_id`` defaults to ``0``.
Django sends a resource of data type ``NONE`` as execute without body, and
each other resource as write with ``format=CBOR``. The task maps the response
to the operation status:

- ``2xx``: ``CONFIRMED``.
- ``502`` with ``code``: ``FAILED`` at once, without retry.
- ``400``: ``FAILED`` at once, without retry. The request is invalid.
- Each other status or a connection error: ``QUEUED`` for a retry, and
  ``FAILED`` after 3 attempts. Django sends a queued operation again the next
  time it processes the pending operations of the endpoint, for example after a
  registration update.

A ``504`` does not prove that the device did not apply the operation, so a
retry can apply a write or an execute a second time.

Timeouts
--------

.. list-table::
   :header-rows: 1
   :widths: 50 50

   * - Timeout
     - Value
   * - Device response (command API ``timeout``)
     - 5 s (default and value that Django sends)
   * - HTTP request from Django to the command API
     - Device timeout + 5 s
   * - HTTP request from the gateway to the ingest API
     - 10 s per attempt
   * - Ingest retries
     - 2, 4, 8, 16 and 32 s between the 6 attempts
