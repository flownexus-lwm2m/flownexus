# Copyright (c) 2024 Jonas Remmert
#
# SPDX-License-Identifier: Apache-2.0
#

import argparse
import subprocess
import sys
import signal
import shutil
import os
import time
import docker
import threading
import re

BASE_IMEI = 100000000000000
TEMP_CONF_DIR = './conf_tmp'
APP = 'lwm2m_client'
BINDIR = os.path.abspath(f'./{APP}/endpoint_binaries')
NET_TOOLS_DIR = os.path.abspath('../../tools/net-tools')
DOCKER_BUILD_LOG_ENABLE = False
CWD = os.getcwd()
CONTAINER_VOLUME_MAPPING = {
    CWD: {'bind': CWD, 'mode': 'rw'},
    NET_TOOLS_DIR: {'bind': '/net-tools', 'mode': 'rw'}
}
# Check if NET_TOOLS_DIR is a directory
if not os.path.isdir(NET_TOOLS_DIR):
    raise FileNotFoundError(f"Directory {NET_TOOLS_DIR} not found")

# Remember the number of clients, to stop them when the script is interrupted
num_clients = 1

# Configuration for the Zephyr client instances
ZEPHYR_CONF = """
CONFIG_NET_CONFIG_MY_IPV4_ADDR="{ip_addr}"
CONFIG_NET_CONFIG_MY_IPV4_GW="{gw_addr}"
CONFIG_LWM2M_APP_ID="urn:imei:{imei}"
CONFIG_ETH_NATIVE_POSIX_DRV_NAME="{zeth_name}"
CONFIG_ETH_NATIVE_POSIX_MAC_ADDR="{hwaddr}"
CONFIG_ETH_NATIVE_POSIX_RANDOM_MAC=n
CONFIG_DNS_SERVER1="8.8.8.8"
"""

# Configuration for the network interfaces
IF_CONF = """
INTERFACE="{if_name}"
ip link set dev {if_name} up
ip link set dev {if_name} address {hwaddr}

ip address add {if_ip_addr} dev {if_name}
ip route add {if_ip_route} dev {if_name} > /dev/null 2>&1

iptables -t nat -A POSTROUTING -j MASQUERADE -s {if_ip_route}

sysctl -w net.ipv4.ip_forward=1
iptables -P FORWARD ACCEPT
"""


class DockerManager:
    def __init__(self, volumes):
        self.client = docker.from_env()
        self.volumes = volumes
        self.container = None
        self.image = None
        self.leshan_ip = None


    def build_container(self):
        print("Building image from ./Dockerfile")
        image, build_logs = self.client.images.build(path=os.getcwd(),
                                                     dockerfile='Dockerfile',
                                                     tag='net-tools-img')
        if DOCKER_BUILD_LOG_ENABLE:
            for chunk in build_logs:
                if 'stream' in chunk:
                    print(chunk['stream'], end='')

        self.image = image


    def get_ip_from_domain(self, domain="leshan"):
        """ Gets the IP address of the specified domain by pinging it inside the container. """
        if not self.container:
            raise RuntimeError("Container is not running. Call start_container first.")

        # Execute the command
        command = f"ping -c 1 {domain}"
        exit_code, output = self.run_cmd_sync(command, logging=False)

        if exit_code == 0:
            ip_address_match = re.search(r'\((\d+\.\d+\.\d+\.\d+)\)', output)
            if ip_address_match:
                self.leshan_ip = ip_address_match.group(1)
                return True
            else:
                return False
        else:
            return False


    def start_container(self):
        print(f"Starting container")

        if not self.container:
            self.container = self.client.containers.run(
                self.image,
                "tail -f /dev/null",  # Keep the container running
                volumes=self.volumes,
                working_dir=os.getcwd(),
                detach=True,
                privileged=True,
                network="server_mynetwork"
            )


    def _stream_output(self, exec_id):
        """
        Private method to stream output from the exec instance.
        """
        output_stream = self.client.api.exec_start(exec_id, stream=True)
        for chunk in output_stream:
            print(chunk.decode('utf-8'), end='')


    def run_cmd_async(self, command, logging=False):
        """
        Execute a command inside the container and return immediately after
        starting the process.

        Returns the exec_id of the command.
        """
        if not self.container:
            raise RuntimeError("Container is not running. Call start_container first.")
        exec_id = self.client.api.exec_create(self.container.id, command)

        if logging:
            thread = threading.Thread(target=self._stream_output, args=(exec_id,))
            thread.start()
        else:
            self.client.api.exec_start(exec_id, detach=True)
        return exec_id


    def run_cmd_sync(self, command, logging=False):
        """
        Execute a command inside the container and wait for the process to finish.

        Returns the exit code of the command.
        """
        if not self.container:
            raise RuntimeError("Container is not running. Call start_container first.")
        exec_id = self.client.api.exec_create(self.container.id, command)
        output_stream = self.client.api.exec_start(exec_id, stream=True)

        output = ''
        for chunk in output_stream:
            line = chunk.decode('utf-8')
            output += line
            if logging:
                print(line, end='')  # Print each line as it is generated

        # Check the exit code of the command
        exec_inspect = self.client.api.exec_inspect(exec_id)
        exit_code = exec_inspect.get('ExitCode')

        return exit_code, output


    def attach_to_container(self):
        if self.container is None:
            raise RuntimeError("Container is not running. Please run the container first.")

        # Use subprocess to attach to the container's shell
        subprocess.run(["docker", "exec", "-it", str(self.container.id), "/bin/bash"])


    def stop_container(self):
        print(f"Stopping container.")
        if self.container:
            self.container.stop(timeout=1)
            self.container.remove()
            self.container = None


