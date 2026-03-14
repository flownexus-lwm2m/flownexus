#
# Copyright (c) 2024 Jonas Remmert
#
# SPDX-License-Identifier: Apache-2.0
#
import argparse
import os
import signal
import sys

import yaml

from device_simulator import MockBackend


def signal_handler(sig, frame, backend):
    if backend:
        backend.stop()
    sys.exit(0)


def main():
    parser = argparse.ArgumentParser(description="Flownexus Mock Device Simulator")
    parser.add_argument(
        "--config",
        type=str,
        required=True,
        help="Path to simulation YAML config file",
    )

    args = parser.parse_args()

    config = {}
    with open(args.config) as f:
        config = yaml.safe_load(f)

    backend = MockBackend(config)

    signal.signal(signal.SIGINT, lambda s, f: signal_handler(s, f, backend))
    signal.signal(signal.SIGTERM, lambda s, f: signal_handler(s, f, backend))

    try:
        backend.start()
    except Exception as e:
        print(f"Simulation failed: {e}")
        if backend:
            backend.stop()
        sys.exit(1)


if __name__ == "__main__":
    main()
