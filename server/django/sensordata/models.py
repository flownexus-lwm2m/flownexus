#
# Copyright (c) 2024 Jonas Remmert
#
# SPDX-License-Identifier: Apache-2.0
#

from pathlib import Path
from typing import Any

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models, transaction
from django.utils import timezone


class Site(models.Model):
    """Represents an internal organizational grouping within one deployment."""

    name = models.CharField(max_length=255, unique=True)
    description = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ["name"]

    def __str__(self):
        return self.name


class SiteMembership(models.Model):
    """Links users to sites with specific roles and permissions."""

    PERMISSION_FIELDS = (
        "can_view_overview",
        "can_view_firmware",
        "can_view_data_analysis",
        "can_manage_firmware",
        "can_perform_operations",
        "can_manage_devices",
    )

    class Role(models.TextChoices):
        ADMIN = "ADMIN", "Site Admin"
        USER = "USER", "Site User"

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="site_memberships"
    )
    site = models.ForeignKey(Site, on_delete=models.CASCADE, related_name="memberships")
    role = models.CharField(max_length=20, choices=Role.choices, default=Role.USER)

    # Feature-based permissions
    can_view_overview = models.BooleanField(default=True)
    can_view_firmware = models.BooleanField(default=False)
    can_view_data_analysis = models.BooleanField(default=True)

    # Operational permissions
    can_manage_firmware = models.BooleanField(default=False)  # Upload/delete firmware
    can_perform_operations = models.BooleanField(default=False)  # Write/Execute on devices
    can_manage_devices = models.BooleanField(default=False)  # Transfer devices between sites

    joined_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ("user", "site")
        ordering = ["-joined_at"]

    def __str__(self):
        return f"{self.user.username} - {self.site.name} ({self.role})"

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        self._explicit_permission_fields = {
            field_name for field_name in self.PERMISSION_FIELDS if field_name in kwargs
        }
        super().__init__(*args, **kwargs)

    def is_admin(self):
        return self.role == self.Role.ADMIN

    def is_global_admin(self):
        """Global admins are identified by is_superuser flag."""
        return self.user.is_superuser

    def apply_role_defaults(self, preserve_explicit: bool = False) -> None:
        """Apply the default permission set for the current role."""
        permission_defaults = {
            "can_view_overview": True,
            "can_view_data_analysis": True,
        }

        if self.role == self.Role.ADMIN:
            permission_defaults.update(
                {
                    "can_view_firmware": True,
                    "can_manage_firmware": True,
                    "can_perform_operations": True,
                    "can_manage_devices": False,
                }
            )
        else:
            permission_defaults.update(
                {
                    "can_view_firmware": False,
                    "can_manage_firmware": False,
                    "can_perform_operations": False,
                    "can_manage_devices": False,
                }
            )

        for field_name, default_value in permission_defaults.items():
            if preserve_explicit and field_name in self._explicit_permission_fields:
                continue
            setattr(self, field_name, default_value)

    def save(self, *args: Any, **kwargs: Any) -> None:
        if self._state.adding and kwargs.get("update_fields") is None:
            self.apply_role_defaults(preserve_explicit=True)
        super().save(*args, **kwargs)


class Endpoint(models.Model):
    """Represents a specific device in the IoT ecosystem."""

    endpoint = models.CharField(max_length=255, primary_key=True)
    registered = models.BooleanField(default=False)
    site = models.ForeignKey(
        Site, on_delete=models.PROTECT, related_name="endpoints", null=True, blank=True
    )

    def __str__(self):
        return Path(self.endpoint).name


class ResourceType(models.Model):
    """Map LwM2M object/resource IDs to human-readable names and data types."""

    TIME = "TIME"
    STRING = "STRING"
    OPAQUE = "OPAQUE"
    INTEGER = "INTEGER"
    FLOAT = "FLOAT"
    BOOLEAN = "BOOLEAN"

    TYPE_CHOICES = [
        (TIME, "int_value"),
        (STRING, "str_value"),
        (INTEGER, "int_value"),
        (FLOAT, "float_value"),
        (BOOLEAN, "int_value"),
    ]

    object_id = models.IntegerField()
    resource_id = models.IntegerField()
    name = models.CharField(max_length=255)
    data_type = models.CharField(max_length=50, choices=TYPE_CHOICES)

    class Meta:
        unique_together = ("object_id", "resource_id")

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
    timestamp_created = models.DateTimeField(blank=True, null=True, db_index=True)

    def save(self, *args, **kwargs):
        if not self.timestamp_created:
            self.timestamp_created = timezone.now()
        super().save(*args, **kwargs)

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

    event = models.ForeignKey(Event, related_name="resources", on_delete=models.PROTECT)
    resource = models.ForeignKey(Resource, on_delete=models.PROTECT)

    class Meta:
        unique_together = ("event", "resource")


