#
# Copyright (c) 2026 Jonas Remmert
#
# SPDX-License-Identifier: Apache-2.0
#

import pytest
from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.core.management.base import CommandError
from django.urls import reverse

from sensordata.models import Endpoint, ResourceType, Site, SiteMembership

User = get_user_model()


@pytest.mark.django_db
class TestMockSetupCommands:
    def test_load_initial_resource_types_is_idempotent(self):
        call_command("load_initial_resource_types")
        first_count = ResourceType.objects.count()

        call_command("load_initial_resource_types")

        assert ResourceType.objects.count() == first_count
        assert ResourceType.objects.get(object_id=10240, resource_id=0).name == "ep_registered"

    def test_load_mock_scenario_updates_existing_records(self):
        call_command("load_mock_scenario", config="multi-site")

        warehouse = Site.objects.get(name="Warehouse")
        warehouse.description = "outdated"
        warehouse.save(update_fields=["description"])

        user = User.objects.get(username="user-warehouse")
        membership = SiteMembership.objects.get(user=user, site=warehouse)
        membership.can_view_firmware = False
        membership.save(update_fields=["can_view_firmware"])

        call_command("load_mock_scenario", config="multi-site")

        warehouse.refresh_from_db()
        membership.refresh_from_db()

        assert warehouse.description == "Storage facility with environmental monitoring"
        assert membership.can_view_firmware is True

    def test_load_mock_scenario_fails_for_missing_file(self):
        with pytest.raises(CommandError):
            call_command("load_mock_scenario", config="missing-scenario")


@pytest.mark.django_db
class TestMockRegistrationHandling:
    def test_registration_resource_marks_endpoint_as_registered(self, client, settings):
        settings.CELERY_TASK_ALWAYS_EAGER = True
        settings.CELERY_TASK_EAGER_PROPAGATES = True
        call_command("load_initial_resource_types")

        payload = {
            "ep": "urn:imei:123",
            "obj_id": 10240,
            "val": {
                "kind": "singleResource",
                "id": 0,
                "type": "INTEGER",
                "value": "1",
            },
        }

        response = client.post(
            reverse("post-single-resource"),
            payload,
            content_type="application/json",
        )

        assert response.status_code == 201
        endpoint = Endpoint.objects.get(endpoint="urn:imei:123")
        assert endpoint.registered is True
