#
# Copyright (c) 2026 Jonas Remmert
#
# SPDX-License-Identifier: Apache-2.0
#

"""Consumer check of the gateway to Django contract.

The golden files in ``contract/gateway`` are recorded from the real gateway
(``devtools/zephyr/e2e/test_contract.py``). These tests post the recorded
ingest requests to the ingest API, answer Django's command requests with
the recorded gateway responses, and check the resulting database state.
"""

import json
from datetime import UTC, datetime
from pathlib import Path
from unittest.mock import patch

import pytest
from django.core.management import call_command

from sensordata.models import Endpoint, EndpointOperation, Event, Resource, ResourceType
from sensordata.tasks import send_operation

GOLDEN_DIR = Path(__file__).resolve().parents[4] / "contract/gateway"
ENDPOINT = "urn:imei:contract"
TIMESTAMPS = ["2026-01-01T00:00:00Z", "2026-01-01T00:00:01Z", "2026-01-01T00:00:02Z"]
TIME_MS = 1767225600000


def _substitute(value):
    """Replace golden-file placeholders with concrete values."""

    if isinstance(value, dict):
        return {
            (TIMESTAMPS[0] if key == "<timestamp>" else key): _substitute(item)
            for key, item in value.items()
        }
    if isinstance(value, list):
        # Each item of a timestamped Send gets its own, increasing timestamp
        result = [_substitute(item) for item in value]
        for index, item in enumerate(value):
            if isinstance(item, dict) and list(item) == ["<timestamp>"]:
                result[index] = {TIMESTAMPS[index]: result[index][TIMESTAMPS[0]]}
        return result
    return {"<endpoint>": ENDPOINT, "<time>": str(TIME_MS), "<timestamp>": TIMESTAMPS[0]}.get(
        value, value
    )


def golden(kind, name):
    return json.loads((GOLDEN_DIR / kind / f"{name}.json").read_text())


class GatewayResponse:
    """A recorded gateway response in place of ``requests.Response``."""

    def __init__(self, recorded):
        self.status_code = recorded["status"]
        self._body = _substitute(recorded["body"])
        self.text = json.dumps(self._body)

    def json(self):
        return self._body


def command_response(name, index=0):
    return GatewayResponse(golden("command", name)["steps"][0]["responses"][index])


def replay(client, name, *, step=None):
    steps = golden("ingest", name)["steps"]
    for current in steps if step is None else [steps[step]]:
        for request in current["requests"]:
            response = client.generic(
                request["method"],
                request["path"],
                json.dumps(_substitute(request["body"])),
                content_type="application/json",
            )
            assert response.status_code == 201, (request["path"], response.content)


def values(object_id, resource_id):
    return [
        r.get_value()
        for r in Resource.objects.filter(
            endpoint__endpoint=ENDPOINT,
            resource_type__object_id=object_id,
            resource_type__resource_id=resource_id,
        ).order_by("timestamp_created", "id")
    ]


@pytest.fixture(autouse=True)
def resource_types(db):
    call_command("load_initial_resource_types")


@pytest.fixture(autouse=True)
def gateway_read():
    """Answer Django's read of /3 after a registration with the recorded response."""

    with patch("sensordata.tasks.requests.get") as get:
        get.return_value = command_response("read_device_object")
        yield get


def _ingest_names():
    return sorted(path.stem for path in (GOLDEN_DIR / "ingest").glob("*.json"))


@pytest.mark.django_db
@pytest.mark.parametrize("name", _ingest_names())
def test_every_golden_request_is_accepted(client, name):
    replay(client, name)


@pytest.mark.django_db
class TestRegistrationLifecycle:
    def test_registration_marks_endpoint_registered(self, client):
        replay(client, "registration_lifecycle", step=0)

        assert Endpoint.objects.get(endpoint=ENDPOINT).registered is True
        assert values(10240, 0) == [TIME_MS]

    def test_registration_reads_device_object(self, client, gateway_read):
        replay(client, "registration_lifecycle", step=0)

        assert gateway_read.call_args.args[0].endswith(f"/api/clients/{ENDPOINT}/3")
        assert values(3, 0) == ["Zephyr"]
        assert values(3, 3) == ["1.0"]
        assert Event.objects.filter(endpoint_id=ENDPOINT, event_type="3").count() == 1

    def test_update_and_deregistration(self, client, gateway_read):
        replay(client, "registration_lifecycle", step=0)
        replay(client, "registration_lifecycle", step=1)
        assert values(10240, 2) == [TIME_MS]
        assert Endpoint.objects.get(endpoint=ENDPOINT).registered is True

        replay(client, "registration_lifecycle", step=2)
        assert values(10240, 1) == [TIME_MS]
        assert Endpoint.objects.get(endpoint=ENDPOINT).registered is False
        assert gateway_read.call_count == 1

    def test_late_event_does_not_change_the_state(self, client):
        replay(client, "registration_lifecycle", step=0)
        late = {"ep": ENDPOINT, "event": "unregistered", "time": "2025-12-31T23:59:59Z"}
        url = "/flownexus/ingest/registration"
        response = client.post(url, late, content_type="application/json")

        assert response.status_code == 201
        assert Endpoint.objects.get(endpoint=ENDPOINT).registered is True
        assert len(values(10240, 1)) == 1


