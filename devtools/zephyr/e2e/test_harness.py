# Copyright (c) 2026 Jonas Remmert
#
# SPDX-License-Identifier: Apache-2.0

"""Fast tests for process ownership, shell and log I/O, and stale data checks."""

from __future__ import annotations

import os
import sys
import time
from pathlib import Path

import pytest
import requests

from . import contract
from .harness import (
    HarnessError,
    ProcessSupervisor,
    attach_device,
    matching_resource,
    named_operation,
    named_resource,
    poll_until,
)


def test_matching_resource_requires_exact_value() -> None:
    rows = [{"resource_type": "3303/5700 - temperature", "value": 21.5}]

    assert matching_resource(rows, "temperature", 21.5)
    assert not matching_resource(rows, "temperature", 21.4)
    assert not matching_resource(rows, "humidity", 21.5)
    assert named_resource(rows, "temperature") == rows[0]
    assert named_resource(rows, "humidity") is None
    assert named_operation([{"id": 7, "status": "QUEUED"}], 7)["status"] == "QUEUED"
    assert named_operation([{"id": 7, "status": "QUEUED"}], 8) is None


def test_poll_until_times_out_with_last_value() -> None:
    with pytest.raises(HarnessError, match="expected value"):
        poll_until(
            lambda: {"value": "wrong"},
            lambda value: value["value"] == "expected",
            timeout=0.02,
            interval=0.005,
            description="expected value",
        )


def test_supervisor_terminates_only_owned_process_and_keeps_log(tmp_path: Path) -> None:
    supervisor = ProcessSupervisor(tmp_path)
    process = supervisor.start(
        "owned",
        [sys.executable, "-c", "import time; print('owned', flush=True); time.sleep(30)"],
        cwd=tmp_path,
        env=os.environ.copy(),
    )
    time.sleep(0.1)
    supervisor.stop_all()

    assert process.poll() is not None
    assert process.log_path.read_text().strip() == "owned"


_FAKE_DEVICE = r"""
import os, sys, tty
master, slave = os.openpty()
tty.setraw(master)
print("uart_0 connected to pseudotty: " + os.ttyname(slave), flush=True)
print("Client initialized", flush=True)
pending = b""
while True:
    pending += os.read(master, 1024)
    while b"\n" in pending:
        line, pending = pending.split(b"\n", 1)
        cmd = line.decode().strip()
        if cmd == "exit":
            sys.exit(0)
        if cmd == "log":
            print("event happened", flush=True)
        reply = "\r\nstart failed: -11" if cmd == "bad" else (f"\r\nok {cmd}" if cmd else "")
        os.write(master, f"{cmd}{reply}\r\n\x1b[1;32muart:~$ \x1b[m".encode())
"""


def _fake_device(tmp_path: Path):
    supervisor = ProcessSupervisor(tmp_path)
    process = supervisor.start(
        "fake-device",
        [sys.executable, "-u", "-c", _FAKE_DEVICE],
        cwd=tmp_path,
        env=os.environ.copy(),
    )
    return supervisor, attach_device(process, tmp_path, timeout=5)


def test_shell_returns_response_without_echo_and_prompt(tmp_path: Path) -> None:
    supervisor, device = _fake_device(tmp_path)

    assert device.shell.command("status", timeout=1) == ["ok status"]
    assert "ok status" in (tmp_path / "fake-device-shell.log").read_text()
    supervisor.stop_all()


def test_shell_fails_on_command_error(tmp_path: Path) -> None:
    supervisor, device = _fake_device(tmp_path)

    with pytest.raises(HarnessError, match="failed"):
        device.shell.command("bad", timeout=1)
    assert device.shell.command("bad", timeout=1, check=False) == ["start failed: -11"]
    supervisor.stop_all()


def test_logs_are_separate_from_shell(tmp_path: Path) -> None:
    supervisor, device = _fake_device(tmp_path)

    assert device.shell.command("log", timeout=1) == ["ok log"]
    assert device.logs.wait_for("event happened", timeout=1)
    supervisor.stop_all()


def test_shell_fails_when_process_dies(tmp_path: Path) -> None:
    supervisor, device = _fake_device(tmp_path)

    with pytest.raises(HarnessError, match="exited|Timed out"):
        device.shell.command("exit", timeout=1)
    with pytest.raises(HarnessError, match="exited"):
        device.logs.wait_for("never", timeout=1)
    supervisor.stop_all()


def test_contract_normalizes_volatile_values() -> None:
    body = {
        "ep": "urn:imei:e2e-1",
        "val": [
            {"2026-10-18T17:40:24Z": {"nodes": {"/3/0/13": {"type": "TIME", "value": 17}}}},
            {"null": {"nodes": {"/3303/0/5700": {"type": "FLOAT", "value": "21.5"}}}},
        ],
    }

    assert contract.normalize(body, "urn:imei:e2e-1") == {
        "ep": "<endpoint>",
        "val": [
            {"<timestamp>": {"nodes": {"/3/0/13": {"type": "TIME", "value": "<time>"}}}},
            {"null": {"nodes": {"/3303/0/5700": {"type": "FLOAT", "value": "21.5"}}}},
        ],
    }


def test_recording_sink_records_requests_per_endpoint() -> None:
    sink = contract.RecordingSink(host="127.0.0.1", status=503)
    try:
        url = f"http://127.0.0.1:{sink.port}/flownexus/ingest/registration"
        assert requests.post(url, json={"ep": "a", "event": "registered"}).status_code == 503
        requests.post(url, json={"ep": "b"})

        recorded = sink.wait_settled("a", known=0, timeout=1, quiet=0.05)
        assert [r.normalized("a") for r in recorded] == [
            {
                "method": "POST",
                "path": "/flownexus/ingest/registration",
                "body": {"ep": "<endpoint>", "event": "registered"},
            }
        ]
        with pytest.raises(TimeoutError):
            sink.wait_settled("a", known=1, timeout=0.05)
    finally:
        sink.close()


def test_every_golden_file_has_a_scenario() -> None:
    """A golden file without a producer scenario would never be checked again."""

    from .test_contract import GOLDEN_DIR, SCENARIOS

    recorded = {(path.parent.name, path.stem) for path in GOLDEN_DIR.glob("*/*.json")}
    assert recorded == {(scenario.kind, name) for name, scenario in SCENARIOS.items()}
