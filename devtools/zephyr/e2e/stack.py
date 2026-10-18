# Copyright (c) 2026 Jonas Remmert
#
# SPDX-License-Identifier: Apache-2.0

"""Local service stack used by the Zephyr E2E scenarios."""

from __future__ import annotations

import os
import shutil
import socket
import subprocess
import time

from .harness import HarnessError, ManagedProcess, ProcessSupervisor, RunConfig, wait_for_http


class LocalStack:
    """Run Django, Celery, Redis, and the Leshan image in isolation."""

    def __init__(self, config: RunConfig) -> None:
        self.config = config
        self.supervisor = ProcessSupervisor(config.artifact_dir)
        self._redis_container = f"flownexus-e2e-redis-{config.endpoint.rsplit('-', 1)[-1]}"
        self._leshan_container = f"flownexus-e2e-leshan-{config.endpoint.rsplit('-', 1)[-1]}"
        self._containers = (self._redis_container, self._leshan_container)
        self._processes: dict[str, ManagedProcess] = {}
        self._runtime: str | None = None
        self.db_path = config.artifact_dir / "db.sqlite3"
        self.media_path = config.artifact_dir / "media"

    @property
    def django_url(self) -> str:
        return f"http://127.0.0.1:{self.config.django_port}"

    @property
    def ingest_url(self) -> str:
        return f"{self.django_url}/flownexus/ingest"

    @property
    def leshan_url(self) -> str:
        return f"http://127.0.0.1:{self.config.leshan_http_port}"

    @property
    def redis_url(self) -> str:
        return f"redis://127.0.0.1:{self.config.redis_port}/0"

    def _env(self) -> dict[str, str]:
        env = os.environ.copy()
        env.update(
            {
                "DJANGO_SETTINGS_MODULE": "core.settings",
                "DJANGO_DB_PATH": str(self.db_path),
                "MEDIA_ROOT": str(self.media_path),
                "DJANGO_ALLOWED_HOSTS": (
                    "127.0.0.1,localhost,host.docker.internal,host.containers.internal"
                ),
                "CELERY_BROKER_URL": self.redis_url,
                "CELERY_RESULT_BACKEND": self.redis_url,
                "LESHAN_URI": self.leshan_url,
                "PYTHONUNBUFFERED": "1",
            }
        )
        return env

    def _run_management(self, *arguments: str) -> None:
        command = ["uv", "run", "--no-sync", "--no-dev", "python", "manage.py", *arguments]
        log_path = self.config.artifact_dir / f"management-{'-'.join(arguments)}.log"
        result = subprocess.run(
            command,
            cwd=self.config.root / "server/django",
            env=self._env(),
            stdout=log_path.open("w"),
            stderr=subprocess.STDOUT,
            check=False,
        )
        if result.returncode:
            raise HarnessError(f"Django command failed ({' '.join(arguments)}); see {log_path}")

    def _require_command(self, command: str) -> None:
        if shutil.which(command) is None:
            raise HarnessError(f"Required command is missing: {command}")

    def _select_runtime(self) -> tuple[str, str]:
        """Return the first working runtime that has the Leshan image, and the image.

        Hosts can run podman and docker side by side with separate image
        stores, so the runtime that built the image must also run it.
        """

        image = os.environ.get("FLOWNEXUS_LESHAN_IMAGE", "localhost/flownexus-leshan:latest")
        runtimes = []
        for command in ("podman", "docker"):
            if shutil.which(command) is None:
                continue
            if subprocess.run([command, "info"], capture_output=True, check=False).returncode:
                continue
            runtimes.append(command)
            inspect = [command, "image", "inspect", image]
            if subprocess.run(inspect, capture_output=True, check=False).returncode == 0:
                return command, image
        if not runtimes:
            raise HarnessError("No working container runtime (podman or docker)")
        raise HarnessError(
            f"Leshan image {image} is missing in {', '.join(runtimes)}; "
            "build it with make leshan-image"
        )

    def _host_gateway(self) -> tuple[str, str]:
        if self._runtime == "docker":
            return "host.docker.internal:host-gateway", "host.docker.internal"
        return "host.containers.internal:host-gateway", "host.containers.internal"

    def _wait_tcp(self, host: str, port: int, process: ManagedProcess, description: str) -> None:
        deadline = time.monotonic() + self.config.timeout
        while time.monotonic() < deadline:
            if process.poll() is not None:
                raise HarnessError(
                    f"{description} exited with {process.poll()}; see {process.log_path}"
                )
            try:
                with socket.create_connection((host, port), timeout=1):
                    return
            except OSError:
                time.sleep(0.2)
        raise HarnessError(f"Timed out waiting for {description}; see {process.log_path}")

    def start(self) -> None:
        """Start the stack and clean partial startup on any failure."""

        try:
            self._start()
        except BaseException:
            self.stop()
            raise

    def start_gateway(self, data_sender_port: int) -> None:
        """Start only the Leshan image, posting ingest requests to a host port."""

        try:
            self._runtime, image = self._select_runtime()
            self.config.artifact_dir.mkdir(parents=True, exist_ok=True)
            self._start_leshan(image, data_sender_port)
        except BaseException:
            self.stop()
            raise

    def _start(self) -> None:
        """Initialize and start all services, failing on the first bad owner."""

        self._require_command("uv")
        self._runtime, leshan_image = self._select_runtime()
        self.config.artifact_dir.mkdir(parents=True, exist_ok=True)
        self.media_path.mkdir(parents=True, exist_ok=True)

        redis = self.supervisor.start(
            "redis",
            [
                self._runtime,
                "run",
                "--rm",
                "--name",
                self._redis_container,
                "-p",
                f"127.0.0.1:{self.config.redis_port}:6379",
                "docker.io/library/redis:8.4-alpine",
                "redis-server",
                "--save",
                "",
                "--appendonly",
                "no",
            ],
            cwd=self.config.root,
            env=self._env(),
        )
        self._processes["redis"] = redis
        self._wait_tcp("127.0.0.1", self.config.redis_port, redis, "Redis")

        self._run_management("migrate", "--noinput")
        self._run_management("loaddata", "db_initial_data.json")
        self._run_management("load_initial_resource_types")

        django = self.supervisor.start(
            "django",
            [
                "uv",
                "run",
                "--no-sync",
                "--no-dev",
                "uvicorn",
                "core.asgi:application",
                "--host",
                "0.0.0.0",
                "--port",
                str(self.config.django_port),
                "--workers",
                "1",
            ],
            cwd=self.config.root / "server/django",
            env=self._env(),
        )
        self._processes["django"] = django
        wait_for_http(
            f"{self.django_url}/admin/login/", timeout=self.config.timeout, process=django
        )

        celery = self.supervisor.start(
            "celery",
            [
                "uv",
                "run",
                "--no-sync",
                "--no-dev",
                "celery",
                "-A",
                "core",
                "worker",
                "--loglevel=info",
                "--pool=solo",
                "--hostname",
                f"e2e-{self.config.endpoint.rsplit('-', 1)[-1]}@%h",
            ],
            cwd=self.config.root / "server/django",
            env=self._env(),
        )
        self._processes["celery"] = celery
        # A Celery worker does not expose HTTP readiness.  Its process must
        # stay alive through a short broker round trip before tests proceed.
        self._wait_celery(celery)
        self._start_leshan(leshan_image, self.config.django_port)

    def _start_leshan(self, image: str, data_sender_port: int) -> None:
        add_host, host_alias = self._host_gateway()
        leshan = self.supervisor.start(
            "leshan",
            [
                self._runtime,
                "run",
                "--rm",
                "--name",
                self._leshan_container,
                "--add-host",
                add_host,
                "-e",
                f"DATA_SENDER_URI=http://{host_alias}:{data_sender_port}",
                "-p",
                f"127.0.0.1:{self.config.leshan_http_port}:8080",
                "-p",
                f"127.0.0.1:{self.config.leshan_coap_port}:5683/udp",
                image,
            ],
            cwd=self.config.root,
            env=self._env(),
        )
        self._processes["leshan"] = leshan
        wait_for_http(f"{self.leshan_url}/health", timeout=self.config.timeout, process=leshan)

    def _wait_celery(self, process: ManagedProcess) -> None:
        deadline = time.monotonic() + self.config.timeout
        while time.monotonic() < deadline:
            if process.poll() is not None:
                raise HarnessError(f"Celery exited with {process.poll()}; see {process.log_path}")
            result = subprocess.run(
                [
                    "uv",
                    "run",
                    "--no-sync",
                    "--no-dev",
                    "celery",
                    "-A",
                    "core",
                    "inspect",
                    "ping",
                    "--timeout=1",
                ],
                cwd=self.config.root / "server/django",
                env=self._env(),
                capture_output=True,
                text=True,
                check=False,
            )
            if result.returncode == 0 and "pong" in result.stdout:
                return
            time.sleep(0.5)
        raise HarnessError(f"Timed out waiting for Celery worker; see {process.log_path}")

    def stop(self) -> None:
        """Stop owned processes and remove only this run's containers."""

        self.supervisor.stop_all()
        if self._runtime is not None:
            for container in self._containers:
                subprocess.run(
                    [self._runtime, "stop", "-t", "2", container],
                    capture_output=True,
                    check=False,
                )
        self._processes.clear()
