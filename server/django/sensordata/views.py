#
# Copyright (c) 2024 Jonas Remmert
#
# SPDX-License-Identifier: Apache-2.0
#
import logging
import traceback

from django.shortcuts import get_object_or_404
from drf_spectacular.utils import extend_schema
from rest_framework import serializers, status
from rest_framework.exceptions import ValidationError
from rest_framework.response import Response
from rest_framework.views import APIView

from .models import Endpoint, EndpointOperation, FirmwareUpdate, Resource
from .serializers.composite_resource_serializer import CompositeResourceSerializer
from .serializers.generic_serializer import (
    EndpointOperationSerializer,
    EndpointSerializer,
    FirmwareSerializer,
    FirmwareUpdateSerializer,
)
from .serializers.single_resource_serializer import SingleResourceSerializer
from .serializers.timestamped_resource_serializer import TimestampedResourceSerializer

logger = logging.getLogger(__name__)

# API Views


class PostSingleResourceView(APIView):
    """API View for posting a single resource."""

    serializer_class = SingleResourceSerializer

    def post(self, request):
        serializer = self.serializer_class(data=request.data)
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
    """API View for posting a composite resource."""

    serializer_class = CompositeResourceSerializer

    def post(self, request):
        serializer = self.serializer_class(data=request.data)
        try:
            if serializer.is_valid(raise_exception=True):
                serializer.save()
                return Response(serializer.validated_data, status=status.HTTP_201_CREATED)
        except ValidationError as e:
            logger.error("Validation error: %s", e)
            logger.error("Request data: %s", request.data)
            logger.error("Backtrace: %s", traceback.format_exc())
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class PostTimestampedResourceView(APIView):
    serializer_class = TimestampedResourceSerializer

    def post(self, request):
        serializer = TimestampedResourceSerializer(data=request.data, many=False)
        try:
            if serializer.is_valid(raise_exception=True):
                serializer.save()
                return Response(serializer.validated_data, status=status.HTTP_201_CREATED)
        except ValidationError as e:
            logger.error("Validation error: %s", e)
            logger.error("Request data: %s", request.data)
            logger.error("Backtrace: %s", traceback.format_exc())
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class EndpointListView(APIView):
    """API View for listing all endpoints."""

    serializer_class = EndpointSerializer

    @extend_schema(
        operation_id="endpoints_list",
        responses={200: EndpointSerializer(many=True)},
    )
    def get(self, request):
        endpoints = Endpoint.objects.all()
        serializer = EndpointSerializer(endpoints, many=True)
        return Response(serializer.data)


class EndpointDetailView(APIView):
    """API View for retrieving a single endpoint."""

    serializer_class = EndpointSerializer

    @extend_schema(
        operation_id="endpoints_retrieve",
        responses={200: EndpointSerializer},
    )
    def get(self, request, endpoint_id):
        endpoint = get_object_or_404(Endpoint, endpoint=endpoint_id)
        serializer = EndpointSerializer(endpoint)
        return Response(serializer.data)


class EndpointResourceSerializer(serializers.Serializer):
    """Serializer for endpoint resource data."""

    resource_id = serializers.IntegerField()
    resource_type = serializers.CharField()
    value = serializers.CharField()
    timestamp_created = serializers.DateTimeField()


class EndpointResourceListView(APIView):
    """API View for listing resources associated with an endpoint."""

    serializer_class = EndpointResourceSerializer

    @extend_schema(
        operation_id="endpoints_resources_list",
        responses={200: EndpointResourceSerializer(many=True)},
    )
    def get(self, request, endpoint_id):
        endpoint = get_object_or_404(Endpoint, endpoint=endpoint_id)
        resources = Resource.objects.filter(endpoint=endpoint)
        data = [
            {
                "resource_id": r.id,
                "resource_type": str(r.resource_type),
                "value": r.get_value(),
                "timestamp_created": r.timestamp_created,
            }
            for r in resources
        ]
        return Response(data)


class EndpointResourceDetailView(APIView):
    """API View for retrieving a single resource associated with an endpoint."""

    serializer_class = EndpointResourceSerializer

    @extend_schema(
        operation_id="endpoints_resources_retrieve",
        responses={200: EndpointResourceSerializer},
    )
    def get(self, request, endpoint_id, resource_id):
        endpoint = get_object_or_404(Endpoint, endpoint=endpoint_id)
        resource = get_object_or_404(Resource, endpoint=endpoint, id=resource_id)
        data = {
            "resource_id": resource.id,
            "resource_type": str(resource.resource_type),
            "value": resource.get_value(),
            "timestamp_created": resource.timestamp_created,
        }
        return Response(data)


class EndpointFirmwareView(APIView):
    """API View for retrieving and posting firmware updates for an endpoint."""

    serializer_class = FirmwareUpdateSerializer

    @extend_schema(
        operation_id="endpoints_firmware_list",
        responses={200: FirmwareUpdateSerializer(many=True)},
    )
    def get(self, request, endpoint_id):
        endpoint = get_object_or_404(Endpoint, endpoint=endpoint_id)
        firmware_updates = FirmwareUpdate.objects.filter(endpoint=endpoint)
        serializer = FirmwareUpdateSerializer(firmware_updates, many=True)
        return Response(serializer.data)

    @extend_schema(
        operation_id="endpoints_firmware_create",
        request=FirmwareSerializer,
        responses={201: FirmwareUpdateSerializer},
    )
    def post(self, request, endpoint_id):
        endpoint = get_object_or_404(Endpoint, endpoint=endpoint_id)
        firmware_serializer = FirmwareSerializer(data=request.data)
        if firmware_serializer.is_valid():
            firmware = firmware_serializer.save()
            firmware_update = FirmwareUpdate.objects.create(endpoint=endpoint, firmware=firmware)
            update_serializer = FirmwareUpdateSerializer(firmware_update)
            return Response(update_serializer.data, status=status.HTTP_201_CREATED)
        return Response(firmware_serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class EndpointOperationView(APIView):
    """API View for retrieving and posting operations to be performed on an endpoint."""

    serializer_class = EndpointOperationSerializer

    @extend_schema(
        operation_id="endpoints_operations_list",
        responses={200: EndpointOperationSerializer(many=True)},
    )
    def get(self, request, endpoint_id):
        endpoint = get_object_or_404(Endpoint, endpoint=endpoint_id)
        operations = EndpointOperation.objects.filter(resource__endpoint=endpoint)
        serializer = EndpointOperationSerializer(operations, many=True)
        return Response(serializer.data)

    @extend_schema(
        operation_id="endpoints_operations_create",
        request=EndpointOperationSerializer,
        responses={201: EndpointOperationSerializer},
    )
    def post(self, request, endpoint_id):
        endpoint = get_object_or_404(Endpoint, endpoint=endpoint_id)
        serializer = EndpointOperationSerializer(data=request.data)
        if serializer.is_valid():
            serializer.save(resource__endpoint=endpoint)
            return Response(serializer.data, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
