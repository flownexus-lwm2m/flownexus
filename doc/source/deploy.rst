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

.. warning::

  Make sure to change the password to the admin console as well as other
  settings like SECRET_KEY, DEBUG flag in a production environment!

The container can be built and started with the following commands:

.. code-block:: console

  host:~/workspace/flownexus$ make server-build
  host:~/workspace/flownexus$ podman-compose -f server/compose.yml up


.. _setup-a-virtual-server-label:

Production Deployment
---------------------

flownexus can be deployed to a virtual server using Caddy as a reverse proxy.
This deployment supports four subdomains:

* **flownexus.org** - Main landing page (static HTML)
* **docs.flownexus.org** - Documentation (Sphinx HTML)
* **fw.flownexus.org** - Firmware download server
* **dashboard.flownexus.org** - Dynamic dashboard (Django application)

Architecture Overview
.....................

The deployment uses a split traffic routing approach:

* **HTTP/HTTPS (Ports 80/443)**: Handled by Caddy reverse proxy
* **UDP Traffic (Ports 5683/5684)**: Directly bound to host, bypassing Caddy for LwM2M

.. code-block:: text

   Internet
       │
       ├──→ Caddy (Ports 80/443)
       │     ├──→ flownexus.org (static)
       │     ├──→ docs.flownexus.org (static)
       │     ├──→ fw.flownexus.org (static + browse)
       │     └──→ dashboard.flownexus.org (reverse proxy → localhost:8000)
       │
       └──→ LwM2M UDP (Ports 5683/5684) → Direct to Leshan container
             ├──→ 5683/udp - CoAP (unencrypted)
             └──→ 5684/udp - DTLS/CoAPS (encrypted)

This architecture provides:

* **Caddy** - Reverse proxy with automatic HTTPS
* **Podman** - Container runtime (rootless)
* **Podman Compose** - Container orchestration
* **GitHub Actions** - CI/CD pipeline

Server Requirements
...................

* Linux server (tested on Debian 13)
* Domain name with DNS A/AAAA records pointing to server
* Minimum: 1 vCPU

Initial Server Setup
....................

This section contains the required one-time manual bootstrap steps for a new
server. After these steps are complete, normal application deployments are
handled by GitHub Actions.

1. Install required packages:

.. code-block:: console

   vserver:~$ sudo apt update && sudo apt upgrade -y
   vserver:~$ sudo apt install -y podman podman-compose caddy git curl rsync ufw

2. Create a non-root user:

**Important:** Complete this step while logged in as root (or your initial
admin user).

Create a dedicated user for running the application instead of using root:

.. code-block:: console

   vserver:~$ sudo useradd -m -s /bin/bash flownexus
   vserver:~$ sudo passwd flownexus
   vserver:~$ sudo usermod -aG sudo flownexus

**Note:** Log out and log back in for the sudo group membership to take effect.

Allow the GitHub Actions deploy key to run the required deployment commands
without an interactive password prompt:

.. code-block:: console

   vserver:~$ sudo tee /etc/sudoers.d/flownexus-deploy > /dev/null <<'EOF'
   flownexus ALL=(root) NOPASSWD: /usr/bin/rsync
   flownexus ALL=(root) NOPASSWD: /usr/bin/mkdir
   flownexus ALL=(root) NOPASSWD: /usr/bin/chown
   flownexus ALL=(root) NOPASSWD: /usr/bin/chmod
   flownexus ALL=(root) NOPASSWD: /usr/bin/mv
   flownexus ALL=(root) NOPASSWD: /usr/bin/systemctl reload caddy
   flownexus ALL=(root) NOPASSWD: /usr/bin/systemctl restart caddy
   flownexus ALL=(root) NOPASSWD: /usr/bin/systemctl is-active caddy
   flownexus ALL=(root) NOPASSWD: /usr/bin/caddy validate --config /tmp/Caddyfile.new
   EOF

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

4. Create directory structure:

.. code-block:: console

   vserver:~$ sudo mkdir -p /var/www/flownexus/{landing,docs,binaries}
   vserver:~$ sudo mkdir -p ~flownexus/flownexus/server/data
   vserver:~$ sudo chown -R caddy:caddy /var/www/flownexus
   vserver:~$ sudo chown -R flownexus:flownexus ~flownexus/flownexus/server/data
   vserver:~$ sudo mkdir -p /var/log/caddy

5. Configure firewall:

