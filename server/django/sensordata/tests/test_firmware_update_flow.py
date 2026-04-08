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

    @patch("sensordata.tasks.requests")
    def test_version_normalization_underscore_vs_hyphen(self, mock_requests, client, settings):
        """Zephyr devices may report versions with underscores where the server
        stores them with hyphens. Verify that normalization handles this."""
        settings.CELERY_TASK_ALWAYS_EAGER = True

        site = SiteFactory(name="Normalize Site")
        user = UserFactory(username="norm_user")
        from sensordata.models import SiteMembership

        SiteMembershipFactory(
            user=user,
            site=site,
            role=SiteMembership.Role.ADMIN,
            can_manage_firmware=True,
            can_view_firmware=True,
        )
        endpoint = EndpointFactory(endpoint="norm-device", site=site)
        # Server stores version with hyphen
        firmware = FirmwareFactory(version="v0.9.13-dev1")

        mock_requests.put.return_value.status_code = 200
        mock_requests.put.return_value.json.return_value = {"status": "success"}
        mock_requests.post.return_value.status_code = 200
        mock_requests.post.return_value.json.return_value = {"status": "success"}

        # Start update
        client.force_login(user)
        url = reverse("frontend:firmware_list")
        data = {
            "start_update": "1",
            "endpoint": endpoint.endpoint,
            "firmware": firmware.id,
        }
        response = client.post(url, data)
        assert response.status_code == 302

        firmware_update = FirmwareUpdate.objects.get(endpoint=endpoint, firmware=firmware)

        # Simulate full update cycle: DOWNLOADING -> DOWNLOADED -> UPDATING
        for state_val in [
            FirmwareUpdate.State.STATE_DOWNLOADING,
            FirmwareUpdate.State.STATE_DOWNLOADED,
            FirmwareUpdate.State.STATE_UPDATING,
        ]:
            payload = {
                "ep": endpoint.endpoint,
                "obj_id": 5,
                "val": {
                    "kind": "singleResource",
                    "id": 3,
                    "type": "INTEGER",
                    "value": str(state_val),
                },
            }
            client.post(reverse("post-single-resource"), payload, content_type="application/json")

        # Device reboots and reports version with underscore instead of hyphen
        payload_version = {
            "ep": endpoint.endpoint,
            "obj_id": 3,
            "val": {
                "kind": "singleResource",
                "id": 3,
                "type": "STRING",
                "value": "v0.9.13_dev1",
            },
        }
        client.post(
            reverse("post-single-resource"), payload_version, content_type="application/json"
        )

        firmware_update.refresh_from_db()
        assert firmware_update.result == FirmwareUpdate.Result.RESULT_SUCCESS
        assert firmware_update.state == FirmwareUpdate.State.STATE_IDLE

    @patch("sensordata.tasks.requests")
    def test_mid_download_reboot_marks_update_failed(self, mock_requests, client, settings):
        """If the device reboots mid-download and reports its old firmware
        version, the update should be marked as FAILED (simplified design --
        no deferred re-send logic)."""
        settings.CELERY_TASK_ALWAYS_EAGER = True

        site = SiteFactory(name="Reboot Site")
        user = UserFactory(username="reboot_user")
        from sensordata.models import SiteMembership

        SiteMembershipFactory(
            user=user,
            site=site,
            role=SiteMembership.Role.ADMIN,
            can_manage_firmware=True,
            can_view_firmware=True,
        )
        endpoint = EndpointFactory(endpoint="reboot-device", site=site)
        firmware = FirmwareFactory(version="v2.0.0")

        mock_requests.put.return_value.status_code = 200
        mock_requests.put.return_value.json.return_value = {"status": "success"}
        mock_requests.post.return_value.status_code = 200
        mock_requests.post.return_value.json.return_value = {"status": "success"}

        # Start update
        client.force_login(user)
        url = reverse("frontend:firmware_list")
        data = {
            "start_update": "1",
            "endpoint": endpoint.endpoint,
            "firmware": firmware.id,
        }
        response = client.post(url, data)
        assert response.status_code == 302

        firmware_update = FirmwareUpdate.objects.get(endpoint=endpoint, firmware=firmware)

        # Simulate DOWNLOADING state
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

        # Device reboots mid-download and reports OLD firmware version
        payload_old_version = {
            "ep": endpoint.endpoint,
            "obj_id": 3,
            "val": {
                "kind": "singleResource",
                "id": 3,
                "type": "STRING",
                "value": "v1.0.0",
            },
        }
        client.post(
            reverse("post-single-resource"),
            payload_old_version,
            content_type="application/json",
        )

        # Should be marked as FAILED -- simplified design treats any
        # version mismatch after reboot as a failure.
        firmware_update.refresh_from_db()
        assert firmware_update.result == FirmwareUpdate.Result.RESULT_UPDATE_FAILED
        assert firmware_update.state == FirmwareUpdate.State.STATE_IDLE

    @patch("sensordata.tasks.requests")
    def test_send_uri_failure_propagates_to_firmware_update(self, mock_requests, client, settings):
        """When the send_operation task fails after 3 retries, the parent
        FirmwareUpdate should be marked as FAILED automatically."""
        settings.CELERY_TASK_ALWAYS_EAGER = True

        site = SiteFactory(name="Propagate Site")
        user = UserFactory(username="prop_user")
        from sensordata.models import SiteMembership

        SiteMembershipFactory(
            user=user,
            site=site,
            role=SiteMembership.Role.ADMIN,
            can_manage_firmware=True,
            can_view_firmware=True,
        )
        endpoint = EndpointFactory(endpoint="prop-device", site=site)
        firmware = FirmwareFactory(version="v2.0.0")

        # Simulate Leshan API returning errors (device offline)
        mock_requests.put.return_value.status_code = 504
        mock_requests.put.return_value.json.return_value = {"error": "timeout"}

        # Start update -- the send_uri_operation will be created and dispatched
        # eagerly, but the first attempt only bumps transmit_counter to 1.
        client.force_login(user)
        url = reverse("frontend:firmware_list")
        data = {
            "start_update": "1",
            "endpoint": endpoint.endpoint,
            "firmware": firmware.id,
        }
        response = client.post(url, data)
        assert response.status_code == 302

        firmware_update = FirmwareUpdate.objects.get(endpoint=endpoint, firmware=firmware)

        # After the first eager dispatch the operation should be re-queued
        # (transmit_counter == 1, threshold is 3).
        firmware_update.send_uri_operation.refresh_from_db()
        assert firmware_update.send_uri_operation.status == EndpointOperation.Status.QUEUED
        assert firmware_update.send_uri_operation.transmit_counter == 1

        # Manually invoke send_operation two more times to hit the 3-retry limit
        from sensordata.tasks import send_operation

        send_operation(firmware_update.send_uri_operation.id)
        firmware_update.send_uri_operation.refresh_from_db()
        assert firmware_update.send_uri_operation.transmit_counter == 2
        assert firmware_update.send_uri_operation.status == EndpointOperation.Status.QUEUED

        send_operation(firmware_update.send_uri_operation.id)
        firmware_update.send_uri_operation.refresh_from_db()
        assert firmware_update.send_uri_operation.transmit_counter == 3
        assert firmware_update.send_uri_operation.status == EndpointOperation.Status.FAILED

        # The failure should have propagated to the FirmwareUpdate
        firmware_update.refresh_from_db()
        assert firmware_update.result == FirmwareUpdate.Result.RESULT_UPDATE_FAILED
        assert firmware_update.state == FirmwareUpdate.State.STATE_IDLE

    @patch("sensordata.tasks.requests")
    def test_multiple_active_updates_auto_cleanup(self, mock_requests, client, settings):
        """When multiple FirmwareUpdate objects exist with RESULT_DEFAULT for the
        same endpoint, the older ones should be auto-cleaned (marked FAILED) and
        only the newest one should be kept active."""
        settings.CELERY_TASK_ALWAYS_EAGER = True

        site = SiteFactory(name="Cleanup Site")
        user = UserFactory(username="cleanup_user")
        from sensordata.models import SiteMembership

        SiteMembershipFactory(
            user=user,
            site=site,
            role=SiteMembership.Role.ADMIN,
            can_manage_firmware=True,
            can_view_firmware=True,
        )
        endpoint = EndpointFactory(endpoint="cleanup-device", site=site)
        firmware_v1 = FirmwareFactory(version="v1.0.0")
        firmware_v2 = FirmwareFactory(version="v2.0.0")

        mock_requests.put.return_value.status_code = 200
        mock_requests.put.return_value.json.return_value = {"status": "success"}
        mock_requests.post.return_value.status_code = 200
        mock_requests.post.return_value.json.return_value = {"status": "success"}

        # Start first update
        client.force_login(user)
        url = reverse("frontend:firmware_list")
        data = {
            "start_update": "1",
            "endpoint": endpoint.endpoint,
            "firmware": firmware_v1.id,
        }
        response = client.post(url, data)
        assert response.status_code == 302

        fw_update_1 = FirmwareUpdate.objects.get(endpoint=endpoint, firmware=firmware_v1)
        assert fw_update_1.result == FirmwareUpdate.Result.RESULT_DEFAULT

        # Start second update (bypassing the form-level clean() validation
        # to simulate the race condition that happens in practice)
        fw_update_2 = FirmwareUpdate(endpoint=endpoint, firmware=firmware_v2)
        fw_update_2.save()
        assert fw_update_2.result == FirmwareUpdate.Result.RESULT_DEFAULT

        # Both are active (RESULT_DEFAULT)
        active_count = FirmwareUpdate.objects.filter(
            endpoint=endpoint, result=FirmwareUpdate.Result.RESULT_DEFAULT
        ).count()
        assert active_count == 2

        # Trigger handle_fota by sending a state update -- this should
        # auto-cleanup the older duplicate.
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

        # The older update (fw_update_1) should now be marked as FAILED
        fw_update_1.refresh_from_db()
        assert fw_update_1.result == FirmwareUpdate.Result.RESULT_UPDATE_FAILED
        assert fw_update_1.state == FirmwareUpdate.State.STATE_IDLE

        # The newer update (fw_update_2) should still be active
        fw_update_2.refresh_from_db()
        assert fw_update_2.result == FirmwareUpdate.Result.RESULT_DEFAULT
        assert fw_update_2.state == FirmwareUpdate.State.STATE_DOWNLOADING
