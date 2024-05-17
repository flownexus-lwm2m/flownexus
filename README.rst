LwM2M Server
============

This repository hosts a framework to build IoT applications using the LwM2M
protocol. The framework is based on a Leshan LwM2M server and a Django Backend.
This combination allows to manage low power IoT devices, e.g. running Zephyr OS
efficiently.

The project is described in more detail in the linked GitHub pages. The
framework is work in progress and is not yet ready for production use.

External Dependencies
#####################

External components are maintained in their respective versions via a `west`
manifest file. Make sure to configure west to reference the manifest file
(west.yml) in this repository and update all references with::

  # Initialize this repository and external components in a new workspace
  $ pip3 install west
  $ west init -m https://github.com/jonas-rem/lwm2m_server --mr main my_workspace
  $ cd my-workspace
  $ west update

Testing the Framework locally
#############################

The framework can be started locally using docker-compose. By using simulated
Zephyr device running in the same local environment, it can be easily tested.
Please check the documentation for more details.
