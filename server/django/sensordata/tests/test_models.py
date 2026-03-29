#
# Copyright (c) 2024 Jonas Remmert
#
# SPDX-License-Identifier: Apache-2.0
#

import importlib

import pytest
from django.apps import apps as django_apps
from django.contrib.auth.models import Permission
from django.db import IntegrityError

from sensordata.factories import (
    EndpointFactory,
    ResourceFactory,
    ResourceTypeFactory,
    SiteFactory,
    SiteMembershipFactory,
    UserFactory,
)
from sensordata.models import ResourceType, Site, SiteMembership

backfill_module = importlib.import_module("sensordata.migrations.0002_squash")
DEFAULT_SITE_NAME = backfill_module.DEFAULT_SITE_NAME
_build_membership_fields = backfill_module.build_membership_fields
backfill_legacy_site_memberships = backfill_module.backfill_legacy_site_memberships


@pytest.mark.django_db
class TestModels:
    def test_endpoint_str(self):
        endpoint = EndpointFactory(endpoint="urn:imei:12345")
        assert str(endpoint) == "urn:imei:12345"

    def test_resource_type_str(self):
        rt = ResourceTypeFactory(object_id=3303, resource_id=5700, name="Temp")
        assert str(rt) == "3303/5700 - Temp"

    def test_resource_creation(self):
        resource = ResourceFactory(float_value=25.5)
        assert resource.get_value() == 25.5
        assert resource.timestamp_created is not None

    def test_resource_type_unique_together(self):
        ResourceTypeFactory(object_id=3303, resource_id=5700)
        with pytest.raises(IntegrityError):
            ResourceType.objects.create(
                object_id=3303, resource_id=5700, name="Duplicate", data_type=ResourceType.FLOAT
            )


@pytest.mark.django_db
class TestSiteModel:
    def test_site_creation(self):
        site = SiteFactory(name="Test Site")
        assert str(site) == "Test Site"
        assert site.is_active is True

    def test_site_ordering(self):
        SiteFactory(name="Charlie Site")
        SiteFactory(name="Alpha Site")
        SiteFactory(name="Bravo Site")

        sites = list(Site.objects.all())
        assert sites[0].name == "Alpha Site"
        assert sites[1].name == "Bravo Site"
        assert sites[2].name == "Charlie Site"


@pytest.mark.django_db
class TestSiteMembershipModel:
    def test_site_membership_creation(self):
        user = UserFactory()
        site = SiteFactory()
        membership = SiteMembershipFactory(user=user, site=site, role=SiteMembership.Role.USER)

        assert membership.user == user
        assert membership.site == site
        assert membership.role == SiteMembership.Role.USER
        assert membership.is_admin() is False

    def test_site_membership_admin_role(self):
        user = UserFactory()
        site = SiteFactory()
        membership = SiteMembershipFactory(user=user, site=site, role=SiteMembership.Role.ADMIN)

        assert membership.is_admin() is True

    def test_site_membership_global_admin(self):
        user = UserFactory()
        user.is_superuser = True
        user.save()
        site = SiteFactory()
        membership = SiteMembershipFactory(user=user, site=site)

        assert membership.is_global_admin() is True

    def test_site_membership_unique_together(self):
        user = UserFactory()
        site = SiteFactory()
        SiteMembershipFactory(user=user, site=site)

        with pytest.raises(IntegrityError):
            SiteMembership.objects.create(user=user, site=site, role=SiteMembership.Role.USER)

    def test_site_membership_permissions_defaults(self):
        membership = SiteMembershipFactory()

        assert membership.can_view_overview is True
        assert membership.can_view_firmware is False
        assert membership.can_view_data_analysis is True
        assert membership.can_manage_firmware is False
        assert membership.can_perform_operations is False
        assert membership.can_manage_devices is False

    def test_apply_role_defaults_for_admin(self):
        membership = SiteMembership(
            user=UserFactory(),
            site=SiteFactory(),
            role=SiteMembership.Role.ADMIN,
        )

        membership.apply_role_defaults()

        assert membership.can_view_overview is True
        assert membership.can_view_firmware is True
        assert membership.can_view_data_analysis is True
        assert membership.can_manage_firmware is True
        assert membership.can_perform_operations is True
        assert membership.can_manage_devices is False

    def test_apply_role_defaults_for_user(self):
        membership = SiteMembership(
            user=UserFactory(),
            site=SiteFactory(),
            role=SiteMembership.Role.USER,
            can_view_firmware=True,
            can_manage_firmware=True,
            can_perform_operations=True,
            can_manage_devices=True,
        )

        membership.apply_role_defaults()

        assert membership.can_view_overview is True
        assert membership.can_view_firmware is False
        assert membership.can_view_data_analysis is True
        assert membership.can_manage_firmware is False
        assert membership.can_perform_operations is False
        assert membership.can_manage_devices is False

    def test_site_membership_str(self):
        user = UserFactory(username="testuser")
        site = SiteFactory(name="Test Site")
        membership = SiteMembershipFactory(user=user, site=site, role=SiteMembership.Role.ADMIN)

        assert str(membership) == "testuser - Test Site (ADMIN)"


