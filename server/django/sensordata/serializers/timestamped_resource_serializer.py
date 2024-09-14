#
# Copyright (c) 2024 Jonas Remmert
#
# SPDX-License-Identifier: Apache-2.0
#

from rest_framework import serializers
from .base import HandleResourceMixin, ResourceDataSerializer
from ..models import Endpoint
import logging
from dateutil import parser

logger = logging.getLogger(__name__)


class NodeSerializer(serializers.Serializer):
    nodes = serializers.DictField(
        child=ResourceDataSerializer(),
        help_text="Dictionary of resource paths (e.g., '/3303/0/5700') to resource data"
    )


class TimestampedResourceSerializer(HandleResourceMixin, serializers.Serializer):
    ep = serializers.CharField(max_length=255, help_text="Unique LwM2M Endpoint")
    val = serializers.ListField(
        child=serializers.DictField(
            child=NodeSerializer(),
        )
    )


    def create(self, validated_data):
        ep = validated_data['ep']
        val = validated_data['val']
        # Create an Event only once for the given endpoint
        event_created = False
        endpoint, _ = Endpoint.objects.get_or_create(endpoint=ep)

        for item in val:
            for ts, data in item.items():
                nodes = data.get('nodes', {})

                for path, resource in nodes.items():
                    obj_id = int(path.split('/')[1])
                    if len(nodes) > 1 or len(val) > 1:
                        if not event_created:
                            self.create_event(endpoint, obj_id)
                            event_created = True

                    if ts == 'null':
                        self.handle_resource(endpoint, obj_id, resource)
                    else:
                        timestamp = parser.parse(ts)
                        self.handle_resource(endpoint, obj_id, resource, timestamp)

        return endpoint
