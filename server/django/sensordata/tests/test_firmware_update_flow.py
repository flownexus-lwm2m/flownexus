#
# Copyright (c) 2026 Jonas Remmert
#
# SPDX-License-Identifier: Apache-2.0
#

from unittest.mock import patch

import pytest
from django.urls import reverse

from sensordata.factories import (
    EndpointFactory,
    FirmwareFactory,
    ResourceTypeFactory,
    SiteFactory,
    SiteMembershipFactory,
    UserFactory,
)
from sensordata.models import EndpointOperation, FirmwareUpdate, ResourceType


@pytest.mark.django_db(transaction=True)
class TestFirmwareUpdateFlow:
    @pytest.fixture(autouse=True)
    def setup_resources(self):
        # Create necessary ResourceTypes for FOTA
        self.rt_fw_version = ResourceTypeFactory(
            object_id=3, resource_id=3, name="Firmware Version", data_type=ResourceType.STRING
        )
        self.rt_pkg_uri = ResourceTypeFactory(
            object_id=5, resource_id=1, name="Package URI", data_type=ResourceType.STRING
        )
        self.rt_update = ResourceTypeFactory(
            object_id=5, resource_id=2, name="Update", data_type="NONE"
        )
        self.rt_state = ResourceTypeFactory(
            object_id=5, resource_id=3, name="State", data_type=ResourceType.INTEGER
        )
        self.rt_result = ResourceTypeFactory(
            object_id=5, resource_id=5, name="Update Result", data_type=ResourceType.INTEGER
        )

    @patch("sensordata.tasks.requests")
    def test_full_firmware_update_cycle(self, mock_requests, client, settings):
        # Ensure Celery tasks run immediately
        settings.CELERY_TASK_ALWAYS_EAGER = True

        # 1. Setup: Site, User, Device and Firmware
        site = SiteFactory(name="Update Site")
        user = UserFactory(username="update_user")
        from sensordata.models import SiteMembership

        SiteMembershipFactory(
            user=user,
            site=site,
            role=SiteMembership.Role.ADMIN,
            can_manage_firmware=True,
            can_view_firmware=True,
        )
        endpoint = EndpointFactory(endpoint="test-device", site=site)
        firmware = FirmwareFactory(version="v2.0.0")

        # Mock Leshan API responses
        mock_requests.put.return_value.status_code = 200
        mock_requests.put.return_value.json.return_value = {"status": "success"}
        mock_requests.post.return_value.status_code = 200
        mock_requests.post.return_value.json.return_value = {"status": "success"}

        # 2. Start Update (User Action via View)
        client.force_login(user)
        url = reverse("frontend:firmware_list")
        data = {
            "start_update": "1",
            "endpoint": endpoint.endpoint,
            "firmware": firmware.id,
        }
        response = client.post(url, data)
        assert response.status_code == 302

        # Verify FirmwareUpdate object created

        firmware_update = FirmwareUpdate.objects.get(endpoint=endpoint, firmware=firmware)

        # Verify initial state
        assert firmware_update.state == FirmwareUpdate.State.STATE_IDLE
        assert firmware_update.result == FirmwareUpdate.Result.RESULT_DEFAULT

        # Verify Send URI operation created and sent
        firmware_update.send_uri_operation.refresh_from_db()
        assert firmware_update.send_uri_operation is not None
        assert (
            firmware_update.send_uri_operation.status == EndpointOperation.Status.CONFIRMED
        )  # Because eager execution

        # Verify requests.put was called with the binary URL
        mock_requests.put.assert_called()
        args, kwargs = mock_requests.put.call_args
        assert f"/clients/{endpoint.endpoint}/5/0/1" in args[0]
        assert kwargs["json"]["value"] == firmware.binary.url

        # 3. Simulate Device Reporting STATE_DOWNLOADING
        payload_downloading = {
            "ep": endpoint.endpoint,
            "obj_id": 5,
            "val": {
                "kind": "singleResource",
                "id": 3,
                "type": "INTEGER",
                "value": str(FirmwareUpdate.State.STATE_DOWNLOADING),
            },
        }
        client.post(
            reverse("post-single-resource"), payload_downloading, content_type="application/json"
        )

        firmware_update.refresh_from_db()
        assert firmware_update.state == FirmwareUpdate.State.STATE_DOWNLOADING

        # 4. Simulate Device Reporting STATE_DOWNLOADED
        # This should trigger the EXECUTE command
        payload_downloaded = {
            "ep": endpoint.endpoint,
            "obj_id": 5,
            "val": {
                "kind": "singleResource",
                "id": 3,
                "type": "INTEGER",
                "value": str(FirmwareUpdate.State.STATE_DOWNLOADED),
            },
        }
        client.post(
            reverse("post-single-resource"), payload_downloaded, content_type="application/json"
        )

        firmware_update.refresh_from_db()
        assert firmware_update.state == FirmwareUpdate.State.STATE_DOWNLOADED

        # Verify Execute operation created and sent
        assert firmware_update.execute_operation is not None
        assert firmware_update.execute_operation.status == EndpointOperation.Status.CONFIRMED

        # Verify requests.post was called (Execute is a POST)
        mock_requests.post.assert_called()
        args, kwargs = mock_requests.post.call_args
        assert f"/clients/{endpoint.endpoint}/5/0/2" in args[0]

        # 5. Simulate Device Reporting STATE_UPDATING
        payload_updating = {
            "ep": endpoint.endpoint,
            "obj_id": 5,
            "val": {
                "kind": "singleResource",
                "id": 3,
                "type": "INTEGER",
                "value": str(FirmwareUpdate.State.STATE_UPDATING),
            },
        }
        client.post(
            reverse("post-single-resource"), payload_updating, content_type="application/json"
        )

        firmware_update.refresh_from_db()
        assert firmware_update.state == FirmwareUpdate.State.STATE_UPDATING

        # 6. Simulate Device Reboot with New Version (Success)
        payload_version = {
            "ep": endpoint.endpoint,
            "obj_id": 3,
            "val": {"kind": "singleResource", "id": 3, "type": "STRING", "value": "v2.0.0"},
        }
        client.post(
            reverse("post-single-resource"), payload_version, content_type="application/json"
        )

        firmware_update.refresh_from_db()
        assert firmware_update.result == FirmwareUpdate.Result.RESULT_SUCCESS
        assert firmware_update.state == FirmwareUpdate.State.STATE_IDLE
