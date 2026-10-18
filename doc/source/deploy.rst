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
  host:~/workspace$ west init -m https://github.com/flownexus-lwm2m/flownexus --mr main
  host:~/workspace$ west update

Container Environment
---------------------

Both components run in a container. The Leshan gateway (Leshan 2.0.0-M18)
runs in an ``eclipse-temurin:25-jre`` container and the Django server runs in
a ``python:3.14-slim`` container. This allows for an easy and reproducible setup
of the server.

  .. uml::
   :caption: Both components running in one machine using Podman Compose

   @startuml
   package "Container Environment"  #DDDDDD {
     [Leshan] as Leshan
     [Django] as Django
     database "Database" as DB
     Leshan <-right-> Django : REST API
     Django <-down-> DB
   }
   @enduml

The following diagram shows the Container Environment. The file
``compose.yml`` defines the services and their configuration. The file
``leshan/Containerfile`` defines the Leshan container, ``Dockerfile.django``
the Django container and ``Dockerfile.redis`` the Redis container. Compose runs
the images without source mounts, as in production.

The container can be built and started with the following commands:

.. code-block:: console

  host:~/workspace/flownexus$ make server-build
  host:~/workspace/flownexus$ podman-compose -f server/compose.yml up

``make image-smoke-test`` starts the three images on a private network and
checks the admin login, static files, Celery through Redis, and the Leshan
health route from Django. CI runs the same test before it publishes the images.


.. _setup-a-virtual-server-label:

Production Deployment
---------------------

GitHub Actions deploys flownexus to one Debian server with an Ansible playbook
(``deploy/ansible``). The server runs the CI-built images from GHCR as rootless
Podman containers with systemd Quadlets, behind nginx with a Let's Encrypt
certificate. The server does not build images and needs no git checkout.

Sites
.....

nginx serves up to four sites. Each site has its own host name, set by a
GitHub variable. No host name is fixed, and the host names need not share a
domain.

.. list-table::
   :widths: 30 15 55
   :header-rows: 1

   * - Variable
     - Default
     - Site
   * - ``FLOWNEXUS_DASHBOARD_HOST``
     - required
     - Django dashboard and API (reverse proxy to ``127.0.0.1:8000``)
   * - ``FLOWNEXUS_FW_HOST``
     - required
     - Firmware downloads from ``/binaries/`` (IoT-safe TLS)
   * - ``FLOWNEXUS_LANDING_HOST``
     - off
     - flownexus landing page (``utils/landing_page``)
   * - ``FLOWNEXUS_DOCS_HOST``
     - off
     - This documentation (Sphinx HTML)

A customer deployment usually sets only the dashboard and firmware hosts. The
landing page and documentation are the flownexus project sites; when their
variable is empty, the playbook does not render their nginx site, and the
workflow does not build the documentation.

Devices download firmware from ``https://<FLOWNEXUS_FW_HOST>/binaries/...``.
The server sends only the path; the device firmware contains the host name. A
change of ``FLOWNEXUS_FW_HOST`` therefore needs a firmware that uses the new
host.

LwM2M CoAP (5683/udp) goes directly to the Leshan container and bypasses nginx.

.. code-block:: text

   Internet
       │
       ├── nginx (80/tcp, 443/tcp)
       │    ├── FLOWNEXUS_DASHBOARD_HOST → 127.0.0.1:8000 (Django)
       │    ├── FLOWNEXUS_FW_HOST        → /var/www/flownexus/binaries
       │    ├── FLOWNEXUS_LANDING_HOST   → /var/www/flownexus/landing (optional)
       │    └── FLOWNEXUS_DOCS_HOST      → /var/www/flownexus/docs (optional)
       │
       └── 5683/udp (CoAP) → Leshan container

IoT Firmware Downloads (TLS Record Sizing)
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

The firmware download server (``FLOWNEXUS_FW_HOST``) is configured with
``ssl_buffer_size 1370`` in nginx. This limits TLS record sizes to fit within a
single TCP segment (1500 byte MTU - IP/TCP headers - TLS overhead), which is
the industry standard for IoT-compatible HTTPS.

Constrained devices like the **Nordic nRF9160** have a modem-offloaded TLS
engine with a maximum receive buffer of **2048 bytes** for TLS records. Standard
web servers (including Go-based servers like Caddy) use dynamic TLS record
sizing that can send records up to 16KB, causing the modem to reject the
download with ``NRF_EMSGSIZE`` (errno 122). The ``ssl_buffer_size`` directive
in nginx is the server-side fix for this limitation.

HTTP/2 is intentionally disabled on the firmware server block because HTTP/2
framing adds overhead that can push effective TLS record sizes above device
limits. Gzip compression is also disabled since firmware binaries are not
compressible.

