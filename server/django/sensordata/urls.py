#
# Copyright (c) 2024 Jonas Remmert
#
# SPDX-License-Identifier: Apache-2.0
#

from django.urls import path
from .views import CreateSensorDataView, TemperatureDataView, PostSingleResourceView, PostCompositeResourceView

urlpatterns = [
    path('endpointdata/', CreateSensorDataView.as_view(), name='add_sensor_data'),
    path('temperature/', TemperatureDataView.as_view(), name='temperature_data'),
    path('resource/single', PostSingleResourceView.as_view(), name='post-single-resource'),
    path('resource/composite', PostCompositeResourceView.as_view(), name='post-composite-resource'),
]