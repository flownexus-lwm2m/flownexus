Flownexus LwM2M client
######################

LwM2M client for ``native_sim``, used by the Flownexus device tests and
end-to-end (E2E) tests. It follows the structure of Zephyr's
``samples/net/lwm2m_client``: ``main.c`` starts the network and the
registration (RD) client, each LwM2M object has its own file, and all LwM2M
interaction goes through the Zephyr ``lwm2m`` shell.

Structure
*********

``src/main.c``
   Network and Security object setup, RD client and L4 event callbacks.
   The engine pauses on network loss and resumes on recovery.
``src/device.c``
   Device object (3). The callbacks for reboot (3/0/4), factory reset
   (3/0/5) and writes to the UTC offset (3/0/14) only write a log line, so
   tests can observe them.
``src/sensors.c``
   IPSO temperature (3303) and humidity (3304) objects.
``src/fota.c``
   Simulated Firmware Update object (5). Writes to the Package URI (5/0/1)
   and the Update execute (5/0/2) only write a log line. The client does not
   download the package. On execute, it sends the state (5/0/3) to the
   server.
``src/shell.c``
   ``flownexus`` shell commands to start the RD client, to simulate network
   loss and to set and send the firmware update state and result.

To add an object, add a ``<name>_obj_init()`` in a new file, declare it in
``src/app.h`` and call it from ``main()``.

Build and run
*************

From the repository root::

   make build-sim
   devtools/zephyr/client/build/zephyr/zephyr.exe --uart_stdinout

With ``--uart_stdinout``, shell and logs share one terminal. Without it, logs
stay on stdout and the shell runs on its own pseudo terminal (PTY). The binary
prints the PTY path at boot. Attach with ``screen /dev/pts/N``, or start the
binary with ``--attach_uart``.

On ``native_sim``, the client uses the native simulator offloaded sockets
(NSOS, see ``boards/native_sim_native_64.conf``), so no TAP interface is
necessary. The default server is ``coap://127.0.0.1:5683``.

These overlays are available:

- ``overlay-dtls.conf``: DTLS with PSK
- ``overlay-bootstrap.conf``: bootstrap server
- ``overlay-queue.conf``: queue mode

Set ``CONFIG_LWM2M_APP_AUTOSTART=y`` to register with ``CONFIG_LWM2M_APP_ID``
at boot.

Shell
*****

::

   flownexus start <endpoint> [server-uri]      # first start
   lwm2m write /3303/0/5700 -f 21.5             # set a sensor value
   lwm2m send /3303/0/5700                      # LwM2M Send
   lwm2m update                                 # registration update
   lwm2m stop / lwm2m start <endpoint>          # deregister / restart
   flownexus net down / flownexus net up        # simulate network loss
   flownexus fota state 2                       # set and send 5/0/3
   flownexus fota result 8                      # set and send 5/0/3, 5/0/5
   lwm2m write /3/0/3 -s 2.0.0                  # firmware version
   lwm2m read /3/0/14 -s

The ``lwm2m`` shell needs a client context, so the first start must use
``flownexus start`` (or autostart). The optional server URI of
``flownexus start`` overrides ``CONFIG_LWM2M_APP_SERVER``.

Tests
*****

Twister runs ``test_shell.yml`` with the shell harness and builds each
overlay::

   west twister -T devtools/zephyr/client -p native_sim/native/64

The full-stack scenarios against Django and Leshan are in
``devtools/zephyr/e2e``.
