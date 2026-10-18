# Copyright (c) 2026 Jonas Remmert
#
# SPDX-License-Identifier: Apache-2.0

"""Initial local E2E workflows for the Zephyr application.

Run with ``FLOWNEXUS_RUN_E2E=1`` after building the Leshan image and a
native_sim binary. The device is driven through the Zephyr ``lwm2m`` shell
and the ``flownexus`` application shell.
"""

from __future__ import annotations

import os
import re
from pathlib import Path

import pytest

from .harness import (
    DjangoApi,
    ProcessSupervisor,
    RunConfig,
    ShellContract,
    matching_resource,
    named_operation,
    poll_until,
    start_zephyr,
    write_run_metadata,
)
from .stack import LocalStack

pytestmark = pytest.mark.e2e


def _binary(root: Path) -> Path:
    candidate = os.getenv("FLOWNEXUS_ZEPHYR_BINARY")
    if candidate:
        return Path(candidate).expanduser().resolve()
    return root / "devtools/zephyr/client/build/zephyr/zephyr.exe"


@pytest.fixture(scope="session")
def e2e_context(tmp_path_factory: pytest.TempPathFactory, request: pytest.FixtureRequest):
    if os.getenv("FLOWNEXUS_RUN_E2E") != "1":
        pytest.skip("set FLOWNEXUS_RUN_E2E=1 to run local service E2E scenarios")
    root = Path(__file__).resolve().parents[3]
    artifact_root = Path(os.getenv("FLOWNEXUS_E2E_ARTIFACT_ROOT", tmp_path_factory.mktemp("e2e")))
    config = RunConfig.create(root, artifact_root)
    write_run_metadata(config)
    supervisor = ProcessSupervisor(config.artifact_dir)
    stack = LocalStack(config)
    try:
        stack.start()
        binary = _binary(root)
        device = start_zephyr(
            supervisor,
            config,
            binary=binary,
            arguments=os.getenv("FLOWNEXUS_ZEPHYR_ARGS", "").split(),
        )
        server = f"coap://127.0.0.1:{config.leshan_coap_port}"
        device.shell.command(ShellContract.start(config.endpoint, server))
        api = DjangoApi(stack.ingest_url, config.endpoint, config.artifact_dir / "db.sqlite3")
        yield config, stack, supervisor, device, api
    finally:
        supervisor.stop_all()
        stack.stop()
        if not config.retain_artifacts and config.artifact_dir.exists():
            for path in config.artifact_dir.iterdir():
                path.unlink()
            config.artifact_dir.rmdir()


def test_registration_is_for_the_current_endpoint(e2e_context) -> None:
    config, stack, _, _, api = e2e_context
    endpoint = poll_until(
        api.endpoint_data,
        lambda value: value.get("endpoint") == config.endpoint and value.get("registered") is True,
        timeout=config.timeout,
        description=f"registration of {config.endpoint}",
    )
    assert endpoint == {"endpoint": config.endpoint, "registered": True}


def test_exact_telemetry_and_event_delivery(e2e_context) -> None:
    config, _, _, device, api = e2e_context
    value = 17.25
    device.shell.command(ShellContract.write_float("/3303/0/5700", value))
    initial_events = api.events()
    device.shell.command(ShellContract.send("/3303/0/5700", "/3304/0/5700"))

    resources = poll_until(
        api.resources,
        lambda rows: matching_resource(rows, "temperature", value),
        timeout=config.timeout,
        description="exact temperature telemetry",
    )
    assert matching_resource(resources, "temperature", value)
    events = poll_until(
        api.events,
        lambda rows: len(rows) > len(initial_events),
        timeout=config.timeout,
        description="telemetry event",
    )
    assert any(event["event_type"] in {"3303", "3304"} for event in events[len(initial_events) :])


def test_server_operation_is_received_by_device_and_confirmed(e2e_context) -> None:
    """Queue a write of Device/UTC offset and deliver it on registration update."""

    config, _, _, device, api = e2e_context
    value = "+02:00"
    api.seed_resource(3, 14, "STRING", value)
    resources = poll_until(
        api.resources,
        lambda rows: matching_resource(rows, "utc_offset", value),
        timeout=config.timeout,
        description="seeded utc_offset resource",
    )
    resource = next(
        row
        for row in reversed(resources)
        if row["resource_type"].endswith(" - utc_offset") and row["value"] == value
    )
    operation = api.create_operation(resource["resource_id"], "send")

    device.shell.command(ShellContract.update())
    device.logs.wait_for(re.escape(f"write 3/0/14={value}"), timeout=config.timeout)

    def operation_confirmed(rows: list[dict]) -> bool:
        row = named_operation(rows, operation["id"])
        return row is not None and row.get("status") == "CONFIRMED"

    confirmed = poll_until(
        api.operations,
        operation_confirmed,
        timeout=config.timeout,
        description=f"operation {operation['id']} confirmed",
    )
    assert named_operation(confirmed, operation["id"])["status"] == "CONFIRMED"


