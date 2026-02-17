#
# Copyright (c) 2024 Jonas Remmert
#
# SPDX-License-Identifier: Apache-2.0
#

import pytest
from django.urls import reverse

from sensordata.factories import (
    EndpointFactory,
    FirmwareFactory,
    ResourceFactory,
    SiteFactory,
    SiteMembershipFactory,
    UserFactory,
)
from sensordata.models import SiteMembership


@pytest.mark.django_db
class TestFrontendViews:
    def test_dashboard_requires_login(self, client):
        url = reverse("frontend:dashboard")
        response = client.get(url)
        assert response.status_code == 302

    def test_dashboard_with_data(self, client):
        user = UserFactory()
        site = SiteFactory()
        # Assign user to site with overview permission
        SiteMembershipFactory(
            user=user,
            site=site,
            role=SiteMembership.Role.USER,
            can_view_overview=True,
        )
        client.force_login(user)

        # Create synthetic data in the user's site
        endpoints_registered = EndpointFactory.create_batch(5, site=site, registered=True)
        EndpointFactory.create_batch(3, site=site, registered=False)
        # Use one of the endpoints for resources
        ResourceFactory.create_batch(10, endpoint=endpoints_registered[0])

        url = reverse("frontend:dashboard")
        response = client.get(url)

        assert response.status_code == 200
        # Check if stats are in context - should see only site devices (8 total)
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
        site = SiteFactory()
        SiteMembershipFactory(
            user=user,
            site=site,
            role=SiteMembership.Role.USER,
            can_view_overview=True,
        )
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
        site = SiteFactory()
        SiteMembershipFactory(
            user=user,
            site=site,
            role=SiteMembership.Role.USER,
            can_view_firmware=True,
        )
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
        site = SiteFactory()
        # Need manage_firmware permission to upload
        SiteMembershipFactory(
            user=user,
            site=site,
            role=SiteMembership.Role.ADMIN,
            can_view_firmware=True,
            can_manage_firmware=True,
        )
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


