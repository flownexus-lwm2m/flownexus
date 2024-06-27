from django.urls import path
from .views import CreateSensorDataView, TemperatureDataView

urlpatterns = [
    path('endpointdata/', CreateSensorDataView.as_view(), name='add_sensor_data'),
    path('temperature/', TemperatureDataView.as_view(), name='temperature_data'),
]
