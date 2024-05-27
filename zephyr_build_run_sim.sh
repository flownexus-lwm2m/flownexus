#!/bin/bash

# Function to stop networking
cleanup() {
    ../tools/net-tools/net-setup.sh stop
}

# Register the cleanup function to be called on the EXIT signal
trap cleanup EXIT

# Start networking via net-tools
../tools/net-tools/net-setup.sh start

## Build and run Zephyr
west build -p=auto -b qemu_x86 fw_test/lwm2m_client -- -DCONF=overlay-lwm2m-1.1.conf
west build -t run

cleanup
