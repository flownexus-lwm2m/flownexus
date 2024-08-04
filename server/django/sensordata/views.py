#
# Copyright (c) 2024 Jonas Remmert
#
# SPDX-License-Identifier: Apache-2.0
#
import traceback, logging
from rest_framework.generics import ListAPIView
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from django.shortcuts import render
from django.contrib.auth.decorators import login_required
from .models import Endpoint, Resource, Event, EndpointOperation, Firmware, ResourceType
from rest_framework.exceptions import ValidationError
from .serializers.single_resource_serializer import SingleResourceSerializer
from .serializers.composite_resource_serializer import CompositeResourceSerializer
from .serializers.generic_resource_serializer import GenericResourceSerializer
import traceback


logger = logging.getLogger(__name__)


class PostSingleResourceView(APIView):
    serializer_class = SingleResourceSerializer

    def post(self, request):
        serializer = SingleResourceSerializer(data=request.data, many=False)
        try:
            if serializer.is_valid(raise_exception=True):
                serializer.save()
                return Response(serializer.validated_data, status=status.HTTP_201_CREATED)
        except ValidationError as e:
            logger.error("Validation error: %s", e)
            logger.error("Request data: %s", request.data)
            logger.error("Backtrace: %s", traceback.format_exc())
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

class PostCompositeResourceView(APIView):
    serializer_class = CompositeResourceSerializer

    def post(self, request):
        serializer = CompositeResourceSerializer(data=request.data, many=False)
        try:
            if serializer.is_valid(raise_exception=True):
                serializer.save()
                return Response(serializer.validated_data, status=status.HTTP_201_CREATED)
        except ValidationError as e:
            logger.error("Validation error: %s", e)
            logger.error("Request data: %s", request.data)
            logger.error("Backtrace: %s", traceback.format_exc())
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

class ResourceDataView(ListAPIView):
    serializer_class = GenericResourceSerializer

    def get_queryset(self):
        resource_name = self.kwargs.get('resource_name')
        logger.debug(f"Received request for resource type: {resource_name}")
        try:
            resource_type = ResourceType.objects.get(name=resource_name)
            logger.debug(f"Found resource type: {resource_type}")
            return Resource.objects.filter(resource_type=resource_type)
        except ResourceType.DoesNotExist:
            logger.error(f"Resource type {resource_name} not found")
            return Response({"error": f"{resource_name} resource type not found"}, status=status.HTTP_404_NOT_FOUND)

    def get(self, request, *args, **kwargs):
        resource_name = self.kwargs.get('resource_name')
        queryset = self.get_queryset()

        if not queryset.exists():
            logger.error(f"Resource type {resource_name} not found")
            return Response({"error": f"{resource_name} resource type not found"}, status=status.HTTP_404_NOT_FOUND)

        logger.debug(f"{resource_name.capitalize()} resources: {queryset}")
        serializer = self.get_serializer(queryset, many=True)
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
    pending_operations = EndpointOperation.objects.filter(status='QUEUED')
    return render(request, 'pending_communication_dashboard.html', {'pending_operations': pending_operations, 'title': 'Pending Communication'})
