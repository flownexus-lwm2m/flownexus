#
# Copyright (c) 2024 Jonas Remmert
#
# SPDX-License-Identifier: Apache-2.0
#

from django.urls import path
from .views import PostSingleResourceView, PostCompositeResourceView


urlpatterns = [
    path('resource/single', PostSingleResourceView.as_view(), name='post-single-resource'),
    path('resource/composite', PostCompositeResourceView.as_view(), name='post-composite-resource'),
]
