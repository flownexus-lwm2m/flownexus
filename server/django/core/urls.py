#
# Copyright (c) 2024 Jonas Remmert
#
# SPDX-License-Identifier: Apache-2.0
#

from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.urls import include, path

urlpatterns = [
    path("admin/", admin.site.urls),
    path("flownexus/ingest/", include("sensordata.urls")),
    path("", include("frontend.urls")),
    path("accounts/", include("django.contrib.auth.urls")),
]

# Serve static firmware files
urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
