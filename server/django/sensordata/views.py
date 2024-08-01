#
# Copyright (c) 2024 Jonas Remmert
#
# SPDX-License-Identifier: Apache-2.0
#

from rest_framework.generics import GenericAPIView
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from django.shortcuts import render
from django.contrib.auth.decorators import login_required
from .models import Endpoint, Resource, Event, EndpointOperation, Firmware, ResourceType
from .serializers.single_resource_serializer import SingleResourceSerializer
from .serializers.composite_resource_serializer import CompositeResourceSerializer
from .serializers.generic_resource_serializer import GenericResourceSerializer
import logging

logger = logging.getLogger(__name__)


class PostSingleResourceView(APIView):
    serializer_class = SingleResourceSerializer

    def post(self, request):
        serializer = SingleResourceSerializer(data=request.data, many=False)
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.validated_data, status=status.HTTP_201_CREATED)
        logger.error(serializer.errors)
        logger.error(request.data)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

class PostCompositeResourceView(APIView):
    serializer_class = CompositeResourceSerializer

    def post(self, request):
        serializer = CompositeResourceSerializer(data=request.data, many=False)
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.validated_data, status=status.HTTP_201_CREATED)
        logger.error(serializer.errors)
        logger.error(request.data)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

class ResourceDataView(GenericAPIView):
    serializer_class = GenericResourceSerializer

    def get(self, request, resource_name):
        try:
            resource_type = ResourceType.objects.get(name=resource_name)
        except ResourceType.DoesNotExist:
            return Response({"error": f"{resource_name} resource type not found"}, status=status.HTTP_404_NOT_FOUND)

        resources = Resource.objects.filter(resource_type=resource_type)
        logger.debug(f"{resource_name.capitalize()} resources: {resources}")
        serializer = self.get_serializer(resources, many=True)
        logger.debug(f"{resource_name.capitalize()} data: {serializer.data}")
        return Response(serializer.data, status=status.HTTP_200_OK)


@login_required
def license_dashboard_view(request):
    return render(request, 'license.html', {'title': 'Project Information and Licenses'})

@login_required
def admin_dashboard_view(request):
    devices = Endpoint.objects.all()
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
    pending_operations = EndpointOperation.objects.filter(status='pending')
    return render(request, 'pending_communication_dashboard.html', {'pending_operations': pending_operations, 'title': 'Pending Communication'})
