Build and Deploy
================

Development Setup
-----------------

The build instructions in the documentation are tested for a native Linux
Machine. For MacOS or Windows consider creating a docker container build. One
of the developers uses the following `devcontainer.json` build environment:

.. code-block:: json

  {
    "name": "Ubuntu",
    "image": "mcr.microsoft.com/devcontainers/base:jammy",
    "runArgs": [
      "--cap-add=NET_ADMIN",
      "--cap-add=MKNOD",
      "--device=/dev/net/tun",
      "--sysctl=net.ipv6.conf.all.disable_ipv6=0",
      "--sysctl=net.ipv6.conf.default.disable_ipv6=0"
    ],
    "postCreateCommand": "apt-get update && apt-get install -y iproute2 && echo 'IPv6 is enabled.'",
    "remoteUser": "root"
  }

Before you we start with any development here are a few things you should get
configured:

* Get the Zephyr SDK downloaded and configured in your root directory. You can
  find the instructions `here
  <https://docs.zephyrproject.org/latest/develop/toolchains/zephyr_sdk.html>`_.

* Setup a virtual environment for the project.

.. code-block:: console

  host:~$ sudo apt update && sudo apt upgrade
  host:~$ sudo apt install python3-pip python3.10-venv
  host:~$ python3.10 -m venv venv
  host:~$ source venv/bin/activate
  host:~$ pip install --upgrade pip && pip install west
  host:~$ west init -m https://github.com/jonas-rem/lwm2m_server --mr main flownexus_workspace
  host:~$ cd flownexus_workspace
  host:~/flownexus_workspace$ west update

Container Environment
---------------------

Both components run in a Docker container. The Leshan server is running in a
``openjdk:17-slim`` container and the Django server is running in a
``python:3.11-slim`` container. This allows for an easy and reproducible setup
of the server.

  .. uml::
   :caption: Both components running in one machine using Docker Compose

   @startuml
   package "Docker Compose Environment"  #DDDDDD {
     [Leshan] as Leshan
     [Django] as Django
     database "Database" as DB
     Leshan <-right-> Django : REST API
     Django <-down-> DB
   }
   @enduml

The following diagram shows the Docker Compose environment. The file
``docker-compose.yml`` defines the services and their configuration. The file
``Dockerfile.leshan`` defines the Leshan container and the file
``Dockerfile.django`` defines the Django container.

.. warning::

  Make sure to change the password to the admin console as well as other
  settings like SECRET_KEY, DEBUG flag in a production environment!

The container can be build and started with the following commands:

.. code-block:: console

  host:~/flownexus_workspace/lwm2m_server/server$ docker compose build
  [+] Building 0.5s (20/20) FINISHED                               docker:default
   => [leshan internal] load build definition from Dockerfile.leshan         0.0s
   => [leshan internal] load metadata for docker.io/library/openjdk:17-slim  0.4s
   => [django internal] load build definition from Dockerfile.django         0.0s
   => [django internal] load metadata for docker.io/library/python:3.11-sli  0.4s
   => [leshan 1/5] FROM docker.io/library/openjdk:17-slim@sha256:aaa3b3cb27  0.0s
   => [django 1/5] FROM docker.io/library/python:3.11-slim@sha256:d11b9bd5e  0.0s
   => CACHED [leshan 2/5] WORKDIR /leshan                                    0.0s
   => CACHED [leshan 3/5] COPY . /leshan/                                    0.0s
   => CACHED [leshan 4/5] RUN apt-get update &&     apt-get install -y mave  0.0s
   => CACHED [leshan 5/5] RUN chmod +x /leshan/leshan_build_run.sh           0.0s
   => => exporting layers                                                    0.0s
   => => writing image sha256:a017577ba2b175374148f5c3f128ac117ba5436ceaeff  0.0s
   => => naming to docker.io/library/server-leshan                           0.0s
   => CACHED [django 2/5] WORKDIR /django                                    0.0s
   => CACHED [django 3/5] COPY . /django/                                    0.0s
   => CACHED [django 4/5] RUN pip install --no-cache-dir -r /django/require  0.0s
   => CACHED [django 5/5] RUN chmod +x /django/django_start.sh               0.0s
   => => writing image sha256:1c88f1227753b08cf994c4e61d5cdcf97d68f260c99ad  0.0s
   => => naming to docker.io/library/server-django                           0.0s


.. code-block:: console

  host:~/flownexus_workspace/lwm2m_server/server$ docker compose up
  [+] Running 2/0
   ✔ Container server-leshan-1  Created                                      0.0s
   ✔ Container server-django-1  Created                                      0.0s
  Attaching to django-1, leshan-1
  [..]
  django-1  | Starting development server at http://0.0.0.0:8000/
  leshan-1  | [main] INFO org.eclipse.leshan.server.LeshanServer - CoAP over UDP endpoint based on Californium library available at coap://0.0.0.0:5683.
  leshan-1  | LeshanServer started
  ^CGracefully stopping... (press Ctrl+C again to force)
  [+] Stopping 2/2
   ✔ Container server-django-1  Stopped                                     10.3s
   ✔ Container server-leshan-1  Stopped                                     10.5s
