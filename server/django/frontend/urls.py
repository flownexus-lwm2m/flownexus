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
    path("firmware/", views.firmware_list, name="firmware_list"),
    path("data/", views.data_analysis, name="data_analysis"),
]
