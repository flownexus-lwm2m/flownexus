# Copyright (c) 2026 Jonas Remmert
#
# SPDX-License-Identifier: Apache-2.0

"""Process and protocol helpers for local Flownexus E2E tests.

The harness deliberately owns every process it starts.  It does not use
``pkill`` or a shared compose project, and each run gets a fresh database,
Redis namespace, endpoint identity, and artifact directory.
"""

from __future__ import annotations

import json
import os
import re
import signal
import socket
import sqlite3
import subprocess
import threading
import time
import tty
import uuid
from collections.abc import Iterable
from dataclasses import dataclass, field
from pathlib import Path
from queue import Empty, Queue

import requests


class HarnessError(RuntimeError):
    """Raised when a local E2E prerequisite or process fails."""


def free_tcp_port() -> int:
    """Return an unused TCP port.

    Ports are reserved only for discovery.  The caller must still handle a
    bind race when starting its process.
    """

    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind(("127.0.0.1", 0))
        return int(sock.getsockname()[1])


def free_udp_port() -> int:
    """Return an unused UDP port."""

    with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sock:
        sock.bind(("127.0.0.1", 0))
        return int(sock.getsockname()[1])


@dataclass(frozen=True)
class RunConfig:
    """Paths, ports, and bounded polling settings for one E2E run."""

    root: Path
    artifact_dir: Path
    endpoint: str
    django_port: int
    leshan_http_port: int
    leshan_coap_port: int
    redis_port: int
    timeout: float = 90.0
    poll_interval: float = 0.25
    retain_artifacts: bool = True

    @classmethod
    def create(cls, root: Path, artifact_root: Path | None = None) -> RunConfig:
        run_id = uuid.uuid4().hex[:12]
        artifact_dir = (artifact_root or root / "devtools/zephyr/e2e-artifacts") / run_id
        return cls(
            root=root,
            artifact_dir=artifact_dir,
            endpoint=f"urn:imei:e2e-{run_id}",
            django_port=free_tcp_port(),
            leshan_http_port=free_tcp_port(),
            leshan_coap_port=free_udp_port(),
            redis_port=free_tcp_port(),
        )


@dataclass
class ManagedProcess:
    """A subprocess and its retained output file."""

    name: str
    process: subprocess.Popen[bytes]
    log_path: Path
    output: Queue[str] = field(default_factory=Queue)

    def poll(self) -> int | None:
        return self.process.poll()

    def stop(self, timeout: float = 10.0) -> None:
        if self.process.poll() is not None:
            return
        try:
            self.process.send_signal(signal.SIGTERM)
            self.process.wait(timeout=timeout)
        except subprocess.TimeoutExpired:
            self.process.kill()
            self.process.wait(timeout=5)


class ProcessSupervisor:
    """Start, inspect, and stop only the processes owned by this run."""

    def __init__(self, artifact_dir: Path) -> None:
        self.artifact_dir = artifact_dir
        self.processes: list[ManagedProcess] = []

    def start(
        self,
        name: str,
        command: list[str],
        *,
        cwd: Path,
        env: dict[str, str],
    ) -> ManagedProcess:
        self.artifact_dir.mkdir(parents=True, exist_ok=True)
        log_path = self.artifact_dir / f"{name}.log"
        try:
            process = subprocess.Popen(
                command,
                cwd=cwd,
                env=env,
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                start_new_session=True,
            )
        except BaseException:
            raise
        managed = ManagedProcess(name, process, log_path)
        threading.Thread(target=self._capture_output, args=(managed,), daemon=True).start()
        self.processes.append(managed)
        return managed

    @staticmethod
    def _capture_output(managed: ManagedProcess) -> None:
        stdout = managed.process.stdout
        if stdout is None:
            return
        with managed.log_path.open("w", encoding="utf-8", errors="replace") as log_file:
            for raw_line in iter(stdout.readline, b""):
                line = raw_line.decode(errors="replace").rstrip("\r\n")
                log_file.write(f"{line}\n")
                log_file.flush()
                managed.output.put(line)

    def stop_all(self) -> None:
        for process in reversed(self.processes):
            process.stop()


def wait_for_http(
    url: str, *, timeout: float, process: ManagedProcess | None = None
) -> requests.Response:
    """Poll an HTTP endpoint and fail early if its owner exits."""

    deadline = time.monotonic() + timeout
    last_error: Exception | None = None
    while time.monotonic() < deadline:
        if process is not None and process.poll() is not None:
            raise HarnessError(
                f"{process.name} exited with status {process.poll()}; see {process.log_path}"
            )
        try:
            response = requests.get(url, timeout=1)
            if response.ok:
                return response
            last_error = HarnessError(f"{url} returned HTTP {response.status_code}")
        except requests.RequestException as exc:
            last_error = exc
        time.sleep(0.2)
    raise HarnessError(f"Timed out waiting for {url}: {last_error}")