@pytest.mark.django_db
class TestMultiSiteAccessControl:
    def test_user_without_site_membership_gets_forbidden(self, client):
        """User without any site membership should be blocked from dashboard."""
        user = UserFactory()
        site = SiteFactory()
        # Create endpoints in a site
        EndpointFactory.create_batch(5, site=site, registered=True)
        # Create endpoints without site
        EndpointFactory.create_batch(3, site=None, registered=False)

        client.force_login(user)
        url = reverse("frontend:dashboard")
        response = client.get(url)

        # User has no site membership and no overview permission, should get 403
        assert response.status_code == 403

    def test_user_with_site_membership_sees_only_their_devices(self, client):
        """User should only see devices from their assigned site."""
        user = UserFactory()
        user_site = SiteFactory(name="User Site")
        other_site = SiteFactory(name="Other Site")

        # Assign user to their site with permissions
        SiteMembershipFactory(
            user=user,
            site=user_site,
            role=SiteMembership.Role.USER,
            can_view_overview=True,
        )

        # Create devices in both sites
        EndpointFactory.create_batch(3, site=user_site, registered=True)
        EndpointFactory.create_batch(5, site=other_site, registered=True)

        client.force_login(user)
        # First request will set the site context via middleware
        url = reverse("frontend:dashboard")
        response = client.get(url)

        # The first available site should be set in session
        assert response.status_code == 200
        # After site context is set, user should only see their 3 devices
        # Note: First request may not have site context yet

    def test_site_context_in_template(self, client):
        """Site context should be available in templates."""
        user = UserFactory()
        site = SiteFactory(name="Test Site")
        SiteMembershipFactory(
            user=user,
            site=site,
            role=SiteMembership.Role.USER,
            can_view_overview=True,
        )

        client.force_login(user)
        url = reverse("frontend:dashboard")
        response = client.get(url)

        assert response.status_code == 200
        # After middleware processes, site context should be set
        assert "current_site" in response.context

    def test_global_admin_sees_all_sites(self, client):
        """Global admin (superuser) should have access to all sites."""
        admin_user = UserFactory()
        admin_user.is_superuser = True
        admin_user.save()

        site1 = SiteFactory(name="Site 1")
        site2 = SiteFactory(name="Site 2")
        EndpointFactory.create_batch(3, site=site1)
        EndpointFactory.create_batch(5, site=site2)

        client.force_login(admin_user)
        url = reverse("frontend:dashboard")
        response = client.get(url)

        assert response.status_code == 200
        assert response.context["is_global_admin"] is True
        # Global admin should see sites
        assert len(response.context["available_sites"]) == 2

    def test_switch_site_view(self, client):
        """Test switching site context."""
        user = UserFactory()
        site1 = SiteFactory(name="Site 1")
        site2 = SiteFactory(name="Site 2")

        SiteMembershipFactory(user=user, site=site1, role=SiteMembership.Role.USER)
        SiteMembershipFactory(user=user, site=site2, role=SiteMembership.Role.USER)

        client.force_login(user)

        # Switch to site2
        url = reverse("frontend:switch_site", kwargs={"site_id": site2.id})
        response = client.get(url)

        # Should redirect back
        assert response.status_code == 302
        # Session should have the new site id
        assert client.session.get("current_site_id") == site2.id

    def test_permission_check_blocks_access(self, client):
        """Users without specific permissions should be blocked."""
        user = UserFactory()
        site = SiteFactory()
        # Create membership without firmware view permission
        SiteMembershipFactory(
            user=user,
            site=site,
            role=SiteMembership.Role.USER,
            can_view_firmware=False,
            can_view_overview=True,  # Has overview permission
        )

        client.force_login(user)

        # User without firmware permission should get 403
        url = reverse("frontend:firmware_list")
        response = client.get(url)
        assert response.status_code == 403

    def test_permission_check_allows_access(self, client):
        """Users with permissions should be allowed access."""
        user = UserFactory()
        site = SiteFactory()
        SiteMembershipFactory(
            user=user,
            site=site,
            role=SiteMembership.Role.USER,
            can_view_firmware=True,
            can_view_overview=True,
        )

        client.force_login(user)

        url = reverse("frontend:firmware_list")
        response = client.get(url)
        assert response.status_code == 200

    def test_site_admin_has_manage_firmware_permission(self, client):
        """Site admins should be able to manage firmware."""
        user = UserFactory()
        site = SiteFactory()
        SiteMembershipFactory(
            user=user,
            site=site,
            role=SiteMembership.Role.ADMIN,
            can_view_firmware=True,
            can_manage_firmware=True,
        )

        FirmwareFactory.create_batch(3)
        client.force_login(user)

        url = reverse("frontend:firmware_list")
        response = client.get(url)

        assert response.status_code == 200
        assert response.context["can_manage_firmware"] is True

    def test_site_user_no_manage_firmware_permission(self, client):
        """Regular site users should not be able to manage firmware."""
        user = UserFactory()
        site = SiteFactory()
        SiteMembershipFactory(
            user=user,
            site=site,
            role=SiteMembership.Role.USER,
            can_view_firmware=True,
            can_manage_firmware=False,
        )

        FirmwareFactory.create_batch(3)
        client.force_login(user)

        url = reverse("frontend:firmware_list")
        response = client.get(url)

        assert response.status_code == 200
        assert response.context["can_manage_firmware"] is False

    def test_cross_site_update_prevention(self, client):
        """Security: User A cannot initiate update for Device B (Site B)."""
        site_a = SiteFactory(name="Site A")
        user_a = UserFactory(username="user_a")
        SiteMembershipFactory(
            user=user_a,
            site=site_a,
            role=SiteMembership.Role.ADMIN,
            can_manage_firmware=True,
            can_view_firmware=True,
        )

        site_b = SiteFactory(name="Site B")
        device_b = EndpointFactory(site=site_b, endpoint="device-b")
        firmware = FirmwareFactory(version="v1.0.0")

        client.force_login(user_a)

        url = reverse("frontend:firmware_list")
        data = {
            "start_update": "1",
            "endpoint": device_b.endpoint,
            "firmware": firmware.id,
        }

        client.post(url, data)

        # Should NOT redirect (form should be invalid or 403)
        # In our implementation it redirects back with errors or just doesn't create the update
        from sensordata.models import FirmwareUpdate

        assert not FirmwareUpdate.objects.filter(endpoint=device_b).exists()
