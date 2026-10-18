Weblog
======

Gateway Contract and Leshan 2.0.0-M18
-------------------------------------
.. admonition:: #4
   :class: alert alert-info

   :Date: Oct 18, 2026
   :Author: https://github.com/jonas-rem
   :Tags: Release Notes, Leshan

   Behavior changes of the Leshan gateway and its contract to Django
   (:doc:`/architecture/gateway_contract`):

   - The gateway runs Leshan 2.0.0-M18, Jetty 12 and Java 25.
   - Golden files in ``contract/gateway`` record the gateway behavior; the E2E
     suite and the Django tests check both sides against them. Java unit tests
     cover the gateway's command mapping, write parser and ingest retry.
   - A command that the device rejects ends as ``FAILED`` in Django. Before,
     the gateway answered HTTP 200 and Django recorded ``CONFIRMED``.
   - The gateway posts registration events to
     ``/flownexus/ingest/registration`` instead of object 10240 readings.
   - Django reads the Device object after a registration. The gateway no
     longer reads ``/3`` or sets observations on its own.
   - A device that registers again without deregistering, for example after
     a reboot, stays registered in Django. Late registration events no longer
     change the registration state.
   - An invalid command request (unknown format, bad timeout, mismatched
     resource ID) is answered with ``400`` and ends as ``FAILED`` in Django.
   - The gateway retries ingest requests for about one minute while Django is
     unavailable.
   - Operations can target object instances other than 0.
   - Django skips resources without a resource type instead of rejecting the
     whole request.
   - The demo servlets (events, object specs, client listing and the other
     LwM2M operations) are removed. The command API serves read, write and
     execute.

Release v0.1.0
--------------
.. admonition:: #3
   :class: alert alert-info

   :Date: Aug 4, 2024
   :Author: https://github.com/jonas-rem
   :Tags: Release Notes

   First release of the project. This is a development release.

   - Created a flownexus logo.
   - Generic database model for LwM2M objects.
   - Added a frontend mockup based on AtminLTE.
   - ReST APIs inbetween Leshan and Django.
   - Asynchronous task queue for Endpoint interactions from Django
     via Celery.
   - Bidirectional communication between L2M2M endpoints and Django via Leshan.
   - Subscribe to single and composite Observations in Leshan statically.
   - OTA Update functionality on the server side. Full-functioning
     firmware example pending.

Update Documentation & Add Weblog
---------------------------------
.. admonition:: #2
   :class: alert alert-info

   :Date: May 15, 2024
   :Author: https://github.com/Kappuccino111
   :Tags: Add, Update

   - Switched the new documentation to *Sphinx-Book-Theme* for better readability and navigation.
   - Added a new section for the weblog to keep track of updates and changes in the project.

Project Starts
--------------
.. admonition:: #1
   :class: alert alert-info

   :Date: January 1, 2024
   :Author: https://github.com/jonas-rem
   :Tags: Update

   - The project has started and the initial documentation has been added.
