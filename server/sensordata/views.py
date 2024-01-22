from rest_framework import viewsets
from .models import TimeTemperature
from .serializers import TimeTemperatureSerializer
from django.views.generic.list import ListView

class TimeTemperatureViewSet(viewsets.ModelViewSet):
    queryset = TimeTemperature.objects.all()
    serializer_class = TimeTemperatureSerializer

class TimeTemperatureListView(ListView):
    model = TimeTemperature
    template_name = 'sensordata/timetemperature_list.html'
    context_object_name = 'timetemperature_list'
