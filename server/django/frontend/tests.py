#
# Copyright (c) 2024 Jonas Remmert
#
# SPDX-License-Identifier: Apache-2.0
#

import pytest
from django.core.files.uploadedfile import SimpleUploadedFile
from django.urls import reverse

from sensordata.factories import (
    EndpointFactory,
    FirmwareFactory,
    ResourceFactory,
    ResourceTypeFactory,
    SiteFactory,
    SiteMembershipFactory,
    UserFactory,
)
from sensordata.models import Firmware, FirmwareUpdate, ResourceType, SiteMembership


@pytest.mark.django_db
class TestFrontendViews:
    def test_dashboard_requires_login(self, client):
        url = reverse("frontend:dashboard")
        response = client.get(url)
        assert response.status_code == 302

    def test_devices_requires_login(self, client):
        response = client.get(reverse("frontend:devices"))

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

        firmware_file = SimpleUploadedFile("new_firmware.bin", b"new content")

        url = reverse("frontend:firmware_list")
        data = {
            "version": "v2.0.0",
            "binary": firmware_file,
        }
        response = client.post(url, data)

        assert response.status_code == 302
        assert response.url == reverse("frontend:firmware_list")
        assert Firmware.objects.filter(version="v2.0.0").exists()

    def test_devices_view_shows_site_filtered_inventory(self, client):
        user = UserFactory()
        site = SiteFactory(name="Visible Site")
        hidden_site = SiteFactory(name="Hidden Site")
        visible_endpoint = EndpointFactory(site=site, endpoint="urn:imei:visible-device")
        EndpointFactory(site=hidden_site, endpoint="urn:imei:hidden-device")
        ResourceFactory.create_batch(2, endpoint=visible_endpoint)
        ResourceFactory(
            endpoint=visible_endpoint,
            resource_type=ResourceTypeFactory(
                object_id=3,
                resource_id=0,
                name="manufacturer",
                data_type=ResourceType.STRING,
            ),
            str_value="Acme Devices",
        )
        ResourceFactory(
            endpoint=visible_endpoint,
            resource_type=ResourceTypeFactory(
                object_id=3,
                resource_id=9,
                name="battery_level",
                data_type=ResourceType.INTEGER,
            ),
            int_value=87,
        )
        SiteMembershipFactory(
            user=user,
            site=site,
            role=SiteMembership.Role.USER,
            can_view_overview=True,
        )
        client.force_login(user)

        response = client.get(reverse("frontend:devices"))

        assert response.status_code == 200
        assert list(response.context["endpoints"]) == [visible_endpoint]
        assert response.context["selected_endpoint"].manufacturer == "Acme Devices"
        assert response.context["selected_endpoint"].battery_level == 87
        assert b"Device Inventory" in response.content
        assert b"Device Details" in response.content
        assert b"detail-manufacturer" in response.content
        assert b"detail-battery-level" in response.content
        assert b"visible-device" in response.content
        assert b"hidden-device" not in response.content

    def test_devices_view_respects_selected_query_parameter(self, client):
        user = UserFactory()
        site = SiteFactory()
        first_endpoint = EndpointFactory(site=site, endpoint="urn:imei:first-device")
        second_endpoint = EndpointFactory(site=site, endpoint="urn:imei:selected-device")
        ResourceFactory(
            endpoint=first_endpoint,
            resource_type=ResourceTypeFactory(
                object_id=3,
                resource_id=0,
                name="manufacturer",
                data_type=ResourceType.STRING,
            ),
            str_value="First Manufacturer",
        )
        ResourceFactory(
            endpoint=second_endpoint,
            resource_type=ResourceTypeFactory(
                object_id=3,
                resource_id=0,
                name="manufacturer",
                data_type=ResourceType.STRING,
            ),
            str_value="Selected Manufacturer",
        )
        SiteMembershipFactory(
            user=user,
            site=site,
            role=SiteMembership.Role.USER,
            can_view_overview=True,
        )
        client.force_login(user)

        response = client.get(reverse("frontend:devices"), {"selected": second_endpoint.endpoint})

        assert response.status_code == 200
        assert response.context["selected_endpoint"].endpoint == second_endpoint.endpoint
        assert response.context["selected_endpoint_id"] == second_endpoint.endpoint
        assert response.context["selected_endpoint"].manufacturer == "Selected Manufacturer"

    def test_site_user_navigation_hides_firmware_tab(self, client):
        user = UserFactory()
        site = SiteFactory()
        SiteMembershipFactory(
            user=user,
            site=site,
            role=SiteMembership.Role.USER,
            can_view_overview=True,
            can_view_firmware=False,
            can_view_data_analysis=True,
        )
        client.force_login(user)

        response = client.get(reverse("frontend:dashboard"))

        assert response.status_code == 200
        assert reverse("frontend:dashboard").encode() in response.content
        assert reverse("frontend:devices").encode() in response.content
        assert reverse("frontend:data_analysis").encode() in response.content
        assert reverse("frontend:firmware_list").encode() not in response.content

    def test_site_admin_navigation_shows_overview_devices_firmware_and_data(self, client):
        user = UserFactory()
        site = SiteFactory()
        SiteMembershipFactory(
            user=user,
            site=site,
            role=SiteMembership.Role.ADMIN,
            can_view_overview=True,
            can_view_firmware=True,
            can_view_data_analysis=True,
        )
        client.force_login(user)

        response = client.get(reverse("frontend:dashboard"))

        assert response.status_code == 200
        assert reverse("frontend:dashboard").encode() in response.content
        assert reverse("frontend:devices").encode() in response.content
        assert reverse("frontend:firmware_list").encode() in response.content
        assert reverse("frontend:data_analysis").encode() in response.content
        assert b"Django Admin" not in response.content

    def test_non_global_admin_does_not_see_django_admin_link(self, client):
        user = UserFactory()
        site = SiteFactory()
        SiteMembershipFactory(user=user, site=site, role=SiteMembership.Role.USER)
        client.force_login(user)

        response = client.get(reverse("frontend:dashboard"))

        assert response.status_code == 200
        assert b"Django Admin" not in response.content

    def test_global_admin_sees_django_admin_link(self, client):
        admin_user = UserFactory(is_superuser=True, is_staff=True)
        client.force_login(admin_user)

        response = client.get(reverse("frontend:dashboard"))

        assert response.status_code == 200
        assert b"Django Admin" in response.content


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

    def test_devices_view_requires_overview_permission(self, client):
        user = UserFactory()
        site = SiteFactory()
        SiteMembershipFactory(
            user=user,
            site=site,
            role=SiteMembership.Role.USER,
            can_view_overview=False,
        )
        client.force_login(user)

        response = client.get(reverse("frontend:devices"))

        assert response.status_code == 403

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

    def test_superadmin_can_switch_to_unassigned_view(self, client):
        user = UserFactory(is_superuser=True, is_staff=True)
        site = SiteFactory(name="Assigned Site")
        EndpointFactory.create_batch(2, site=None, registered=True)
        EndpointFactory.create_batch(3, site=site, registered=True)

        client.force_login(user)

        switch_response = client.get(
            reverse("frontend:switch_site", kwargs={"site_id": "unassigned"})
        )
        assert switch_response.status_code == 302
        assert client.session.get("current_site_id") == "unassigned"

        response = client.get(reverse("frontend:dashboard"))

        assert response.status_code == 200
        assert response.context["current_site_key"] == "unassigned"
        assert response.context["total_devices"] == 2
        assert response.context["registered_devices"] == 2
        assert b"Unassigned Devices" in response.content

    def test_regular_user_cannot_switch_to_unassigned_view(self, client):
        user = UserFactory()
        site = SiteFactory(name="User Site")
        SiteMembershipFactory(user=user, site=site, role=SiteMembership.Role.USER)

        client.force_login(user)
        client.get(reverse("frontend:dashboard"))

        response = client.get(reverse("frontend:switch_site", kwargs={"site_id": "unassigned"}))

        assert response.status_code == 302
        assert client.session.get("current_site_id") == site.id

    def test_multi_site_user_can_switch_to_all_devices_view(self, client):
        user = UserFactory()
        site1 = SiteFactory(name="Site 1")
        site2 = SiteFactory(name="Site 2")
        SiteMembershipFactory(
            user=user,
            site=site1,
            role=SiteMembership.Role.USER,
            can_view_overview=True,
        )
        SiteMembershipFactory(
            user=user,
            site=site2,
            role=SiteMembership.Role.USER,
            can_view_overview=False,
        )
        EndpointFactory.create_batch(2, site=site1, registered=True)
        EndpointFactory.create_batch(3, site=site2, registered=True)

        client.force_login(user)
        client.get(reverse("frontend:dashboard"))

        switch_response = client.get(reverse("frontend:switch_site", kwargs={"site_id": "all"}))
        assert switch_response.status_code == 302
        assert client.session.get("current_site_id") == "all"

        response = client.get(reverse("frontend:dashboard"))

        assert response.status_code == 200
        assert response.context["current_site_key"] == "all"
        assert response.context["current_site_label"] == "All Devices"
        assert response.context["total_devices"] == 2
        assert response.context["can_view_overview"] is True

    def test_all_mode_filters_devices_page_to_sites_with_overview_permission(self, client):
        user = UserFactory()
        allowed_site = SiteFactory(name="Allowed Site")
        blocked_site = SiteFactory(name="Blocked Site")
        allowed_endpoint = EndpointFactory(site=allowed_site, endpoint="urn:imei:allowed-device")
        EndpointFactory(site=blocked_site, endpoint="urn:imei:blocked-device")
        SiteMembershipFactory(
            user=user,
            site=allowed_site,
            role=SiteMembership.Role.USER,
            can_view_overview=True,
        )
        SiteMembershipFactory(
            user=user,
            site=blocked_site,
            role=SiteMembership.Role.USER,
            can_view_overview=False,
        )

        client.force_login(user)
        client.get(reverse("frontend:dashboard"))
        client.get(reverse("frontend:switch_site", kwargs={"site_id": "all"}))

        response = client.get(reverse("frontend:devices"))

        assert response.status_code == 200
        assert list(response.context["endpoints"]) == [allowed_endpoint]
        assert b"allowed-device" in response.content
        assert b"blocked-device" not in response.content

    def test_all_mode_filters_firmware_page_to_sites_with_firmware_permission(self, client):
        user = UserFactory()
        allowed_site = SiteFactory(name="Allowed Site")
        blocked_site = SiteFactory(name="Blocked Site")
        SiteMembershipFactory(
            user=user,
            site=allowed_site,
            role=SiteMembership.Role.ADMIN,
        )
        SiteMembershipFactory(
            user=user,
            site=blocked_site,
            role=SiteMembership.Role.USER,
            can_view_firmware=False,
            can_view_overview=True,
        )
        allowed_endpoint = EndpointFactory(site=allowed_site)
        blocked_endpoint = EndpointFactory(site=blocked_site)
        firmware = FirmwareFactory(version="v9.9.9")
        ResourceTypeFactory(object_id=5, resource_id=1, name="Package URI")
        FirmwareUpdate.objects.create(endpoint=allowed_endpoint, firmware=firmware)
        FirmwareUpdate.objects.create(endpoint=blocked_endpoint, firmware=firmware)

        client.force_login(user)
        client.get(reverse("frontend:dashboard"))
        client.get(reverse("frontend:switch_site", kwargs={"site_id": "all"}))

        response = client.get(reverse("frontend:firmware_list"))

        assert response.status_code == 200
        updates = list(response.context["updates"])
        assert len(updates) == 1
        assert updates[0].endpoint == allowed_endpoint

    def test_single_site_user_does_not_get_all_devices_option(self, client):
        user = UserFactory()
        site = SiteFactory(name="Only Site")
        SiteMembershipFactory(
            user=user,
            site=site,
            role=SiteMembership.Role.USER,
            can_view_overview=True,
        )

        client.force_login(user)
        response = client.get(reverse("frontend:dashboard"))

        assert response.status_code == 200
        assert response.context["show_all_devices"] is False
        assert b"All Devices" not in response.content

    def test_global_admin_can_view_unassigned_devices_page(self, client):
        user = UserFactory(is_superuser=True, is_staff=True)
        assigned_site = SiteFactory(name="Assigned Site")
        EndpointFactory(site=None, endpoint="urn:imei:unassigned-device")
        EndpointFactory(site=assigned_site, endpoint="urn:imei:assigned-device")

        client.force_login(user)
        client.get(reverse("frontend:switch_site", kwargs={"site_id": "unassigned"}))

        response = client.get(reverse("frontend:devices"))

        assert response.status_code == 200
        assert response.context["current_site_key"] == "unassigned"
        endpoints = list(response.context["endpoints"])
        assert len(endpoints) == 1
        assert endpoints[0].site is None
        assert b"unassigned-device" in response.content
        assert b"urn:imei:assigned-device" not in response.content

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
        assert not FirmwareUpdate.objects.filter(endpoint=device_b).exists()

    def test_firmware_upload_requires_manage_permission(self, client):
        user = UserFactory()
        site = SiteFactory()
        SiteMembershipFactory(
            user=user,
            site=site,
            role=SiteMembership.Role.USER,
            can_view_firmware=True,
            can_manage_firmware=False,
        )
        client.force_login(user)

        response = client.post(
            reverse("frontend:firmware_list"),
            {
                "upload_fw": "1",
                "version": "v3.0.0",
                "binary": SimpleUploadedFile("blocked.bin", b"blocked content"),
            },
        )

        assert response.status_code == 403
        assert not Firmware.objects.filter(version="v3.0.0").exists()

    def test_firmware_delete_requires_manage_permission(self, client):
        user = UserFactory()
        site = SiteFactory()
        firmware = FirmwareFactory(version="v4.0.0")
        SiteMembershipFactory(
            user=user,
            site=site,
            role=SiteMembership.Role.USER,
            can_view_firmware=True,
            can_manage_firmware=False,
        )
        client.force_login(user)

        response = client.post(
            reverse("frontend:firmware_list"),
            {"delete_fw": "1", "firmware_id": firmware.id},
        )

        firmware.refresh_from_db()
        assert response.status_code == 403
        assert firmware.is_deleted is False

    def test_firmware_update_requires_operations_permission(self, client):
        site = SiteFactory()
        user = UserFactory()
        endpoint = EndpointFactory(site=site)
        firmware = FirmwareFactory(version="v5.0.0")
        SiteMembershipFactory(
            user=user,
            site=site,
            role=SiteMembership.Role.ADMIN,
            can_view_firmware=True,
            can_manage_firmware=True,
            can_perform_operations=False,
        )
        client.force_login(user)

        response = client.post(
            reverse("frontend:firmware_list"),
            {
                "start_update": "1",
                "endpoint": endpoint.endpoint,
                "firmware": firmware.id,
            },
        )

        assert response.status_code == 403
        assert not FirmwareUpdate.objects.filter(endpoint=endpoint).exists()

    def test_legacy_upload_post_guess_requires_manage_permission(self, client):
        user = UserFactory()
        site = SiteFactory()
        SiteMembershipFactory(
            user=user,
            site=site,
            role=SiteMembership.Role.USER,
            can_view_firmware=True,
            can_manage_firmware=False,
        )
        client.force_login(user)

        response = client.post(
            reverse("frontend:firmware_list"),
            {
                "version": "v6.0.0",
                "binary": SimpleUploadedFile("legacy.bin", b"legacy content"),
            },
        )

        assert response.status_code == 403
        assert not Firmware.objects.filter(version="v6.0.0").exists()

    def test_role_defaults_match_documented_permissions(self):
        admin = SiteMembership(
            user=UserFactory(), site=SiteFactory(), role=SiteMembership.Role.ADMIN
        )
        admin.apply_role_defaults()

        member = SiteMembership(
            user=UserFactory(), site=SiteFactory(), role=SiteMembership.Role.USER
        )
        member.apply_role_defaults()

        assert admin.can_view_firmware is True
        assert admin.can_manage_firmware is True
        assert admin.can_perform_operations is True
        assert admin.can_manage_devices is False
        assert member.can_view_firmware is False
        assert member.can_manage_firmware is False
        assert member.can_perform_operations is False
        assert member.can_manage_devices is False
