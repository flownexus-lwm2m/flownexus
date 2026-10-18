#
# Copyright (c) 2026 Jonas Remmert
#
# SPDX-License-Identifier: Apache-2.0
#

"""Consumer check of the gateway to Django contract.

The golden files in ``contract/gateway/ingest`` are recorded from the real
gateway (``devtools/zephyr/e2e/test_contract.py``). These tests post the
same requests to the ingest API and check the resulting database state.
"""

import json
from datetime import UTC, datetime
from pathlib import Path

import pytest
from django.core.management import call_command

from sensordata.models import Endpoint, Event, Resource

GOLDEN_DIR = Path(__file__).resolve().parents[4] / "contract/gateway/ingest"
ENDPOINT = "urn:imei:contract"
TIME_MS = 1767225600000
TIMESTAMPS = ["2026-01-01T00:00:00Z", "2026-01-01T00:00:01Z", "2026-01-01T00:00:02Z"]


def _substitute(value):
    """Replace golden-file placeholders with concrete values."""

    if isinstance(value, dict):
        items = {}
        for key, item in value.items():
            if key == "<timestamp>":
                key = TIMESTAMPS[0]
            items[key] = _substitute(item)
        return items
    if isinstance(value, list):
        # Each item of a timestamped Send gets its own, increasing timestamp
        result = [_substitute(item) for item in value]
        for index, item in enumerate(value):
            if isinstance(item, dict) and list(item) == ["<timestamp>"]:
                result[index] = {TIMESTAMPS[index]: result[index][TIMESTAMPS[0]]}
        return result
    return {"<endpoint>": ENDPOINT, "<time>": str(TIME_MS)}.get(value, value)


def golden(name):
    return json.loads((GOLDEN_DIR / f"{name}.json").read_text())


def requests_of(document):
    for step in document["steps"]:
        for request in step["requests"]:
            yield request["method"], request["path"], _substitute(request["body"])


def replay(client, name, *, step=None):
    document = golden(name)
    if step is not None:
        document = {"steps": [document["steps"][step]]}
    for method, path, body in requests_of(document):
        response = client.generic(method, path, json.dumps(body), content_type="application/json")
        assert response.status_code == 201, (path, response.status_code, response.content)


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


UNKNOWN_RESOURCE = pytest.mark.xfail(
    reason="defect: a resource without ResourceType (3303/5603) fails ingest with HTTP 500",
    raises=Exception,
    strict=True,
)


def _golden_names():
    for path in sorted(GOLDEN_DIR.glob("*.json")):
        marks = [UNKNOWN_RESOURCE] if path.stem == "send_object_instance" else []
        yield pytest.param(path.stem, marks=marks)


@pytest.mark.django_db
@pytest.mark.parametrize("name", _golden_names())
def test_every_golden_request_is_accepted(client, name):
    replay(client, name)


@pytest.mark.django_db
class TestRegistrationLifecycle:
    def test_registration_marks_endpoint_registered(self, client):
        replay(client, "registration_lifecycle", step=0)

        assert Endpoint.objects.get(endpoint=ENDPOINT).registered is True
        assert values(10240, 0) == [TIME_MS]

    def test_onboarding_read_stores_device_object(self, client):
        replay(client, "registration_lifecycle", step=0)

        assert values(3, 0) == ["Zephyr"]
        assert values(3, 3) == ["1.0"]
        assert Event.objects.filter(endpoint_id=ENDPOINT, event_type="3").count() == 1

    def test_update_and_deregistration(self, client):
        replay(client, "registration_lifecycle", step=0)
        replay(client, "registration_lifecycle", step=1)
        assert values(10240, 2) == [TIME_MS]
        assert Endpoint.objects.get(endpoint=ENDPOINT).registered is True

        replay(client, "registration_lifecycle", step=2)
        assert values(10240, 1) == [TIME_MS]
        assert Endpoint.objects.get(endpoint=ENDPOINT).registered is False


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

    @UNKNOWN_RESOURCE
    def test_object_instance(self, client):
        replay(client, "send_object_instance")

        assert values(3303, 5700) == [20.0]

    def test_cached_timeseries_keeps_device_timestamps(self, client):
        replay(client, "send_cached_timeseries")

        rows = Resource.objects.filter(endpoint__endpoint=ENDPOINT).order_by("timestamp_created")
        assert [r.get_value() for r in rows] == [10.5, 11.5, 12.5]
        assert [r.timestamp_created for r in rows] == [
            datetime.fromisoformat(ts).replace(tzinfo=UTC) for ts in TIMESTAMPS
        ]
