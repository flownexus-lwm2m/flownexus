LwM2M Server
============

Update west
###########

Make sure to configure west to reference the manifest file (west.yml) and
update all references with::

  $ west update

Build and Flash the Firmware
############################

Build and flash the firmware application with::

  $ west build app -p
  $ west flash

Documentation
#############

See Sphinx documentation in the linked github pages for a more details.
