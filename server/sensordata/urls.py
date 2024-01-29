from django.urls import path
from .views import CreateSensorDataView

urlpatterns = [
    path('endpointdata/', CreateSensorDataView.as_view(), name='add_sensor_data'),
]
