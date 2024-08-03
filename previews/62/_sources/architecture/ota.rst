Over the Air Updates
====================

Over the Air (OTA) updates are a way to update the firmware of a device
remotely. This is a mandatory feature for any IoT device. The device must be
able to update its firmware without any physical user intervention.

flownexus implements OTA updates according to the LwM2M protocol. The LwM2M
protocol specifies how to update the firmware of a device. The OTA process is
implemented by sending a link to a firmware via LwM2M object 5/0/1 - Package
URI. This method is called Pull via HTTP(s) and is faster, compared to a
transfer via CoAP. Updates via CoAP blockwise transfer to download the firmware
are not supported.

More information about a possible firmware implementation can be found in the
``lwm2m_client`` firmware sample at
``flownexus/simulation/lwm2m_client/src/firmware_update.c``.

.. note::

   Firmware Updates are implemented in the LwM2M server and the example
   firmware. A set up a PKI with self-signed certificates is required for the
   server to communicate with the device via https. This setup will be
   described in upcoming releases shortly.

Update process of a Firmware
----------------------------

The update process is described in detail in the `LwM2M core specification
v1.1.1`_ Chapter *E.6 LwM2M Object: Firmware Update*. This chapter summarizes
the update process:

1. flownexus sends a link to the firmware to the device via LwM2M object 5/0/1
   - Package URI. It is a relative link to the firmware on the server, e.g.
   ``/media/firmware/v0.1.0.bin``. The host ``https://flownexus.org`` is
   fixed in firmware.
2. The device downloads the firmware from the server via http(s) and sets the
   state to ``STATE_DOWNLOADING``.
3. The device sets the state to ``STATE_DOWNLOADED`` after the download is
   complete.
4. flownexus executes the command 5/0/2 - Update to the device.
5. The device sets the state to ``STATE_UPDATING`` upon receiving the command.
6. The device updates the firmware and communicates the result to flownexus.

This process ensures that errors during the update process are handled and
communicated to the backend.

States of a OTA Update
......................

There are 4 device states during an OTA update. flownexus tracks the state of
the device during the update process in the database (FirmwareUpdate table).
Once the update is completed (failed or successful), the state is set always
set to ``STATE_IDLE``.


.. table:: Device States during an OTA Update

   +-------------------+-----------------------+
   | State             | Description           |
   +===================+=======================+
   | STATE_IDLE        | device is idle        |
   +-------------------+-----------------------+
   | STATE_DOWNLOADING | device is downloading |
   +-------------------+-----------------------+
   | STATE_DOWNLOADED  | download is complete  |
   +-------------------+-----------------------+
   | STATE_UPDATING    | device is updating    |
   +-------------------+-----------------------+

Result Codes for an OTA Update
..............................

For every OTA update, a result is generated after the update failed or
successful. There can be only one active OTA update at a time for each client.
An active OTA is indicated by the result ``RESULT_DEFAULT``. The result for
each OTA update is stored in the database (FirmwareUpdate table).

.. table:: Result Codes for an OTA Update

   +-------------------------+------------------------+
   | Result                  | Description            |
   +=========================+========================+
   | RESULT_DEFAULT          | default state          |
   +-------------------------+------------------------+
   | RESULT_SUCCESS          | update was successful  |
   +-------------------------+------------------------+
   | RESULT_NO_STORAGE       | no storage available   |
   +-------------------------+------------------------+
   | RESULT_OUT_OF_MEM       | out of memory          |
   +-------------------------+------------------------+
   | RESULT_CONNECTION_LOST  | connection was lost    |
   +-------------------------+------------------------+
   | RESULT_INTEGRITY_FAILED | integrity check failed |
   +-------------------------+------------------------+
   | RESULT_UNSUP_FW         | unsupported firmware   |
   +-------------------------+------------------------+
   | RESULT_INVALID_URI      | invalid uri provided   |
   +-------------------------+------------------------+
   | RESULT_UPDATE_FAILED    | update failed          |
   +-------------------------+------------------------+
   | RESULT_UNSUP_PROTO      | unsupported protocol   |
   +-------------------------+------------------------+


.. _LwM2M core specification v1.1.1: https://www.openmobilealliance.org/release/LightweightM2M/V1_1_1-20190617-A/OMA-TS-LightweightM2M_Core-V1_1_1-20190617-A.pdf


Leshan Data Format
..................