@pytest.mark.django_db
class TestSend:
    def test_single_resource(self, client):
        replay(client, "send_single_resource")

        assert values(3303, 5700) == [21.5]
        assert not Event.objects.filter(endpoint_id=ENDPOINT).exists()

    def test_multiple_resources_form_one_event(self, client):
        replay(client, "send_multiple_resources")

        assert values(3303, 5700) == [17.25]
        assert values(3304, 5700) == [45.5]
        event = Event.objects.get(endpoint_id=ENDPOINT)
        assert event.resources.count() == 2

    def test_object_instance_stores_known_resources(self, client):
        replay(client, "send_object_instance")

        assert values(3303, 5700) == [20.0]

    def test_cached_timeseries_keeps_device_timestamps(self, client):
        replay(client, "send_cached_timeseries")

        rows = Resource.objects.filter(endpoint__endpoint=ENDPOINT).order_by("timestamp_created")
        assert [r.get_value() for r in rows] == [10.5, 11.5, 12.5]
        assert [r.timestamp_created for r in rows] == [
            datetime.fromisoformat(ts).replace(tzinfo=UTC) for ts in TIMESTAMPS
        ]


# Expected operation status for each response of each command golden file.
# read_device_object answers the read of /3 (TestRegistrationLifecycle).
COMMAND_RESULTS = {
    "write_resource": ["CONFIRMED"],
    "execute_resource": ["CONFIRMED"],
    "write_rejected": ["FAILED"],
    "invalid_request": ["FAILED", "FAILED"],
    "device_timeout": ["QUEUED"],
    "unknown_endpoint": ["QUEUED"],
}


def test_every_command_golden_file_is_covered():
    recorded = {path.stem for path in (GOLDEN_DIR / "command").glob("*.json")}
    assert recorded == set(COMMAND_RESULTS) | {"read_device_object"}
    for name, statuses in COMMAND_RESULTS.items():
        assert len(golden("command", name)["steps"][0]["responses"]) == len(statuses), name


@pytest.mark.django_db
class TestCommandResults:
    def operation(self, object_id, resource_id, value=None):
        endpoint, _ = Endpoint.objects.get_or_create(endpoint=ENDPOINT)
        resource_type = ResourceType.objects.get(object_id=object_id, resource_id=resource_id)
        field = resource_type.get_value_field()
        resource = Resource.objects.create(
            endpoint=endpoint,
            resource_type=resource_type,
            **({field: value} if field else {}),
        )
        return EndpointOperation.objects.create(resource=resource, operation_type="send")

    def send(self, operation, name, index=0):
        with patch("sensordata.tasks.requests") as requests:
            requests.put.return_value = command_response(name, index)
            requests.post.return_value = command_response(name, index)
            send_operation(operation.id)
        operation.refresh_from_db()
        return requests

    @pytest.mark.parametrize(
        "name,index,status",
        [
            (name, index, status)
            for name, statuses in COMMAND_RESULTS.items()
            for index, status in enumerate(statuses)
        ],
    )
    def test_gateway_response_sets_operation_status(self, name, index, status):
        operation = self.operation(3, 14, "+02:00")
        self.send(operation, name, index)

        assert operation.status == status
        assert operation.transmit_counter == (0 if status == "CONFIRMED" else 1)

    def test_execute_is_sent_as_post(self):
        operation = self.operation(3, 4)
        requests = self.send(operation, "execute_resource")

        requests.post.assert_called_once()
        requests.put.assert_not_called()

    def test_instance_id_is_part_of_the_path(self):
        operation = self.operation(3, 14, "+02:00")
        operation.instance_id = 2
        operation.save()
        requests = self.send(operation, "write_resource")

        assert requests.put.call_args.args[0].endswith(f"/clients/{ENDPOINT}/3/2/14")
