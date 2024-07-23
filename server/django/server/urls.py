#
# Copyright (c) 2024 Jonas Remmert
#
# SPDX-License-Identifier: Apache-2.0
#

from django.contrib import admin
from django.urls import include, path
from django.conf.urls.static import static
from django.conf import settings

urlpatterns = [
    path('admin/', admin.site.urls),
    path('leshan_api/', include('sensordata.urls')),
]

# Serve static firmware files
urlpatterns += static(settings.FIRMWARE_URL, document_root=settings.FIRMWARE_ROOT)
