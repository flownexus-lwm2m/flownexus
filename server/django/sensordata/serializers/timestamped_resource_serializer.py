#
# Copyright (c) 2024 Jonas Remmert
#
# SPDX-License-Identifier: Apache-2.0
#

from rest_framework import serializers
from .base import HandleResourceMixin, ResourceDataSerializer
from ..models import Endpoint
import logging

logger = logging.getLogger(__name__)


class TsValueSerializer(serializers.Serializer):
    nodes = serializers.DictField(
        child=ResourceDataSerializer(),
        help_text="Dictionary of resource paths (e.g., '/3303/0/5700') to resource data"
    )


class TimestampedResourceSerializer(HandleResourceMixin, serializers.Serializer):
    ep = serializers.CharField(max_length=255, help_text="Unique LwM2M Endpoint")
    val = TsValueSerializer()

    def create(self, validated_data):
        ep = validated_data['ep']
        val = validated_data['val']

        endpoint, _ = Endpoint.objects.get_or_create(endpoint=ep)

        nodes = val.get('nodes', {})

        # If multiple resources are present, create and assign them to an
        # event. Take the first object id as the event type.
        if len(nodes) > 1:
            obj_id = int(list(nodes.keys())[0].split('/')[1])
            self.create_event(endpoint, obj_id)

        for path, resource in nodes.items():
            obj_id = int(path.split('/')[1])
            self.handle_resource(endpoint, obj_id, resource)

        return endpoint
