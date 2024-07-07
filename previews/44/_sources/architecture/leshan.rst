Leshan
======

Build and Run
-------------

The Leshan server can also run locally, without the need of a docker container.

.. code-block:: console

  host:~$ sudo apt update
  host:~$ sudo apt install openjdk-17-jdk maven
  host:~$ source venv/bin/activate
  host:~$ cd flownexus_workspace/lwm2m_server/server/leshan
  host:lwm2m_server/server/leshan$ ./leshan_build_run.sh

The Leshan server should now be up and running under the following URL:
``http://localhost:8080``.
