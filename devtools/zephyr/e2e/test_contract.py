# Copyright (c) 2026 Jonas Remmert
#
# SPDX-License-Identifier: Apache-2.0

"""Producer check of the gateway to Django contract.

Each scenario drives a fresh native_sim device against the Leshan image,
which posts to a recording sink instead of Django. The recorded requests
and command responses must match ``contract/gateway/<kind>/<scenario>.json``.
Set ``FLOWNEXUS_UPDATE_GOLDEN=1`` to re-record the files instead.

A step command is a device shell command, ``sleep <seconds>`` on the host,
or ``http <METHOD> <path> [json]`` against the gateway command API, as
Django sends it.
"""

from __future__ import annotations

import difflib
import json
import os
import time
from dataclasses import dataclass
from pathlib import Path

import pytest
import requests

from . import contract
from .harness import ProcessSupervisor, RunConfig, start_zephyr, write_run_metadata
from .stack import LocalStack

pytestmark = pytest.mark.e2e

ROOT = Path(__file__).resolve().parents[3]
GOLDEN_DIR = ROOT / "contract/gateway"
START = "flownexus start <endpoint> <server>"
DEVICE = "/api/clients/<endpoint>"
# Query parameters as sensordata.tasks sends them
PARAMS = "?timeout=5&format=CBOR"


@dataclass(frozen=True)
class Scenario:
    description: str
    steps: tuple[tuple[str, ...], ...]
    setup: tuple[str, ...] = (START,)
    kind: str = "ingest"


SCENARIOS = {
    "registration_lifecycle": Scenario(
        "Register, update the registration, and deregister.",
        steps=((START,), ("lwm2m update",), ("lwm2m stop",)),
        setup=(),
    ),
    "send_single_resource": Scenario(
        "LwM2M Send of one resource.",
        steps=(("lwm2m write /3303/0/5700 -f 21.5", "lwm2m send /3303/0/5700"),),
    ),
    "send_multiple_resources": Scenario(
        "LwM2M Send of resources from two objects.",
        steps=(
            (
                "lwm2m write /3303/0/5700 -f 17.25",
                "lwm2m write /3304/0/5700 -f 45.5",
                "lwm2m send /3303/0/5700 /3304/0/5700",
            ),
        ),
    ),
    "send_object_instance": Scenario(
        "LwM2M Send of a whole object instance.",
        steps=(("lwm2m send /3303/0",),),
    ),
    "send_cached_timeseries": Scenario(
        "LwM2M Send of cached values, each with its own timestamp. Zephyr stores "
        "timestamps in seconds, and Leshan rejects two values of one path with the "
        "same timestamp, so the writes are more than a second apart.",
        steps=(
            (
                "lwm2m cache /3303/0/5700 4",
                "lwm2m write /3303/0/5700 -f 10.5",
                "sleep 1.1",
                "lwm2m write /3303/0/5700 -f 11.5",
                "sleep 1.1",
                "lwm2m write /3303/0/5700 -f 12.5",
                "lwm2m send /3303/0/5700",
            ),
        ),
    ),
    "read_device_object": Scenario(
        "Read of the Device object, as Django requests it after a registration.",
        steps=((f"http GET {DEVICE}/3?timeout=5",),),
        kind="command",
    ),
    "write_resource": Scenario(
        "Write of a single resource that the device accepts.",
        steps=(
            (
                f"http PUT {DEVICE}/3/0/14{PARAMS} "
                '{"id": 14, "kind": "singleResource", "value": "+02:00", "type": "STRING"}',
            ),
        ),
        kind="command",
    ),
    "write_rejected": Scenario(
        "Write of a read-only resource; the device answers 4.05.",
        steps=(
            (
                f"http PUT {DEVICE}/3/0/0{PARAMS} "
                '{"id": 0, "kind": "singleResource", "value": "Rejected", "type": "STRING"}',
            ),
        ),
        kind="command",
    ),
    "execute_resource": Scenario(
        "Execute of a resource without arguments.",
        steps=((f"http POST {DEVICE}/3/0/4{PARAMS}",),),
        kind="command",
    ),
    "device_timeout": Scenario(
        "Write while the device is offline; the gateway times out.",
        steps=(
            (
                "lwm2m pause",
                f"http PUT {DEVICE}/3/0/14?timeout=2&format=CBOR "
                '{"id": 14, "kind": "singleResource", "value": "+03:00", "type": "STRING"}',
            ),
        ),
        kind="command",
    ),
    "unknown_endpoint": Scenario(
        "Command for an endpoint that is not registered.",
        steps=(("http GET /api/clients/urn:imei:unknown/3?timeout=5",),),
        setup=(),
        kind="command",
    ),
}


