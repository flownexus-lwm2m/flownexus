import logging
from django.utils import timezone
from django.contrib import admin
from .tasks import process_pending_operations
from .models import (
    Endpoint,
    ResourceType,
    Resource,
    Event,
    EventResource,
    EndpointOperation,
    Firmware
)

log = logging.getLogger('sensordata')


@admin.register(Endpoint)
class EndpointAdmin(admin.ModelAdmin):
    list_display = ('endpoint', 'registered')
    search_fields = ('endpoint', 'registered')
    readonly_fields = ('endpoint', 'registered')

    def get_model_perms(self, request):
        return {
            'add': False,
            'change': False,
            'delete': False,
            'view': True,
        }

@admin.register(ResourceType)
class ResourceTypeAdmin(admin.ModelAdmin):
    list_display = ('object_id', 'resource_id', 'name', 'data_type')
    search_fields = ('object_id', 'resource_id', 'name')
    readonly_fields = ('object_id', 'resource_id', 'name', 'data_type')

    def get_model_perms(self, request):
        return {
            'add': False,
            'change': False,
            'delete': False,
            'view': True,
        }


@admin.register(Resource)
class ResourceAdmin(admin.ModelAdmin):
    list_display = ('endpoint', 'resource_type', 'timestamp')
    search_fields = ('endpoint__endpoint', 'resource_type__name')
    list_filter = ('endpoint', 'resource_type', 'timestamp')


@admin.register(Event)
class EventAdmin(admin.ModelAdmin):
    list_display = ('endpoint', 'event_type', 'start_time', 'end_time')
    search_fields = ('endpoint__endpoint', 'event_type')
    list_filter = ('endpoint', 'event_type')


@admin.register(EventResource)
class EventResourceAdmin(admin.ModelAdmin):
    list_display = ('event', 'resource')
    search_fields = ('event__event_type', 'resource__resource_type__name')
    list_filter = ('event', 'resource__resource_type')


@admin.register(EndpointOperation)
class EndpointOperationAdmin(admin.ModelAdmin):
    list_display = ('resource', 'operation_type', 'status', 'timestamp_created',
                    'transmit_counter', 'last_attempt')
    search_fields = ('resource__endpoint__endpoint', 'operation_type', 'status')
    list_filter = ('resource__resource_type', 'operation_type', 'status', 'timestamp_created')
    readonly_fields = ('status', 'timestamp_created', 'transmit_counter',
                       'last_attempt', 'operation_type')

    def save_model(self, request, obj, form, change):
        # Update created timestamp, as we handle a manual entry.
        obj.timestamp_created = timezone.now()
        super().save_model(request, obj, form, change)

        # Trigger the async task to process the operation
        process_pending_operations.delay(obj.resource.endpoint.endpoint)


@admin.register(Firmware)
class FirmwareAdmin(admin.ModelAdmin):
    list_display = ('version', 'file_name', 'download_url', 'created_at')
