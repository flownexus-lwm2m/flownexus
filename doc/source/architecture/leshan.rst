Leshan
======

Build and Run
-------------

``server/leshan/Containerfile`` builds the Leshan gateway image. The build
stage runs ``mvn package`` (including the tests), and the runtime stage
contains only the JRE and ``leshan-svr.jar``. Compose, the E2E suite, and CI
use this Containerfile.

.. code-block:: console

  host:~/workspace/flownexus$ make leshan-image
  host:~/workspace/flownexus$ podman run --rm -p 5683:5683/udp -p 8080:8080 \
      -e DATA_SENDER_URI=http://host.containers.internal:8000 \
      localhost/flownexus-leshan:latest

The gateway listens on CoAP port 5683/udp and on HTTP port 8080. These ports
are not configurable. ``GET /health`` returns 200 when the web server runs and
does not read the registration store.

CI publishes the image as ``ghcr.io/flownexus-lwm2m/flownexus-leshan`` on each
push to ``main`` and each ``v*`` tag, after the E2E suite passes. The tags are
``sha-<short sha>`` and the ``git describe --tags`` output. GHCR creates a new
organization package as private, so a maintainer must set the package
visibility to public once after the first push.

Leshans Role in flownexus
-------------------------

Lehsan is considered a production ready LwM2M server and is used in many
commercial products. It is used as an LwM2M server in flownexus. It is
responsible for registering and managing :term:`endpoint`. There is no application
specific logic implemented in Leshan related Java code within flownexus. The
goal is to have all application logic within the Django application.

Leshan can be seen as a proxy between the LwM2M endpoints Django. There is no
direct communication between Django and endpoints.

.. _lwm2m-observe-label:

LwM2M Observe
-------------

.. glossary::

  LwM2M observe
    The `LwM2M observe` operation allows an LwM2M Server to monitor changes to
    specific Resources, Resources within an Object Instance, or all Object
    Instances of an Object on an LwM2M Client. An endpoint must
    remember these observation requests until re-registration.

  Single and CompositeObserve
    Leshan supports two types of observe requests: Single and CompositeObserve.
    SingleObserve is a simple observe request for a single resource.
    CompositeObserve is a more complex observe request that subscribes to
    multiple :term:`Resources <Resource>` of one :term:`Object`.


Once an endpoint registers to Leshan, Leshan will initiate an observe request
to selected resources. With every new registration of an endpoint, the observe
requests are re-initiated.

.. note::
   The observe initiation will move from Leshan to Django with future versions.
   Django is informed about new registrations and will then initiate the
   observe requests. This allows a more centralized approach and better control
   over the observe requests via the database model.

   For testing, the Leshan server currently initiates the following two observe
   requests:

   - SingleObserve (Temperature Sensor Value): ``{3303, 0, 5700}``
   - CompositeObject (Custom Object Id): ``{10300}``

CoAP Block-wise Transfer Limit
-------------------------------

LwM2M devices may send large payloads (e.g. batched sensor data via the LwM2M
Send operation) using CoAP block-wise transfer (RFC 7959). In this mode the
device splits the payload into smaller blocks and sends them sequentially.
Californium, the CoAP library underlying Leshan, reassembles the blocks in
memory before passing the complete body to the application.

To guard against memory exhaustion, Californium enforces a maximum reassembly
size via the ``MAX_RESOURCE_BODY_SIZE`` configuration key. If the total
assembled payload exceeds this limit, the server aborts the transfer and returns
a ``4.13 Request Entity Too Large`` CoAP response to the device.

The Californium default for this value is 8 KB. flownexus raises it to **20 KB**
to accommodate larger LwM2M Send payloads. The setting is applied in
``LeshanSvr.java`` when constructing the endpoints provider:

.. code-block:: java

   new CaliforniumServerEndpointsProvider.Builder()
       .setConfiguration(cfg ->
           cfg.set(CoapConfig.MAX_RESOURCE_BODY_SIZE, 20480))
       .build();

If devices need to transmit payloads larger than 20 KB, increase the value
accordingly and rebuild the Leshan container.
