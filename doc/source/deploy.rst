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

Both components run in a container. The Leshan server is running in a
``openjdk:17-slim`` container and the Django server is running in a
``python:3.11-slim`` container. This allows for an easy and reproducible setup
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
``Dockerfile.leshan`` defines the Leshan container and the file
``Dockerfile.django`` defines the Django container.

The container can be built and started with the following commands:

.. code-block:: console

  host:~/workspace/flownexus$ make server-build
  host:~/workspace/flownexus$ podman-compose -f server/compose.yml up


.. _setup-a-virtual-server-label:

Production Deployment
---------------------

flownexus can be deployed to a virtual server using nginx as a reverse proxy
with certbot for automatic TLS certificates. The default configuration supports
four subdomains (using ``flownexus.org`` as the example domain -- substitute
your own throughout):

* **flownexus.org** - Main landing page (static HTML)
* **docs.flownexus.org** - Documentation (Sphinx HTML)
* **fw.flownexus.org** - Firmware download server (IoT-safe TLS)
* **dashboard.flownexus.org** - Dynamic dashboard (Django application)

Architecture Overview
.....................

The deployment uses a split traffic routing approach:

* **HTTP/HTTPS (Ports 80/443)**: Handled by nginx reverse proxy
* **UDP Traffic (Ports 5683/5684)**: Directly bound to host, bypassing nginx for LwM2M

.. code-block:: text

   Internet
       │
       ├── nginx (Ports 80/443)
       │    ├── <domain> (static)
       │    ├── docs.<domain> (static)
       │    ├── fw.<domain> (static, IoT-safe TLS)
       │    └── dashboard.<domain> (reverse proxy → localhost:8000)
       │
       └── LwM2M UDP (Ports 5683/5684) → Direct to Leshan container
            ├── 5683/udp - CoAP (unencrypted)
            └── 5684/udp - DTLS/CoAPS (encrypted)

This architecture provides:

* **nginx** - Reverse proxy with IoT-compatible TLS record sizing
* **certbot** - Automatic HTTPS via Let's Encrypt
* **Podman** - Container runtime (rootless)
* **systemd Quadlet** - Container orchestration via systemd units
* **GitHub Actions** - CI/CD pipeline

IoT Firmware Downloads (TLS Record Sizing)
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

The firmware download server (``fw.<domain>``) is configured with
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

Container Management with systemd Quadlet
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

The production deployment uses **systemd Quadlet** instead of Podman Compose. Quadlet
provides native systemd integration for rootless containers, offering several advantages:

* **Automatic startup** - Containers start on boot via systemd
* **Better lifecycle management** - systemd handles stop/start/restart
* **Health checks** - systemd monitors container health automatically
* **Logging** - Centralized logging via ``journalctl``
* **Crash recovery** - Automatic restart on failure
* **SSH session independence** - Containers persist after logout (via ``loginctl enable-linger``)

Quadlet files are located in ``deploy/quadlet/`` and define three services:

* **flownexus-redis** - Redis cache and message broker
* **flownexus-leshan** - LwM2M server with CoAP/DTLS endpoints
* **flownexus-django** - Django application with Celery worker

Each service is defined as a ``.container`` file that systemd converts to a service unit.
Logs are captured by systemd journal, viewable with ``journalctl --user -u flownexus-<service> -f``
(see `Troubleshooting`_ for details).

For local development and testing, use ``make run-mock`` or
``podman-compose -f server/compose.yml up`` which provides the same container
configuration but without systemd integration.

Server Requirements
...................

* Linux server (tested on Debian 13)
* Domain name with DNS A/AAAA records pointing to server
* Minimum: 1 vCPU

Initial Server Setup
....................

This section contains the required one-time manual bootstrap steps for a new
server. After that, normal deployments are handled by GitHub Actions via
``deploy/deploy-flownexus``.

1. Install required packages:

.. code-block:: console

   vserver:~$ sudo apt update && sudo apt upgrade -y
   vserver:~$ sudo apt install -y podman podman-compose nginx python3-certbot-nginx git curl rsync ufw

2. Create a non-root user:

**Important:** Complete this step while logged in as root (or your initial
admin user).

Create a dedicated user for running the application instead of using root:

