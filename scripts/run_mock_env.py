#!/usr/bin/env python3
#
# Copyright (c) 2026 Jonas Remmert
#
# SPDX-License-Identifier: Apache-2.0
#

import os
import signal
import subprocess
import sys
import time

# Use absolute paths to avoid relative path confusion
ROOT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
VENV_BIN = os.path.join(ROOT_DIR, "server/django/.venv/bin")
PYTHON_EXEC = os.path.join(VENV_BIN, "python")
CELERY_EXEC = os.path.join(VENV_BIN, "celery")


def signal_handler(sig, frame):
    print("\nShutting down mock environment...")
    for p in processes:
        try:
            # Kill the entire process group
            os.killpg(os.getpgid(p.pid), signal.SIGTERM)
        except Exception:
            pass

    # Wait a bit and force kill if still alive
    time.sleep(1)
    for p in processes:
        try:
            os.killpg(os.getpgid(p.pid), signal.SIGKILL)
        except Exception:
            pass

    sys.exit(0)


signal.signal(signal.SIGINT, signal_handler)
signal.signal(signal.SIGTERM, signal_handler)

processes = []

# 1. Start Redis
print("--- Starting Redis ---")
subprocess.run(["podman-compose", "-f", "server/compose.yml", "up", "-d", "redis"], cwd=ROOT_DIR)
time.sleep(2)  # Give Redis a moment


# 2. Environment for Django and Celery
env = os.environ.copy()
env["LESHAN_URI"] = "http://localhost:8081"
env["PYTHONPATH"] = os.path.join(ROOT_DIR, "server/django")

# 3. Start Django
print("--- Starting Django ---")
django_cmd = [
    PYTHON_EXEC,
    os.path.join(ROOT_DIR, "server/django/manage.py"),
    "runserver",
    "0.0.0.0:8000",
]
p_django = subprocess.Popen(django_cmd, env=env, cwd=ROOT_DIR, preexec_fn=os.setsid)
processes.append(p_django)

# Wait for Django to be ready
print("Waiting for Django...")
for _ in range(30):
    try:
        import requests

        resp = requests.get("http://localhost:8000", timeout=1)
        print("Django is ready!")
        break
    except Exception:
        time.sleep(1)
else:
    print("Warning: Django not ready, proceeding anyway...")

# 4. Start Celery
print("--- Starting Celery ---")
celery_cmd = [CELERY_EXEC, "-A", "core", "worker", "--loglevel=info", "-P", "gevent", "-c", "10"]
p_celery = subprocess.Popen(
    celery_cmd, env=env, cwd=os.path.join(ROOT_DIR, "server/django"), preexec_fn=os.setsid
)
processes.append(p_celery)

# 5. Start Simulation
print("--- Starting Simulation ---")
sim_cmd = [
    PYTHON_EXEC,
    os.path.join(ROOT_DIR, "simulation/simulate.py"),
    "--config",
    os.path.join(ROOT_DIR, "simulation/sim_mock.yaml"),
]
p_sim = subprocess.Popen(sim_cmd, env=env, cwd=ROOT_DIR, preexec_fn=os.setsid)
processes.append(p_sim)

print("\nMock Environment is UP!")
print("Dashboard: http://localhost:8000")
print("Press Ctrl+C to stop everything.")

try:
    while True:
        time.sleep(1)
        # Check if any process died
        for p in processes:
            if p.poll() is not None:
                # If it's the simulation, it might have finished if duration was set
                # but usually it should stay up.
                print(f"Process {p.args} died with code {p.returncode}")
                signal_handler(None, None)
except KeyboardInterrupt:
    signal_handler(None, None)


print("\nMock Environment is UP!")
print("Dashboard: http://localhost:8000")
print("Press Ctrl+C to stop everything.")

try:
    while True:
        time.sleep(1)
        # Check if any process died
        for p in processes:
            if p.poll() is not None:
                print(f"Process {p.args} died with code {p.returncode}")
                signal_handler(None, None)
except KeyboardInterrupt:
    signal_handler(None, None)