docker_manager = DockerManager(CONTAINER_VOLUME_MAPPING)


def signal_handler(sig, frame):
    docker_manager.stop_container()
    sys.exit(0)

# Build Zephyr clients to control certain parameters like ipaddr, IMEI.
def build_clients(num_clients, logging):

    for i in range(num_clients):
        print(f'Building Zephyr client [{i + 1}/{num_clients}]', end='\r')
        if (i + 1) == num_clients:
            print()

        file_path = os.path.join(TEMP_CONF_DIR, f'ep.{i}.conf')
        ip_addr = f'192.0.{i}.3'
        hwaddr = f'00:00:5e:01:{i:02x}:00'
        gw_addr = f'192.0.{i}.1'
        imei = str(BASE_IMEI + i)
        zeth_name = f'zeth.{i}'

        # Create a temporary file for the Kconfig options
        with open(file_path, 'w') as config_file:
            config_file.write(ZEPHYR_CONF.format(ip_addr=ip_addr,
                                                 gw_addr=gw_addr,
                                                 hwaddr=hwaddr,
                                                 imei=imei,
                                                 zeth_name=zeth_name))

        build_cmd = [
            'west', 'build', '-p=auto', '-b', 'native_sim', APP, '--',
            f'-DEXTRA_CONF_FILE=overlay-lwm2m-1.1.conf ../{file_path}'
        ]

        # Run the command, capturing both stdout and stderr
        result = subprocess.run(build_cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)

        # Check if the command failed
        if result.returncode:
            print("Command failed with return code:", result.returncode)
            print("Standard Output:\n", result.stdout.decode())
            print("Standard Error:\n", result.stderr.decode())
            print("Failed to build Zephyr client, exiting...")
            signal_handler(signal.SIGINT, None)
        elif logging:
            print("Standard Output:\n", result.stdout.decode())
            print("Standard Error:\n", result.stderr.decode())

        # Copy files to the endpoint_binaries directory
        source = 'build/zephyr/zephyr.exe'
        destination = f'{BINDIR}/ep_{i}.exe'
        shutil.copy(source, destination)


