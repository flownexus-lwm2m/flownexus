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
