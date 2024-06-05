from django.urls import path
from .views import PostResourceView

urlpatterns = [
    path('resource', PostResourceView.as_view(), name='post_resource'),
]
