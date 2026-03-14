#
# Copyright (c) 2024 Jonas Remmert
#
# SPDX-License-Identifier: Apache-2.0
#

import sys
import time

import requests

BASE_URL = "http://localhost:8000/flownexus/ingest"
ENDPOINT_ID = "urn:imei:100000000000000"
TIMEOUT = 60  # seconds


def verify():
    start_time = time.time()
    while time.time() - start_time < TIMEOUT:
        try:
            response = requests.get(f"{BASE_URL}/endpoints/{ENDPOINT_ID}/")
            if response.status_code == 200:
                print(f"Successfully verified endpoint {ENDPOINT_ID}")
                # Now check if it has resources
                res_response = requests.get(f"{BASE_URL}/endpoints/{ENDPOINT_ID}/resources/")
                if res_response.status_code == 200 and len(res_response.json()) > 0:
                    print("Successfully verified resources exist.")
                    return True
                else:
                    print("Endpoint exists but no resources yet...")
            else:
                print(f"Endpoint {ENDPOINT_ID} not found yet (status {response.status_code})...")
        except requests.exceptions.ConnectionError:
            print("Waiting for server...")

        time.sleep(5)

    print("Verification timed out!")
    return False


if __name__ == "__main__":
    if verify():
        sys.exit(0)
    else:
        sys.exit(1)
