#
# Copyright (c) 2024 Jonas Remmert
#
# SPDX-License-Identifier: Apache-2.0
#
"""
Test-specific Django settings.

These settings are optimized for test execution speed while maintaining
correctness. They should NOT be used in production.
"""

from .settings import *  # noqa: F403

# Use fast password hashing to speed up user creation in tests
# MD5 is not secure but is 1000x faster than PBKDF2 - acceptable for tests
PASSWORD_HASHERS = ["django.contrib.auth.hashers.MD5PasswordHasher"]

# Always execute Celery tasks synchronously in tests
CELERY_TASK_ALWAYS_EAGER = True
CELERY_TASK_EAGER_PROPAGATES = True

# Remove WhiteNoise middleware - not needed for tests (no static file serving)
# This eliminates warnings about missing static_collect directory
MIDDLEWARE = [
    m
    for m in MIDDLEWARE  # noqa: F405
    if m != "whitenoise.middleware.WhiteNoiseMiddleware"
]