.. code-block:: console

   vserver:~$ sudo useradd -m -s /bin/bash flownexus
   vserver:~$ sudo passwd flownexus
   vserver:~$ sudo usermod -aG sudo flownexus

**Note:** Log out and log back in for the sudo group membership to take effect.

Allow the GitHub Actions deploy key to run the deploy script without an
interactive password prompt:

.. code-block:: console

   vserver:~$ sudo sh -c "printf '%s\n' 'flownexus ALL=(root) NOPASSWD: /home/flownexus/flownexus/deploy/deploy-flownexus' > /etc/sudoers.d/flownexus-deploy && chmod 440 /etc/sudoers.d/flownexus-deploy"

Validate the sudoers file before continuing:

.. code-block:: console

   vserver:~$ sudo visudo -cf /etc/sudoers.d/flownexus-deploy

Set up SSH access for the new user. Since the user is new, add your SSH key
manually:

.. code-block:: console

   # Create .ssh directory and add your public key
   vserver:~$ sudo mkdir -p ~flownexus/.ssh
   vserver:~$ echo "YOUR_PUBLIC_KEY_HERE" | sudo tee ~flownexus/.ssh/authorized_keys

   # Fix permissions (important!)
   vserver:~$ sudo chmod 700 ~flownexus/.ssh
   vserver:~$ sudo chmod 600 ~flownexus/.ssh/authorized_keys
   vserver:~$ sudo chown -R flownexus:flownexus ~flownexus/.ssh

Replace ``YOUR_PUBLIC_KEY_HERE`` with your actual public key content from
``~/.ssh/id_ed25519.pub`` on your local machine.

Now you can SSH as the flownexus user:

.. code-block:: console

   local:~$ ssh flownexus@your-server-ip

**Generate SSH Key for GitHub Actions (on your local machine):**

Before setting up GitHub Actions, generate a dedicated SSH key pair:

.. code-block:: console

   # Generate a new SSH key (do NOT add a passphrase)
   local:~$ ssh-keygen -t ed25519 -C "github-actions-deploy" -f ~/.ssh/flownexus_deploy

   # This creates two files:
   # ~/.ssh/flownexus_deploy     (private key - keep secret!)
   # ~/.ssh/flownexus_deploy.pub (public key - copy to server)

   # Copy the public key to the server (as root or flownexus user)
   local:~$ cat ~/.ssh/flownexus_deploy.pub

   # On the server, add this to authorized_keys:
   vserver:~$ echo "PASTE_PUBLIC_KEY_HERE" >> ~flownexus/.ssh/authorized_keys

   # Add the private key to GitHub Secrets:
   # 1. Go to GitHub repo → Settings → Secrets and variables → Actions
   # 2. Click "New repository secret"
   # 3. Name: SSH_PRIVATE_KEY
   # 4. Value: Copy contents of ~/.ssh/flownexus_deploy (private key)
   # 5. Click "Add secret"

3. Clone the repository:

.. code-block:: console

   vserver:~$ cd ~flownexus
   vserver:~flownexus$ git clone https://github.com/flownexus-lwm2m/flownexus.git

4. Configure firewall:

.. code-block:: console

   vserver:~$ sudo ufw enable
   vserver:~$ sudo ufw allow 22/tcp    # SSH
   vserver:~$ sudo ufw allow 80/tcp    # HTTP
   vserver:~$ sudo ufw allow 443/tcp   # HTTPS
   vserver:~$ sudo ufw allow 5683/udp  # LwM2M CoAP (unencrypted)
   vserver:~$ sudo ufw allow 5684/udp  # LwM2M DTLS/CoAPS (encrypted)

5. Configure nginx and obtain TLS certificates:

Remove the default nginx site that would otherwise conflict with the flownexus
configuration:

.. code-block:: console

   vserver:~$ sudo rm -f /etc/nginx/sites-enabled/default

Obtain a single SAN certificate covering all domains. Certbot will temporarily
use nginx to complete the ACME challenge, so nginx must be running and DNS must
already resolve to this server:

.. code-block:: console

   vserver:~$ sudo certbot certonly --nginx --cert-name flownexus.org \
        -d flownexus.org \
        -d docs.flownexus.org \
        -d fw.flownexus.org \
        -d dashboard.flownexus.org

