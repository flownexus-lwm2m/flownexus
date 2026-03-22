#!/usr/bin/env python3
#
# Copyright (c) 2026 Jonas Remmert
#
# SPDX-License-Identifier: Apache-2.0
#

import argparse
import os
import signal
import subprocess
import sys
import tempfile
import time
from pathlib import Path

import yaml

ROOT_DIR = Path(__file__).resolve().parent.parent.parent
COMPOSE_FILE = ROOT_DIR / "server/compose.yml"
SCENARIO_DIR = ROOT_DIR / "devtools/mock/scenarios"
SIM_CONFIG = ROOT_DIR / "devtools/mock/config.yaml"

processes = []
redis_started = False


def build_env(db_path):
    env = os.environ.copy()
    env["DJANGO_DB_PATH"] = str(db_path)
    env["LESHAN_URI"] = "http://localhost:8081"
    env["PYTHONPATH"] = str(ROOT_DIR / "server/django")
    return env


def load_scenario(scenario_name):
    scenario_path = SCENARIO_DIR / f"{scenario_name}.yaml"
    if not scenario_path.exists():
        sys.exit(f"Scenario not found: {scenario_path}")

    with scenario_path.open(encoding="utf-8") as handle:
        return yaml.safe_load(handle) or {}


def create_sim_config(scenario, temp_dir):
    """Create a temporary simulation config based on scenario settings."""
    devices = scenario.get("devices", {})
    config = {
        "type": "mock",
        "url": "http://localhost:8000/flownexus/ingest",
        "device_count": devices.get("count", 5),
        "interval": devices.get("interval", 2.0),
        "duration": 0,
        "run": True,
        "enable_leshan_api": True,
    }

    config_path = temp_dir / "mock_sim_config.yaml"
    with open(config_path, "w") as f:
        yaml.dump(config, f)

    return config_path


def run_command(command, env, description, cwd=ROOT_DIR, quiet=False):
    stdout = subprocess.DEVNULL if quiet else None
    stderr = subprocess.DEVNULL if quiet else None
    result = subprocess.run(command, cwd=cwd, env=env, stdout=stdout, stderr=stderr)
    if result.returncode != 0:
        sys.exit(f"{description} failed")


def start_process(command, env, description, cwd=ROOT_DIR, quiet=False):
    stdout = subprocess.DEVNULL if quiet else None
    stderr = subprocess.DEVNULL if quiet else None
    process = subprocess.Popen(
        command,
        cwd=cwd,
        env=env,
        preexec_fn=os.setsid,
        stdout=stdout,
        stderr=stderr,
    )
    processes.append((description, process))
    return process


def shutdown(signum=None, frame=None):
    del signum, frame
    print("\nShutting down mock environment...")

    for _, process in processes:
        try:
            os.killpg(os.getpgid(process.pid), signal.SIGTERM)
        except ProcessLookupError:
            pass

    time.sleep(1)

    for _, process in processes:
        if process.poll() is None:
            try:
                os.killpg(os.getpgid(process.pid), signal.SIGKILL)
            except ProcessLookupError:
                pass

    if redis_started:
        subprocess.run(
            ["podman-compose", "-f", str(COMPOSE_FILE), "stop", "redis"],
            cwd=ROOT_DIR,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )

    sys.exit(0)


def setup_database(env, scenario_name, quiet):
    print("\n--- Setting up temporary database ---")
    run_command(
        ["uv", "run", "--no-dev", "python", "server/django/manage.py", "migrate"],
        env,
        "Database migration",
        quiet=quiet,
    )
    run_command(
        [
            "uv",
            "run",
            "--no-dev",
            "python",
            "server/django/manage.py",
            "load_initial_resource_types",
        ],
        env,
        "Resource type load",
        quiet=quiet,
    )
    run_command(
        [
            "uv",
            "run",
            "--no-dev",
            "python",
            "server/django/manage.py",
            "load_scenario",
            "--config",
            scenario_name,
        ],
        env,
        "Scenario load",
        quiet=quiet,
    )
    print("Database setup complete.")


