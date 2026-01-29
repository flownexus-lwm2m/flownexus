#
# Copyright (c) 2024 Jonas Remmert
#
# SPDX-License-Identifier: Apache-2.0
#

import pytest
from django.urls import reverse

from sensordata.factories import EndpointFactory, FirmwareFactory, ResourceFactory, UserFactory


@pytest.mark.django_db
class TestFrontendViews:
    def test_dashboard_requires_login(self, client):
        url = reverse("frontend:dashboard")
        response = client.get(url)
        assert response.status_code == 302

    def test_dashboard_with_data(self, client):
        user = UserFactory()
        client.force_login(user)

        # Create synthetic data
        endpoints_registered = EndpointFactory.create_batch(5, registered=True)
        EndpointFactory.create_batch(3, registered=False)
        # Use one of the endpoints for resources to avoid creating new ones
        ResourceFactory.create_batch(10, endpoint=endpoints_registered[0])

        url = reverse("frontend:dashboard")
        response = client.get(url)

        assert response.status_code == 200
        # Check if stats are in context
        assert response.context["total_devices"] == 8
        assert response.context["registered_devices"] == 5
        assert response.context["offline_devices"] == 3
        assert "chart_labels" in response.context
        assert "chart_data" in response.context
        # Check for content
        assert b"Overview" in response.content
        assert b"Total Devices" in response.content

    def test_dashboard_view_toggle(self, client):
        user = UserFactory()
        client.force_login(user)

        # Daily view
        url = reverse("frontend:dashboard") + "?view=daily"
        response = client.get(url)
        assert response.status_code == 200
        assert response.context["view_mode"] == "daily"

        # Hourly view
        url = reverse("frontend:dashboard") + "?view=hourly"
        response = client.get(url)
        assert response.status_code == 200
        assert response.context["view_mode"] == "hourly"

        # 5-min view
        url = reverse("frontend:dashboard") + "?view=five_min"
        response = client.get(url)
        assert response.status_code == 200
        assert response.context["view_mode"] == "five_min"
        assert len(response.context["chart_labels"]) == 48

    def test_firmware_list_view(self, client):
        user = UserFactory()
        client.force_login(user)

        FirmwareFactory.create_batch(3)

        url = reverse("frontend:firmware_list")
        response = client.get(url)

        assert response.status_code == 200
        assert len(response.context["firmwares"]) == 3
        assert b"Firmware Management" in response.content
        assert b"v1.0.0" in response.content

    def test_firmware_upload(self, client):
        user = UserFactory()
        client.force_login(user)

        from django.core.files.uploadedfile import SimpleUploadedFile

        firmware_file = SimpleUploadedFile("new_firmware.bin", b"new content")

        url = reverse("frontend:firmware_list")
        data = {
            "version": "v2.0.0",
            "binary": firmware_file,
        }
        response = client.post(url, data)

        assert response.status_code == 302
        assert response.url == reverse("frontend:firmware_list")

        from sensordata.models import Firmware

        assert Firmware.objects.filter(version="v2.0.0").exists()
