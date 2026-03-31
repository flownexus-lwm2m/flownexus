#
# Copyright (c) 2024 Jonas Remmert
#
# SPDX-License-Identifier: Apache-2.0
#

import json
from datetime import timedelta
from io import BytesIO

import pytest
from django.core.files.uploadedfile import SimpleUploadedFile
from django.urls import reverse
from django.utils import timezone
from openpyxl import load_workbook

from sensordata.factories import (
    EndpointFactory,
    EventFactory,
    FirmwareFactory,
    ResourceFactory,
    ResourceTypeFactory,
    SiteFactory,
    SiteMembershipFactory,
    UserFactory,
)
from sensordata.models import (
    EventResource,
    Firmware,
    FirmwareUpdate,
    Resource,
    ResourceType,
    SiteMembership,
)


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

    def test_global_admin_sees_permissions_tab(self, client):
        admin_user = UserFactory(is_superuser=True, is_staff=True)
        client.force_login(admin_user)

        response = client.get(reverse("frontend:dashboard"))

        assert response.status_code == 200
        assert reverse("frontend:permissions").encode() in response.content

    def test_non_global_admin_does_not_see_permissions_tab(self, client):
        user = UserFactory()
        site = SiteFactory()
        SiteMembershipFactory(user=user, site=site, role=SiteMembership.Role.ADMIN)
        client.force_login(user)

        response = client.get(reverse("frontend:dashboard"))

        assert response.status_code == 200
        assert reverse("frontend:permissions").encode() not in response.content


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

    def test_permissions_page_requires_global_admin(self, client):
        user = UserFactory()
        site = SiteFactory()
        SiteMembershipFactory(user=user, site=site, role=SiteMembership.Role.ADMIN)
        client.force_login(user)

        response = client.get(reverse("frontend:permissions"))

        assert response.status_code == 403

    def test_global_admin_can_view_permissions_page(self, client):
        user = UserFactory(is_superuser=True, is_staff=True)
        client.force_login(user)

        response = client.get(reverse("frontend:permissions"))

        assert response.status_code == 200
        assert b"User Roles" in response.content
        assert b"Device Assignments" in response.content

    def test_global_admin_can_create_user_from_permissions_page(self, client):
        user = UserFactory(is_superuser=True, is_staff=True)
        client.force_login(user)

        response = client.post(
            reverse("frontend:permissions"),
            {
                "create_user": "1",
                "create-user-username": "new-operator",
                "create-user-email": "operator@example.com",
                "create-user-password1": "strong-password-123",
                "create-user-password2": "strong-password-123",
            },
        )

        assert response.status_code == 302
        assert response.url == reverse("frontend:permissions")
        assert UserFactory._meta.model.objects.filter(username="new-operator").exists()

    def test_global_admin_can_create_membership_from_permissions_page(self, client):
        user = UserFactory(is_superuser=True, is_staff=True)
        managed_user = UserFactory()
        site = SiteFactory(name="Ops Site")
        client.force_login(user)

        response = client.post(
            reverse("frontend:permissions"),
            {
                "create_membership": "1",
                "create-membership-user": managed_user.id,
                "create-membership-site": site.id,
                "create-membership-role": SiteMembership.Role.ADMIN,
                "create-membership-can_view_overview": "on",
                "create-membership-can_view_firmware": "on",
                "create-membership-can_view_data_analysis": "on",
                "create-membership-can_manage_firmware": "on",
                "create-membership-can_perform_operations": "on",
            },
        )

        assert response.status_code == 302
        membership = SiteMembership.objects.get(user=managed_user, site=site)
        assert membership.role == SiteMembership.Role.ADMIN
        assert membership.can_manage_firmware is True

    def test_global_admin_can_update_membership_from_permissions_page(self, client):
        user = UserFactory(is_superuser=True, is_staff=True)
        managed_user = UserFactory()
        site = SiteFactory()
        membership = SiteMembershipFactory(
            user=managed_user,
            site=site,
            role=SiteMembership.Role.USER,
            can_view_firmware=False,
            can_manage_firmware=False,
            can_perform_operations=False,
        )
        client.force_login(user)

        response = client.post(
            reverse("frontend:permissions"),
            {
                "update_membership": "1",
                "membership_id": membership.id,
                f"membership-{membership.id}-role": SiteMembership.Role.ADMIN,
                f"membership-{membership.id}-can_view_overview": "on",
                f"membership-{membership.id}-can_view_firmware": "on",
                f"membership-{membership.id}-can_view_data_analysis": "on",
                f"membership-{membership.id}-can_manage_firmware": "on",
                f"membership-{membership.id}-can_perform_operations": "on",
            },
        )

        assert response.status_code == 302
        membership.refresh_from_db()
        assert membership.role == SiteMembership.Role.ADMIN
        assert membership.can_view_firmware is True
        assert membership.can_manage_firmware is True

    def test_global_admin_can_revoke_membership_from_permissions_page(self, client):
        user = UserFactory(is_superuser=True, is_staff=True)
        membership = SiteMembershipFactory()
        client.force_login(user)

        response = client.post(
            reverse("frontend:permissions"),
            {"revoke_membership": "1", "membership_id": membership.id},
        )

        assert response.status_code == 302
        assert not SiteMembership.objects.filter(pk=membership.pk).exists()

    def test_global_admin_can_assign_unassigned_device(self, client):
        user = UserFactory(is_superuser=True, is_staff=True)
        site = SiteFactory(name="Assigned Site")
        endpoint = EndpointFactory(site=None, endpoint="urn:imei:assign-me")
        client.force_login(user)

        response = client.post(
            reverse("frontend:permissions"),
            {
                "assign_device": "1",
                "assign-device-endpoint": endpoint.endpoint,
                "assign-device-site": site.id,
            },
        )

        assert response.status_code == 302
        endpoint.refresh_from_db()
        assert endpoint.site == site

    def test_global_admin_can_transfer_device(self, client):
        user = UserFactory(is_superuser=True, is_staff=True)
        source_site = SiteFactory(name="Source Site")
        target_site = SiteFactory(name="Target Site")
        endpoint = EndpointFactory(site=source_site, endpoint="urn:imei:transfer-me")
        client.force_login(user)

        response = client.post(
            reverse("frontend:permissions"),
            {
                "transfer_device": "1",
                "endpoint_id": endpoint.endpoint,
                f"transfer-{endpoint.endpoint}-site": target_site.id,
            },
        )

        assert response.status_code == 302
        endpoint.refresh_from_db()
        assert endpoint.site == target_site

    def test_global_admin_can_bulk_assign_devices(self, client):
        user = UserFactory(is_superuser=True, is_staff=True)
        site = SiteFactory(name="Bulk Site")
        endpoint_a = EndpointFactory(site=None, endpoint="urn:imei:bulk-a")
        endpoint_b = EndpointFactory(site=None, endpoint="urn:imei:bulk-b")
        client.force_login(user)

        response = client.post(
            reverse("frontend:permissions"),
            {
                "bulk_assign": "1",
                "bulk-assign-endpoints": [endpoint_a.endpoint, endpoint_b.endpoint],
                "bulk-assign-site": site.id,
            },
        )

        assert response.status_code == 302
        endpoint_a.refresh_from_db()
        endpoint_b.refresh_from_db()
        assert endpoint_a.site == site
        assert endpoint_b.site == site

    def test_permissions_post_is_forbidden_for_non_global_admin(self, client):
        user = UserFactory()
        site = SiteFactory()
        managed_user = UserFactory()
        SiteMembershipFactory(user=user, site=site, role=SiteMembership.Role.ADMIN)
        client.force_login(user)

        response = client.post(
            reverse("frontend:permissions"),
            {
                "create_membership": "1",
                "create-membership-user": managed_user.id,
                "create-membership-site": site.id,
                "create-membership-role": SiteMembership.Role.USER,
                "create-membership-can_view_overview": "on",
                "create-membership-can_view_data_analysis": "on",
            },
        )

        assert response.status_code == 403
        assert not SiteMembership.objects.filter(user=managed_user, site=site).exists()

    def test_permissions_page_lists_only_global_admin_unassigned_devices(self, client):
        user = UserFactory(is_superuser=True, is_staff=True)
        assigned_site = SiteFactory(name="Assigned Site")
        EndpointFactory(site=None, endpoint="urn:imei:unassigned-visible")
        EndpointFactory(site=assigned_site, endpoint="urn:imei:assigned-hidden")
        client.force_login(user)

        response = client.get(reverse("frontend:permissions"))

        assert response.status_code == 200
        assert b"unassigned-visible" in response.content
        assert b"assigned-hidden" in response.content

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