def wait_for_django():
    import requests

    print("Waiting for Django...")
    for _ in range(30):
        try:
            response = requests.get("http://localhost:8000", timeout=1)
            if response.status_code < 500:
                print("Django is ready!")
                return
        except requests.RequestException:
            time.sleep(1)

    sys.exit("Django did not become ready in time")


def print_login_info(scenario_name, scenario):
    users = scenario.get("users", [])
    if scenario_name == "multi-site":
        print("\nTest Users:")
        for user in users:
            username = user["username"]
            password = user["password"]
            if user.get("is_superuser"):
                role = "Global superuser"
            else:
                memberships = user.get("sites", [])
                site_names = ", ".join(site["name"] for site in memberships)
                role = memberships[0].get("role", "USER") if memberships else "USER"
                role = f"{role} - {site_names}" if site_names else role
            print(f"  {username} / {password} ({role})")
    else:
        admin_user = users[0] if users else {"username": "admin", "password": "admin"}
        print(f"\nDefault Login: {admin_user['username']} / {admin_user['password']}")


def main():
    global redis_started

    parser = argparse.ArgumentParser(description="Run the flownexus mock environment")
    parser.add_argument("--scenario", default="default", help="Scenario config name")
    parser.add_argument("--fresh", action="store_true", help="Delete existing temp database")
    parser.add_argument("-v", "--verbose", action="store_true", help="Show subprocess output")
    args = parser.parse_args()

    scenario = load_scenario(args.scenario)

    temp_dir = Path(tempfile.gettempdir())
    sim_config = create_sim_config(scenario, temp_dir)
    db_path = temp_dir / f"flownexus_mock_{args.scenario}.sqlite3"
    if args.fresh and db_path.exists():
        print(f"Removing existing database: {db_path}")
        db_path.unlink()

    env = build_env(db_path)
    quiet = not args.verbose

    print(f"Using temporary database: {db_path}")
    setup_database(env, args.scenario, quiet)

    print("\n--- Starting Redis ---")
    run_command(
        ["podman-compose", "-f", str(COMPOSE_FILE), "up", "-d", "redis"],
        os.environ.copy(),
        "Redis startup",
        quiet=quiet,
    )
    redis_started = True
    time.sleep(2)

    print("--- Starting Django ---")
    start_process(
        ["uv", "run", "--no-dev", "python", "server/django/manage.py", "runserver", "0.0.0.0:8000"],
        env,
        "Django",
        quiet=quiet,
    )
    wait_for_django()

    print("--- Starting Celery ---")
    celery_loglevel = "info" if args.verbose else "warning"
    start_process(
        [
            "uv",
            "run",
            "--no-dev",
            "celery",
            "-A",
            "core",
            "worker",
            f"--loglevel={celery_loglevel}",
            "-P",
            "gevent",
            "-c",
            "10",
        ],
        env,
        "Celery",
        cwd=ROOT_DIR / "server/django",
        quiet=quiet,
    )

    print("--- Starting Simulation ---")
    start_process(
        [
            "uv",
            "run",
            "--group",
            "mock",
            "python",
            "devtools/mock/run.py",
            "--config",
            str(sim_config),
        ],
        env,
        "Simulation",
        quiet=False,
    )

    print("\n" + "=" * 60)
    print("Mock Environment is UP!")
    print(f"Scenario: {args.scenario}")
    print("Dashboard: http://localhost:8000")
    print(f"Database: {db_path}")
    print("=" * 60)
    print_login_info(args.scenario, scenario)
    print("\nPress Ctrl+C to stop everything.")

    while True:
        time.sleep(1)
        for description, process in processes:
            if process.poll() is not None:
                print(f"{description} exited with code {process.returncode}")
                shutdown()


if __name__ == "__main__":
    signal.signal(signal.SIGINT, shutdown)
    signal.signal(signal.SIGTERM, shutdown)
    main()