@pytest.mark.django_db
class TestEndpointSiteAssignment:
    def test_endpoint_site_assignment(self):
        site = SiteFactory()
        endpoint = EndpointFactory(site=site)

        assert endpoint.site == site
        assert site.endpoints.count() == 1
        assert site.endpoints.first() == endpoint

    def test_endpoint_without_site(self):
        endpoint = EndpointFactory(site=None)

        assert endpoint.site is None


@pytest.mark.django_db
class TestLegacyMembershipBackfill:
    def test_build_membership_fields_returns_none_without_legacy_permissions(self):
        assert _build_membership_fields(set()) is None

    def test_build_membership_fields_maps_admin_capabilities(self):
        fields = _build_membership_fields(
            {"view_endpoint", "change_firmware", "add_endpointoperation"}
        )

        assert fields == {
            "role": "ADMIN",
            "can_view_overview": True,
            "can_view_firmware": True,
            "can_view_data_analysis": True,
            "can_manage_firmware": True,
            "can_perform_operations": True,
            "can_manage_devices": False,
        }

    def test_backfill_assigns_to_only_active_site(self):
        site = SiteFactory(name="Only Active Site", is_active=True)
        user = UserFactory(is_superuser=False)
        permission = Permission.objects.get(codename="view_endpoint")
        user.user_permissions.add(permission)

        backfill_legacy_site_memberships(django_apps, None)

        membership = SiteMembership.objects.get(user=user)
        assert membership.site == site
        assert membership.role == SiteMembership.Role.USER
        assert membership.can_view_overview is True
        assert membership.can_view_data_analysis is True
        assert membership.can_view_firmware is False

    def test_backfill_uses_default_site_when_multiple_active_sites(self):
        SiteFactory(name="Alpha Site", is_active=True)
        SiteFactory(name="Bravo Site", is_active=True)
        user = UserFactory(is_superuser=False)
        permission = Permission.objects.get(codename="change_firmware")
        user.user_permissions.add(permission)

        backfill_legacy_site_memberships(django_apps, None)

        membership = SiteMembership.objects.get(user=user)
        assert membership.site.name == DEFAULT_SITE_NAME
        assert membership.role == SiteMembership.Role.ADMIN
        assert membership.can_manage_firmware is True
        assert membership.can_view_firmware is True

    def test_backfill_skips_superusers_plain_users_and_existing_memberships(self):
        only_site = SiteFactory(name="Only Active Site", is_active=True)
        superuser = UserFactory(is_superuser=True, is_staff=True)
        plain_user = UserFactory(is_superuser=False)
        existing_user = UserFactory(is_superuser=False)
        new_user = UserFactory(is_superuser=False)

        legacy_permission = Permission.objects.get(codename="view_endpoint")
        superuser.user_permissions.add(legacy_permission)
        existing_user.user_permissions.add(legacy_permission)
        new_user.user_permissions.add(legacy_permission)
        SiteMembershipFactory(user=existing_user, site=only_site, role=SiteMembership.Role.ADMIN)

        backfill_legacy_site_memberships(django_apps, None)

        assert SiteMembership.objects.filter(user=superuser).count() == 0
        assert SiteMembership.objects.filter(user=plain_user).count() == 0
        assert SiteMembership.objects.filter(user=existing_user).count() == 1
        assert SiteMembership.objects.filter(user=new_user, site=only_site).count() == 1