This creates one certificate lineage at
``/etc/letsencrypt/live/flownexus.org/`` with all four domains as SANs. The
deployment script renders nginx against that lineage path by default. Certbot
installs a systemd timer that renews it automatically before expiry.

.. important::

   Pass ``--cert-name flownexus.org`` exactly as shown above. Without an
   explicit lineage name, certbot may reuse a different existing certificate
   name such as ``dashboard.flownexus.org``, which leaves the certificate valid
   but causes deployment to fail because nginx is rendered against the expected
   lineage path.

.. note::

   If any domain uses a **manually provisioned certificate** (e.g. a private
   CA for IoT device trust), skip it from the certbot invocation above and
   instead copy the certificate files to ``/etc/nginx/ssl/`` before deploying:

   .. code-block:: console

      vserver:~$ sudo install -d -m 755 /etc/nginx/ssl
      vserver:~$ sudo install -m 644 fw.crt /etc/nginx/ssl/
      vserver:~$ sudo install -m 640 -o root -g www-data fw.key /etc/nginx/ssl/

   The ``deploy/nginx.conf`` for that server block must then reference
   ``/etc/nginx/ssl/fw.crt`` and ``/etc/nginx/ssl/fw.key`` directly instead
   of the Let's Encrypt paths. This is done in the deployment-specific branch.

Add the deploy user to the ``www-data`` group so it can write files that nginx
serves:

.. code-block:: console

   vserver:~$ sudo usermod -aG www-data flownexus

Environment Variables
.....................

Django reads its configuration from environment variables at runtime. This
separates deployment-specific settings from the application code, so the same
container image runs in development (with safe defaults) or production (with
hardened settings) without rebuilding.

**The Django secret key**

Django uses a secret key to cryptographically sign sessions, CSRF tokens, and
password reset links. If an attacker obtains the key, they can forge session
cookies and impersonate any user. The development default key (prefixed
``django-insecure-``) is public knowledge because it lives in the repository
-- it must never be used on an internet-facing server.

The deploy script handles this automatically. On first run it:

1. Generates a cryptographically random 50-character key using Python's
   ``secrets`` module
2. Writes it to ``~flownexus/.config/flownexus/env`` with permissions ``0600``
   (readable only by the deploy user)
3. Skips generation on all subsequent deploys so the key is stable across
   redeploys

The file is never committed to the repository or passed through GitHub Actions.
Verify it was created after the first deploy:

.. code-block:: console

   vserver:~$ cat ~flownexus/.config/flownexus/env
   DJANGO_SECRET_KEY=<your-generated-key>

.. warning::

   Never copy, share, or log this key. If it leaks, delete the file and
   redeploy to rotate it. All existing sessions will be invalidated.

**Other production environment variables**

The remaining variables are set inline in
``deploy/quadlet/flownexus-django.container``. These are deployment config,
not secrets, so keeping them in version control is fine:

.. list-table::
   :widths: 40 35 25
   :header-rows: 1

   * - Variable
     - Production value
     - Purpose
   * - ``DJANGO_DEBUG``
     - ``False``
     - Disables debug mode and detailed error pages
   * - ``DJANGO_ALLOWED_HOSTS``
     - ``dashboard.flownexus.org,localhost,127.0.0.1``
     - Restricts ``Host`` headers Django will respond to
   * - ``DJANGO_CSRF_ORIGINS``
     - ``https://dashboard.flownexus.org``
     - Trusted origins for CSRF checks

For local development (``make run-mock``, tests), no environment variables are
needed -- ``settings.py`` defaults are used automatically.

When deploying to a different domain, update these values in the quadlet file
on the relevant deployment branch.

New Server Deployment Checklist
................................

Use this as a reference when setting up a server from scratch.

**Server preparation**

- Install required packages: ``podman``, ``podman-compose``, ``nginx``,
  ``python3-certbot-nginx``, ``git``, ``curl``, ``rsync``, ``ufw``
- Create the ``flownexus`` deploy user
- Add deploy user to ``www-data`` group: ``sudo usermod -aG www-data flownexus``
- Add your personal SSH public key to ``~flownexus/.ssh/authorized_keys``
- Generate a dedicated SSH key pair for GitHub Actions (no passphrase):
  ``ssh-keygen -t ed25519 -C "github-actions-deploy"``
