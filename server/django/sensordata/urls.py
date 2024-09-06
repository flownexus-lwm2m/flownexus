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
    ResourceDataView
)

urlpatterns = [
    path('data/<str:resource_name>/', ResourceDataView.as_view(), name='resource-data'),
    path('resource/single', PostSingleResourceView.as_view(), name='post-single-resource'),
    path('resource/composite', PostCompositeResourceView.as_view(), name='post-composite-resource'),
    path('resource/timestamped', PostTimestampedResourceView.as_view(), name='post-timestamped-resource'),
]
