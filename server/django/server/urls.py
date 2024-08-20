#
# Copyright (c) 2024 Jonas Remmert
#
# SPDX-License-Identifier: Apache-2.0
#

from django.contrib import admin
from django.urls import include, path
from sensordata import views
from django.conf.urls.static import static
from django.conf import settings

urlpatterns = [
    path('admin/', admin.site.urls),
    path('leshan_api/', include('sensordata.urls')),
    path('admin_dashboard/', views.admin_dashboard_view, name='admin_dashboard'),
    path('firmware_dashboard/', views.firmware_dashboard_view, name='firmware_dashboard'),
    path('event_dashboard/', views.event_dashboard_view, name='event_dashboard'),
    path('graph_dashboard/', views.graph_dashboard_view, name='graph_dashboard'),
    path('pending_communication_dashboard/', views.pending_communication_dashboard_view, name='pending_communication_dashboard'),
    path('license/', views.license_dashboard_view, name='license_dashboard'),
    path('accounts/', include('django.contrib.auth.urls')),
    path('', views.admin_dashboard_view, name='default'),
]

# Serve static firmware files
urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
