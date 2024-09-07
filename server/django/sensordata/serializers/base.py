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


    def create_event(self, ep, event_type):
        """
        Create an Event instance for the given endpoint and event type. If no event
        is created, the resource data won't be associated with any event.
        """
        event_data = {
            'endpoint': ep,
            'event_type': event_type,
        }
        self.event = Event.objects.create(**event_data)


    def handle_resource(self, ep, obj_id, res):
        # Some LwM2M Resources are currently unsupported, we can skip them for now.
        if res['kind'] == 'multiResource':
            logging.error(f"multiResource currently not supported, skipping...")
            return

        res_id = res['id']
        # Fetch resource information from Database
        res_type = ResourceType.objects.get(object_id=obj_id, resource_id=res_id)
        if not res_type:
            err = f"Resource type {obj_id}/{res_id} not found"
            raise serializers.ValidationError(err)

        # Validate that datatype is matching the resource type
        data_type = dict(ResourceType.TYPE_CHOICES).get(res['type'])
        res_data_type = dict(ResourceType.TYPE_CHOICES).get(res_type.data_type)
        if not data_type:
            err = f"Unsupported data type '{res['type']}', skipping..."
            logger.error(err)
            raise serializers.ValidationError(err)
        if data_type != res_data_type:
            err = f"Mismatch between ResourceType.data_type '{res_data_type}' " \
                  f"and Resource value type '{data_type}'"
            raise serializers.ValidationError(err)

        # Create the Resource instance based on value type
        logger.debug(f"Adding resource_type: {res_type}")
        resource_data = {
            'endpoint': ep,
            'resource_type': res_type,
            data_type: res['value']
        }

        created_res = Resource.objects.create(**resource_data)

        # Create EventResource linking the event and the resource
        if self.event is not None:
            EventResource.objects.create(event=self.event, resource=created_res)
            logger.debug(f"Added EventResource: {self.event} - {created_res}")

        # Update the registration status if the resource is a registration resource
        if res_type.name in ['ep_registered', 'ep_registration_update']:
            ep.registered = True
            ep.save()
            process_pending_operations.delay(ep.endpoint)
            return
        elif res_type.name == 'ep_unregistered':
            ep.registered = False
            ep.save()
            return

        # Cond 1: Check for fota update after ep registration.
        # "Firmware Version - 3/0/3" Resource.
        #
        # Cond 2: Handle FOTA Update
        elif ((res_type.object_id == 3 and res_type.resource_id == 3) or
               res_type.object_id == 5):
            self.handle_fota(ep, res_type, res['value'])
            return


    def handle_fota(self, ep, res_type, value):
        # There must be exactly one FirmwareUpdate object with
        # result = 0 (RESULT_DEFAULT).
        fw_query = FirmwareUpdate.objects.filter(endpoint=ep,
                             result=FirmwareUpdate.Result.RESULT_DEFAULT)

        # Check for exactly one FirmwareUpdate object
        if fw_query.count() == 0:
            if res_type.object_id == 3 and res_type.resource_id == 3:
                # Just a regular reboot, no FOTA update
                return
            err = "No FirmwareUpdate object found for endpoint"
            raise serializers.ValidationError
        if fw_query.count() != 1:
            err = "Multiple active FirmwareUpdate objects found for endpoint"
            logger.info(fw_query)
            raise serializers.ValidationError(err)

        # Exactly one FirmwareUpdate object found
        fw_obj = fw_query.get()

        # Device Rebooted
        if res_type.object_id == 3 and res_type.resource_id == 3:
            if (fw_obj.state == FirmwareUpdate.State.STATE_IDLE and \
               fw_obj.result == FirmwareUpdate.Result.RESULT_DEFAULT):
                # Update hasn't been started yet
                return
            expected_version = fw_obj.firmware.version
            reported_version = value
            if expected_version == reported_version:
                fw_obj.result = FirmwareUpdate.Result.RESULT_SUCCESS
            else:
                fw_obj.result = FirmwareUpdate.Result.RESULT_UPDATE_FAILED
            fw_obj.state = FirmwareUpdate.State.STATE_IDLE
            self.abort_pending_fota_comms(fw_obj)
            fw_obj.save()
            return

        # Update state changed
        if res_type.resource_id == 3:
            fw_obj.state = value
            if int(value) == FirmwareUpdate.State.STATE_DOWNLOADED:
                # Create "Update" resource to execute the update, no payload
                exec_update = ResourceType.objects.get(object_id = 5, resource_id = 2)
                exec_res = Resource.objects.create( endpoint = ep, resource_type = exec_update)
                exec_operation = EndpointOperation.objects.create(resource=exec_res)
                fw_obj.execute_operation = exec_operation
                process_pending_operations.delay(ep.endpoint)
        # Update Result changed (Success/Failure)
        elif res_type.resource_id == 5:
            fw_obj.result = value
            # In cases (success/failure), the update process is finished.
            fw_obj.state = FirmwareUpdate.State.STATE_IDLE
            self.abort_pending_fota_comms(fw_obj)
        else:
            return
        fw_obj.save()


    # In case an update is finished (success/failure), abort any pending
    # operations (send URI, execute update). All communications should usually
    # be closed already.
    def abort_pending_fota_comms(self, fw_obj):
        # Abort all open operations
        if fw_obj.execute_operation:
            status = fw_obj.execute_operation.status
            if status in (EndpointOperation.Status.QUEUED, EndpointOperation.Status.SENDING):
                fw_obj.execute_operation.status = EndpointOperation.Status.FAILED

        if fw_obj.send_uri_operation:
            status = fw_obj.send_uri_operation.status
            if status in (EndpointOperation.Status.QUEUED, EndpointOperation.Status.SENDING):
                fw_obj.send_uri_operation.status = EndpointOperation.Status.FAILED
