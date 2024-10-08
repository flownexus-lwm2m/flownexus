#
# Copyright (c) 2024 Jonas Remmert
#
# SPDX-License-Identifier: Apache-2.0
#

from rest_framework import serializers
from ..models import (
        ResourceType,
        Resource,
        Event,
        EventResource,
        FirmwareUpdate,
        EndpointOperation
)
from ..tasks import process_pending_operations
import logging

logger = logging.getLogger(__name__)


class ResourceDataSerializer(serializers.Serializer):
    KIND_CHOICES = [
        'singleResource',
        'multiResource',
    ]
    kind = serializers.ChoiceField(choices=KIND_CHOICES)
    id = serializers.IntegerField(help_text="Resource ID")
    type = serializers.ChoiceField(choices=ResourceType.TYPE_CHOICES)
    value = serializers.CharField(max_length=255,
                                  required=False,
                                  allow_blank=True,
                                  help_text="The value associated with the resource,\
                                             type-dependent. Provide either the field\
                                             value or values"
    )
    values = serializers.DictField(child=serializers.CharField(max_length=255),
                                   required=False,
                                   allow_empty=True,
                                   help_text="The list of values associated with the resource.\
                                              Provide either the field value or values."
    )


class HandleResourceMixin:
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.event = None


    def create_event(self, endpoint, event_type):
        """
        Create an Event instance for the given endpoint and event type. If no event
        is created, the resource data won't be associated with any event.
        """
        event_data = {
            'endpoint': endpoint,
            'event_type': event_type,
        }
        self.event = Event.objects.create(**event_data)


    def handle_resource(self, endpoint, obj_id, res):
        # Some LwM2M Resources are currently unsupported, we can skip them for now.
        if res['kind'] == 'multiResource':
            logging.error(f"multiResource currently not supported, skipping...")
            return

        res_id = res['id']
        # Fetch resource information from Database
        resource_type = ResourceType.objects.get(object_id=obj_id, resource_id=res_id)
        if not resource_type:
            err = f"Resource type {obj_id}/{res_id} not found"
            raise serializers.ValidationError(err)

        # Validate that datatype is matching the resource type
        data_type = dict(ResourceType.TYPE_CHOICES).get(res['type'])
        res_data_type = dict(ResourceType.TYPE_CHOICES).get(resource_type.data_type)
        if not data_type:
            err = f"Unsupported data type '{res['type']}', skipping..."
            logger.error(err)
            raise serializers.ValidationError(err)
        if data_type != res_data_type:
            err = f"Mismatch between ResourceType.data_type '{res_data_type}' " \
                  f"and Resource value type '{data_type}'"
            raise serializers.ValidationError(err)

        # Create the Resource instance based on value type
        logger.debug(f"Adding resource_type: {resource_type}")
        resource_data = {
            'endpoint': endpoint,
            'resource_type': resource_type,
            data_type: res['value']
        }

        created_res = Resource.objects.create(**resource_data)

        # Create EventResource linking the event and the resource
        if self.event is not None:
            EventResource.objects.create(event=self.event, resource=created_res)
            logger.debug(f"Added EventResource: {self.event} - {created_res}")

        # Update the registration status if the resource is a registration resource
        if resource_type.name == 'ep_registered':
            endpoint.registered = True
            endpoint.save()
            return
        elif resource_type.name == 'ep_unregistered':
            endpoint.registered = False
            endpoint.save()
            return
        elif resource_type.name == 'ep_registration_update':
            process_pending_operations.delay(endpoint.endpoint)
            return

        # Cond 1: Check for fota update after ep registration.
        # "Firmware Version - 3/0/3" Resource.
        #
        # Cond 2: Handle FOTA Update
        elif ((resource_type.object_id == 3 and resource_type.resource_id == 3) or
               resource_type.object_id == 5):
            # There must be exactly one FirmwareUpdate object with
            # result = 0 (RESULT_DEFAULT).
            fw_queryset = FirmwareUpdate.objects.filter(endpoint=endpoint,
                                 result=FirmwareUpdate.Result.RESULT_DEFAULT)
            cnt = fw_queryset.count()
            if cnt == 1:
                fw_obj = fw_queryset.get()
            elif cnt == 0:
                if resource_type.resource_id == 3:
                    # This case can happen if the result is updated before the
                    # state. Can be ignored, as a result will automatically set the
                    # state to IDLE.
                    return
                else:
                    err = "No active FirmwareUpdate object found for endpoint"
                    raise serializers.ValidationError(err)
            else:
                err = "Multiple active FirmwareUpdate objects found for endpoint"
                logger.info(fw_queryset)
                raise serializers.ValidationError(err)

            # Compare version with expected version and set download state/result
            if resource_type.object_id == 3 and resource_type.resource_id == 3:
                fw_obj.state = FirmwareUpdate.State.STATE_IDLE
                expected_version = fw_obj.firmware.version
                reported_version = res['value']
                if expected_version == reported_version:
                    fw_obj.result = FirmwareUpdate.Result.RESULT_SUCCESS
                else:
                    fw_obj.result = FirmwareUpdate.Result.RESULT_UPDATE_FAILED
                fw_obj.save()
                return

            if resource_type.resource_id == 3:
                if int(res['value']) == FirmwareUpdate.State.STATE_DOWNLOADED:
                    # Create "Update" resource to execute the update, no payload
                    exec_resource = Resource.objects.create(endpoint = endpoint,
                        resource_type = ResourceType.objects.get(object_id = 5, resource_id = 2)
                        )
                    exec_operation = EndpointOperation.objects.create(resource=exec_resource)
                    fw_obj.state = res['value']
                    fw_obj.execute_operation = exec_operation
                    fw_obj.save()
                    process_pending_operations.delay(endpoint.endpoint)
            elif resource_type.resource_id == 5:
                fw_obj.result = res['value']
                fw_obj.state = FirmwareUpdate.State.STATE_IDLE
                fw_obj.save()
