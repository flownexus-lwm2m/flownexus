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

@admin.register(Firmware)
class FirmwareAdmin(admin.ModelAdmin):
    list_display = ('version', 'file_name', 'download_url', 'created_at')
    search_fields = ('version', 'file_name')
    list_filter = ('created_at',)
