#
# Copyright (c) 2024 Jonas Remmert
#
# SPDX-License-Identifier: Apache-2.0
#
import http.server
import json
import logging
import math
import os
import random
import threading
import time
from urllib.parse import urlparse

import requests

logger = logging.getLogger(__name__)


class MockLeshanHandler(http.server.BaseHTTPRequestHandler):
    def do_PUT(self):
        # Handle /api/clients/{ep}/5/0/1 (Package URI)
        path = urlparse(self.path).path
        content_length = int(self.headers.get("Content-Length", 0))
        post_data = self.rfile.read(content_length).decode("utf-8")

        print(f"Mock Leshan received PUT: {path}")

        try:
            data = json.loads(post_data)
            path_parts = path.strip("/").split("/")
            print(f"Parsed path parts: {path_parts}")

            if "clients" in path_parts:
                idx = path_parts.index("clients")
                # Expected: .../clients/{ep}/{obj}/{inst}/{res}
                if len(path_parts) >= idx + 5:
                    endpoint = path_parts[idx + 1]
                    obj_id = path_parts[idx + 2]
                    inst_id = path_parts[idx + 3]
                    res_id = path_parts[idx + 4]
                    print(f"Endpoint: {endpoint}, Obj: {obj_id}, Inst: {inst_id}, Res: {res_id}")

                    if obj_id == "5" and res_id == "1":
                        uri = data.get("value")
                        print(f"FOTA Triggered for {endpoint}: {uri}")
                        self.send_response(200)
                        self.end_headers()
                        self.wfile.write(json.dumps({"status": "SUCCESS"}).encode())
                        # Start FOTA thread
                        mock_backend = getattr(self.server, "mock_backend", None)
                        if mock_backend is None:
                            self.send_response(500)
                            self.end_headers()
                            return
                        threading.Thread(
                            target=mock_backend.process_fota, args=(endpoint, uri)
                        ).start()
                        return
        except Exception as e:
            print(f"Error in MockLeshanHandler PUT: {e}")

        print(f"Mock Leshan 404 on PUT: {path}")
        self.send_response(404)
        self.end_headers()

    def do_POST(self):
        # Handle /api/clients/{ep}/5/0/2 (Execute Update)
        path = urlparse(self.path).path
        print(f"Mock Leshan received POST: {path}")
        path_parts = path.strip("/").split("/")

        try:
            if "clients" in path_parts:
                idx = path_parts.index("clients")
                if len(path_parts) >= idx + 5:
                    endpoint = path_parts[idx + 1]
                    obj_id = path_parts[idx + 2]
                    inst_id = path_parts[idx + 3]
                    res_id = path_parts[idx + 4]
                    print(f"Endpoint: {endpoint}, Obj: {obj_id}, Inst: {inst_id}, Res: {res_id}")

                    if obj_id == "5" and res_id == "2":
                        self.send_response(200)
                        self.end_headers()
                        self.wfile.write(json.dumps({"status": "SUCCESS"}).encode())
                        # Trigger Update execution
                        mock_backend = getattr(self.server, "mock_backend", None)
                        if mock_backend is None:
                            self.send_response(500)
                            self.end_headers()
                            return
                        threading.Thread(target=mock_backend.execute_fota, args=(endpoint,)).start()
                        return
        except Exception as e:
            print(f"Error in MockLeshanHandler POST: {e}")

        print(f"Mock Leshan 404 on POST: {path}")
        self.send_response(404)
        self.end_headers()

    def log_message(self, format, *args):
        return  # Silence standard logging