.. code-block:: console

   vserver:~$ sudo ufw enable
   vserver:~$ sudo ufw allow 22/tcp    # SSH
   vserver:~$ sudo ufw allow 80/tcp    # HTTP
   vserver:~$ sudo ufw allow 443/tcp   # HTTPS
   vserver:~$ sudo ufw allow 5683/udp  # LwM2M CoAP (unencrypted)
   vserver:~$ sudo ufw allow 5684/udp  # LwM2M DTLS/CoAPS (encrypted)

Optional Manual Backend Start
.............................

This section is not required for normal deployments. Use it only for the first
local smoke test on a fresh server or for manual recovery/debugging.

1. Start the containers:

.. code-block:: console

   vserver:~flownexus/flownexus$ export APP_VERSION=$(git describe --always --dirty --tags)
   vserver:~flownexus/flownexus$ podman-compose -f server/compose.yml up -d --build

2. Verify services are running:

.. code-block:: console

   vserver:~flownexus/flownexus$ podman ps
   vserver:~flownexus/flownexus$ curl http://localhost:8000/admin/login/
   vserver:~flownexus/flownexus$ curl http://localhost/admin/login/

Automated CI/CD
................

This is the normal deployment path after the initial server bootstrap. When
code is pushed to the main branch:

1. **Build static assets locally** (landing page, Sphinx documentation)
2. **Deploy static files via rsync** to ``/var/www/flownexus/``
3. **Deploy Caddyfile** and reload Caddy configuration
4. **SSH to server and run** ``git pull origin main`` to update backend code
5. **Build and restart containers** with ``podman-compose -f server/compose.yml up -d --build``

The backend code is pulled directly from the repository on the server, ensuring
the deployed code matches the git commit exactly.

The Django container stores its SQLite database in
``~flownexus/flownexus/server/data/db.sqlite3`` and stores uploaded
firmware directly in ``/var/www/flownexus/binaries`` so the same files are
immediately available through the firmware download host. These paths are
configured via ``DJANGO_DB_HOST_PATH`` and ``FIRMWARE_STORAGE_HOST_PATH`` in
the deployment environment; local development falls back to ``./data`` and
``./firmware`` inside ``server/``.

Required GitHub Secrets:

* ``SSH_PRIVATE_KEY`` - Private key for the deploy user

The workflow uses ``sudo -n`` on the server for ``rsync``, Caddy validation,
directory ownership fixes, and Caddy reload/health checks. The deploy user must
therefore have the matching passwordless sudo rules configured as shown above.

To deploy to a different domain or server layout, update ``deploy/Caddyfile``
and the environment values in ``.github/workflows/deploy.yml``.

Optional Certificate Maintenance
................................

Caddy automatically manages Let's Encrypt certificates. No manual intervention
is required. Certificates are stored in ``/var/lib/caddy/``.

Use the following only if you need to troubleshoot or force a renewal:

.. code-block:: console

   vserver:~$ sudo caddy reload --config /etc/caddy/Caddyfile

Troubleshooting
.................

Everything in this section is optional and only needed for debugging a broken
deployment or validating a suspicious state.

Caddy Issues
~~~~~~~~~~~~

**Check Caddy logs:**

.. code-block:: console

   vserver:~$ sudo journalctl -u caddy -f

**Validate configuration:**

.. code-block:: console

   vserver:~$ sudo caddy validate --config /etc/caddy/Caddyfile

**Test Caddy locally:**

.. code-block:: console

   vserver:~$ sudo caddy run --config /etc/caddy/Caddyfile

Container Issues
~~~~~~~~~~~~~~~~

**Check container status:**

.. code-block:: console

   vserver:~$ podman ps -a

**View logs:**

.. code-block:: console

   vserver:~$ podman logs flownexus-django
   vserver:~$ podman logs flownexus-leshan
   vserver:~$ podman logs flownexus-redis

**Restart specific service:**

.. code-block:: console

   vserver:~$ podman restart flownexus-django

SSL Certificate Issues
~~~~~~~~~~~~~~~~~~~~~~

Caddy handles SSL automatically. If certificates fail:

.. code-block:: console

   # Force certificate renewal
   vserver:~$ sudo caddy reload --config /etc/caddy/Caddyfile

   # Check certificate status
   vserver:~$ sudo caddy list-modules | grep tls

Security Considerations
.......................

This section is guidance to review before exposing the stack publicly. It is
not an extra deployment procedure, but these items still matter for a real
internet-facing setup.

