from django.contrib import admin
from django.urls import include, path
from sensordata import views as sensordata_views

urlpatterns = [
    path('admin/', admin.site.urls),
    path('api/', include('sensordata.urls')),
    path('sensordata/list/', sensordata_views.SensorDataListView.as_view(), name='sensordata_list'),
]
