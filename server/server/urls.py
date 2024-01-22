from django.contrib import admin
from django.urls import include, path
from sensordata import views as sensordata_views

urlpatterns = [
    path('admin/', admin.site.urls),
    path('api/', include('sensordata.urls')),
    path('timetemperature/list/', sensordata_views.TimeTemperatureListView.as_view(), name='timetemperature_list'),
]
