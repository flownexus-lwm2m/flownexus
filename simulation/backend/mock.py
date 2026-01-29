#
# Copyright (c) 2024 Jonas Remmert
#
# SPDX-License-Identifier: Apache-2.0
#
import logging
import math
import random
import time

import requests

logger = logging.getLogger(__name__)


class MockBackend:
    def __init__(self, config):
        self.config = config
        self.device_count = config.get("device_count", 5)
        self.interval = config.get("interval", 5.0)
        self.target_url = config.get("url", "http://localhost:8000/flownexus/ingest")
        self.duration = config.get("duration", 0)  # 0 means infinite
        self.run = config.get("run", True)
        self.endpoints = []
        self.start_time = time.time()

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
                logger.error(f"Failed to register {urn}: {response.status_code} {response.text}")
                return False

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

    def start(self):
        if not self.run:
            print("Mock backend started, but 'run' is false. Doing nothing.")
            return

        print(f"Starting Mock Simulation: {self.device_count} devices at {self.target_url}")

        # Register devices
        for i in range(self.device_count):
            imei = i + 1
            if self._register_device(imei):
                self.endpoints.append(imei)

        if not self.endpoints:
            print("No devices registered. Exiting.")
            return

        print(f"Simulation running. Interval: {self.interval}s")
        tick = 0
        try:
            while True:
                if self.duration > 0 and (time.time() - self.start_time) > self.duration:
                    print("Duration reached. Stopping simulation.")
                    break

                for imei in self.endpoints:
                    self._send_telemetry(imei, tick)

                tick += 1
                time.sleep(self.interval)
        except KeyboardInterrupt:
            print("\nSimulation stopped by user.")

    def stop(self):
        pass
