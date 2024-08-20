#
# Copyright (c) 2024 Jonas Remmert
#
# SPDX-License-Identifier: Apache-2.0
#

from django.db import models
from django.core.exceptions import ValidationError
from django.db import transaction
import os


class Endpoint(models.Model):
    """Represents a specific device in the IoT ecosystem."""
    endpoint = models.CharField(max_length=255, primary_key=True)
    registered = models.BooleanField(default=False)

    def __str__(self):
        return os.path.basename(self.endpoint)


class ResourceType(models.Model):
    """Map LwM2M object/resource IDs to human-readable names and data types."""

    TIME = 'TIME'
    STRING = 'STRING'
    OPAQUE = 'OPAQUE'
    INTEGER = 'INTEGER'
    FLOAT = 'FLOAT'
    BOOLEAN = 'BOOLEAN'

    TYPE_CHOICES = [
        (TIME, 'int_value'),
        (STRING, 'str_value'),
        (INTEGER, 'int_value'),
        (FLOAT, 'float_value'),
        (BOOLEAN, 'int_value'),
    ]

    object_id = models.IntegerField()
    resource_id = models.IntegerField()
    name = models.CharField(max_length=255)
    data_type = models.CharField(max_length=50, choices=TYPE_CHOICES)

    class Meta:
        unique_together = ('object_id', 'resource_id')

    def __str__(self):
        return f"{self.object_id}/{self.resource_id} - {self.name}"

    def get_value_field(self):
        return dict(ResourceType.TYPE_CHOICES).get(self.data_type)


class Resource(models.Model):
    """Stores individual resource data, such as sensor readings, from an endpoint."""
    endpoint = models.ForeignKey(Endpoint, on_delete=models.PROTECT)
    resource_type = models.ForeignKey(ResourceType, on_delete=models.PROTECT)
    int_value = models.IntegerField(null=True, blank=True)
    float_value = models.FloatField(null=True, blank=True)
    str_value = models.CharField(max_length=512, null=True, blank=True)
    timestamp_created = models.DateTimeField(auto_now_add=True, blank=True)

    def __str__(self):
        return f"{self.endpoint} - {self.resource_type} - {self.timestamp_created}"

    # Gets the correct value field, based on the linked ResourceType
    def get_value(self):
        value_field = self.resource_type.get_value_field()
        if value_field:
            return getattr(self, value_field)
        return None


class Event(models.Model):
    """
    Represents a significant event in the system that is associated with a
    endpoint and various resources.
    """
    endpoint = models.ForeignKey(Endpoint, on_delete=models.PROTECT)
    event_type = models.CharField(max_length=100)
    time = models.DateTimeField(auto_now_add=True, blank=True)

    def __str__(self):
        return f"{self.endpoint} - {self.event_type} - {self.time}"


class EventResource(models.Model):
    """Acts as a many-to-many bridge table that links resources to their respective events."""
    event = models.ForeignKey(Event, related_name='resources', on_delete=models.PROTECT)
    resource = models.ForeignKey(Resource, on_delete=models.PROTECT)

    class Meta:
        unique_together = ('event', 'resource')


class EndpointOperation(models.Model):
    """Operation to be performed on an endpoint"""

    class Status(models.TextChoices):
        SENDING = 'SENDING'
        QUEUED = 'QUEUED'
        CONFIRMED = 'CONFIRMED'
        FAILED = 'FAILED'

    resource = models.ForeignKey(Resource, on_delete=models.PROTECT)
    operation_type = models.CharField(max_length=100)  # e.g., 'send', 'update'
    status = models.CharField(
        max_length=100,
        choices=Status.choices,
        default=Status.QUEUED,
    )
    transmit_counter = models.IntegerField(default=0)
    timestamp_created = models.DateTimeField(auto_now_add=True, blank=True)
    last_attempt = models.DateTimeField(auto_now_add=False, null=True)

    def __str__(self):
        return f"{self.resource} - {self.operation_type} - {self.status}"


