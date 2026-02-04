#
# Copyright (c) 2026 Jonas Remmert
#
# SPDX-License-Identifier: Apache-2.0
#

import logging
import re
import time

logger = logging.getLogger("core.request_logging")


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