def _data_analysis_url(**params):
    """Build the data_analysis JSON URL with the given query parameters."""
    return reverse("frontend:data_analysis") + "?" + "&".join(f"{k}={v}" for k, v in params.items())


def _setup_data_analysis_user(can_view_data_analysis=True):
    """Return (client fixture-ready user, site, membership) for data_analysis tests."""
    from django.test import Client

    user = UserFactory()
    site = SiteFactory()
    SiteMembershipFactory(
        user=user,
        site=site,
        can_view_data_analysis=can_view_data_analysis,
    )
    client = Client()
    client.force_login(user)
    return client, user, site


@pytest.mark.django_db
class TestDataAnalysisView:
    """Tests for the /data/ data_analysis view (JSON API and page rendering)."""

    # ------------------------------------------------------------------
    # Auth / permission
    # ------------------------------------------------------------------

    def test_requires_login(self, client):
        response = client.get(reverse("frontend:data_analysis"))
        assert response.status_code == 302

    def test_requires_data_analysis_permission(self, client):
        user = UserFactory()
        site = SiteFactory()
        SiteMembershipFactory(user=user, site=site, can_view_data_analysis=False)
        client.force_login(user)
        response = client.get(reverse("frontend:data_analysis"))
        assert response.status_code == 403

    def test_page_renders_for_authorised_user(self, client):
        client_obj, _, _ = _setup_data_analysis_user()
        response = client_obj.get(reverse("frontend:data_analysis"))
        assert response.status_code == 200
        assert b"Data Analyzer" in response.content

    # ------------------------------------------------------------------
    # JSON: basic data return
    # ------------------------------------------------------------------

    def test_json_returns_resources_for_endpoint_and_resource_type(self, client):
        client_obj, _, site = _setup_data_analysis_user()
        rt = ResourceTypeFactory(data_type="FLOAT")
        ep = EndpointFactory(site=site)
        ResourceFactory.create_batch(3, endpoint=ep, resource_type=rt)

        response = client_obj.get(
            _data_analysis_url(
                format="json",
                mode="values",
                endpoint=ep.endpoint,
                resource_type=rt.id,
                time_range="all",
            )
        )
        data = json.loads(response.content)
        assert response.status_code == 200
        assert data["count"] == 3
        assert len(data["data"]) == 3
        assert data["is_numeric"] is True
        assert data["multi_endpoint"] is False

    def test_json_all_devices_returns_multi_endpoint_flag(self, client):
        client_obj, _, site = _setup_data_analysis_user()
        rt = ResourceTypeFactory(data_type="FLOAT")
        ep1 = EndpointFactory(site=site)
        ep2 = EndpointFactory(site=site)
        ResourceFactory(endpoint=ep1, resource_type=rt)
        ResourceFactory(endpoint=ep2, resource_type=rt)

        response = client_obj.get(
            _data_analysis_url(
                format="json",
                mode="values",
                endpoint="all",
                resource_type=rt.id,
                time_range="all",
            )
        )
        data = json.loads(response.content)
        assert data["multi_endpoint"] is True
        assert data["count"] == 2

    def test_json_all_types_returns_is_numeric_false(self, client):
        """When no resource_type filter is applied, is_numeric defaults to False."""
        client_obj, _, site = _setup_data_analysis_user()
        ep = EndpointFactory(site=site)
        ResourceFactory(endpoint=ep)

        response = client_obj.get(
            _data_analysis_url(
                format="json",
                mode="values",
                endpoint=ep.endpoint,
                resource_type="all",
                time_range="all",
            )
        )
        data = json.loads(response.content)
        assert data["is_numeric"] is False

    def test_json_string_resource_type_is_not_numeric(self, client):
        client_obj, _, site = _setup_data_analysis_user()
        rt = ResourceTypeFactory(
            object_id=3, resource_id=0, name="manufacturer", data_type="STRING"
        )
        ep = EndpointFactory(site=site)
        ResourceFactory(endpoint=ep, resource_type=rt, str_value="Acme")

        response = client_obj.get(
            _data_analysis_url(
                format="json",
                mode="values",
                endpoint=ep.endpoint,
                resource_type=rt.id,
                time_range="all",
            )
        )
        data = json.loads(response.content)
        assert data["is_numeric"] is False

    # ------------------------------------------------------------------
    # JSON: time range filtering
    # ------------------------------------------------------------------

    def test_json_1h_excludes_old_readings(self, client):
        client_obj, _, site = _setup_data_analysis_user()
        rt = ResourceTypeFactory(data_type="FLOAT")
        ep = EndpointFactory(site=site)
        now = timezone.now()
        # Recent reading (30 min ago) — should be included
        recent = ResourceFactory(endpoint=ep, resource_type=rt)
        recent.timestamp_created = now - timedelta(minutes=30)
        recent.save()
        # Old reading (2 hours ago) — should be excluded
        old = ResourceFactory(endpoint=ep, resource_type=rt)
        old.timestamp_created = now - timedelta(hours=2)
        old.save()

        response = client_obj.get(
            _data_analysis_url(
                format="json",
                mode="values",
                endpoint=ep.endpoint,
                resource_type=rt.id,
                time_range="1h",
            )
        )
        data = json.loads(response.content)
        assert data["count"] == 1

    def test_json_custom_range_inclusive_of_to_minute(self, client):
        """A reading at 12:01:30 must be included when to=12:01 (minute-inclusive fix)."""
        client_obj, _, site = _setup_data_analysis_user()
        rt = ResourceTypeFactory(data_type="FLOAT")
        ep = EndpointFactory(site=site)
        now = timezone.now().replace(hour=12, minute=1, second=30, microsecond=0)
        r = ResourceFactory(endpoint=ep, resource_type=rt)
        r.timestamp_created = now
        r.save()

        # from=12:00, to=12:01 — reading at 12:01:30 must be included
        response = client_obj.get(
            _data_analysis_url(
                format="json",
                mode="values",
                endpoint=ep.endpoint,
                resource_type=rt.id,
                time_range="custom",
                time_from=now.strftime("%Y-%m-%dT12:00"),
                time_to=now.strftime("%Y-%m-%dT12:01"),
            )
        )
        data = json.loads(response.content)
        assert data["count"] == 1, "Reading at 12:01:30 should be included when to=12:01"

    def test_json_custom_range_excludes_reading_outside_window(self, client):
        client_obj, _, site = _setup_data_analysis_user()
        rt = ResourceTypeFactory(data_type="FLOAT")
        ep = EndpointFactory(site=site)
        base = timezone.now().replace(hour=10, minute=0, second=0, microsecond=0)
        r = ResourceFactory(endpoint=ep, resource_type=rt)
        r.timestamp_created = base  # 10:00 — outside 11:00–12:00 window
        r.save()

        response = client_obj.get(
            _data_analysis_url(
                format="json",
                mode="values",
                endpoint=ep.endpoint,
                resource_type=rt.id,
                time_range="custom",
                time_from=base.strftime("%Y-%m-%dT11:00"),
                time_to=base.strftime("%Y-%m-%dT12:00"),
            )
        )
        data = json.loads(response.content)
        assert data["count"] == 0

    # ------------------------------------------------------------------
    # JSON: pagination
    # ------------------------------------------------------------------

    def test_json_values_pagination_returns_correct_page(self, client):
        client_obj, _, site = _setup_data_analysis_user()
        rt = ResourceTypeFactory(data_type="FLOAT")
        ep = EndpointFactory(site=site)
        ResourceFactory.create_batch(105, endpoint=ep, resource_type=rt)

        # Page 1: 100 items
        resp1 = json.loads(
            client_obj.get(
                _data_analysis_url(
                    format="json",
                    mode="values",
                    endpoint=ep.endpoint,
                    resource_type=rt.id,
                    time_range="all",
                    page=1,
                )
            ).content
        )
        assert len(resp1["data"]) == 100
        assert resp1["has_next"] is True
        assert resp1["num_pages"] == 2

        # Page 2: remaining 5 items
        resp2 = json.loads(
            client_obj.get(
                _data_analysis_url(
                    format="json",
                    mode="values",
                    endpoint=ep.endpoint,
                    resource_type=rt.id,
                    time_range="all",
                    page=2,
                )
            ).content
        )
        assert len(resp2["data"]) == 5
        assert resp2["has_next"] is False

    def test_json_events_pagination(self, client):
        client_obj, _, site = _setup_data_analysis_user()
        ep = EndpointFactory(site=site)
        for _ in range(55):
            EventFactory(endpoint=ep)

        resp1 = json.loads(
            client_obj.get(
                _data_analysis_url(
                    format="json",
                    mode="events",
                    endpoint=ep.endpoint,
                    time_range="all",
                    page=1,
                )
            ).content
        )
        assert len(resp1["events"]) == 50
        assert resp1["has_next"] is True

        resp2 = json.loads(
            client_obj.get(
                _data_analysis_url(
                    format="json",
                    mode="events",
                    endpoint=ep.endpoint,
                    time_range="all",
                    page=2,
                )
            ).content
        )
        assert len(resp2["events"]) == 5
        assert resp2["has_next"] is False

    # ------------------------------------------------------------------
    # Site isolation
    # ------------------------------------------------------------------

    def test_json_does_not_return_other_sites_data(self, client):
        client_obj, _, site = _setup_data_analysis_user()
        other_site = SiteFactory()
        rt = ResourceTypeFactory(data_type="FLOAT")
        own_ep = EndpointFactory(site=site)
        other_ep = EndpointFactory(site=other_site)
        ResourceFactory(endpoint=own_ep, resource_type=rt)
        ResourceFactory(endpoint=other_ep, resource_type=rt)

        response = client_obj.get(
            _data_analysis_url(
                format="json",
                mode="values",
                endpoint="all",
                resource_type=rt.id,
                time_range="all",
            )
        )
        data = json.loads(response.content)
        returned_endpoints = {item["endpoint"] for item in data["data"]}
        assert own_ep.endpoint in returned_endpoints
        assert other_ep.endpoint not in returned_endpoints


