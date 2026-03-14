#
# Copyright (c) 2024 Jonas Remmert
#
# SPDX-License-Identifier: Apache-2.0
#
import argparse
import signal
import sys

import yaml
from device_simulator import ZephyrBackend


def signal_handler(sig, frame, backend):
    if backend:
        backend.stop()
    sys.exit(0)


def main():
    parser = argparse.ArgumentParser(description="Flownexus Zephyr Device Simulator")
    parser.add_argument(
        "--config",
        type=str,
        required=True,
        help="Path to simulation YAML config file",
    )
    parser.add_argument(
        "--build",
        action="store_true",
        help="Build Zephyr binaries",
    )
    parser.add_argument(
        "--run",
        action="store_true",
        help="Run simulation",
    )
    parser.add_argument(
        "--local",
        action="store_true",
        dest="local_leshan",
        help="Use local Leshan server",
    )

    args = parser.parse_args()

    config = {}
    with open(args.config) as f:
        config = yaml.safe_load(f)

    # Override YAML with CLI args if explicitly provided
    if args.build:
        config["build"] = True
    if args.run:
        config["run"] = True
    if args.local_leshan:
        config["local_leshan"] = True

    backend = ZephyrBackend(config)

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