class MockBackend:
    def __init__(self, config):
        self.config = config
        self.device_count = int(config.get("device_count", 5))
        self.interval = float(config.get("interval", 5.0))
        self.target_url = config.get("url", "http://localhost:8000/flownexus/ingest")
        self.duration = config.get("duration", 0)  # 0 means infinite
        self.run = config.get("run", True)
        self.endpoints = []
        # start_time is set in start() after registration completes
        self.fota_states = {}  # ep -> current_fota_info
        self.enable_leshan_api = config.get("enable_leshan_api", True)
        self.leshan_api_port = config.get("leshan_api_port", 8081)

    def _register_device(self, imei):
        urn = f"urn:imei:{imei}"
        url_composite = f"{self.target_url}/resource/composite"

        # 1. Registration Event
        reg_payload = {
            "ep": urn,
            "val": {
                "/10240": {
                    "kind": "obj",
                    "id": 10240,
                    "instances": [
                        {
                            "id": 0,
                            "kind": "instance",
                            "resources": [
                                {
                                    "kind": "singleResource",
                                    "id": 0,
                                    "type": "INTEGER",
                                    "value": 1,
                                }
                            ],
                        }
                    ],
                }
            },
        }

        try:
            response = requests.post(url_composite, json=reg_payload, timeout=5)
            if response.status_code != 201:
                print(f"Failed to register {urn}: {response.status_code}")
                logger.error(f"Failed to register {urn}: {response.status_code} {response.text}")
                return False

            print(f"Registered device: {urn}")
            logger.info(f"Registered device: {urn}")

            # 2. Device Info Event (sent after registration accepted)
            info_payload = {
                "ep": urn,
                "val": {
                    "/3": {
                        "kind": "obj",
                        "id": 3,
                        "instances": [
                            {
                                "id": 0,
                                "kind": "instance",
                                "resources": [
                                    {
                                        "kind": "singleResource",
                                        "id": 0,
                                        "type": "STRING",
                                        "value": "Acme Corp",
                                    },
                                    {
                                        "kind": "singleResource",
                                        "id": 1,
                                        "type": "STRING",
                                        "value": "Mock Device",
                                    },
                                    {
                                        "kind": "singleResource",
                                        "id": 2,
                                        "type": "STRING",
                                        "value": str(imei),
                                    },
                                    {
                                        "kind": "singleResource",
                                        "id": 3,
                                        "type": "STRING",
                                        "value": "v0.0.1",
                                    },
                                ],
                            }
                        ],
                    }
                },
            }
            requests.post(url_composite, json=info_payload, timeout=5)
            return True

        except Exception as e:
            logger.error(f"Error registering {urn}: {e}")
        return False

    def _send_telemetry(self, imei, tick):
        urn = f"urn:imei:{imei}"
        # Sine wave for temperature (Object 3303, Resource 5700)
        temp = 20 + 5 * math.sin(tick / 10.0 + int(imei) % 10)
        # Random humidity (Object 3304, Resource 5700)
        hum = 40 + 20 * random.random()

        payload = {
            "ep": urn,
            "val": [
                {
                    "null": {
                        "nodes": {
                            "/3303/0/5700": {
                                "kind": "singleResource",
                                "id": 5700,
                                "type": "FLOAT",
                                "value": round(temp, 2),
                            },
                            "/3304/0/5700": {
                                "kind": "singleResource",
                                "id": 5700,
                                "type": "FLOAT",
                                "value": round(hum, 2),
                            },
                        }
                    }
                }
            ],
        }
        try:
            url = f"{self.target_url}/resource/timestamped"
            requests.post(url, json=payload, timeout=5)
        except Exception as e:
            logger.error(f"Error sending telemetry for {urn}: {e}")

    def report_fota_state(self, endpoint, state):
        payload = {
            "ep": endpoint,
            "obj_id": 5,
            "val": {
                "kind": "singleResource",
                "id": 3,
                "type": "INTEGER",
                "value": str(state),
            },
        }
        url = f"{self.target_url}/resource/single"
        try:
            requests.post(url, json=payload, timeout=5)
            logger.info(f"Reported FOTA state {state} for {endpoint}")
        except Exception as e:
            logger.error(f"Error reporting FOTA state: {e}")

    def process_fota(self, endpoint, uri):
        logger.info(f"Processing FOTA for {endpoint} with URI: {uri}")
        time.sleep(11)
        self.report_fota_state(endpoint, 1)  # DOWNLOADING

        # Verify download
        try:
            # Construct absolute URL if it's relative
            base_url = urlparse(self.target_url)
            if uri.startswith("/"):
                download_url = f"{base_url.scheme}://{base_url.netloc}{uri}"
            else:
                download_url = uri

            logger.info(f"Mock downloading from: {download_url}")
            resp = requests.get(download_url, timeout=10)
            if resp.status_code == 200:
                print(f"Download successful, size: {len(resp.content)} bytes")
                # Extract version from filename
                filename = os.path.basename(uri)
                # If the filename contains 'v' and numbers, it's likely the version
                # Otherwise, it might be an arbitrary name.
                # We'll strip common extensions.
                version = filename
                for ext in [".bin", ".exe", ".xlsx", ".zip"]:
                    if version.endswith(ext):
                        version = version[: -len(ext)]

                print(f"Mock device '{endpoint}' parsed version '{version}' from file")
                self.fota_states[endpoint] = {"version": version}
            else:
                logger.error(f"Download failed: {resp.status_code}")
                # We could report a failure result here (5/0/5)
                return
        except Exception as e:
            logger.error(f"FOTA Download error: {e}")
            return

        time.sleep(11)
        self.report_fota_state(endpoint, 2)  # DOWNLOADED

    def execute_fota(self, endpoint):
        print(f"Executing FOTA for {endpoint}")
        time.sleep(11)
        self.report_fota_state(endpoint, 3)  # UPDATING
        time.sleep(11)

        # Simulate reboot and report new version

        version = self.fota_states.get(endpoint, {}).get("version", "v1.0.0-mock")
        print(f"Mock device '{endpoint}' rebooting and reporting version: {version}")
        payload = {
            "ep": endpoint,
            "obj_id": 3,
            "val": {
                "kind": "singleResource",
                "id": 3,
                "type": "STRING",
                "value": version,
            },
        }
        url = f"{self.target_url}/resource/single"
        try:
            requests.post(url, json=payload, timeout=5)
            logger.info(f"Reported new version {version} for {endpoint}")
        except Exception as e:
            logger.error(f"Error reporting new version: {e}")

    def start(self):
        if not self.run:
            print("Mock backend started, but 'run' is false. Doing nothing.")
            return

        # Start Mock Leshan API
        if self.enable_leshan_api:
            server_address = ("", self.leshan_api_port)
            try:
                httpd = http.server.HTTPServer(server_address, MockLeshanHandler)
                httpd.mock_backend = self
                threading.Thread(target=httpd.serve_forever, daemon=True).start()
                print(f"Mock Leshan API listening on port {self.leshan_api_port}")
            except OSError as e:
                print(
                    f"Warning: Could not start Mock Leshan API on port {self.leshan_api_port}: {e}"
                )

        print(f"\nStarting Mock Simulation: {self.device_count} devices")
        print(f"   Target: {self.target_url}")
        print(f"   Interval: {self.interval}s\n")

        # Register devices
        print("Registering devices...")
        for i in range(self.device_count):
            imei = i + 1
            if self._register_device(imei):
                self.endpoints.append(imei)

        if not self.endpoints:
            print("No devices registered. Exiting.")
            return

        print(f"\n{len(self.endpoints)}/{self.device_count} devices registered successfully")
        print(f"Sending telemetry every {self.interval}s (Press Ctrl+C to stop)\n")

        # Start the duration timer now that registration is complete
        self.start_time = time.time()

        tick = 0
        last_status_time = time.time()
        telemetry_count = 0

        try:
            while True:
                if self.duration > 0 and (time.time() - self.start_time) > self.duration:
                    print("\nDuration reached. Stopping simulation.")
                    break

                for imei in self.endpoints:
                    self._send_telemetry(imei, tick)
                    telemetry_count += 1

                tick += 1

                # Print status update every 30 seconds
                if time.time() - last_status_time >= 30:
                    print(
                        f"Status: {len(self.endpoints)} devices active | "
                        f"{telemetry_count} telemetry samples sent | "
                        f"Running for {int(time.time() - self.start_time)}s"
                    )
                    telemetry_count = 0
                    last_status_time = time.time()

                time.sleep(self.interval)
        except KeyboardInterrupt:
            print("\n\nSimulation stopped by user.")
            print(f"   Runtime: {int(time.time() - self.start_time)}s")

    def stop(self):
        pass