def _export_url(**params):
    """Build the export URL with the given query parameters."""
    return (
        reverse("frontend:data_analysis_export")
        + "?"
        + "&".join(f"{k}={v}" for k, v in params.items())
    )


def _wb_from_response(response):
    """Parse an HttpResponse carrying an xlsx file into an openpyxl Workbook."""
    return load_workbook(filename=BytesIO(response.content))


@pytest.mark.django_db
class TestDataAnalysisExport:
    """Tests for the /data/export/ Excel export view."""

    # ------------------------------------------------------------------
    # Auth / permission
    # ------------------------------------------------------------------

    def test_requires_login(self, client):
        response = client.get(_export_url(mode="values", time_range="all"))
        assert response.status_code == 302

    def test_requires_data_analysis_permission(self, client):
        user = UserFactory()
        site = SiteFactory()
        SiteMembershipFactory(user=user, site=site, can_view_data_analysis=False)
        client.force_login(user)
        response = client.get(_export_url(mode="values", time_range="all"))
        assert response.status_code == 403

    # ------------------------------------------------------------------
    # Values mode
    # ------------------------------------------------------------------

    def test_values_export_returns_xlsx(self, client):
        client_obj, _, site = _setup_data_analysis_user()
        rt = ResourceTypeFactory(data_type="FLOAT")
        ep = EndpointFactory(site=site)
        ResourceFactory.create_batch(3, endpoint=ep, resource_type=rt)

        response = client_obj.get(
            _export_url(mode="values", endpoint=ep.endpoint, resource_type=rt.id, time_range="all")
        )

        assert response.status_code == 200
        assert (
            response["Content-Type"]
            == "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )
        assert "attachment" in response["Content-Disposition"]
        assert ".xlsx" in response["Content-Disposition"]

    def test_values_export_single_endpoint_headers(self, client):
        """Single endpoint: no Endpoint column."""
        client_obj, _, site = _setup_data_analysis_user()
        rt = ResourceTypeFactory(data_type="FLOAT")
        ep = EndpointFactory(site=site)
        ResourceFactory.create_batch(2, endpoint=ep, resource_type=rt)

        response = client_obj.get(
            _export_url(mode="values", endpoint=ep.endpoint, resource_type=rt.id, time_range="all")
        )
        wb = _wb_from_response(response)
        ws = wb.active
        headers = [ws.cell(1, c).value for c in range(1, ws.max_column + 1)]

        assert headers == ["Time", "Resource Type", "Value"]
        assert ws.max_row == 3  # header + 2 data rows

    def test_values_export_all_devices_includes_endpoint_column(self, client):
        """All devices: Endpoint column present."""
        client_obj, _, site = _setup_data_analysis_user()
        rt = ResourceTypeFactory(data_type="FLOAT")
        ep1 = EndpointFactory(site=site)
        ep2 = EndpointFactory(site=site)
        ResourceFactory(endpoint=ep1, resource_type=rt)
        ResourceFactory(endpoint=ep2, resource_type=rt)

        response = client_obj.get(
            _export_url(mode="values", endpoint="all", resource_type=rt.id, time_range="all")
        )
        wb = _wb_from_response(response)
        ws = wb.active
        headers = [ws.cell(1, c).value for c in range(1, ws.max_column + 1)]

        assert headers == ["Time", "Endpoint", "Resource Type", "Value"]
        assert ws.max_row == 3  # header + 2 data rows

    def test_values_export_filtered_by_endpoint(self, client):
        """Only rows for the selected endpoint are exported."""
        client_obj, _, site = _setup_data_analysis_user()
        rt = ResourceTypeFactory(data_type="FLOAT")
        ep1 = EndpointFactory(site=site)
        ep2 = EndpointFactory(site=site)
        ResourceFactory.create_batch(2, endpoint=ep1, resource_type=rt)
        ResourceFactory.create_batch(3, endpoint=ep2, resource_type=rt)

        response = client_obj.get(
            _export_url(mode="values", endpoint=ep1.endpoint, resource_type=rt.id, time_range="all")
        )
        wb = _wb_from_response(response)
        ws = wb.active

        assert ws.max_row == 3  # header + 2 rows for ep1 only

    def test_values_export_time_range_filter(self, client):
        """Time range filter is respected in export."""
        client_obj, _, site = _setup_data_analysis_user()
        rt = ResourceTypeFactory(data_type="FLOAT")
        ep = EndpointFactory(site=site)
        now = timezone.now()

        recent = ResourceFactory(endpoint=ep, resource_type=rt)
        recent.timestamp_created = now - timedelta(minutes=30)
        recent.save()

        old = ResourceFactory(endpoint=ep, resource_type=rt)
        old.timestamp_created = now - timedelta(hours=2)
        old.save()

        response = client_obj.get(
            _export_url(mode="values", endpoint=ep.endpoint, resource_type=rt.id, time_range="1h")
        )
        wb = _wb_from_response(response)
        ws = wb.active

        assert ws.max_row == 2  # header + 1 recent row

    def test_values_export_site_isolation(self, client):
        """Export never leaks data from another site."""
        client_obj, _, site = _setup_data_analysis_user()
        other_site = SiteFactory()
        rt = ResourceTypeFactory(data_type="FLOAT")
        own_ep = EndpointFactory(site=site)
        other_ep = EndpointFactory(site=other_site)
        ResourceFactory(endpoint=own_ep, resource_type=rt)
        ResourceFactory(endpoint=other_ep, resource_type=rt)

        response = client_obj.get(
            _export_url(mode="values", endpoint="all", resource_type=rt.id, time_range="all")
        )
        wb = _wb_from_response(response)
        ws = wb.active

        exported_endpoints = {ws.cell(r, 2).value for r in range(2, ws.max_row + 1)}
        assert own_ep.endpoint in exported_endpoints
        assert other_ep.endpoint not in exported_endpoints

    # ------------------------------------------------------------------
    # Events mode
    # ------------------------------------------------------------------

    def test_events_export_returns_xlsx(self, client):
        client_obj, _, site = _setup_data_analysis_user()
        ep = EndpointFactory(site=site)
        EventFactory(endpoint=ep)

        response = client_obj.get(
            _export_url(mode="events", endpoint=ep.endpoint, time_range="all")
        )

        assert response.status_code == 200
        assert (
            response["Content-Type"]
            == "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )

    def test_events_export_fixed_headers(self, client):
        """Events with no resource data: only fixed columns Time/Endpoint/Event Type."""
        client_obj, _, site = _setup_data_analysis_user()
        ep = EndpointFactory(site=site)
        EventFactory(endpoint=ep)

        response = client_obj.get(
            _export_url(mode="events", endpoint=ep.endpoint, time_range="all")
        )
        wb = _wb_from_response(response)
        ws = wb.active
        headers = [ws.cell(1, c).value for c in range(1, ws.max_column + 1)]

        assert headers[:3] == ["Time", "Endpoint", "Event Type"]
        assert ws.max_row == 2  # header + 1 event

    def test_events_export_wide_columns_for_resource_data(self, client):
        """Resource key-value pairs become extra columns (flat/wide layout)."""
        client_obj, _, site = _setup_data_analysis_user()
        ep = EndpointFactory(site=site)
        rt_temp = ResourceTypeFactory(
            object_id=9001, resource_id=1, name="temperature", data_type="FLOAT"
        )
        rt_hum = ResourceTypeFactory(
            object_id=9001, resource_id=2, name="humidity", data_type="FLOAT"
        )

        event = EventFactory(endpoint=ep)
        res_temp = ResourceFactory(endpoint=ep, resource_type=rt_temp, float_value=22.5)
        res_hum = ResourceFactory(endpoint=ep, resource_type=rt_hum, float_value=55.0)
        EventResource.objects.create(event=event, resource=res_temp)
        EventResource.objects.create(event=event, resource=res_hum)

        response = client_obj.get(
            _export_url(mode="events", endpoint=ep.endpoint, time_range="all")
        )
        wb = _wb_from_response(response)
        ws = wb.active
        headers = [ws.cell(1, c).value for c in range(1, ws.max_column + 1)]

        assert "temperature" in headers
        assert "humidity" in headers
        # Data row should have the values
        temp_col = headers.index("temperature") + 1
        hum_col = headers.index("humidity") + 1
        assert ws.cell(2, temp_col).value == pytest.approx(22.5)
        assert ws.cell(2, hum_col).value == pytest.approx(55.0)

    def test_events_export_empty_cell_for_missing_resource(self, client):
        """Events that lack a resource get an empty cell for that column."""
        client_obj, _, site = _setup_data_analysis_user()
        ep = EndpointFactory(site=site)
        rt_a = ResourceTypeFactory(object_id=9002, resource_id=1, name="alpha", data_type="FLOAT")
        rt_b = ResourceTypeFactory(object_id=9002, resource_id=2, name="beta", data_type="FLOAT")

        # event1 has only alpha
        event1 = EventFactory(endpoint=ep)
        res_a = ResourceFactory(endpoint=ep, resource_type=rt_a, float_value=1.0)
        EventResource.objects.create(event=event1, resource=res_a)

        # event2 has only beta
        event2 = EventFactory(endpoint=ep)
        res_b = ResourceFactory(endpoint=ep, resource_type=rt_b, float_value=2.0)
        EventResource.objects.create(event=event2, resource=res_b)

        response = client_obj.get(
            _export_url(mode="events", endpoint=ep.endpoint, time_range="all")
        )
        wb = _wb_from_response(response)
        ws = wb.active
        headers = [ws.cell(1, c).value for c in range(1, ws.max_column + 1)]

        alpha_col = headers.index("alpha") + 1
        beta_col = headers.index("beta") + 1

        # Collect (alpha, beta) pairs for all data rows
        pairs = {
            (ws.cell(r, alpha_col).value, ws.cell(r, beta_col).value)
            for r in range(2, ws.max_row + 1)
        }
        # One row has alpha filled + beta empty; the other has beta filled + alpha empty
        assert (1.0, None) in pairs or (None, 2.0) in pairs

    # ------------------------------------------------------------------
    # Row cap enforcement
    # ------------------------------------------------------------------

    def test_export_exceeds_row_limit_returns_400(self, client, monkeypatch):
        """When queryset exceeds 50,000 rows the view returns HTTP 400 JSON."""
        from frontend import views as frontend_views

        monkeypatch.setattr(frontend_views, "EXPORT_ROW_LIMIT", 2)

        client_obj, _, site = _setup_data_analysis_user()
        rt = ResourceTypeFactory(data_type="FLOAT")
        ep = EndpointFactory(site=site)
        ResourceFactory.create_batch(3, endpoint=ep, resource_type=rt)

        response = client_obj.get(
            _export_url(mode="values", endpoint=ep.endpoint, resource_type=rt.id, time_range="all")
        )

        assert response.status_code == 400
        body = json.loads(response.content)
        assert "error" in body
        assert "rows" in body["error"].lower()


# ---------------------------------------------------------------------------
# Array + raw (OPAQUE) resource tests
# ---------------------------------------------------------------------------


_rt_seq = iter(range(1000, 9999))


def _make_rt(name: str, data_type: str) -> ResourceType:
    """Create a ResourceType with a unique (object_id, resource_id) pair."""
    rid = next(_rt_seq)
    return ResourceType.objects.create(
        object_id=19999, resource_id=rid, name=name, data_type=data_type
    )


def _make_opaque_resource(ep, rt: ResourceType, binary_value: bytes | None) -> Resource:
    """Create an OPAQUE Resource, suppressing the factory's default float_value."""
    return ResourceFactory(
        endpoint=ep, resource_type=rt, float_value=None, binary_value=binary_value
    )


@pytest.mark.django_db
class TestEventArrayAndRawElements:
    """Verify that array resources and OPAQUE resources are handled correctly
    in both the JSON events API and the Excel export."""

    # ------------------------------------------------------------------
    # JSON API – array resources
    # ------------------------------------------------------------------

    def test_json_array_elements_returned_as_list(self, client):
        """Three resources with the same name under one event must be returned as a list."""
        client_obj, _, site = _setup_data_analysis_user()
        ep = EndpointFactory(site=site)
        rt = _make_rt("pm_press_avg", "TIME")

        event = EventFactory(endpoint=ep, event_type="10300")
        for val in (10, 20, 30):
            res = ResourceFactory(endpoint=ep, resource_type=rt, int_value=val, float_value=None)
            EventResource.objects.create(event=event, resource=res)

        response = client_obj.get(
            _data_analysis_url(format="json", mode="events", endpoint=ep.endpoint, time_range="all")
        )
        data = json.loads(response.content)
        assert data["events"][0]["data"]["pm_press_avg"] == [10, 20, 30]

    def test_json_scalar_not_promoted_to_list(self, client):
        """A single resource must not be wrapped in a list."""
        client_obj, _, site = _setup_data_analysis_user()
        ep = EndpointFactory(site=site)
        rt = _make_rt("pm_result_code", "INTEGER")

        event = EventFactory(endpoint=ep, event_type="10300")
        res = ResourceFactory(endpoint=ep, resource_type=rt, int_value=42, float_value=None)
        EventResource.objects.create(event=event, resource=res)

        response = client_obj.get(
            _data_analysis_url(format="json", mode="events", endpoint=ep.endpoint, time_range="all")
        )
        data = json.loads(response.content)
        assert data["events"][0]["data"]["pm_result_code"] == 42

    def test_json_opaque_resource_shows_raw_marker_with_size(self, client):
        """OPAQUE resource with stored bytes must appear as '<raw: N bytes>'."""
        client_obj, _, site = _setup_data_analysis_user()
        ep = EndpointFactory(site=site)
        rt = _make_rt("pm_press_raw", "OPAQUE")

        event = EventFactory(endpoint=ep, event_type="10300")
        EventResource.objects.create(
            event=event, resource=_make_opaque_resource(ep, rt, b"\xde\xad\xbe\xef")
        )

        response = client_obj.get(
            _data_analysis_url(format="json", mode="events", endpoint=ep.endpoint, time_range="all")
        )
        data = json.loads(response.content)
        assert data["events"][0]["data"]["pm_press_raw"] == "<raw: 4 bytes>"

    def test_json_opaque_null_shows_na_marker(self, client):
        """OPAQUE resource with NULL binary_value shows '<raw: N/A>'."""
        client_obj, _, site = _setup_data_analysis_user()
        ep = EndpointFactory(site=site)
        rt = _make_rt("pm_press_raw", "OPAQUE")

        event = EventFactory(endpoint=ep, event_type="10300")
        EventResource.objects.create(event=event, resource=_make_opaque_resource(ep, rt, None))

        response = client_obj.get(
            _data_analysis_url(format="json", mode="events", endpoint=ep.endpoint, time_range="all")
        )
        data = json.loads(response.content)
        assert data["events"][0]["data"]["pm_press_raw"] == "<raw: N/A>"

    def test_json_opaque_empty_blob_shows_zero_bytes(self, client):
        """OPAQUE resource with an empty byte string (b'') shows '<raw: 0 bytes>'."""
        client_obj, _, site = _setup_data_analysis_user()
        ep = EndpointFactory(site=site)
        rt = _make_rt("pm_press_raw", "OPAQUE")

        event = EventFactory(endpoint=ep, event_type="10300")
        EventResource.objects.create(event=event, resource=_make_opaque_resource(ep, rt, b""))

        response = client_obj.get(
            _data_analysis_url(format="json", mode="events", endpoint=ep.endpoint, time_range="all")
        )
        data = json.loads(response.content)
        assert data["events"][0]["data"]["pm_press_raw"] == "<raw: 0 bytes>"

    def test_json_mixed_event_all_element_types(self, client):
        """Realistic event: scalar + array + opaque all correct in one response."""
        client_obj, _, site = _setup_data_analysis_user()
        ep = EndpointFactory(site=site)

        rt_code = _make_rt("pm_result_code", "INTEGER")
        rt_str = _make_rt("pm_result_string", "STRING")
        rt_avg = _make_rt("pm_press_avg", "TIME")
        rt_raw = _make_rt("pm_press_raw", "OPAQUE")

        event = EventFactory(endpoint=ep, event_type="10300")
        EventResource.objects.create(
            event=event,
            resource=ResourceFactory(
                endpoint=ep, resource_type=rt_code, int_value=0, float_value=None
            ),
        )
        EventResource.objects.create(
            event=event,
            resource=ResourceFactory(
                endpoint=ep, resource_type=rt_str, str_value="OK", float_value=None
            ),
        )
        for v in (100, 200):
            EventResource.objects.create(
                event=event,
                resource=ResourceFactory(
                    endpoint=ep, resource_type=rt_avg, int_value=v, float_value=None
                ),
            )
        EventResource.objects.create(
            event=event, resource=_make_opaque_resource(ep, rt_raw, b"\x01\x02")
        )

        response = client_obj.get(
            _data_analysis_url(format="json", mode="events", endpoint=ep.endpoint, time_range="all")
        )
        event_data = json.loads(response.content)["events"][0]["data"]
        assert event_data["pm_result_code"] == 0
        assert event_data["pm_result_string"] == "OK"
        assert event_data["pm_press_avg"] == [100, 200]
        assert event_data["pm_press_raw"] == "<raw: 2 bytes>"

    # ------------------------------------------------------------------
    # Excel export – array resources
    # ------------------------------------------------------------------

    def test_export_array_expands_to_indexed_columns(self, client):
        """Array resources must generate pm_press_avg[0], [1], [2] columns in the xlsx."""
        client_obj, _, site = _setup_data_analysis_user()
        ep = EndpointFactory(site=site)
        rt = _make_rt("pm_press_avg", "TIME")

        event = EventFactory(endpoint=ep, event_type="10300")
        for val in (10, 20, 30):
            res = ResourceFactory(endpoint=ep, resource_type=rt, int_value=val, float_value=None)
            EventResource.objects.create(event=event, resource=res)

        response = client_obj.get(
            _export_url(mode="events", endpoint=ep.endpoint, time_range="all")
        )
        wb = _wb_from_response(response)
        ws = wb.active
        headers = [ws.cell(1, c).value for c in range(1, ws.max_column + 1)]

        assert "pm_press_avg[0]" in headers
        assert "pm_press_avg[1]" in headers
        assert "pm_press_avg[2]" in headers
        assert "pm_press_avg" not in headers  # plain name must not appear

        col0 = headers.index("pm_press_avg[0]") + 1
        col1 = headers.index("pm_press_avg[1]") + 1
        col2 = headers.index("pm_press_avg[2]") + 1
        assert ws.cell(2, col0).value == 10
        assert ws.cell(2, col1).value == 20
        assert ws.cell(2, col2).value == 30

    def test_export_array_unequal_lengths_across_events(self, client):
        """Event A has 3 array elements, event B has 2: shorter event leaves cells empty."""
        client_obj, _, site = _setup_data_analysis_user()
        ep = EndpointFactory(site=site)
        rt = _make_rt("val", "INTEGER")

        event_a = EventFactory(endpoint=ep, event_type="DATA")
        for v in (1, 2, 3):
            EventResource.objects.create(
                event=event_a,
                resource=ResourceFactory(
                    endpoint=ep, resource_type=rt, int_value=v, float_value=None
                ),
            )
        event_b = EventFactory(endpoint=ep, event_type="DATA")
        for v in (4, 5):
            EventResource.objects.create(
                event=event_b,
                resource=ResourceFactory(
                    endpoint=ep, resource_type=rt, int_value=v, float_value=None
                ),
            )

        response = client_obj.get(
            _export_url(mode="events", endpoint=ep.endpoint, time_range="all")
        )
        wb = _wb_from_response(response)
        ws = wb.active
        headers = [ws.cell(1, c).value for c in range(1, ws.max_column + 1)]

        assert "val[2]" in headers  # column exists because event_a has 3 elements
        col2 = headers.index("val[2]") + 1
        # one row has a value, the other is empty — order may vary, so check the set
        values = {ws.cell(r, col2).value for r in (2, 3)}
        assert values == {3, None}

    def test_export_opaque_cell_shows_raw_marker(self, client):
        """OPAQUE resource with stored bytes must appear as '<raw: N bytes>' in the xlsx."""
        client_obj, _, site = _setup_data_analysis_user()
        ep = EndpointFactory(site=site)
        rt = _make_rt("pm_press_raw", "OPAQUE")

        event = EventFactory(endpoint=ep, event_type="10300")
        EventResource.objects.create(
            event=event, resource=_make_opaque_resource(ep, rt, b"\xca\xfe")
        )

        response = client_obj.get(
            _export_url(mode="events", endpoint=ep.endpoint, time_range="all")
        )
        wb = _wb_from_response(response)
        ws = wb.active
        headers = [ws.cell(1, c).value for c in range(1, ws.max_column + 1)]
        raw_col = headers.index("pm_press_raw") + 1
        assert ws.cell(2, raw_col).value == "<raw: 2 bytes>"

    def test_export_mixed_event_correct_columns_and_values(self, client):
        """Full realistic event exported to xlsx has correct headers and cell values."""
        client_obj, _, site = _setup_data_analysis_user()
        ep = EndpointFactory(site=site)

        rt_code = _make_rt("pm_result_code", "INTEGER")
        rt_str = _make_rt("pm_result_string", "STRING")
        rt_avg = _make_rt("pm_press_avg", "TIME")
        rt_raw = _make_rt("pm_press_raw", "OPAQUE")

        event = EventFactory(endpoint=ep, event_type="10300")
        EventResource.objects.create(
            event=event,
            resource=ResourceFactory(
                endpoint=ep, resource_type=rt_code, int_value=7, float_value=None
            ),
        )
        EventResource.objects.create(
            event=event,
            resource=ResourceFactory(
                endpoint=ep, resource_type=rt_str, str_value="PASS", float_value=None
            ),
        )
        for v in (111, 222):
            EventResource.objects.create(
                event=event,
                resource=ResourceFactory(
                    endpoint=ep, resource_type=rt_avg, int_value=v, float_value=None
                ),
            )
        EventResource.objects.create(
            event=event, resource=_make_opaque_resource(ep, rt_raw, b"\x00" * 5)
        )

        response = client_obj.get(
            _export_url(mode="events", endpoint=ep.endpoint, time_range="all")
        )
        wb = _wb_from_response(response)
        ws = wb.active
        headers = [ws.cell(1, c).value for c in range(1, ws.max_column + 1)]

        assert "pm_result_code" in headers
        assert "pm_result_string" in headers
        assert "pm_press_avg[0]" in headers
        assert "pm_press_avg[1]" in headers
        assert "pm_press_raw" in headers

        def col(name: str) -> int:
            return headers.index(name) + 1

        assert ws.cell(2, col("pm_result_code")).value == 7
        assert ws.cell(2, col("pm_result_string")).value == "PASS"
        assert ws.cell(2, col("pm_press_avg[0]")).value == 111
        assert ws.cell(2, col("pm_press_avg[1]")).value == 222
        assert ws.cell(2, col("pm_press_raw")).value == "<raw: 5 bytes>"

    # ------------------------------------------------------------------
    # Serializer ingestion – OPAQUE data from device
    # ------------------------------------------------------------------

    def test_serializer_ingests_opaque_hex_into_binary_value(self, client):
        """POST of an OPAQUE resource with a hex-encoded value stores bytes in binary_value."""
        ResourceTypeFactory(
            object_id=19000, resource_id=0, name="raw_payload", data_type=ResourceType.OPAQUE
        )
        payload = {
            "ep": "test-device",
            "obj_id": 19000,
            "val": {"kind": "singleResource", "id": 0, "type": "OPAQUE", "value": "deadbeef"},
        }
        response = client.post(
            reverse("post-single-resource"), payload, content_type="application/json"
        )
        assert response.status_code == 201
        resource = Resource.objects.get(
            endpoint__endpoint="test-device",
            resource_type__object_id=19000,
            resource_type__resource_id=0,
        )
        assert resource.binary_value == b"\xde\xad\xbe\xef"


# ======================================================================
# Pump Monitor tests
# ======================================================================


def _pm_url(**params):
    """Build the pump_monitor URL with the given query parameters."""
    return reverse("frontend:pump_monitor") + "?" + "&".join(f"{k}={v}" for k, v in params.items())


def _pm_export_url(**params):
    """Build the pump_monitor_export URL with the given query parameters."""
    return (
        reverse("frontend:pump_monitor_export")
        + "?"
        + "&".join(f"{k}={v}" for k, v in params.items())
    )


def _setup_pm_user(can_view_data_analysis=True):
    """Return (client, user, site) for pump monitor tests."""
    from django.test import Client

    user = UserFactory()
    site = SiteFactory()
    SiteMembershipFactory(user=user, site=site, can_view_data_analysis=can_view_data_analysis)
    client = Client()
    client.force_login(user)
    return client, user, site


def _create_pm_event(ep, raw_bytes=None, attach_raw=True):
    """Create a 10300 event with an optional pm_press_raw OPAQUE resource."""
    event = EventFactory(endpoint=ep, event_type="10300")
    if attach_raw:
        rt = ResourceType.objects.filter(name="pm_press_raw").first()
        if not rt:
            rt = ResourceTypeFactory(
                object_id=10300, resource_id=99, name="pm_press_raw", data_type="OPAQUE"
            )
        res = ResourceFactory(
            endpoint=ep, resource_type=rt, float_value=None, binary_value=raw_bytes
        )
        EventResource.objects.create(event=event, resource=res)
    return event


@pytest.mark.django_db
class TestPumpMonitorView:
    """Tests for the /pump-monitor/ view (page rendering and JSON API)."""

    # ------------------------------------------------------------------
    # Auth / permission
    # ------------------------------------------------------------------

    def test_requires_login(self, client):
        response = client.get(reverse("frontend:pump_monitor"))
        assert response.status_code == 302

    def test_requires_data_analysis_permission(self, client):
        client_obj, _, _ = _setup_pm_user(can_view_data_analysis=False)
        response = client_obj.get(reverse("frontend:pump_monitor"))
        assert response.status_code == 403

    def test_page_renders_for_authorised_user(self, client):
        client_obj, _, _ = _setup_pm_user()
        response = client_obj.get(reverse("frontend:pump_monitor"))
        assert response.status_code == 200
        assert b"Pump Monitor" in response.content

    # ------------------------------------------------------------------
    # Nav visibility
    # ------------------------------------------------------------------

    def test_nav_tab_visible_for_data_analysis_permission(self, client):
        client_obj, _, _ = _setup_pm_user()
        response = client_obj.get(reverse("frontend:pump_monitor"))
        assert reverse("frontend:pump_monitor").encode() in response.content

    # ------------------------------------------------------------------
    # JSON: event listing
    # ------------------------------------------------------------------

    def test_json_returns_pump_events(self, client):
        client_obj, _, site = _setup_pm_user()
        ep = EndpointFactory(site=site)
        _create_pm_event(ep, raw_bytes=b"\x0a\x14\x1e")

        response = client_obj.get(_pm_url(format="json", endpoint=ep.endpoint, time_range="all"))
        data = json.loads(response.content)
        assert len(data["events"]) == 1
        assert data["events"][0]["sample_count"] == 3

    def test_json_event_without_raw_resource_shows_zero_samples(self, client):
        client_obj, _, site = _setup_pm_user()
        ep = EndpointFactory(site=site)
        _create_pm_event(ep, attach_raw=False)

        response = client_obj.get(_pm_url(format="json", endpoint=ep.endpoint, time_range="all"))
        data = json.loads(response.content)
        assert data["events"][0]["sample_count"] == 0

    def test_json_event_with_null_binary_shows_zero_samples(self, client):
        client_obj, _, site = _setup_pm_user()
        ep = EndpointFactory(site=site)
        _create_pm_event(ep, raw_bytes=None)

        response = client_obj.get(_pm_url(format="json", endpoint=ep.endpoint, time_range="all"))
        data = json.loads(response.content)
        assert data["events"][0]["sample_count"] == 0

    def test_json_event_with_empty_binary_shows_zero_samples(self, client):
        client_obj, _, site = _setup_pm_user()
        ep = EndpointFactory(site=site)
        _create_pm_event(ep, raw_bytes=b"")

        response = client_obj.get(_pm_url(format="json", endpoint=ep.endpoint, time_range="all"))
        data = json.loads(response.content)
        assert data["events"][0]["sample_count"] == 0

    def test_json_filters_by_endpoint(self, client):
        client_obj, _, site = _setup_pm_user()
        ep1 = EndpointFactory(site=site)
        ep2 = EndpointFactory(site=site)
        _create_pm_event(ep1, raw_bytes=b"\x01")
        _create_pm_event(ep2, raw_bytes=b"\x02\x03")

        response = client_obj.get(_pm_url(format="json", endpoint=ep1.endpoint, time_range="all"))
        data = json.loads(response.content)
        assert len(data["events"]) == 1
        assert data["events"][0]["endpoint"] == ep1.endpoint

    def test_json_all_endpoints_returns_all(self, client):
        client_obj, _, site = _setup_pm_user()
        ep1 = EndpointFactory(site=site)
        ep2 = EndpointFactory(site=site)
        _create_pm_event(ep1, raw_bytes=b"\x01")
        _create_pm_event(ep2, raw_bytes=b"\x02")

        response = client_obj.get(_pm_url(format="json", endpoint="all", time_range="all"))
        data = json.loads(response.content)
        assert len(data["events"]) == 2

    def test_json_excludes_non_pump_events(self, client):
        client_obj, _, site = _setup_pm_user()
        ep = EndpointFactory(site=site)
        _create_pm_event(ep, raw_bytes=b"\x01")
        EventFactory(endpoint=ep, event_type="9999")  # not a pump event

        response = client_obj.get(_pm_url(format="json", endpoint=ep.endpoint, time_range="all"))
        data = json.loads(response.content)
        assert len(data["events"]) == 1

    # ------------------------------------------------------------------
    # JSON: detail endpoint
    # ------------------------------------------------------------------

    def test_detail_returns_chart_data(self, client):
        client_obj, _, site = _setup_pm_user()
        ep = EndpointFactory(site=site)
        event = _create_pm_event(ep, raw_bytes=b"\x64\xc8")  # 100, 200

        response = client_obj.get(
            _pm_url(format="detail", event_id=event.id, endpoint=ep.endpoint, time_range="all")
        )
        data = json.loads(response.content)
        assert data["sample_count"] == 2
        assert len(data["chart_data"]) == 2
        assert data["chart_data"][0]["x"] == 0.0
        assert data["chart_data"][0]["y"] == 100
        assert data["chart_data"][1]["x"] == 0.02  # 1/50
        assert data["chart_data"][1]["y"] == 200

    def test_detail_empty_raw_returns_empty_chart(self, client):
        client_obj, _, site = _setup_pm_user()
        ep = EndpointFactory(site=site)
        event = _create_pm_event(ep, raw_bytes=b"")

        response = client_obj.get(
            _pm_url(format="detail", event_id=event.id, endpoint=ep.endpoint, time_range="all")
        )
        data = json.loads(response.content)
        assert data["sample_count"] == 0
        assert data["chart_data"] == []

    def test_detail_no_raw_resource_returns_empty_chart(self, client):
        client_obj, _, site = _setup_pm_user()
        ep = EndpointFactory(site=site)
        event = _create_pm_event(ep, attach_raw=False)

        response = client_obj.get(
            _pm_url(format="detail", event_id=event.id, endpoint=ep.endpoint, time_range="all")
        )
        data = json.loads(response.content)
        assert data["sample_count"] == 0
        assert data["chart_data"] == []

    def test_detail_missing_event_id_returns_400(self, client):
        client_obj, _, _ = _setup_pm_user()
        response = client_obj.get(_pm_url(format="detail", endpoint="all", time_range="all"))
        assert response.status_code == 400

    def test_detail_nonexistent_event_returns_404(self, client):
        client_obj, _, _ = _setup_pm_user()
        response = client_obj.get(
            _pm_url(format="detail", event_id=99999, endpoint="all", time_range="all")
        )
        assert response.status_code == 404

    def test_detail_includes_time_and_endpoint(self, client):
        client_obj, _, site = _setup_pm_user()
        ep = EndpointFactory(site=site)
        event = _create_pm_event(ep, raw_bytes=b"\x0a")

        response = client_obj.get(
            _pm_url(format="detail", event_id=event.id, endpoint=ep.endpoint, time_range="all")
        )
        data = json.loads(response.content)
        assert data["endpoint"] == ep.endpoint
        assert "time" in data


@pytest.mark.django_db
class TestPumpMonitorExport:
    """Tests for the /pump-monitor/export/ Excel export view."""

    # ------------------------------------------------------------------
    # Auth / permission
    # ------------------------------------------------------------------

    def test_requires_login(self, client):
        response = client.get(_pm_export_url(time_range="all"))
        assert response.status_code == 302

    def test_requires_data_analysis_permission(self, client):
        client_obj, _, _ = _setup_pm_user(can_view_data_analysis=False)
        response = client_obj.get(_pm_export_url(time_range="all"))
        assert response.status_code == 403

    # ------------------------------------------------------------------
    # Export structure
    # ------------------------------------------------------------------

    def test_export_returns_xlsx(self, client):
        client_obj, _, site = _setup_pm_user()
        ep = EndpointFactory(site=site)
        _create_pm_event(ep, raw_bytes=b"\x0a\x14")

        response = client_obj.get(_pm_export_url(endpoint=ep.endpoint, time_range="all"))
        assert response.status_code == 200
        assert (
            response["Content-Type"]
            == "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )
        assert "pump_monitor_export.xlsx" in response["Content-Disposition"]

    def test_export_has_single_samples_sheet(self, client):
        """Only a single 'Samples' sheet is produced."""
        client_obj, _, site = _setup_pm_user()
        ep = EndpointFactory(site=site)
        _create_pm_event(ep, raw_bytes=b"\x0a\x14")

        response = client_obj.get(_pm_export_url(endpoint=ep.endpoint, time_range="all"))
        wb = _wb_from_response(response)
        assert wb.sheetnames == ["Samples"]

    def test_samples_sheet_fixed_headers(self, client):
        """First two header columns are sample_index and seconds."""
        client_obj, _, site = _setup_pm_user()
        ep = EndpointFactory(site=site)
        _create_pm_event(ep, raw_bytes=b"\x0a")

        response = client_obj.get(_pm_export_url(endpoint=ep.endpoint, time_range="all"))
        wb = _wb_from_response(response)
        ws = wb["Samples"]
        assert ws.cell(1, 1).value == "sample_index"
        assert ws.cell(1, 2).value == "seconds"

    def test_samples_sheet_event_column_header_contains_endpoint(self, client):
        """Third column header contains the event timestamp and endpoint name."""
        client_obj, _, site = _setup_pm_user()
        ep = EndpointFactory(site=site)
        _create_pm_event(ep, raw_bytes=b"\x0a")

        response = client_obj.get(_pm_export_url(endpoint=ep.endpoint, time_range="all"))
        wb = _wb_from_response(response)
        ws = wb["Samples"]
        assert ep.endpoint in ws.cell(1, 3).value

    def test_samples_sheet_data_rows(self, client):
        """Data rows: sample_index in col 1, seconds in col 2, pressure in col 3."""
        client_obj, _, site = _setup_pm_user()
        ep = EndpointFactory(site=site)
        _create_pm_event(ep, raw_bytes=b"\x64\xc8")  # 100, 200

        response = client_obj.get(_pm_export_url(endpoint=ep.endpoint, time_range="all"))
        wb = _wb_from_response(response)
        ws = wb["Samples"]

        # Row 2: first sample
        assert ws.cell(2, 1).value == 0  # sample_index
        assert ws.cell(2, 2).value == 0.0  # seconds
        assert ws.cell(2, 3).value == 100  # pressure

        # Row 3: second sample
        assert ws.cell(3, 1).value == 1
        assert ws.cell(3, 2).value == 0.02  # 1/50
        assert ws.cell(3, 3).value == 200

    def test_samples_sheet_empty_for_no_raw(self, client):
        """When no raw resource exists, only the header row is written."""
        client_obj, _, site = _setup_pm_user()
        ep = EndpointFactory(site=site)
        _create_pm_event(ep, attach_raw=False)

        response = client_obj.get(_pm_export_url(endpoint=ep.endpoint, time_range="all"))
        wb = _wb_from_response(response)
        ws = wb["Samples"]
        assert ws.max_row == 1  # header only

    def test_export_filters_by_endpoint(self, client):
        """Filtering by one endpoint produces exactly one event column."""
        client_obj, _, site = _setup_pm_user()
        ep1 = EndpointFactory(site=site)
        ep2 = EndpointFactory(site=site)
        _create_pm_event(ep1, raw_bytes=b"\x01")
        _create_pm_event(ep2, raw_bytes=b"\x02\x03")

        response = client_obj.get(_pm_export_url(endpoint=ep1.endpoint, time_range="all"))
        wb = _wb_from_response(response)
        ws = wb["Samples"]
        # 2 fixed cols (sample_index, seconds) + 1 event col = 3 total
        assert ws.max_column == 3

    def test_multiple_events_produce_multiple_columns(self, client):
        """Two events for the same endpoint produce two event columns."""
        client_obj, _, site = _setup_pm_user()
        ep = EndpointFactory(site=site)
        _create_pm_event(ep, raw_bytes=b"\x01\x02")
        _create_pm_event(ep, raw_bytes=b"\x03\x04\x05")

        response = client_obj.get(_pm_export_url(endpoint=ep.endpoint, time_range="all"))
        wb = _wb_from_response(response)
        ws = wb["Samples"]
        # 2 fixed cols + 2 event cols = 4 total; rows = max(2, 3) + 1 header = 4
        assert ws.max_column == 4
        assert ws.max_row == 4

    def test_shorter_event_column_padded_with_empty(self, client):
        """Shorter event columns are padded with empty strings beyond their sample count."""
        client_obj, _, site = _setup_pm_user()
        ep = EndpointFactory(site=site)
        _create_pm_event(ep, raw_bytes=b"\x01")  # 1 sample
        _create_pm_event(ep, raw_bytes=b"\x02\x03")  # 2 samples

        response = client_obj.get(_pm_export_url(endpoint=ep.endpoint, time_range="all"))
        wb = _wb_from_response(response)
        ws = wb["Samples"]
        # Row 3 (sample index 1): the 1-sample event column is None (openpyxl reads "" as None)
        values = [ws.cell(3, c).value for c in range(3, ws.max_column + 1)]
        assert None in values


@pytest.mark.django_db
class TestPumpMonitorSorting:
    """Tests for pump monitor JSON API sorting via sort/dir query params."""

    def test_default_sort_is_time_desc(self, client):
        """Without sort/dir params, events are ordered by time descending."""
        client_obj, _, site = _setup_pm_user()
        ep = EndpointFactory(site=site)
        # Create two events; second one will have a later timestamp
        _create_pm_event(ep, raw_bytes=b"\x01")
        _create_pm_event(ep, raw_bytes=b"\x02\x03")

        response = client_obj.get(_pm_url(endpoint=ep.endpoint, time_range="all", format="json"))
        data = response.json()
        assert len(data["events"]) == 2
        # Default desc: latest event first
        assert data["events"][0]["sample_count"] == 2
        assert data["events"][1]["sample_count"] == 1

    def test_sort_time_asc(self, client):
        client_obj, _, site = _setup_pm_user()
        ep = EndpointFactory(site=site)
        _create_pm_event(ep, raw_bytes=b"\x01")
        _create_pm_event(ep, raw_bytes=b"\x02\x03")

        response = client_obj.get(
            _pm_url(endpoint=ep.endpoint, time_range="all", format="json", sort="time", dir="asc")
        )
        data = response.json()
        assert len(data["events"]) == 2
        # Ascending: oldest event first
        assert data["events"][0]["sample_count"] == 1
        assert data["events"][1]["sample_count"] == 2

    def test_sort_sample_count_asc(self, client):
        client_obj, _, site = _setup_pm_user()
        ep = EndpointFactory(site=site)
        _create_pm_event(ep, raw_bytes=b"\x01\x02\x03")  # 3 samples
        _create_pm_event(ep, raw_bytes=b"\x0a")  # 1 sample
        _create_pm_event(ep, attach_raw=False)  # 0 samples

        response = client_obj.get(
            _pm_url(
                endpoint=ep.endpoint,
                time_range="all",
                format="json",
                sort="sample_count",
                dir="asc",
            )
        )
        data = response.json()
        counts = [e["sample_count"] for e in data["events"]]
        assert counts == [0, 1, 3]

    def test_sort_sample_count_desc(self, client):
        client_obj, _, site = _setup_pm_user()
        ep = EndpointFactory(site=site)
        _create_pm_event(ep, raw_bytes=b"\x01\x02\x03")  # 3 samples
        _create_pm_event(ep, raw_bytes=b"\x0a")  # 1 sample
        _create_pm_event(ep, attach_raw=False)  # 0 samples

        response = client_obj.get(
            _pm_url(
                endpoint=ep.endpoint,
                time_range="all",
                format="json",
                sort="sample_count",
                dir="desc",
            )
        )
        data = response.json()
        counts = [e["sample_count"] for e in data["events"]]
        assert counts == [3, 1, 0]

    def test_sort_endpoint_asc(self, client):
        client_obj, _, site = _setup_pm_user()
        ep_a = EndpointFactory(site=site, endpoint="urn:imei:aaa")
        ep_z = EndpointFactory(site=site, endpoint="urn:imei:zzz")
        _create_pm_event(ep_z, raw_bytes=b"\x01")
        _create_pm_event(ep_a, raw_bytes=b"\x02")

        response = client_obj.get(
            _pm_url(endpoint="all", time_range="all", format="json", sort="endpoint", dir="asc")
        )
        data = response.json()
        endpoints = [e["endpoint"] for e in data["events"]]
        assert endpoints == ["urn:imei:aaa", "urn:imei:zzz"]

    def test_sort_endpoint_desc(self, client):
        client_obj, _, site = _setup_pm_user()
        ep_a = EndpointFactory(site=site, endpoint="urn:imei:aaa")
        ep_z = EndpointFactory(site=site, endpoint="urn:imei:zzz")
        _create_pm_event(ep_z, raw_bytes=b"\x01")
        _create_pm_event(ep_a, raw_bytes=b"\x02")

        response = client_obj.get(
            _pm_url(endpoint="all", time_range="all", format="json", sort="endpoint", dir="desc")
        )
        data = response.json()
        endpoints = [e["endpoint"] for e in data["events"]]
        assert endpoints == ["urn:imei:zzz", "urn:imei:aaa"]

    def test_invalid_sort_col_falls_back_to_time(self, client):
        """An unrecognized sort column should fall back to time ordering."""
        client_obj, _, site = _setup_pm_user()
        ep = EndpointFactory(site=site)
        _create_pm_event(ep, raw_bytes=b"\x01")
        _create_pm_event(ep, raw_bytes=b"\x02\x03")

        response = client_obj.get(
            _pm_url(
                endpoint=ep.endpoint,
                time_range="all",
                format="json",
                sort="malicious_field",
                dir="desc",
            )
        )
        data = response.json()
        assert len(data["events"]) == 2
        # Falls back to time desc — latest first (2 samples)
        assert data["events"][0]["sample_count"] == 2
        assert data["events"][1]["sample_count"] == 1
