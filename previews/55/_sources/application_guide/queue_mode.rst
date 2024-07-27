Queue Mode
==========

When configuring a energy saving endpoint that uses LTE-M or NB-IoT, queue mode
must be enabled in Zephyr so the device will sleep between data transmissions.
The `Zephyr documentation
<https://docs.zephyrproject.org/latest/connectivity/networking/api/lwm2m.html>`_
explains the LwM2M Client in Zephyr in detail.

.. code-block:: kconfig
  :caption: Enable Queue Mode in Zephyr with a registration update interval of
   10 minutes

   CONFIG_LWM2M_QUEUE_MODE_ENABLED=y
   CONFIG_LWM2M_QUEUE_MODE_UPTIME=20
   CONFIG_LWM2M_RD_CLIENT_STOP_POLLING_AT_IDLE=y

   # Default lifetime is 10 minutes
   CONFIG_LWM2M_ENGINE_DEFAULT_LIFETIME=600

See chapter :ref:`data-flow-backend-to-endpoint-label` to know know more about
how queue mode is implemented in FlowNexus.

eDRX Settings
-------------

eDRX (Extended Discontinuous Reception) is a feature that allows the device to
sleep for longer periods of time. The device will wake up periodically to check
downlink paging messages. If new messages are available, the device will stay
awake to receive them. Otherwise, the device will go back to sleep. - `Nordic
Devzone Article
<https://devzone.nordicsemi.com/nordic/nordic-blog/b/blog/posts/maximizing-battery-lifetime-in-cellular-iot-an-analysis-of-edrx-psm-and-as-rai>`_

Setting the eDRX interval to a value significantly smaller than the timeout
value of the LwM2M server would theoretically allow FlowNexus to reach
endpoints at any time.

.. warning::

   This approach has not yet been tested! The typical way is to configure
   endpoints to connect to the server within specific intervals. Inbetween
   those intervalls, the endpoint will sleep and can't be reached from the
   server.
