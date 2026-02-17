#
# Copyright (c) 2024 Jonas Remmert
#
# SPDX-License-Identifier: Apache-2.0
#

import pytest
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
        assert membership.can_view_firmware is True
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
