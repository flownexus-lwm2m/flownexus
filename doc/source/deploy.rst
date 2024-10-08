Build and Deploy
================

Build Setup
-----------

The build instructions in the documentation are tested for a native Linux
Machine. For MacOS or Windows consider creating a docker container build. One
of the developers uses the following `devcontainer.json` build environment:

.. code-block:: json

  {
    "name": "Ubuntu",
    "image": "mcr.microsoft.com/devcontainers/base:jammy",
    "features": {
		"ghcr.io/devcontainers/features/docker-in-docker:2": {},
		"ghcr.io/devcontainers/features/docker-outside-of-docker:1": {}
	 },
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
  host:~$ mkdir workspace && cd workspace
  host:~/workspace$ west init -m https://github.com/jonas-rem/flownexus --mr main
  host:~/workspace$ west update

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

  host:~/workspace/flownexus/server$ docker compose build
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

  host:~/workspace/flownexus/server$ docker compose up
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

.. _setup-a-virtual-server-label:

Setup a Virtual Server
----------------------

flownexus can be deployed to a virtual server. This chapter explains a basic
setup of a virtual server with a domain name. A requirement is to have a Linux
server and a domain name. The domain name must point to the server, e.g. via a
A/AAAA-Record.

The setup has been tested with a Debian 12 server with a 1C/1GB RAM
configuration.

CA and self-signed Certificate
..............................

Leshan and the HTTPs download server for firware binaries use self-signed
certificates. The flownexus frontend uses certificates that have been issued
via Let's Encrypt. The following commands create a self-signed certificate for
the domain ``flownexus.org``:

**Create a Certificate Authority (CA)**

1. Generate the CA Private Key:

   .. code-block::

      openssl ecparam -genkey -name prime256v1 -out ca.key

2. Create a Self-Signed CA Certificate with 100 years validity:

   .. code-block::

      openssl req -new -x509 -key ca.key -out ca.crt -days 36500 -subj "/CN=flownexus.org"


**Create a Server Certificate Signed by the CA**

1. Generate the Server Private Key

   .. code-block::

      openssl ecparam -genkey -name prime256v1 -out fw_flownexus_org.key

2. Generate a Certificate Signing Request (CSR)

   .. code-block::

        openssl req -new -key fw_flownexus_org.key -out fw_flownexus_org.csr -subj "/CN=fw.flownexus.org"

3. Generate the Server Certificate Signed by the CA

   .. code-block::

      openssl x509 -req -in fw_flownexus_org.csr -CA ca.crt -CAkey ca.key -CAcreateserial -out fw_flownexus_org.crt -days 3650 -sha256


**Generated Files**

- ``ca.key``: CA private key
- ``ca.crt``: CA certificate
- ``fw_flownexus_org.key``: Server private key
- ``fw_flownexus_org.csr``: Server certificate signing request
- ``fw_flownexus_org.crt``: Server certificate signed by the CA

Copy the server certificate and key to the server and store then in
``/etc/nginx/ssl/``. Keep the CA certificate and key in a secure location.

Nginx as Reverse Proxy
......................

The following steps show how to configure Nginx as a reverse proxy for the
flownexus server. The Nginx server listens on port 443 and forwards the
requests to the Django server running on port 8000:


.. code-block:: console
   :caption: Nginx setup, create Let's Encrypt certificate


   # Update Sytem, install required packages and enable the firewall
   vserver:~/ apt update
   vserver:~/ apt install git docker docker-compose nginx certbot python3-certbot-nginx

   # Generate a certificate with letsencrypt:
   vserver:~/ certbot --nginx -d flownexus.org -d www.flownexus.org
   vserver:~/ Create nginx config at /etc/nginx/sites-available/flownexus (see example below)


.. code-block:: nginx
   :caption: Nginx config for the Frontend ``/etc/nginx/sites-available/flownexus.org``
   :linenos:

   server {
           listen 443 ssl http2;
           listen [::]:443 ssl http2;
           server_name flownexus.org www.flownexus.org;

           error_log /var/log/nginx/flownexus.org.error.log;
           access_log /var/log/nginx/flownexus.org.access.log;
           ssl_certificate /etc/letsencrypt/live/flownexus.org/fullchain.pem; # managed by Certbot
           ssl_certificate_key /etc/letsencrypt/live/flownexus.org/privkey.pem; # managed by Certbot

           location / {
                   proxy_pass http://127.0.0.1:8000/;
                   proxy_set_header Host $http_host;
                   proxy_set_header X-Real-IP $remote_addr;
                   proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
                   proxy_set_header X-Forwarded-Proto $scheme;
                   proxy_set_header X-Frame-Options SAMEORIGIN;
           }
   }

   server {
           listen 80;
           listen [::]:80;
           server_name flownexus.org www.flownexus.org;

           # Redirect all HTTP requests to HTTPs
           return 301 https://$host$request_uri;
   }


.. code-block:: nginx
   :caption: Nginx config for the https dl Server ``/etc/nginx/sites-available/fw.flownexus.org``
   :linenos:

   server {
           listen 443 ssl;
           listen [::]:443 ssl http2;
           server_name fw.flownexus.org;

           ssl_certificate /etc/nginx/ssl/fw_flownexus_org.crt;
           ssl_certificate_key /etc/nginx/ssl/fw_flownexus_org.key;

           location /binaries {
                   root /var/www/flownexus/;
                   # Debug option: uncomment to list files
                   # autoindex on;
           }
   }

   server {
        listen 80;
        server_name fw.flownexus.org;

        # Redirect all HTTP requests to HTTPS
        return 301 https://$host$request_uri;
   }


After creating the Nginx config, activate the config and restart the Nginx.

.. code-block:: console
   :caption: Activate the Nginx config

   # Activate the Nginx config:
   vserver:~/ ln -s /etc/nginx/sites-available/flownexus.org /etc/nginx/sites-enabled/
   vserver:~/ ln -s /etc/nginx/sites-available/fw.flownexus.org /etc/nginx/sites-enabled/

   # Test the Nginx config:
   vserver:~/ nginx -t

   # Restart Nginx:
   vserver:~/ systemctl restart nginx

Test the Download Server
........................

If you have setup an A/AAAA-Record, you can now test the download server. It is
available at https://fw.flownexus.org/binaries. If you uncomment the option
``autoindex on;`` in the Nginx config, you can list the files in the directory.

.. figure:: images/https_server_demo.png
   :width: 50%

Start flownexus
...............

After the setup, download flownexus and start it with using docker compose in
detached mode. Make sure to change the ``DEPLOY_SECRET_KEY`` and ``DEBUG`` flag
in the ``settings.py`` file before deploying.:

.. code-block:: console
   :caption: Start flownexus with docker compose


   vserver:~/ git clone https://github.com/jonas-rem/flownexus.git
   # Change the DEPLOY_SECRET_KEY and DEBUG flag in the settings.py file
   vserver:~/flownexus/server$ docker-compose up -d

flownexus is now available at https://flownexus.org. The server is running in a
Docker container and the Nginx server is used as a reverse proxy.

Security Considerations
.......................

Consider
enabling the firewall and only keep required ports open:

- **Port 80, TCP**: HTTP
- **Port 443, TCP**: HTTPS
- **Port 22, TCP**: SSH
- **Port 5683, UDP**: CoAP

.. warning::

  flownexus is not production ready. This server setup is only intended for
  testing purposes.

  The current flownexus configuration uses the default Django
  ``DEPLOY_SECRET_KEY`` and enables the ``DEBUG`` flag. This is a security risk
  and must be change before deploying.

  Currently, the default django inbuild webserver is used. This is not
  recommended for production use. Consider using a production-ready webserver
  like Nginx or Apache.
