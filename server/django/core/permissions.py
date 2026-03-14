#
# Copyright (c) 2026 Jonas Remmert
#
# SPDX-License-Identifier: Apache-2.0
#

from __future__ import annotations

from django.db.models import QuerySet

from core.middleware import UNASSIGNED_SITE_KEY
from sensordata.models import Endpoint, Site, SiteMembership


def has_site_permission(user, request_context, permission_name: str) -> bool:
    """Return whether the user has a permission in the current site context."""
    if user.is_superuser:
        return True

    if getattr(request_context, "current_site_key", None) == "all":
        return sites_with_permission(user, permission_name).exists()

    membership = getattr(request_context, "site_membership", None)
    if membership is None:
        return False
    return bool(getattr(membership, permission_name, False))


def sites_with_permission(user, permission_name: str) -> QuerySet[Site]:
    """Return active sites where the user has the given permission."""
    if user.is_superuser:
        return Site.objects.filter(is_active=True)

    return Site.objects.filter(
        is_active=True,
        memberships__user=user,
        **{f"memberships__{permission_name}": True},
    ).distinct()


def memberships_with_permission(user, permission_name: str) -> QuerySet[SiteMembership]:
    """Return memberships where the given permission is granted."""
    return SiteMembership.objects.filter(
        user=user,
        site__is_active=True,
        **{permission_name: True},
    ).select_related("site")


def get_site_filtered_endpoints(request, permission_name: str | None = None) -> QuerySet[Endpoint]:
    """Return endpoints filtered by current context and optional permission scope."""
    current_site_key = getattr(request, "current_site_key", None)

    if current_site_key == UNASSIGNED_SITE_KEY:
        if request.user.is_superuser:
            return Endpoint.objects.filter(site__isnull=True)
        return Endpoint.objects.none()

    if request.user.is_superuser:
        if current_site_key == "all":
            return Endpoint.objects.all()
        site = getattr(request, "site", None)
        if site is not None:
            return Endpoint.objects.filter(site=site)
        return Endpoint.objects.none()

    if current_site_key == "all":
        if permission_name is None:
            site_ids = [site.id for site in getattr(request, "available_sites", [])]
            return Endpoint.objects.filter(site_id__in=site_ids)

        allowed_sites = sites_with_permission(request.user, permission_name)
        return Endpoint.objects.filter(site__in=allowed_sites)

    site = getattr(request, "site", None)
    if site is None:
        return Endpoint.objects.none()

    if permission_name and not has_site_permission(request.user, request, permission_name):
        return Endpoint.objects.none()

    return Endpoint.objects.filter(site=site)
