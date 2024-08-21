#
# Copyright (c) 2024 Jonas Remmert
#
# SPDX-License-Identifier: Apache-2.0
#

import logging
from django.utils import timezone
from django.contrib import admin
from .tasks import process_pending_operations
import os
from .models import (
    Endpoint,
    ResourceType,
    Resource,
    Event,
    EventResource,
    EndpointOperation,
    Firmware,
    FirmwareUpdate
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


class EventResourceInline(admin.TabularInline):
    model = EventResource
    extra = 0
    can_delete = False
    readonly_fields = ('resource',)


@admin.register(Resource)
class ResourceAdmin(admin.ModelAdmin):
    list_display = ('endpoint', 'resource_type', 'timestamp_created')
    search_fields = ('endpoint__endpoint', 'resource_type__name')
    list_filter = ('endpoint__endpoint', 'resource_type', 'timestamp_created')
    readonly_fields = ('timestamp_created',)


@admin.register(Event)
class EventAdmin(admin.ModelAdmin):
    list_display = ('endpoint', 'event_type', 'time')
    search_fields = ('endpoint', 'event_type')
    list_filter = ('endpoint', 'event_type')
    readonly_fields = ('endpoint', 'event_type', 'time')
    inlines = [EventResourceInline]


@admin.register(EventResource)
class EventResourceAdmin(admin.ModelAdmin):
    list_display = ('event', 'resource')
    search_fields = ('event__event_type', 'resource__resource_type__name')
    list_filter = ('event', 'resource__resource_type')
    readonly_fields = ('event', 'resource')


@admin.register(EndpointOperation)
class EndpointOperationAdmin(admin.ModelAdmin):
    list_display = ('resource', 'operation_type', 'status', 'timestamp_created',
                    'transmit_counter', 'last_attempt')
    search_fields = ('resource__endpoint__endpoint', 'operation_type', 'status')
    list_filter = ('resource__resource_type', 'operation_type', 'status', 'timestamp_created')
    readonly_fields = ('status', 'timestamp_created', 'transmit_counter',
                       'last_attempt', 'operation_type')

    # "sesource" has to be setup during create, make read-only after that
    def get_readonly_fields(self, request, obj=None):
        if obj is not None:
            return ('resource',) + self.readonly_fields
        return self.readonly_fields

    def save_model(self, request, obj, form, change):
        # Update created timestamp, as we handle a manual entry.
        obj.timestamp_created = timezone.now()
        super().save_model(request, obj, form, change)

        # Trigger the async task to process the operation
        process_pending_operations.delay(obj.resource.endpoint.endpoint)


@admin.register(Firmware)
class FirmwareAdmin(admin.ModelAdmin):
    list_display = ('version', 'file_name', 'file_link', 'created_at')

    def file_name(self, obj):
        return os.path.basename(obj.binary.name)
    file_name.short_description = 'File Name'

    def file_link(self, obj):
        return obj.binary.url
    file_link.short_description = 'Relative DL-Link'

    # Override the get_form method to make the binary field read-only when
    # editing an existing record
    def get_form(self, request, obj=None, **kwargs):
        form = super().get_form(request, obj, **kwargs)
        if obj:
            form.base_fields['binary'].disabled = True
        form.base_fields['version'].help_text = (
            'The version field must match the binary firmware version.'
            'that is reported to LwM2M Firmware Version field (3/0/3).<br>'
            'This identifier is used to confirm the new firmware after a reboot of the endpoint.'
        )
        return form


@admin.register(FirmwareUpdate)
class FirmwareUpdateAdmin(admin.ModelAdmin):
    list_display = ('endpoint', 'firmware', 'state', 'result',
                    'timestamp_created', 'timestamp_updated',
                    'send_uri_operation', 'execute_operation')
    search_fields = ('endpoint__endpoint', 'firmware__version', 'state', 'result')
    list_filter = ('state', 'result', 'timestamp_created', 'timestamp_updated')
    readonly_fields = ('timestamp_created', 'timestamp_updated',
                       'result', 'state', 'send_uri_operation', 'execute_operation')

    def save_model(self, request, obj, form, change):
        # Custom save logic if needed
        super().save_model(request, obj, form, change)

        # Trigger the async task to process the operation
        process_pending_operations.delay(obj.endpoint.endpoint)
