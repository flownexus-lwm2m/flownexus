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
        payload = {
            "ep": urn,
            "obj_id": 10240,
            "val": {"kind": "singleResource", "id": 0, "type": "INTEGER", "value": 1},
        }
        try:
            url = f"{self.target_url}/resource/single"
            response = requests.post(url, json=payload, timeout=5)
            if response.status_code == 201:
                logger.info(f"Registered device: {urn}")

                # Send Object 3 (Device) resources
                # Resources: 0=Manufacturer, 1=Model Number, 2=Serial Number, 3=Firmware Version
                device_info = [
                    (0, "STRING", "Acme Corp"),
                    (1, "STRING", "Mock Device"),
                    (2, "STRING", str(imei)),
                    (3, "STRING", "v0.0.0"),
                ]

                for rid, rtype, rval in device_info:
                    p = {
                        "ep": urn,
                        "obj_id": 3,
                        "val": {"kind": "singleResource", "id": rid, "type": rtype, "value": rval},
                    }
                    try:
                        requests.post(url, json=p, timeout=5)
                    except Exception as e:
                        logger.error(f"Error sending device info {rid} for {urn}: {e}")

                return True
            else:
                logger.error(f"Failed to register {urn}: {response.status_code} {response.text}")
        except Exception as e:
            logger.error(f"Error registering {urn}: {e}")
        return False

    def _send_telemetry(self, imei, tick):
        urn = f"urn:imei:{imei}"
        # Sine wave for temperature (Object 3303, Resource 5700)
        temp = 20 + 5 * math.sin(tick / 10.0 + int(imei) % 10)
        # Random humidity (Object 3304, Resource 5700)
        hum = 40 + 20 * random.random()

        telemetry = [(3303, "FLOAT", round(temp, 2)), (3304, "FLOAT", round(hum, 2))]

        for obj_id, val_type, value in telemetry:
            payload = {
                "ep": urn,
                "obj_id": obj_id,
                "val": {"kind": "singleResource", "id": 5700, "type": val_type, "value": value},
            }
            try:
                url = f"{self.target_url}/resource/single"
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
            imei = 100000000000000 + i
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