def poll_until(
    callback,
    predicate,
    *,
    timeout: float,
    interval: float = 0.25,
    description: str,
):
    """Poll ``callback`` until ``predicate`` accepts its value."""

    deadline = time.monotonic() + timeout
    value = None
    while time.monotonic() < deadline:
        value = callback()
        if predicate(value):
            return value
        time.sleep(interval)
    raise HarnessError(f"Timed out waiting for {description}; last value: {value!r}")


_SHELL_ERROR = re.compile(r"failed|no lwm2m context|wrong parameter count|command not found")
_ANSI_ESCAPE = re.compile(r"\x1b\[[0-9;?]*[A-Za-z]")
_PTY_ANNOUNCEMENT = r"connected to pseudotty: (/dev/pts/\d+)"
DEFAULT_PROMPT = "uart:~$ "


class LogStream:
    """Log lines a process writes to stdout, consumed in order."""

    def __init__(self, process: ManagedProcess) -> None:
        self.process = process

    def wait_for(self, pattern: str, *, timeout: float = 30.0) -> re.Match[str]:
        """Read until a line matches ``pattern`` or the process exits."""

        compiled = re.compile(pattern)
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            try:
                line = self.process.output.get(timeout=min(0.2, deadline - time.monotonic()))
            except Empty:
                if self.process.poll() is not None:
                    raise HarnessError(
                        f"{self.process.name} exited while waiting for {pattern!r}; "
                        f"see {self.process.log_path}"
                    ) from None
                continue
            if match := compiled.search(line):
                return match
        raise HarnessError(f"Timed out waiting for {self.process.name} log {pattern!r}")


class ZephyrShell:
    """Shell transport over the native_sim UART pseudo terminal.

    Logs stay on the process stdout, so the terminal carries only command
    echoes, responses, and prompts.
    """

    def __init__(
        self,
        pty_path: str,
        process: ManagedProcess,
        *,
        log_path: Path,
        prompt: str = DEFAULT_PROMPT,
    ) -> None:
        self.process = process
        self.log_path = log_path
        self._prompt = prompt
        self._fd = os.open(pty_path, os.O_RDWR | os.O_NOCTTY)
        tty.setraw(self._fd)
        self._buffer = ""
        self._changed = threading.Condition()
        threading.Thread(target=self._read, daemon=True).start()

    def _read(self) -> None:
        with self.log_path.open("w", encoding="utf-8", errors="replace") as log_file:
            while True:
                try:
                    chunk = os.read(self._fd, 4096)
                except OSError:
                    return
                if not chunk:
                    return
                text = _ANSI_ESCAPE.sub("", chunk.decode(errors="replace")).replace("\r", "")
                log_file.write(text)
                log_file.flush()
                with self._changed:
                    self._buffer += text
                    self._changed.notify_all()

    def command(self, command: str, *, timeout: float = 10.0, check: bool = True) -> list[str]:
        """Run ``command`` and return its response lines without echo and prompt."""

        if self.process.poll() is not None:
            raise HarnessError(f"Zephyr exited before {command!r}; see {self.process.log_path}")
        with self._changed:
            self._buffer = ""
        os.write(self._fd, f"{command}\n".encode())

        deadline = time.monotonic() + timeout
        with self._changed:
            while (response := self._response(command)) is None:
                remaining = deadline - time.monotonic()
                if remaining <= 0:
                    raise HarnessError(
                        f"Timed out waiting for prompt after {command!r}: {self._buffer!r}"
                    )
                if self.process.poll() is not None:
                    raise HarnessError(
                        f"Zephyr exited while running {command!r}; see {self.process.log_path}"
                    )
                self._changed.wait(min(0.2, remaining))

        lines = [line.strip() for line in response.splitlines() if line.strip()]
        if check and any(_SHELL_ERROR.search(line) for line in lines):
            raise HarnessError(f"Zephyr command {command!r} failed: {lines!r}")
        return lines

    def _response(self, command: str) -> str | None:
        start = self._buffer.find(command) + len(command) if command else 0
        if command and start < len(command):
            return None
        end = self._buffer.find(self._prompt, start)
        return None if end < 0 else self._buffer[start:end]

    def close(self) -> None:
        os.close(self._fd)


@dataclass
class ZephyrDevice:
    """A running native_sim binary: shell on its pty, logs on stdout."""

    process: ManagedProcess
    shell: ZephyrShell
    logs: LogStream


def start_zephyr(
    supervisor: ProcessSupervisor,
    config: RunConfig,
    *,
    binary: Path,
    arguments: Iterable[str] = (),
    environment: dict[str, str] | None = None,
) -> ZephyrDevice:
    """Launch one native_sim binary and attach to its shell terminal."""

    if not binary.is_file():
        raise HarnessError(f"Zephyr binary does not exist: {binary}")
    env = os.environ.copy()
    if environment:
        env.update(environment)
    process = supervisor.start(
        "zephyr",
        [str(binary), *(arg for arg in arguments if arg)],
        cwd=binary.parent,
        env=env,
    )
    return attach_device(process, config.artifact_dir, timeout=config.timeout)


