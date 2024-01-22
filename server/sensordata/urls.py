from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import TimeTemperatureViewSet


router = DefaultRouter()
router.register(r'timetemperature', TimeTemperatureViewSet)

urlpatterns = [
    path('', include(router.urls)),
]
