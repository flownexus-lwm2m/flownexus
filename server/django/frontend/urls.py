#
# Copyright (c) 2026 Jonas Remmert
#
# SPDX-License-Identifier: Apache-2.0
#

from django.urls import path

from . import views

app_name = "frontend"

urlpatterns = [
    path("", views.dashboard, name="dashboard"),
    path("devices/", views.devices, name="devices"),
    path("firmware/", views.firmware_list, name="firmware_list"),
    path("data/", views.data_analysis, name="data_analysis"),
    path("permissions/", views.permissions, name="permissions"),
    path("profile/", views.profile, name="profile"),
    path("switch-site/<str:site_id>/", views.switch_site, name="switch_site"),
]
