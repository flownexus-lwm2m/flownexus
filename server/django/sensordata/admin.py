import requests
import logging
import os
from django.utils import timezone
from django.contrib import admin
from .models import (
    Device,
    ResourceType,
    Resource,
    Event,
    EventResource,
    DeviceOperation,
    Firmware
)

log = logging.getLogger('sensordata')

# Check if we run in a container or locally
LESHAN_URI = os.getenv('LESHAN_URI', 'http://0.0.0.0:8080') + '/api'


@admin.register(Device)
class DeviceAdmin(admin.ModelAdmin):
    list_display = ('device_id', 'name')
    search_fields = ('device_id', 'name')


@admin.register(ResourceType)
class ResourceTypeAdmin(admin.ModelAdmin):
    list_display = ('object_id', 'resource_id', 'name', 'data_type')
    search_fields = ('object_id', 'resource_id', 'name')


@admin.register(Resource)
class ResourceAdmin(admin.ModelAdmin):
    list_display = ('device', 'resource_type', 'timestamp')
    search_fields = ('device__device_id', 'resource_type__name')
    list_filter = ('device', 'resource_type', 'timestamp')


@admin.register(Event)
class EventAdmin(admin.ModelAdmin):
    list_display = ('device', 'event_type', 'start_time', 'end_time')
    search_fields = ('device__device_id', 'event_type')
    list_filter = ('device', 'event_type')


@admin.register(EventResource)
class EventResourceAdmin(admin.ModelAdmin):
    list_display = ('event', 'resource')
    search_fields = ('event__event_type', 'resource__resource_type__name')
    list_filter = ('event', 'resource')


@admin.register(DeviceOperation)
class DeviceOperationAdmin(admin.ModelAdmin):
    list_display = ('resource', 'operation_type', 'status', 'timestamp_sent',
                    'retransmit_counter', 'last_attempt')
    search_fields = ('resource__device__device_id', 'operation_type', 'status')
    list_filter = ('resource', 'operation_type', 'status', 'timestamp_sent')
    readonly_fields = ('status', 'timestamp_sent', 'retransmit_counter',
                       'last_attempt', 'operation_type')

    def save_model(self, request, obj, form, change):
        # Update both timestamps, as we handle a manual entry. Automatic
        # retries would only update the last_attempt
        obj.last_attempt = timezone.now()
        obj.timestamp_sent = timezone.now()
        super().save_model(request, obj, form, change)

        # Get the resource associated with the device operation
        resource = obj.resource
        device = resource.device
        resource_type = resource.resource_type

        # Determine the value based on the type of resource value
        value = None
        if resource_type.data_type == 'int':
            value = resource.int_value
        elif resource_type.data_type == 'float':
            value = resource.float_value
        elif resource_type.data_type == 'string':
            value = resource.str_value
        elif resource_type.data_type == 'bool':
            value = resource.bool_value
        else:
            # TODO: maybe an execute operation?
            log.error('Resource value not found')
            return


        # Construct the URL based on the device, object_id, and resource_id
        url = (
            f'{LESHAN_URI}/clients/{device.device_id}/'
            f'{resource_type.object_id}/0/{resource_type.resource_id}'
        )
        params = {'timeout': 5, 'format': 'CBOR'}
        headers = {'Content-Type': 'application/json'}
        data = {
            "id": resource_type.resource_id,
            "kind": "singleResource",
            "value": value,
            "type": resource_type.data_type
        }

        # Send the request
        response = requests.put(url, params=params, headers=headers, json=data)

        if response.status_code == 200:
            log.debug(f'Data sent to device {device.device_id} successfully')
            log.debug(f'Response: {response.status_code} - {response.json()}')
            obj.status = 'completed'
        else:
            log.error(f'Failed to send data: {response.status_code}')
            obj.status = 'pending'
            obj.retransmit_counter += 1

        obj.save()

@admin.register(Firmware)
class FirmwareAdmin(admin.ModelAdmin):
    list_display = ('version', 'file_name', 'download_url', 'created_at')
    search_fields = ('version', 'file_name')
    list_filter = ('created_at',)
