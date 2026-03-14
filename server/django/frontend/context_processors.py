#
# Copyright (c) 2026 Jonas Remmert
#
# SPDX-License-Identifier: Apache-2.0
#
import os

from core.permissions import memberships_with_permission

PERMISSION_FIELDS = (
    "can_view_overview",
    "can_view_firmware",
    "can_view_data_analysis",
    "can_manage_firmware",
    "can_perform_operations",
    "can_manage_devices",
)


def version(request):
    """
    Provide the application version to templates.
    The version should be injected as an environment variable (APP_VERSION)
    during the build process.
    """
    version = os.environ.get("APP_VERSION", "unknown")
    return {"APP_VERSION": version}


def site_context(request):
    """
    Provide site context and user permissions to templates.
    This allows templates to show/hide navigation items based on permissions.
    """
    context = {}

    if hasattr(request, "user") and request.user.is_authenticated:
        # Site context
        context["current_site"] = getattr(request, "site", None)
        context["available_sites"] = getattr(request, "available_sites", [])
        context["is_global_admin"] = getattr(request, "is_global_admin", False)
        context["current_site_key"] = getattr(request, "current_site_key", None)
        context["show_unassigned_site"] = context["is_global_admin"]
        # Show "All Devices" option if user has access to more than one site
        context["show_all_devices"] = len(context["available_sites"]) > 1

        if context["current_site_key"] == "all":
            context["current_site_label"] = "All Devices"
        elif context["current_site_key"] == "unassigned":
            context["current_site_label"] = "Unassigned Devices"
        elif context["current_site"]:
            context["current_site_label"] = context["current_site"].name
        else:
            context["current_site_label"] = "Select Site"

        # User's permissions for current site
        site_membership = getattr(request, "site_membership", None)
        if context["is_global_admin"]:
            context["site_role"] = "GLOBAL_ADMIN"
            for permission_field in PERMISSION_FIELDS:
                context[permission_field] = True
        elif context["current_site_key"] == "all":
            context["site_role"] = "MULTI_SITE"
            for permission_field in PERMISSION_FIELDS:
                context[permission_field] = memberships_with_permission(
                    request.user, permission_field
                ).exists()
        elif site_membership:
            context["site_role"] = site_membership.role
            for permission_field in PERMISSION_FIELDS:
                context[permission_field] = getattr(site_membership, permission_field)
        else:
            # No site membership - no permissions
            context["site_role"] = None
            for permission_field in PERMISSION_FIELDS:
                context[permission_field] = False

        context["can_view_devices"] = context["can_view_overview"]

    return context
