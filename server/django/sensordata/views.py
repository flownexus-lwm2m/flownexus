from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from .serializers import LwM2MSerializer
from django.shortcuts import render
from django.contrib.auth.decorators import login_required
from .models import Device, Resource, Event, DeviceOperation, Firmware, ResourceType
import logging

logger = logging.getLogger(__name__)


class CreateSensorDataView(APIView):
    def post(self, request):

        serializer = LwM2MSerializer(data=request.data, many=False)
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.validated_data, status=status.HTTP_201_CREATED)
        else:
            print(serializer.errors)
            logger.error(f"Errors: {serializer.errors}")
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

class TemperatureDataView(APIView):
    def get(self, request):
        try:
            temperature_resource_type = ResourceType.objects.get(name='temperature')
        except ResourceType.DoesNotExist:
            return Response({"error": "Temperature resource type not found"}, status=status.HTTP_404_NOT_FOUND)

        temperature_resources = Resource.objects.filter(resource_type=temperature_resource_type)
        logger.debug(f"Temperature resources: {temperature_resources}")
        data = [
            {
                "timestamp": resource.timestamp.strftime('%Y-%m-%d %H:%M:%S'),
                "value": resource.float_value
            }
            for resource in temperature_resources
        ]
        logger.debug(f"Temperature data: {data}")
        return Response(data, status=status.HTTP_200_OK)



@login_required
def admin_dashboard_view(request):
    devices = Device.objects.all()
    return render(request, 'admin_dashboard.html', {'devices': devices, 'title': 'Admin Dashboard'})

@login_required
def firmware_dashboard_view(request):
    firmware_updates = Firmware.objects.all()
    return render(request, 'firmware_dashboard.html', {'firmware_updates': firmware_updates, 'title': 'Firmware Update Dashboard'})

@login_required
def event_dashboard_view(request):
    events = Event.objects.all()
    return render(request, 'event_dashboard.html', {'events': events, 'title': 'Event Dashboard'})

@login_required
def graph_dashboard_view(request):
    return render(request, 'graph_dashboard.html', {'title': 'Graph Dashboard'})

@login_required
def pending_communication_dashboard_view(request):
    pending_operations = DeviceOperation.objects.filter(status='pending')
    return render(request, 'pending_communication_dashboard.html', {'pending_operations': pending_operations, 'title': 'Pending Communication'})
