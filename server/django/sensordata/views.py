from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from .serializers import GenericLWM2MSerializer
from .models import SensorData
from django.views.generic import ListView
import logging

logger = logging.getLogger(__name__)


class CreateSensorDataView(APIView):
    def post(self, request, format=None):
        serializer = GenericLWM2MSerializer(data=request.data)
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.validated_data, status=status.HTTP_201_CREATED)
        else:
            logger.error(f"Errors: {serializer.errors}")
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

class SensorDataListView(ListView):
    model = SensorData
    template_name = 'timetemperature_list.html'
    context_object_name = 'timetemperature_list'
    queryset = SensorData.objects.all()