- Add the Actions public key to ``~flownexus/.ssh/authorized_keys``
- Add the Actions private key to GitHub: Settings → Secrets → ``SSH_PRIVATE_KEY``
- Configure passwordless sudo for the deploy script in
  ``/etc/sudoers.d/flownexus-deploy`` and validate with ``visudo -cf``
- Open firewall: ports 22/tcp, 80/tcp, 443/tcp, 5683/udp, 5684/udp
- Clone the repository into ``~flownexus/flownexus``
- Remove the default nginx site: ``sudo rm -f /etc/nginx/sites-enabled/default``

**DNS**

- Create an A record for each subdomain (``dashboard``, ``fw``, ``docs``,
  ``<root domain>``) pointing to the server IP
- Wait for DNS propagation before running certbot (ACME challenge requires
  valid DNS)

**TLS certificates**

- Run certbot for a single SAN cert covering all domains and pin the lineage
  name:
  ``sudo certbot certonly --nginx --cert-name <domain> -d <domain> -d docs.<domain> -d fw.<domain> -d dashboard.<domain>``
- For manually provisioned certs (e.g. private CA for IoT), copy them to
  ``/etc/nginx/ssl/`` and reference them in the deployment-specific nginx config

**First deployment**

- Run the deploy script: ``sudo ~flownexus/flownexus/deploy/deploy-flownexus``
  (or push to the tracked branch to trigger GitHub Actions)
- Confirm the secret key file was created:

  .. code-block:: console

     vserver:~$ ls -la ~flownexus/.config/flownexus/env
     # Must show: -rw------- 1 flownexus flownexus

- Confirm all three services are running:

  .. code-block:: console

     vserver:~$ systemctl --user status flownexus-django flownexus-redis flownexus-leshan

- Confirm the health check passes:

  .. code-block:: console

     vserver:~$ curl -sf http://127.0.0.1:8000/admin/login/ > /dev/null && echo OK

- Open the dashboard in a browser and verify HTTPS (no certificate warning)
- **Change the default admin password** in the Django admin interface
- Verify debug mode is off: the ``/`` page must not show a Django debug toolbar
  or stack traces on errors

Automated CI/CD
................

This is the normal deployment path after the initial server bootstrap. When
code is pushed to the main branch:

1. **Build static assets locally** (landing page, Sphinx documentation)
2. **Deploy static files via rsync** to ``/var/www/flownexus/``
3. **Update the backend checkout and run ``deploy/deploy-flownexus``** to refresh code, nginx, and containers

The workflow updates the backend checkout, then runs the deploy script on the
server. The script creates the required directories, installs the nginx
configuration, and restarts the stack. The Django container stores its SQLite
database in ``~flownexus/flownexus/server/data/db.sqlite3`` and stores uploaded
firmware in ``/var/www/flownexus/binaries``.

Required GitHub Secrets:

* ``SSH_PRIVATE_KEY`` - Private key for the deploy user

The workflow uses ``sudo -n`` only to invoke ``deploy/deploy-flownexus``.
That script performs the privileged server setup and restart steps in one place.

To deploy to a different domain or server layout, update ``deploy/nginx.conf``
and the environment values in ``.github/workflows/deploy.yml``.

Troubleshooting
.................

Everything in this section is optional and only needed for debugging a broken
deployment or validating a suspicious state.

nginx Issues
~~~~~~~~~~~~

**Check nginx logs:**

.. code-block:: console

   vserver:~$ sudo journalctl -u nginx -f
   vserver:~$ sudo tail -f /var/log/nginx/error.log

**Validate configuration:**

.. code-block:: console

   vserver:~$ sudo nginx -t

Container Issues
~~~~~~~~~~~~~~~~

**Check service status:**

.. code-block:: console

   vserver:~$ systemctl --user status flownexus-django
   vserver:~$ systemctl --user status flownexus-redis
   vserver:~$ systemctl --user status flownexus-leshan

**View logs (via systemd journal):**

.. code-block:: console

   vserver:~$ journalctl --user -u flownexus-django -f
   vserver:~$ journalctl --user -u flownexus-redis -f
   vserver:~$ journalctl --user -u flownexus-leshan -f

**Restart specific service:**

.. code-block:: console

   vserver:~$ systemctl --user restart flownexus-django

**View all flownexus services:**