Release Flow
............

#. A push to ``main`` runs "System Tests". It builds the Django, Redis and
   Leshan images, runs the gateway contract check, the image smoke test and
   the E2E scenarios, and pushes the images as
   ``ghcr.io/<owner>/flownexus-<service>:sha-<short sha>``.
#. When that run succeeds, the "Deploy" workflow starts for the same commit.
   It skips the deployment if ``FLOWNEXUS_DASHBOARD_HOST`` is not set, so forks
   without a server do not fail.
#. The workflow checks that the three images exist and lists their digests in
   the job summary. Then it runs ``deploy/ansible/site.yml`` over SSH.
#. The playbook configures the host, nginx and TLS, syncs the optional sites,
   pulls the images and writes quadlets that reference the image digests. It
   stops Django and Celery, backs up the database, runs the migrations once,
   and restarts all services. It fails if Django or the Celery worker do not
   answer.
#. The workflow checks each enabled site over HTTPS from the runner.

Deployments do not overlap. A manual run of "Deploy" (``workflow_dispatch``)
deploys the commit given in its ``sha`` input; this is also the rollback path
(see `Rollback and Restore`_).

The playbook changes nginx only through a checked step: it renders the site,
runs ``nginx -t``, and reloads nginx only if the test passes. If the test
fails, it restores the previous site file and stops the deployment, so the
running nginx keeps its configuration.

Services
........

The playbook installs these quadlets in ``~flownexus/.config/containers/systemd``:

* ``flownexus-redis``: Celery broker
* ``flownexus-leshan``: LwM2M server, publishes 5683/udp
* ``flownexus-django``: web application (``web`` command of the Django image)
* ``flownexus-celery``: Celery worker (``worker`` command of the same image)

The migrations run in a one-off container (``migrate`` command) before the
services restart. Into an empty database, ``migrate`` also loads the initial
data, which includes the ``admin`` user with a default password. Change that
password after the first deployment.

GitHub Configuration
....................

Set these in the repository under *Settings → Secrets and variables →
Actions*. The variables must be repository variables, because the workflow
reads ``FLOWNEXUS_DASHBOARD_HOST`` before it selects the ``production``
environment. Secrets can be repository or ``production`` environment secrets.

.. list-table::
   :widths: 30 12 58
   :header-rows: 1

   * - Name
     - Kind
     - Purpose
   * - ``FLOWNEXUS_DASHBOARD_HOST``
     - variable
     - Required. Enables deployment.
   * - ``FLOWNEXUS_FW_HOST``
     - variable
     - Required.
   * - ``FLOWNEXUS_LANDING_HOST``
     - variable
     - Optional site; empty is off.
   * - ``FLOWNEXUS_DOCS_HOST``
     - variable
     - Optional site; empty is off.
   * - ``DEPLOY_HOST``
     - variable
     - SSH host. Default: ``FLOWNEXUS_DASHBOARD_HOST``.
   * - ``DEPLOY_USER``
     - variable
     - SSH user. Default: ``flownexus``.
   * - ``SSH_KNOWN_HOSTS``
     - variable
     - Required. Host key lines for ``DEPLOY_HOST``.
   * - ``FLOWNEXUS_TLS_CERT_NAME``
     - variable
     - Let's Encrypt lineage name. Default: ``FLOWNEXUS_DASHBOARD_HOST``.
   * - ``LETSENCRYPT_EMAIL``
     - variable
     - Optional contact for Let's Encrypt.
   * - ``SSH_PRIVATE_KEY``
     - secret
     - Required. Private key of the deploy user.
   * - ``DJANGO_SECRET_KEY``
     - secret
     - Optional. If not set, the first deployment generates a key on the
       server and keeps it.

The workflow pulls the images with its own ``GITHUB_TOKEN``, so the GHCR
packages can stay private. Get the ``SSH_KNOWN_HOSTS`` value from a trusted
connection to the server, for example:

.. code-block:: console

   local:~$ ssh-keyscan -t ed25519 <DEPLOY_HOST>

Server Setup
............

The playbook installs packages, the firewall, directories, nginx and the
certificate. A new server needs only these manual steps:

1. Install Debian 13 and create the DNS A/AAAA records for each enabled host.
   The certificate request fails if a host does not resolve to the server.
2. Create the deploy user and give it passwordless sudo. Ansible runs the
   host tasks with ``sudo``:

   .. code-block:: console

      vserver:~$ sudo useradd -m -s /bin/bash flownexus
      vserver:~$ echo 'flownexus ALL=(ALL) NOPASSWD: ALL' | sudo tee /etc/sudoers.d/flownexus
      vserver:~$ sudo chmod 440 /etc/sudoers.d/flownexus && sudo visudo -cf /etc/sudoers.d/flownexus