class EndpointOperation(models.Model):
    """Operation to be performed on an endpoint"""

    class Status(models.TextChoices):
        SENDING = "SENDING"
        QUEUED = "QUEUED"
        CONFIRMED = "CONFIRMED"
        FAILED = "FAILED"

    resource = models.ForeignKey(Resource, on_delete=models.PROTECT)
    operation_type = models.CharField(max_length=100)  # e.g., 'send', 'update'
    status = models.CharField(
        max_length=100,
        choices=Status.choices,
        default=Status.QUEUED,
    )
    transmit_counter = models.IntegerField(default=0)
    timestamp_created = models.DateTimeField(auto_now_add=True, blank=True)
    last_attempt = models.DateTimeField(null=True)

    def __str__(self):
        return f"{self.resource} - {self.operation_type} - {self.status}"


class Firmware(models.Model):
    """Represents a firmware update file that can be downloaded by an endpoint."""

    version = models.CharField(max_length=100, unique=True)
    created_at = models.DateTimeField(auto_now_add=True)
    # Upload to MEDIA_ROOT
    binary = models.FileField()
    is_deleted = models.BooleanField(default=False, help_text="Soft delete flag")

    # Limit the binary file size to 1 MB
    def clean(self):
        super().clean()
        max_size = 1 * 1024 * 1024

        if self.binary and self.binary.size > max_size:
            raise ValidationError("The file size must be under 1 MB.")

    def __str__(self):
        return Path(self.version).name


class FirmwareUpdate(models.Model):
    """Represents a firmware update operation for an endpoint."""

    class State(models.IntegerChoices):
        STATE_IDLE = 0, "IDLE"
        STATE_DOWNLOADING = 1, "DOWNLOADING"
        STATE_DOWNLOADED = 2, "DOWNLOADED"
        STATE_UPDATING = 3, "UPDATING"

    class Result(models.IntegerChoices):
        RESULT_DEFAULT = 0, "DEFAULT"
        RESULT_SUCCESS = 1, "SUCCESS"
        RESULT_NO_STORAGE = 2, "NO STORAGE"
        RESULT_OUT_OF_MEM = 3, "OUT OF MEMORY"
        RESULT_CONNECTION_LOST = 4, "CONNECTION LOST"
        RESULT_INTEGRITY_FAILED = 5, "INTEGRITY FAILED"
        RESULT_UNSUP_FW = 6, "UNSUPPORTED FIRMWARE"
        RESULT_INVALID_URI = 7, "INVALID URI"
        RESULT_UPDATE_FAILED = 8, "UPDATE FAILED"
        RESULT_UNSUP_PROTO = 9, "UNSUPPORTED PROTOCOL"

    endpoint = models.ForeignKey(Endpoint, on_delete=models.PROTECT)
    firmware = models.ForeignKey(Firmware, on_delete=models.PROTECT)
    state = models.IntegerField(choices=State.choices, default=State.STATE_IDLE)
    result = models.IntegerField(choices=Result.choices, default=Result.RESULT_DEFAULT)
    timestamp_created = models.DateTimeField(auto_now_add=True, blank=True)
    timestamp_updated = models.DateTimeField(auto_now=True, blank=True)
    # The update is initiated with this resource (send URI)
    send_uri_operation = models.ForeignKey(
        EndpointOperation, null=True, on_delete=models.PROTECT, related_name="send_uri_operation"
    )
    # Once the firmware is downloaded, the update is initiated with this resource
    execute_operation = models.ForeignKey(
        EndpointOperation, null=True, on_delete=models.PROTECT, related_name="execute_operation"
    )

    def clean(self):
        super().clean()
        try:
            if self.endpoint:
                existing_nodes = FirmwareUpdate.objects.filter(
                    endpoint=self.endpoint, result=self.Result.RESULT_DEFAULT
                )
                # If we are editing an existing instance, exclude it
                if self.pk:
                    existing_nodes = existing_nodes.exclude(pk=self.pk)

                if existing_nodes.exists():
                    raise ValidationError("An active update with this endpoint already exists.")
        except Endpoint.DoesNotExist:
            pass
        except Exception:
            # Handle cases where endpoint might not be set yet during form validation
            pass

    # Avoid having multiple ongoing updates for the same endpoint
    def save(self, *args, **kwargs):
        # Check if the instance is being created for the first time
        is_new = self.pk is None
        with transaction.atomic():
            if is_new:
                # Create the send Resource instance if send_uri is provided
                send_resource = Resource(
                    endpoint=self.endpoint,
                    # Assign "Package URI" resource type
                    resource_type=ResourceType.objects.get(object_id=5, resource_id=1),
                    str_value=self.firmware.binary.url,
                )
                send_resource.save()

                self.send_uri_operation = EndpointOperation(resource=send_resource)
                self.send_uri_operation.save()
            super().save(*args, **kwargs)
