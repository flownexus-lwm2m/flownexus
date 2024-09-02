#
# Copyright (c) 2024 Jonas Remmert
#
# SPDX-License-Identifier: Apache-2.0
#

from rest_framework import serializers
from ..models import Endpoint, Resource, Firmware, EndpointOperation, FirmwareUpdate, ResourceType

class EndpointSerializer(serializers.ModelSerializer):
    class Meta:
        model = Endpoint
        fields = ['endpoint', 'registered']

class ResourceTypeSerializer(serializers.ModelSerializer):
    class Meta:
        model = ResourceType
        fields = ['object_id', 'resource_id', 'name', 'data_type']

class GenericResourceSerializer(serializers.ModelSerializer):
    resource_type = ResourceTypeSerializer(read_only=True)

    class Meta:
        model = Resource
        fields = ['id', 'endpoint', 'resource_type', 'int_value', 'float_value', 'str_value', 'timestamp_created']

class FirmwareSerializer(serializers.ModelSerializer):
    class Meta:
        model = Firmware
        fields = ['id', 'version', 'created_at', 'binary']

class EndpointOperationSerializer(serializers.ModelSerializer):
    class Meta:
        model = EndpointOperation
        fields = ['id', 'resource', 'operation_type', 'status', 'timestamp_created', 'last_attempt']

class FirmwareUpdateSerializer(serializers.ModelSerializer):
    firmware = FirmwareSerializer(read_only=True)

    class Meta:
        model = FirmwareUpdate
        fields = ['id', 'endpoint', 'firmware', 'state', 'result', 'timestamp_created', 'timestamp_updated']

class ResourceDataSerializer(serializers.Serializer):
    KIND_CHOICES = [
        'singleResource',
        'multiResource',
    ]
    kind = serializers.ChoiceField(choices=KIND_CHOICES)
    id = serializers.IntegerField(help_text="Resource ID")
    type = serializers.ChoiceField(choices=ResourceType.TYPE_CHOICES)
    value = serializers.CharField(max_length=255, required=False, allow_blank=True)
    values = serializers.DictField(child=serializers.CharField(max_length=255), required=False, allow_empty=True)