def test_fota_through_firmware_object(e2e_context) -> None:
    """Run FOTA through Object 5 and confirm the new version after a re-registration."""

    config, _, _, device, api = e2e_context
    version = f"2.0.0-{config.endpoint.rsplit('-', 1)[-1]}"
    poll_until(
        api.endpoint_data,
        lambda value: value.get("registered") is True,
        timeout=config.timeout,
        description=f"registration of {config.endpoint}",
    )
    update = api.create_firmware_update(version, b"flownexus e2e firmware")

    def update_row(rows: list[dict]) -> dict | None:
        return next((row for row in rows if row["id"] == update["id"]), None)

    def wait_update(description: str, **expected: int) -> dict:
        rows = poll_until(
            api.firmware_updates,
            lambda rows: (
                (row := update_row(rows)) is not None
                and all(row[key] == value for key, value in expected.items())
            ),
            timeout=config.timeout,
            interval=config.poll_interval,
            description=description,
        )
        return update_row(rows)

    # Django sends queued operations, here the Package URI, on registration update.
    device.shell.command(ShellContract.update())
    uri = update["firmware"]["binary"]
    device.logs.wait_for(re.escape(f"write 5/0/1={uri}"), timeout=config.timeout)

    device.shell.command(ShellContract.fota_state(1))
    wait_update("state DOWNLOADING", state=1)
    device.shell.command(ShellContract.fota_state(2))
    device.logs.wait_for(re.escape("execute 5/0/2 (update)"), timeout=config.timeout)
    wait_update("state UPDATING", state=3)

    # Simulated reboot into the new image: the registration makes Leshan read /3.
    device.shell.command(ShellContract.write_string("/3/0/3", version))
    device.shell.command(ShellContract.stop())
    device.logs.wait_for(r"Disconnected", timeout=config.timeout)
    _restart_client(config, device)

    finished = wait_update("FOTA success", result=1)
    assert finished["state"] == 0
    assert finished["firmware"]["version"] == version
    operations = api.operations()
    assert [row["status"] for row in operations[-2:]] == ["CONFIRMED", "CONFIRMED"]


def _restart_client(config, device) -> None:
    """Start the client again; ``start`` fails until the engine is idle after a stop."""

    server = f"coap://127.0.0.1:{config.leshan_coap_port}"
    poll_until(
        lambda: device.shell.command(ShellContract.start(config.endpoint, server), check=False),
        lambda lines: not any("failed" in line for line in lines),
        timeout=config.timeout,
        interval=config.poll_interval,
        description="client restart",
    )


def test_deregistration_marks_endpoint_unregistered(e2e_context) -> None:
    config, _, _, device, api = e2e_context

    def registered(expected: bool) -> dict:
        return poll_until(
            api.endpoint_data,
            lambda value: value.get("registered") is expected,
            timeout=config.timeout,
            description=f"registered={expected} for {config.endpoint}",
        )

    registered(True)
    device.shell.command(ShellContract.stop())
    device.logs.wait_for(r"Disconnected", timeout=config.timeout)
    registered(False)

    _restart_client(config, device)
    registered(True)


@pytest.mark.xfail(
    reason="defect P-008: the gateway returns HTTP 200 for a device error, so Django "
    "records the rejected write as CONFIRMED",
    strict=True,
)
def test_write_rejected_by_device_fails_operation(e2e_context) -> None:
    """Write the read-only Device/Manufacturer; the device answers 4.05."""

    config, _, _, device, api = e2e_context
    value = "Rejected"
    api.seed_resource(3, 0, "STRING", value)
    resources = poll_until(
        api.resources,
        lambda rows: matching_resource(rows, "manufacturer", value),
        timeout=config.timeout,
        description="seeded manufacturer resource",
    )
    resource = next(
        row
        for row in reversed(resources)
        if row["resource_type"].endswith(" - manufacturer") and row["value"] == value
    )
    operation = api.create_operation(resource["resource_id"], "send")
    device.shell.command(ShellContract.update())

    def operation_done(rows: list[dict]) -> bool:
        row = named_operation(rows, operation["id"])
        return row is not None and row.get("status") in {"CONFIRMED", "FAILED"}

    rows = poll_until(
        api.operations,
        operation_done,
        timeout=config.timeout,
        description=f"operation {operation['id']} finished",
    )
    assert named_operation(rows, operation["id"])["status"] == "FAILED"
