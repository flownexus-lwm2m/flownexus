Firmware Setup
==============

LwM2M Version
-------------

The used Leshan version uses LwM2M version 1.1. Make sure to enable this
version in the Zephyr LwM2M client accordingly.

.. code-block:: kconfig
  :caption: Enable LwM2M version 1.1 in Zephyr

   CONFIG_LWM2M_VERSION_1_1=y


LwM2M Transport Format
----------------------

.. code-block:: kconfig
  :caption: Enable CBOR Format

   CONFIG_ZCBOR=y
   CONFIG_ZCBOR_CANONICAL=y


LwM2M SenML Format
------------------

.. note::
   Currently not supported in FlowNexus.

.. code-block:: kconfig
  :caption: Enable LwM2M version 1.1 in Zephyr

   # SenML CBOR - default
   CONFIG_LWM2M_RW_SENML_CBOR_SUPPORT=y
