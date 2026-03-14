#
# Copyright (c) 2026 Jonas Remmert
#
# SPDX-License-Identifier: Apache-2.0
#
import os


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
        if context["current_site_key"] == "unassigned":
            context["current_site_label"] = "Unassigned Devices"
        elif context["current_site"]:
            context["current_site_label"] = context["current_site"].name
        else:
            context["current_site_label"] = "Select Site"

        # User's permissions for current site
        site_membership = getattr(request, "site_membership", None)
        if site_membership:
            context["site_role"] = site_membership.role
            context["can_view_overview"] = site_membership.can_view_overview
            context["can_view_firmware"] = site_membership.can_view_firmware
            context["can_view_data_analysis"] = site_membership.can_view_data_analysis
            context["can_manage_firmware"] = site_membership.can_manage_firmware
            context["can_perform_operations"] = site_membership.can_perform_operations
            context["can_manage_devices"] = site_membership.can_manage_devices
        elif context["is_global_admin"]:
            # Global admins have all permissions
            context["site_role"] = "GLOBAL_ADMIN"
            context["can_view_overview"] = True
            context["can_view_firmware"] = True
            context["can_view_data_analysis"] = True
            context["can_manage_firmware"] = True
            context["can_perform_operations"] = True
            context["can_manage_devices"] = True
        else:
            # No site membership - no permissions
            context["site_role"] = None
            context["can_view_overview"] = False
            context["can_view_firmware"] = False
            context["can_view_data_analysis"] = False
            context["can_manage_firmware"] = False
            context["can_perform_operations"] = False
            context["can_manage_devices"] = False

    return context