.. code-block:: console

   vserver:~$ systemctl --user list-units 'flownexus-*'

SSL Certificate Issues
~~~~~~~~~~~~~~~~~~~~~~

Certificates are managed by certbot (Let's Encrypt). If certificates fail,
check certbot logs and ensure DNS is resolving correctly:

.. code-block:: console

   vserver:~$ sudo certbot certificates
   vserver:~$ sudo certbot renew --dry-run
   vserver:~$ sudo journalctl -u nginx | grep -i "ssl\|tls\|cert"

Security Considerations
.......................

* Use ed25519 SSH keys: ``ssh-keygen -t ed25519 -a 100``
* Keep ``/var/www/flownexus`` writable by ``flownexus`` and readable by nginx
* Regularly update nginx and container base images
* Never commit secrets to the repository

Customizing for Your Deployment
................................

To deploy on a different domain, update the domain names in
``deploy/nginx.conf``, the environment variables (``DJANGO_ALLOWED_HOSTS``,
``DJANGO_CSRF_ORIGINS``) in ``deploy/quadlet/flownexus-django.container``, and
the target server in ``.github/workflows/deploy.yml``.

File Locations
....................

+------------------+----------------------------------------------------------+---------------------------+
| File             | Location                                                 | Purpose                   |
+==================+==========================================================+===========================+
| Static website   | ``/var/www/flownexus/landing/``                          | Landing page              |
+------------------+----------------------------------------------------------+---------------------------+
| Documentation    | ``/var/www/flownexus/docs/``                             | Sphinx HTML               |
+------------------+----------------------------------------------------------+---------------------------+
| Firmware         | ``/var/www/flownexus/binaries/``                         | Firmware downloads        |
+------------------+----------------------------------------------------------+---------------------------+
| SQLite database  | ``~flownexus/flownexus/server/data/``                    | Persistent Django data    |
+------------------+----------------------------------------------------------+---------------------------+
| Database backups | ``~flownexus/backups/``                                  | Automatic DB backups      |
+------------------+----------------------------------------------------------+---------------------------+
| Django env file  | ``~flownexus/.config/flownexus/env``                     | Secret key (auto-created) |
+------------------+----------------------------------------------------------+---------------------------+
| nginx config     | ``/etc/nginx/sites-enabled/flownexus.conf``              | Reverse proxy             |
+------------------+----------------------------------------------------------+---------------------------+
| Let's Encrypt    | ``/etc/letsencrypt/``                                    | SSL certificates          |
+------------------+----------------------------------------------------------+---------------------------+
| Quadlet configs  | ``~flownexus/.config/containers/systemd/``               | Container systemd units   |
+------------------+----------------------------------------------------------+---------------------------+
| Quadlet source   | ``~flownexus/flownexus/deploy/quadlet/``                 | Quadlet definitions       |
+------------------+----------------------------------------------------------+---------------------------+
| Logs             | ``journalctl --user -u flownexus-*``                     | Container logs            |
+------------------+----------------------------------------------------------+---------------------------+

Maintenance
.............

Everything in this section is optional day-2 operations guidance.

Updating Containers
~~~~~~~~~~~~~~~~~~~

Usually GitHub Actions performs updates for you. Use these commands only when
you intentionally want to update or recover the server manually.

**Option 1: Using make deploy (Recommended for manual deploys)**

From your local development machine:

.. code-block:: console

   local:~$ make deploy SERVER=flownexus.org USER=flownexus

This will:
1. SSH to the server and update the git checkout
2. Run the deploy script via sudo

**Option 2: Direct deployment on server**

.. code-block:: console

   vserver:~flownexus/flownexus$ git pull
   vserver:~flownexus/flownexus$ sudo deploy/deploy-flownexus

To create directories and reload nginx without rebuilding containers
(useful after an nginx config change):

.. code-block:: console

   vserver:~flownexus/flownexus$ sudo deploy/deploy-flownexus --setup-only

For local development and testing, use Podman Compose:

.. code-block:: console

   vserver:~flownexus/flownexus$ podman-compose -f server/compose.yml up -d --build

Cleaning Up
~~~~~~~~~~~

Use these commands only for manual housekeeping.

.. code-block:: console

   # Remove old container images
   vserver:~$ podman image prune -a

   # Clean up volumes
   vserver:~$ podman volume prune
