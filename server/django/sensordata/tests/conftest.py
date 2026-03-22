#
# Copyright (c) 2024 Jonas Remmert
#
# SPDX-License-Identifier: Apache-2.0
#

import pytest

from sensordata.factories import SiteFactory, SiteMembershipFactory, UserFactory
from sensordata.models import SiteMembership


@pytest.fixture
def site():
    """Create a basic site."""
    return SiteFactory()


@pytest.fixture
def admin_user():
    """Create a superuser."""
    return UserFactory(is_superuser=True, is_staff=True)


@pytest.fixture
def site_admin():
    """Create a user with site admin role.

    Returns:
        tuple: (user, site, membership)
    """
    site = SiteFactory()
    user = UserFactory()
    membership = SiteMembershipFactory(
        user=user,
        site=site,
        role=SiteMembership.Role.ADMIN,
        can_view_overview=True,
        can_view_firmware=True,
        can_manage_firmware=True,
        can_perform_operations=True,
    )
    return user, site, membership


@pytest.fixture
def site_user():
    """Create a user with regular site user role.

    Returns:
        tuple: (user, site, membership)
    """
    site = SiteFactory()
    user = UserFactory()
    membership = SiteMembershipFactory(
        user=user,
        site=site,
        role=SiteMembership.Role.USER,
        can_view_overview=True,
        can_view_firmware=True,
        can_manage_firmware=False,
        can_perform_operations=False,
    )
    return user, site, membership