def attach_device(process: ManagedProcess, artifact_dir: Path, *, timeout: float) -> ZephyrDevice:
    """Open the shell pty announced on stdout and wait for the client to boot."""

    logs = LogStream(process)
    pty_path = logs.wait_for(_PTY_ANNOUNCEMENT, timeout=timeout).group(1)
    shell = ZephyrShell(pty_path, process, log_path=artifact_dir / f"{process.name}-shell.log")
    logs.wait_for(r"Client initialized", timeout=timeout)
    shell.command("", timeout=timeout)
    return ZephyrDevice(process, shell, logs)


class ShellContract:
    """Zephyr shell commands that drive the Flownexus client."""

    @staticmethod
    def start(endpoint: str, server: str) -> str:
        return f"flownexus start {endpoint} {server}"

    @staticmethod
    def write_float(path: str, value: float) -> str:
        return f"lwm2m write {path} -f {value}"

    @staticmethod
    def send(*paths: str) -> str:
        return f"lwm2m send {' '.join(paths)}"

    @staticmethod
    def update() -> str:
        return "lwm2m update"


@dataclass
class DjangoApi:
    """HTTP client for the internal Django ingest and inspection API."""

    base_url: str
    endpoint: str
    db_path: Path | None = None

    def endpoint_data(self) -> dict:
        response = requests.get(f"{self.base_url}/endpoints/{self.endpoint}/", timeout=2)
        if response.status_code == 404:
            return {}
        response.raise_for_status()
        return response.json()

    def resources(self) -> list[dict]:
        response = requests.get(f"{self.base_url}/endpoints/{self.endpoint}/resources/", timeout=2)
        if response.status_code == 404:
            return []
        response.raise_for_status()
        return response.json()

    def operations(self) -> list[dict]:
        response = requests.get(f"{self.base_url}/endpoints/{self.endpoint}/operations/", timeout=2)
        if response.status_code == 404:
            return []
        response.raise_for_status()
        return response.json()

    def events(self) -> list[dict]:
        """Read event rows from the isolated DB because no event API exists."""

        if self.db_path is None:
            raise HarnessError("DjangoApi.events requires the isolated database path")
        with sqlite3.connect(f"file:{self.db_path}?mode=ro", uri=True) as connection:
            rows = connection.execute(
                "SELECT id, event_type, time FROM sensordata_event "
                "WHERE endpoint_id = ? ORDER BY id",
                (self.endpoint,),
            ).fetchall()
        return [{"id": row[0], "event_type": row[1], "time": row[2]} for row in rows]

    def seed_resource(self, object_id: int, resource_id: int, data_type: str, value: str) -> None:
        response = requests.post(
            f"{self.base_url}/resource/single",
            json={
                "ep": self.endpoint,
                "obj_id": object_id,
                "val": {
                    "kind": "singleResource",
                    "id": resource_id,
                    "type": data_type,
                    "value": value,
                },
            },
            timeout=2,
        )
        response.raise_for_status()

    def create_operation(self, resource_id: int, operation_type: str = "send") -> dict:
        response = requests.post(
            f"{self.base_url}/endpoints/{self.endpoint}/operations/",
            json={"resource": resource_id, "operation_type": operation_type},
            timeout=2,
        )
        response.raise_for_status()
        return response.json()


def resource_value(resource: dict) -> object:
    """Return the value field from Django's resource inspection response."""

    return resource.get("value")


def named_resource(resources: Iterable[dict], resource_name: str) -> dict | None:
    return next(
        (
            resource
            for resource in resources
            if resource.get("resource_type", "").endswith(f" - {resource_name}")
        ),
        None,
    )


def named_operation(operations: Iterable[dict], operation_id: int) -> dict | None:
    return next((row for row in operations if row.get("id") == operation_id), None)


def matching_resource(resources: Iterable[dict], resource_name: str, value: object) -> bool:
    return any(
        resource.get("resource_type", "").endswith(f" - {resource_name}")
        and resource_value(resource) == value
        for resource in resources
    )


def write_run_metadata(config: RunConfig) -> None:
    config.artifact_dir.mkdir(parents=True, exist_ok=True)
    (config.artifact_dir / "run.json").write_text(
        json.dumps(
            {
                "endpoint": config.endpoint,
                "ports": {
                    "django": config.django_port,
                    "leshan_http": config.leshan_http_port,
                    "leshan_coap": config.leshan_coap_port,
                    "redis": config.redis_port,
                },
            },
            indent=2,
        )
        + "\n"
    )