class Firmware(models.Model):
    """Represents a firmware update file that can be downloaded by an endpoint."""
    version = models.CharField(max_length=100, unique=True)
    created_at = models.DateTimeField(auto_now_add=True)
    # Upload to MEDIA_ROOT
    binary = models.FileField()

    # Limit the binary file size to 1 MB
    def clean(self):
        super().clean()
        max_size = 1 * 1024 * 1024

        if self.binary and self.binary.size > max_size:
            raise ValidationError("The file size must be under 1 MB.")

    def __str__(self):
        return os.path.basename(self.version)


class FirmwareUpdate(models.Model):
    """Represents a firmware update operation for an endpoint."""


    class State(models.IntegerChoices):
        STATE_IDLE = 0, 'IDLE'
        STATE_DOWNLOADING = 1, 'DOWNLOADING'
        STATE_DOWNLOADED = 2, 'DOWNLOADED'
        STATE_UPDATING = 3, 'UPDATING'

    class Result(models.IntegerChoices):
        RESULT_DEFAULT = 0, 'DEFAULT'
        RESULT_SUCCESS = 1, 'SUCCESS'
        RESULT_NO_STORAGE = 2, 'NO STORAGE'
        RESULT_OUT_OF_MEM = 3, 'OUT OF MEMORY'
        RESULT_CONNECTION_LOST = 4, 'CONNECTION LOST'
        RESULT_INTEGRITY_FAILED = 5, 'INTEGRITY FAILED'
        RESULT_UNSUP_FW = 6, 'UNSUPPORTED FIRMWARE'
        RESULT_INVALID_URI = 7, 'INVALID URI'
        RESULT_UPDATE_FAILED = 8, 'UPDATE FAILED'
        RESULT_UNSUP_PROTO = 9, 'UNSUPPORTED PROTOCOL'

    endpoint = models.ForeignKey(Endpoint, on_delete=models.PROTECT)
    firmware = models.ForeignKey(Firmware, on_delete=models.PROTECT)
    state = models.IntegerField(choices=State.choices, default=State.STATE_IDLE)
    result = models.IntegerField(choices=Result.choices, default=Result.RESULT_DEFAULT)
    timestamp_created = models.DateTimeField(auto_now_add=True, blank=True)
    timestamp_updated = models.DateTimeField(auto_now=True, blank=True)
    # The update is initiated with this resource (send URI)
    send_uri_operation = models.ForeignKey(EndpointOperation, null=True,
                                           on_delete=models.PROTECT,
                                           related_name='send_uri_operation')
    # Once the firmware is downloaded, the update is initiated with this resource
    execute_operation = models.ForeignKey(EndpointOperation, null=True,
                                          on_delete=models.PROTECT,
                                          related_name='execute_operation')

    # Check for existing non-finished updates for the same endpoint. Only
    # Update processes that have no result (RESULT_DEFAULT) are considered.
    def clean(self):
        super().clean()
        existing_nodes = FirmwareUpdate.objects.filter(
            endpoint = self.endpoint,
            result = self.Result.RESULT_DEFAULT
        )
        if existing_nodes.exists():
            raise ValidationError("An active update with this endpoint already exists.")

    # Avoid having multiple ongoing updates for the same endpoint
    def save(self, *args, **kwargs):
        # Check if the instance is being created for the first time
        is_new = self.pk is None
        with transaction.atomic():
            if is_new:
                # Create the send Resource instance if send_uri is provided
                send_resource = Resource(
                    endpoint = self.endpoint,
                    # Assign "Package URI" resource type
                    resource_type=ResourceType.objects.get(object_id = 5, resource_id = 1),
                    str_value = self.firmware.binary.url,
                )
                send_resource.save()

                self.send_uri_operation = EndpointOperation(resource=send_resource)
                self.send_uri_operation.save()
                print("New instance created")
            super().save(*args, **kwargs)
