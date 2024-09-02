#
# Copyright (c) 2024 Jonas Remmert
#
# SPDX-License-Identifier: Apache-2.0
#

from django.urls import path
from .views import (
    PostSingleResourceView,
    PostCompositeResourceView,
    PostTimestampedResourceView,
    # ResourceDataView
)
from . import views

urlpatterns = [
    path('endpoints/', views.EndpointView.as_view(), name='endpoint-list'),
    path('endpoints/<str:endpoint_id>/', views.EndpointView.as_view(), name='endpoint-detail'),
    path('endpoints/<str:endpoint_id>/resources/', views.EndpointResourceView.as_view(), name='endpoint-resource-list'),
    path('endpoints/<str:endpoint_id>/resources/<int:resource_id>/', views.EndpointResourceView.as_view(), name='endpoint-resource-detail'),
    path('endpoints/<str:endpoint_id>/firmware/', views.EndpointFirmwareView.as_view(), name='endpoint-firmware'),
    path('endpoints/<str:endpoint_id>/operations/', views.EndpointOperationView.as_view(), name='endpoint-operations'),
    path('resource/single', PostSingleResourceView.as_view(), name='post-single-resource'),
    path('resource/composite', PostCompositeResourceView.as_view(), name='post-composite-resource'),
    path('resource/timestamped', PostTimestampedResourceView.as_view(), name='post-timestamped-resource'),
]
