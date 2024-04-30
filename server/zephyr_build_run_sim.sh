#!/bin/bash
#
# Start networking via net-tools
../../tools/net-tools/net-setup.sh &

## Build and run Zephyr
west build -b qemu_x86 ../../zephyr/samples/net/lwm2m_client -- -DCONF=overlay-lwm2m-1.1.conf
west build -t run