Required open ports:

* **Port 22, TCP**: SSH access
* **Port 80, TCP**: HTTP (redirects to HTTPS)
* **Port 443, TCP**: HTTPS
* **Port 5683, UDP**: LwM2M CoAP (unencrypted)
* **Port 5684, UDP**: LwM2M DTLS/CoAPS (encrypted)

Security Best Practices:

1. **SSH Keys**: Use ed25519 keys for deployment: ``ssh-keygen -t ed25519 -a 100``
2. **File Permissions**: Ensure ``/var/www/flownexus`` is owned by ``caddy:caddy``
3. **Firewall**: Only open required ports (22, 80, 443, 5683/udp, 5684/udp)
4. **Updates**: Regularly update Caddy and container base images
5. **Secrets**: Never commit secrets to the repository

Before deploying to production:

1. Change the Django ``SECRET_KEY`` in production settings
2. Disable Django ``DEBUG`` mode
3. Use strong passwords for admin accounts
4. Configure firewall rules
5. Set up automated backups

Customizing for Your Deployment
................................

This section is only needed if you want to change the default domains, server
paths, or deploy user.

To deploy on a different server or domain, update these files:

``deploy/Caddyfile``
~~~~~~~~~~~~~~~~~~~~

Change the configured domains and the Let's Encrypt email address:

.. code-block:: text

   webmaster@flownexus.org
   flownexus.org
   docs.flownexus.org
   fw.flownexus.org
   dashboard.flownexus.org

``.github/workflows/deploy.yml``
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Adjust the deployment environment values near the top of the file:

.. code-block:: yaml

   env:
     DEPLOY_USER: flownexus
     SERVER_HOST: flownexus.org
     APP_ROOT: ~flownexus/flownexus
     DJANGO_DB_HOST_PATH: ~flownexus/flownexus/server/data
     FIRMWARE_STORAGE_HOST_PATH: /var/www/flownexus/binaries

Also update any username or home-directory references in the server setup
commands throughout this chapter.

When following the server setup instructions, replace:

* ``flownexus`` with your desired username
* ``~flownexus`` with your user's home directory
* Server IP addresses in SSH commands

After making these changes, commit and push to trigger deployment.

File Locations
....................

+------------------+--------------------------------------------------+------------------------+
| File             | Location                                         | Purpose                |
+==================+==================================================+========================+
| Static website   | ``/var/www/flownexus/landing/``                  | Landing page           |
+------------------+--------------------------------------------------+------------------------+
| Documentation    | ``/var/www/flownexus/docs/``                     | Sphinx HTML            |
+------------------+--------------------------------------------------+------------------------+
| Firmware         | ``/var/www/flownexus/binaries/``                 | Firmware downloads     |
+------------------+--------------------------------------------------+------------------------+
| SQLite database  | ``~flownexus/flownexus/server/data/``            | Persistent Django data |
+------------------+--------------------------------------------------+------------------------+
| Caddy config     | ``/etc/caddy/Caddyfile``                         | Reverse proxy          |
+------------------+--------------------------------------------------+------------------------+
| Caddy data       | ``/var/lib/caddy/``                              | SSL certificates       |
+------------------+--------------------------------------------------+------------------------+
| Container config | ``~flownexus/flownexus/server/compose.yml``      | Podman services        |
+------------------+--------------------------------------------------+------------------------+
| Logs             | ``/var/log/caddy/``                              | Access logs            |
+------------------+--------------------------------------------------+------------------------+

Maintenance
.............

Everything in this section is optional day-2 operations guidance.

Updating Containers
~~~~~~~~~~~~~~~~~~~

Usually GitHub Actions performs updates for you. Use these commands only when
you intentionally want to update or recover the server manually.

.. code-block:: console

   vserver:~flownexus/flownexus$ git pull
   vserver:~flownexus/flownexus$ export APP_VERSION=$(git describe --always --dirty --tags)
   vserver:~flownexus/flownexus$ podman-compose -f server/compose.yml up -d --build

Cleaning Up
~~~~~~~~~~~

Use these commands only for manual housekeeping.

.. code-block:: console

   # Remove old container images
   vserver:~$ podman image prune -a

   # Clean up volumes
   vserver:~$ podman volume prune

.. warning::

  flownexus is not production ready. This server setup is only intended for
  testing purposes. Review and harden the configuration before using in
  production.
