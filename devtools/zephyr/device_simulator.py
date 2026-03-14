#
# Copyright (c) 2024 Jonas Remmert
#
# SPDX-License-Identifier: Apache-2.0
#
import os
import shutil
import subprocess
import threading
import time

import docker

BASE_IMEI = 100000000000000
TEMP_CONF_DIR = "./conf_tmp"
APP = "lwm2m_client"
BINDIR = os.path.abspath(f"./{APP}/endpoint_binaries")
NET_TOOLS_DIR = os.path.abspath("../../tools/net-tools")
DOCKER_BUILD_LOG_ENABLE = False
CWD = os.getcwd()
CONTAINER_VOLUME_MAPPING = {
    CWD: {"bind": CWD, "mode": "rw"},
    NET_TOOLS_DIR: {"bind": "/net-tools", "mode": "rw"},
}

# Configuration for the Zephyr client instances
ZEPHYR_CONF = """
CONFIG_NET_CONFIG_MY_IPV4_ADDR="{ip_addr}"
CONFIG_NET_CONFIG_MY_IPV4_GW="{gw_addr}"
CONFIG_LWM2M_APP_ID="urn:imei:{imei}"
CONFIG_ETH_NATIVE_TAP_DRV_NAME="{zeth_name}"
CONFIG_ETH_NATIVE_TAP_MAC_ADDR="{hwaddr}"
CONFIG_ETH_NATIVE_TAP_RANDOM_MAC=n
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
        self.network_name = self._find_network()

    def _find_network(self, target="mynetwork"):
        try:
            for net in self.client.networks.list():
                name = net.name
                if name and (name == target or name.endswith(f"_{target}")):
                    return name
        except Exception:
            pass
        return f"server_{target}"

    def build_container(self):
        print("Building image from ./Dockerfile")
        image, build_logs = self.client.images.build(
            path=os.getcwd(), dockerfile="Dockerfile", tag="net-tools-img"
        )
        if DOCKER_BUILD_LOG_ENABLE:
            for chunk in build_logs:
                if "stream" in chunk:
                    print(chunk["stream"], end="")
        self.image = image

    def get_ip_from_domain(self, domain="leshan"):
        try:
            containers = self.client.containers.list()
            for container in containers:
                name = container.name
                if name and (
                    domain == name or f"_{domain}_" in name or name.endswith(f"_{domain}")
                ):
                    networks = container.attrs.get("NetworkSettings", {}).get("Networks", {})
                    for net_info in networks.values():
                        ip = net_info.get("IPAddress", "")
                        if ip:
                            self.leshan_ip = ip
                            return True
                networks = container.attrs.get("NetworkSettings", {}).get("Networks", {})
                for net_info in networks.values():
                    aliases = net_info.get("Aliases", [])
                    if aliases and domain in aliases:
                        ip = net_info.get("IPAddress", "")
                        if ip:
                            self.leshan_ip = ip
                            return True
        except Exception as e:
            print(f"Error finding container for domain {domain}: {e}")
        return False

    def start_container(self):
        if not self.container:
            self.container = self.client.containers.run(
                self.image,
                "tail -f /dev/null",
                volumes=self.volumes,
                working_dir=os.getcwd(),
                detach=True,
                privileged=True,
                network=self.network_name,
            )

    def _stream_output(self, exec_id):
        output_stream = self.client.api.exec_start(exec_id, stream=True)
        for chunk in output_stream:
            print(chunk.decode("utf-8"), end="")

    def run_cmd_async(self, command, logging=False):
        if not self.container:
            raise RuntimeError("Container is not running.")
        exec_id = self.client.api.exec_create(self.container.id, command)
        if logging:
            thread = threading.Thread(target=self._stream_output, args=(exec_id,))
            thread.start()
        else:
            self.client.api.exec_start(exec_id, detach=True)
        return exec_id

    def run_cmd_sync(self, command, logging=False):
        if not self.container:
            raise RuntimeError("Container is not running.")
        exec_id = self.client.api.exec_create(self.container.id, command)
        output_stream = self.client.api.exec_start(exec_id, stream=True)
        output = ""
        for chunk in output_stream:
            line = chunk.decode("utf-8")
            output += line
            if logging:
                print(line, end="")
        exec_inspect = self.client.api.exec_inspect(exec_id)
        exit_code = exec_inspect.get("ExitCode")
        return exit_code, output

    def stop_container(self):
        if self.container:
            self.container.stop(timeout=1)
            self.container.remove()
            self.container = None


class ZephyrBackend:
    def __init__(self, config):
        self.config = config
        self.num_clients = config.get("device_count", 1)
        self.verbose = config.get("verbose", False)
        self.build = config.get("build", False)
        self.run = config.get("run", False)
        self.delay = config.get("delay", 0)
        self.local = config.get("local_leshan", False)
        self.docker_manager = None
        self.zephyr_conf_template = ZEPHYR_CONF

    def setup_podman_env(self):
        if os.environ.get("DOCKER_HOST"):
            return
        if not shutil.which("podman"):
            return
        uid = os.getuid()
        socket_path = f"/run/user/{uid}/podman/podman.sock"
        if not os.path.exists(socket_path):
            try:
                subprocess.run(["systemctl", "--user", "start", "podman.socket"], check=True)
                time.sleep(1)
            except Exception:
                return
        if os.path.exists(socket_path):
            os.environ["DOCKER_HOST"] = f"unix://{socket_path}"

    def build_clients(self):
        for i in range(self.num_clients):
            print(f"Building Zephyr client [{i + 1}/{self.num_clients}]", end="\r")
            file_path = os.path.join(TEMP_CONF_DIR, f"ep.{i}.conf")
            ip_addr = f"192.0.{i}.3"
            hwaddr = f"00:00:5e:01:{i:02x}:00"
            gw_addr = f"192.0.{i}.1"
            imei = str(BASE_IMEI + i)
            zeth_name = f"zeth.{i}"
            with open(file_path, "w") as config_file:
                config_file.write(
                    self.zephyr_conf_template.format(
                        ip_addr=ip_addr,
                        gw_addr=gw_addr,
                        hwaddr=hwaddr,
                        imei=imei,
                        zeth_name=zeth_name,
                    )
                )
            build_cmd = [
                "west",
                "build",
                "-p=auto",
                "-b",
                "native_sim/native/64",
                APP,
                "--",
                f"-DEXTRA_CONF_FILE=overlay-lwm2m-1.1.conf overlay-tls.conf ../{file_path}",
            ]
            result = subprocess.run(build_cmd, capture_output=True)
            if result.returncode:
                print(f"Build failed for client {i}")
                raise RuntimeError(f"Build failed for client {i}")
            shutil.copy("build/zephyr/zephyr.exe", f"{BINDIR}/ep_{i}.exe")

    def setup_net_ifaces(self):
        for i in range(self.num_clients):
            file_path = os.path.join(TEMP_CONF_DIR, f"zeth.{i}.conf")
            if_ip_addr = f"192.0.{i}.1/24"
            if_ip_route = f"192.0.{i}.0/24"
            hwaddr = f"00:00:5e:00:00:{i:02x}"
            if_name = f"zeth.{i}"
            with open(file_path, "w") as config_file:
                config_file.write(
                    IF_CONF.format(
                        if_ip_addr=if_ip_addr,
                        if_ip_route=if_ip_route,
                        hwaddr=hwaddr,
                        if_name=if_name,
                    )
                )
            cmd = f"/net-tools/net-setup.sh --config {file_path} -i zeth.{i} start"
            exit_code, _ = self.docker_manager.run_cmd_sync(cmd, logging=self.verbose)
            if exit_code != 0:
                print("Failed to start zeth")
                raise RuntimeError("Failed to start zeth")

    def start_clients(self):
        for i in range(self.num_clients):
            cmd = f"{BINDIR}/ep_{i}.exe"
            self.docker_manager.run_cmd_async(cmd, logging=self.verbose)
            time.sleep(self.delay / 1000)

    def start(self):
        self.setup_podman_env()
        os.makedirs(TEMP_CONF_DIR, exist_ok=True)
        os.makedirs(BINDIR, exist_ok=True)
        self.docker_manager = DockerManager(CONTAINER_VOLUME_MAPPING)
        self.docker_manager.build_container()
        self.docker_manager.start_container()

        if self.local:
            if not self.docker_manager.get_ip_from_domain("leshan"):
                print("Failed to get IP address of Leshan server.")
                raise RuntimeError("Failed to get IP address of Leshan server.")
            self.zephyr_conf_template += (
                f'\nCONFIG_LWM2M_APP_SERVER="coap://{self.docker_manager.leshan_ip}:5683"'
            )

        if self.build:
            subprocess.run(f"rm -f {BINDIR}/*", shell=True, check=True)
            subprocess.run("rm -f ./conf_tmp/*", shell=True, check=True)
            self.build_clients()

        if self.run:
            self.setup_net_ifaces()
            self.start_clients()
            print(f"Started {self.num_clients} Zephyr clients.")
            while True:
                time.sleep(1)

    def stop(self):
        if self.docker_manager:
            self.docker_manager.stop_container()
