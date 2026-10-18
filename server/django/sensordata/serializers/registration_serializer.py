#
# Copyright (c) 2026 Jonas Remmert
#
# SPDX-License-Identifier: Apache-2.0
#

import logging

from django.db.models import Max
from rest_framework import serializers

from ..models import Endpoint, Resource, ResourceType
from ..tasks import process_pending_operations, read_device_object

logger = logging.getLogger(__name__)

# Registration events are stored as resources of the internal object 10240
EVENT_RESOURCE_IDS = {"registered": 0, "unregistered": 1, "updated": 2}


class RegistrationEventSerializer(serializers.Serializer):
    ep = serializers.CharField(max_length=255, help_text="Unique LwM2M Endpoint")
    event = serializers.ChoiceField(choices=list(EVENT_RESOURCE_IDS))
    time = serializers.DateTimeField(help_text="Time the gateway saw the event")

    def create(self, validated_data):
        endpoint, _ = Endpoint.objects.get_or_create(endpoint=validated_data["ep"])
        event = validated_data["event"]
        time_ms = int(validated_data["time"].timestamp() * 1000)
        events = Resource.objects.filter(endpoint=endpoint, resource_type__object_id=10240)
        latest = events.aggregate(Max("int_value"))["int_value__max"]
        Resource.objects.create(
            endpoint=endpoint,
            resource_type=ResourceType.objects.get(
                object_id=10240, resource_id=EVENT_RESOURCE_IDS[event]
            ),
            int_value=time_ms,
        )

        # The gateway retries failed requests, so an event can arrive late. Keep
        # it in the history, but let only the newest event set the state.
        if latest is not None and time_ms < latest:
            logger.warning(f"Ignoring {event} of {endpoint} older than its last event")
            return endpoint

        endpoint.registered = event != "unregistered"
        endpoint.save()
        if event == "registered":
            read_device_object.delay(endpoint.endpoint)
        if endpoint.registered:
            process_pending_operations.delay(endpoint.endpoint)
        return endpoint
