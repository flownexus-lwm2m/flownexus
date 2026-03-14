#
# Copyright (c) 2026 Jonas Remmert
#
# SPDX-License-Identifier: Apache-2.0
#

import logging
import re
import time

from sensordata.models import Site, SiteMembership

logger = logging.getLogger("core.request_logging")
UNASSIGNED_SITE_KEY = "unassigned"


class RequestLoggingMiddleware:
    """Middleware to log requests with configurable levels for different paths."""

    def __init__(self, get_response):
        self.get_response = get_response
        # Patterns to log at DEBUG level (high-frequency/noisy endpoints)
        self.debug_patterns = [
            re.compile(r"^/\?view="),  # Dashboard polling
            re.compile(r"^/flownexus/ingest/"),  # Data ingestion
        ]

    def __call__(self, request):
        start_time = time.monotonic()
        response = self.get_response(request)
        duration = time.monotonic() - start_time

        # Check if this is a high-frequency endpoint that should be DEBUG
        is_debug_endpoint = any(
            pattern.match(request.get_full_path()) for pattern in self.debug_patterns
        )

        # Get content size: check Content-Length header first, fall back to len(content)
        content_length = response.get("Content-Length")
        if content_length is not None:
            size = content_length
        elif hasattr(response, "content"):
            size = len(response.content)
        else:
            size = "-"

        if is_debug_endpoint:
            logger.debug(
                "%s %s %s %s (%.3fs)",
                request.method,
                request.path,
                response.status_code,
                size,
                duration,
            )
        else:
            logger.info(
                "%s %s %s %s (%.3fs)",
                request.method,
                request.path,
                response.status_code,
                size,
                duration,
            )

        return response


class SiteContextMiddleware:
    """Middleware to manage site context for multi-tenant access control."""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        # Only process for authenticated users
        if request.user.is_authenticated:
            # Set site context
            site_id = request.session.get("current_site_id")
            request.current_site_key = None

            # Global admins can access all sites
            if request.user.is_superuser:
                request.is_global_admin = True
                request.available_sites = list(Site.objects.filter(is_active=True))
            else:
                request.is_global_admin = False
                # Get sites this user has access to
                memberships = SiteMembership.objects.filter(
                    user=request.user,
                    site__is_active=True,
                ).select_related("site")
                request.available_sites = [m.site for m in memberships]

            # Set current site
            if site_id:
                # Verify user has access to this site
                if request.is_global_admin and site_id == UNASSIGNED_SITE_KEY:
                    request.site = None
                    request.current_site_key = UNASSIGNED_SITE_KEY
                elif request.is_global_admin:
                    try:
                        request.site = Site.objects.get(id=site_id, is_active=True)
                        request.current_site_key = str(request.site.id)
                    except Site.DoesNotExist:
                        request.site = self._get_default_site(request)
                else:
                    try:
                        membership = SiteMembership.objects.get(
                            user=request.user, site_id=site_id, site__is_active=True
                        )
                        request.site = membership.site
                        request.site_membership = membership
                        request.current_site_key = str(membership.site.id)
                    except SiteMembership.DoesNotExist:
                        request.site = self._get_default_site(request)
            else:
                # No site selected, use default
                request.site = self._get_default_site(request)

        response = self.get_response(request)
        return response

    def _get_default_site(self, request):
        """Get the first available site for the user."""
        if request.is_global_admin:
            # Global admin can use any active site
            site = Site.objects.filter(is_active=True).first()
            if site:
                request.session["current_site_id"] = site.id
                request.current_site_key = str(site.id)
            return site

        # Regular user - get first site they have access to
        membership = (
            SiteMembership.objects.filter(user=request.user, site__is_active=True)
            .select_related("site")
            .first()
        )
        if membership:
            request.site_membership = membership
            request.session["current_site_id"] = membership.site.id
            request.current_site_key = str(membership.site.id)
            return membership.site
        return None
