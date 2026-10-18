Endpoint Interactions
=====================

flownexus can interact with any endpoint via the LwM2M methods ``Read``,
``Write`` and ``Execute``.


Read
----

Django reads the Device object (``/3``) after each registration of an
endpoint.

.. note::
   Other reads are currently not supported

Write
-----

See Chapter :ref:`data-flow-backend-to-endpoint-label` for more details.


Execute
-------

Django sends a pending operation for a resource of data type ``NONE`` as
execute, for example ``5/0/2`` during a firmware update. See Chapter
:ref:`data-flow-backend-to-endpoint-label` for more details.

Observe
-------

.. note::
   Currently not supported. Endpoints report values with LwM2M Send, see
   chapter :ref:`events-via-send-label`.