3. Generate a key pair without a passphrase for GitHub Actions. Add the public
   key to ``~flownexus/.ssh/authorized_keys`` (mode ``0600``, directory
   ``0700``) and the private key as the ``SSH_PRIVATE_KEY`` secret:

   .. code-block:: console

      local:~$ ssh-keygen -t ed25519 -C github-actions-deploy -f flownexus_deploy

4. Set the GitHub variables and secrets, then run the "Deploy" workflow
   manually or push to ``main``.

The playbook enables ``ufw`` and allows 22/tcp, 80/tcp, 443/tcp and 5683/udp.
Set ``flownexus_manage_firewall: false`` in a manual inventory to keep an
existing firewall.

After the first deployment:

- Change the ``admin`` password in the Django admin.
- Check that ``https://<FLOWNEXUS_DASHBOARD_HOST>/`` shows no debug pages.

Manual Deployment
.................

``make deploy`` runs the same playbook from a workstation. Copy
``deploy/ansible/inventory.example.yml`` to ``deploy/ansible/inventory.yml``
(ignored by git), set the host names and the image prefix, then:

.. code-block:: console

   host:~/workspace/flownexus$ make deploy IMAGE_TAG=sha-<short sha>

Add ``--check --diff --tags host,nginx`` to the ``ansible-playbook`` command to
preview the host and nginx changes without applying them. The ``stack`` tag
cannot run in check mode, because it needs the pulled images.

``make deploy-test`` lints the playbook and tests the rendered nginx site in a
container for a customer setup (dashboard and firmware only) and for all four
sites. CI runs it on each pull request.

Rollback and Restore
....................

To roll back, run the "Deploy" workflow manually with the full 40-character
``sha`` of an older commit. Its images must still exist in GHCR. The playbook
does not reverse migrations. If the older release cannot read the database,
also restore the backup that was made before the newer release.

If the backup or the migration fails, the deployment stops with Django and
Celery stopped, and the quadlets already reference the new images. Roll back
as above, and restore the backup if the migration changed the database.

Before each migration, the playbook writes
``~flownexus/backups/db_<time>_<tag>.sqlite3`` with ``sqlite3 .backup`` and
keeps the newest 30 backups. To restore one:

.. code-block:: console

   vserver:~$ systemctl --user stop flownexus-celery flownexus-django
   vserver:~$ cp ~/backups/db_<time>_<tag>.sqlite3 ~/data/db.sqlite3
   vserver:~$ systemctl --user start flownexus-django flownexus-celery

Each deployment writes the deployed tag and image digests to
``~flownexus/.local/state/flownexus/release.json`` and appends them to
``releases.log`` in the same directory.

Migration from the Script Deployment
....................................

Servers that ran ``deploy/deploy-flownexus`` need these changes once:

- Replace the sudoers rule for the script with the rule from `Server Setup`_.
- Set the GitHub variables. For flownexus.org, set
  ``FLOWNEXUS_TLS_CERT_NAME=flownexus.org`` to keep the existing certificate.
- On the first run, the playbook copies
  ``~flownexus/flownexus/server/data/db.sqlite3`` to ``~flownexus/data`` if no
  database exists there. It does not change the old copy.

After a successful deployment, ``~flownexus/flownexus`` and the old
``localhost/flownexus-*`` images are no longer used.

File Locations
..............

.. list-table::
   :widths: 30 70
   :header-rows: 1

   * - Content
     - Location
   * - SQLite database
     - ``~flownexus/data/db.sqlite3``
   * - Database backups
     - ``~flownexus/backups/``
   * - Firmware
     - ``/var/www/flownexus/binaries/``
   * - Landing page, documentation
     - ``/var/www/flownexus/landing/``, ``/var/www/flownexus/docs/``
   * - Django settings, secret key
     - ``~flownexus/.config/flownexus/django.env``, ``env`` (mode ``0600``)
   * - Quadlets
     - ``~flownexus/.config/containers/systemd/``
   * - Release record
     - ``~flownexus/.local/state/flownexus/``
   * - nginx site
     - ``/etc/nginx/sites-enabled/flownexus.conf``
   * - Certificate
     - ``/etc/letsencrypt/live/<FLOWNEXUS_TLS_CERT_NAME>/``

Troubleshooting
...............

.. code-block:: console

   vserver:~$ systemctl --user list-units 'flownexus-*'
   vserver:~$ journalctl --user -u flownexus-django -f
   vserver:~$ sudo nginx -t
   vserver:~$ sudo journalctl -u nginx
   vserver:~$ sudo certbot certificates
