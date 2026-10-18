# Copyright (c) 2026 Jonas Remmert
#
# SPDX-License-Identifier: Apache-2.0

"""Producer check of the gateway to Django contract.

Each scenario drives a fresh native_sim device against the Leshan image,
which posts to a recording sink instead of Django. The recorded requests
must match ``contract/gateway/ingest/<scenario>.json``. Set
``FLOWNEXUS_UPDATE_GOLDEN=1`` to re-record the files instead. A ``sleep``
step waits on the host; all other steps are device shell commands.
"""

from __future__ import annotations

import difflib
import json
import os
import time
from dataclasses import dataclass
from pathlib import Path

import pytest

from . import contract
from .harness import ProcessSupervisor, RunConfig, start_zephyr, write_run_metadata
from .stack import LocalStack

pytestmark = pytest.mark.e2e

ROOT = Path(__file__).resolve().parents[3]
GOLDEN_DIR = ROOT / "contract/gateway/ingest"
START = "flownexus start <endpoint> <server>"


@dataclass(frozen=True)
class Scenario:
    description: str
    steps: tuple[tuple[str, ...], ...]
    setup: tuple[str, ...] = (START,)


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
    supervisor = ProcessSupervisor(config.artifact_dir)
    device = start_zephyr(supervisor, config, binary=_binary(), name=f"zephyr-{name}")

    def run(commands: tuple[str, ...]) -> None:
        for command in commands:
            if command.startswith("sleep "):
                time.sleep(float(command.split()[1]))
                continue
            device.shell.command(
                command.replace("<endpoint>", endpoint).replace("<server>", server)
            )

    try:
        run(scenario.setup)
        if scenario.setup:
            sink.wait_settled(endpoint, known=0, timeout=config.timeout)
        steps = []
        for commands in scenario.steps:
            known = len(sink.for_endpoint(endpoint))
            run(commands)
            recorded = sink.wait_settled(endpoint, known=known, timeout=config.timeout)
            steps.append(
                {
                    "device": list(commands),
                    "requests": [r.normalized(endpoint) for r in recorded[known:]],
                }
            )
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
    path = GOLDEN_DIR / f"{name}.json"

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