def _binary() -> Path:
    candidate = os.getenv("FLOWNEXUS_ZEPHYR_BINARY")
    if candidate:
        return Path(candidate).expanduser().resolve()
    return ROOT / "devtools/zephyr/client/build/zephyr/zephyr.exe"


@pytest.fixture(scope="module")
def gateway(tmp_path_factory: pytest.TempPathFactory):
    if os.getenv("FLOWNEXUS_RUN_E2E") != "1":
        pytest.skip("set FLOWNEXUS_RUN_E2E=1 to run the gateway contract scenarios")
    artifact_root = Path(
        os.getenv("FLOWNEXUS_E2E_ARTIFACT_ROOT", tmp_path_factory.mktemp("contract"))
    )
    config = RunConfig.create(ROOT, artifact_root)
    write_run_metadata(config)
    sink = contract.RecordingSink()
    stack = LocalStack(config)
    try:
        stack.start_gateway(sink.port)
        yield config, sink
    finally:
        stack.stop()
        sink.close()


def _record(config: RunConfig, sink: contract.RecordingSink, name: str, scenario: Scenario):
    # The shell wraps its echo at 80 columns, so the start command must stay short
    endpoint = f"{config.endpoint}-{sorted(SCENARIOS).index(name)}"
    server = f"coap://127.0.0.1:{config.leshan_coap_port}"
    gateway = f"http://127.0.0.1:{config.leshan_http_port}"
    supervisor = ProcessSupervisor(config.artifact_dir)
    device = start_zephyr(supervisor, config, binary=_binary(), name=f"zephyr-{name}")

    def run(commands: tuple[str, ...]) -> list[dict]:
        responses = []
        for command in commands:
            command = command.replace("<endpoint>", endpoint).replace("<server>", server)
            if command.startswith("sleep "):
                time.sleep(float(command.split()[1]))
            elif command.startswith("http "):
                _, method, path, *body = command.split(" ", 3)
                response = requests.request(
                    method, gateway + path, data=body[0] if body else None, timeout=30
                )
                responses.append(
                    {
                        "status": response.status_code,
                        "body": contract.normalize(response.json(), endpoint),
                    }
                )
            else:
                device.shell.command(command)
        return responses

    try:
        run(scenario.setup)
        if scenario.setup:
            sink.wait_settled(endpoint, known=0, timeout=config.timeout)
        steps = []
        for commands in scenario.steps:
            known = len(sink.for_endpoint(endpoint))
            responses = run(commands)
            recorded = sink.wait_settled(
                endpoint, known=known, timeout=config.timeout, require=not responses
            )
            step = {
                "device": list(commands),
                "requests": [r.normalized(endpoint) for r in recorded[known:]],
            }
            if responses:
                step["responses"] = responses
            steps.append(step)
    finally:
        supervisor.stop_all()
    return {
        "scenario": name,
        "description": scenario.description,
        "setup": list(scenario.setup),
        "steps": steps,
    }


@pytest.mark.parametrize("name", sorted(SCENARIOS))
def test_gateway_requests_match_golden_file(gateway, name: str) -> None:
    config, sink = gateway
    recorded = _record(config, sink, name, SCENARIOS[name])
    path = GOLDEN_DIR / SCENARIOS[name].kind / f"{name}.json"

    if os.getenv("FLOWNEXUS_UPDATE_GOLDEN") == "1":
        contract.dump(path, recorded)
        return

    assert path.is_file(), f"{path} is missing; record it with FLOWNEXUS_UPDATE_GOLDEN=1"
    expected = contract.load(path)
    if recorded != expected:
        diff = difflib.unified_diff(
            json.dumps(expected, indent=2).splitlines(),
            json.dumps(recorded, indent=2).splitlines(),
            fromfile=str(path.relative_to(ROOT)),
            tofile="recorded",
            lineterm="",
        )
        pytest.fail("Gateway requests differ from the golden file:\n" + "\n".join(diff))


def test_gateway_retries_while_django_is_down(gateway) -> None:
    """A 5xx answer from Django makes the gateway send the request again."""

    config, sink = gateway
    endpoint = f"{config.endpoint}-r"
    supervisor = ProcessSupervisor(config.artifact_dir)
    device = start_zephyr(supervisor, config, binary=_binary(), name="zephyr-retry")
    sink.failures = 1
    try:
        device.shell.command(
            f"flownexus start {endpoint} coap://127.0.0.1:{config.leshan_coap_port}"
        )
        recorded = sink.wait_settled(endpoint, known=1, timeout=config.timeout, quiet=3)
    finally:
        sink.failures = 0
        supervisor.stop_all()

    assert [r.status for r in recorded] == [503, 201]
    assert recorded[0].body == recorded[1].body
