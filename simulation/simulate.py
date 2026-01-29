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

# Add the current directory to sys.path to allow importing from backend package
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from backend.mock import MockBackend
from backend.zephyr import ZephyrBackend


def signal_handler(sig, frame, backend):
    print("\nShutting down simulation...")
    if backend:
        backend.stop()
    sys.exit(0)


def main():
    parser = argparse.ArgumentParser(description="Flownexus Device Simulation Dispatcher")
    parser.add_argument(
        "--config", type=str, required=True, help="Path to simulation YAML config file"
    )

    # Convenience overrides for actions
    parser.add_argument("--build", action="store_true", help="Build binaries (Zephyr only)")
    parser.add_argument("--run", action="store_true", help="Run simulation")
    parser.add_argument(
        "--local",
        action="store_true",
        dest="local_leshan",
        help="Use local Leshan server (Zephyr only)",
    )
    parser.add_argument(
        "--type", type=str, choices=["mock", "zephyr"], help="Override simulation type"
    )
    parser.add_argument("--count", type=int, dest="device_count", help="Override number of devices")

    args = parser.parse_args()

    config = {}
    if args.config:
        with open(args.config) as f:
            config = yaml.safe_load(f)

    # Override YAML with CLI args if explicitly provided
    if args.build:
        config["build"] = True
    if args.run:
        config["run"] = True
    if args.local_leshan:
        config["local_leshan"] = True
    if args.type:
        config["type"] = args.type
    if args.device_count:
        config["device_count"] = args.device_count

    sim_type = config.get("type", "zephyr")

    backend = None
    if sim_type == "mock":
        backend = MockBackend(config)
    elif sim_type == "zephyr":
        backend = ZephyrBackend(config)
    else:
        print(f"Unknown simulation type: {sim_type}")
        sys.exit(1)

    # Register signal handlers
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