def setup_net_ifaces(num_clients, logging):
    for i in range(num_clients):
        file_path = os.path.join(TEMP_CONF_DIR, f'zeth.{i}.conf')

        if_ip_addr = f'192.0.{i}.1/24'
        if_ip_route = f'192.0.{i}.0/24'
        hwaddr = f'00:00:5e:00:00:{i:02x}'
        if_name = f'zeth.{i}'

        with open(file_path, 'w') as config_file:
            config_file.write(IF_CONF.format(if_ip_addr=if_ip_addr,
                                             if_ip_route=if_ip_route,
                                             hwaddr=hwaddr,
                                             if_name=if_name))

        print(f'Starting zeth [{i + 1}/{num_clients}]           ', end='\r')
        if (i + 1) == num_clients:
            print()

        # Create the network interface inside the container
        cmd = f'/net-tools/net-setup.sh --config {file_path} -i zeth.{i} start'
        exit_code, _ = docker_manager.run_cmd_sync(cmd, logging=logging)
        if exit_code != 0:
            print('Failed to start zeth')
            signal_handler(signal.SIGINT, None)


def start_clients(num_clients, time_gap, logging):
    processes = []
    for i in range(num_clients):
        cmd = f'{BINDIR}/ep_{i}.exe'
        docker_manager.run_cmd_async(cmd, logging=logging)
        print(f'Starting Zephyr client [{i + 1}/{num_clients}]', end='\r')
        if (i + 1) == num_clients:
            print()

        # Wait for the specified time gap before starting the next process
        time.sleep(time_gap / 1000)

    # Wait for all processes to finish
    for process in processes:
        process.wait()


def main():
    global num_clients
    global ZEPHYR_CONF
    os.makedirs(TEMP_CONF_DIR, exist_ok=True)
    os.makedirs(BINDIR, exist_ok=True)

    parser = argparse.ArgumentParser(
        description='Zephyr Build and Run Script',
        formatter_class=argparse.ArgumentDefaultsHelpFormatter
    )

    parser.add_argument('-n', type=int, default=1,
                        dest='num_clients',
                        help='Number of client instances to start. (1 - 254)')
    parser.add_argument('-v', action='store_true',
                        dest='verbose',
                        help='Enable logging')
    parser.add_argument('-b', action='store_true',
                        dest='build',
                        help='Build the client')
    parser.add_argument('-r', action='store_true',
                        dest='run',
                        help='Run the client.')
    parser.add_argument('-d', type=int, default=0,
                        dest='delay',
                        help='Client start delay [ms]')
    parser.add_argument('-l', action='store_true',
                        dest='local',
                        help='Connect to locally running Leshan server')

    args = parser.parse_args()
    if not args.build and not args.run:
        print('No build/run options provided, build and run n clients with logging:')
        print('  Warning: bindir will be cleaned, do you want to continue? [y/n]')
        response = input()
        if response.lower() != 'y':
            signal_handler(signal.SIGINT, None)
        args.verbose = True
        args.build = True
        args.run = True

    if args.num_clients < 1 or args.num_clients > 254:
        print('Number of clients must be inbetween 1 and 254')
        sys.exit(1)

    # Automatically discard output if more than one client is started
    num_clients = args.num_clients

    # Register the cleanup function to be called on exit signal
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)
    signal.signal(signal.SIGHUP, signal_handler)

    docker_manager.build_container()
    docker_manager.start_container()

    if args.local:
        if not docker_manager.get_ip_from_domain("leshan"):
            print("Failed to get IP address of Leshan server.")
            signal_handler(signal.SIGINT, None)
        zephyr_conf_lwm2m_ip = f'CONFIG_LWM2M_APP_SERVER="coap://{docker_manager.leshan_ip}:5683"'
        ZEPHYR_CONF += f"\n{zephyr_conf_lwm2m_ip}"

    if args.build:
        print(f'Cleaning ./{APP}/endpoint_binaries/, ./conf_tmp/')
        subprocess.run(f'rm -f {BINDIR}/*', shell=True, check=True)
        subprocess.run(f'rm -f ./conf_tmp/*', shell=True, check=True)

        build_clients(num_clients, args.verbose)

    if not args.run:
        return

    setup_net_ifaces(num_clients, args.verbose)
    start_clients(num_clients, args.delay, args.verbose)

    print('Quit <q>;   Attach to Container <a>')
    response = ''
    while response.lower() not in ['q', 'a']:
        response = input()
        if response.lower() == 'q':
            signal_handler(signal.SIGINT, None)
        elif response.lower() == 'a':
            docker_manager.attach_to_container()
        else:
            print('Invalid input')


    while True:
        time.sleep(1)


if __name__ == '__main__':
    main()
