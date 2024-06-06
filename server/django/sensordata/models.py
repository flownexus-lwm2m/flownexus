from django.db import models

class Endpoint(models.Model):
    """Represents a specific device in the IoT ecosystem."""
    endpoint = models.CharField(max_length=255, primary_key=True)
    registered = models.BooleanField(default=False)


class ResourceType(models.Model):
    """Map LwM2M object/resource IDs to human-readable names and data types."""
    object_id = models.IntegerField()
    resource_id = models.IntegerField()
    name = models.CharField(max_length=255)
    # LwM2M data types:
    # - string: UTF-8 encoded sequence of characters
    # - integer: 16-bit signed integer
    # - float: 64-bit IEEE 754 floating point
    # - boolean: 0 or 1
    # - opaque: sequence of binary data
    # - time: POSIX time, number of s since 1970 in UTC (signed integer)
    # - objlnk: link to another object instance
    # - none (''): no data, used for executable resources
    data_type = models.CharField(max_length=50, blank=True)

    class Meta:
        unique_together = ('object_id', 'resource_id')

    def __str__(self):
        return f"{self.object_id}/{self.resource_id} - {self.name}"

class Resource(models.Model):
    """Stores individual resource data, such as sensor readings, from an endpoint."""
    endpoint = models.ForeignKey(Endpoint, on_delete=models.PROTECT)
    resource_type = models.ForeignKey(ResourceType, on_delete=models.PROTECT)
    int_value = models.IntegerField(null=True, blank=True)
    float_value = models.FloatField(null=True, blank=True)
    str_value = models.CharField(max_length=512, null=True, blank=True)
    timestamp = models.DateTimeField()

    class Meta:
        unique_together = ('endpoint', 'resource_type', 'timestamp')

    def __str__(self):
        return f"{self.endpoint} - {self.resource_type} - {self.timestamp}"

class Event(models.Model):
    """
    Represents a significant event in the system that is associated with a
    endpoint and various resources.
    """
    endpoint = models.ForeignKey(Endpoint, on_delete=models.PROTECT)
    event_type = models.CharField(max_length=100)
    start_time = models.DateTimeField()
    end_time = models.DateTimeField()

    def __str__(self):
        return f"{self.event_type} from {self.start_time} to {self.end_time} for {self.endpoint}"

class EventResource(models.Model):
    """Acts as a many-to-many bridge table that links resources to their respective events."""
    event = models.ForeignKey(Event, related_name='resources', on_delete=models.PROTECT)
    resource = models.ForeignKey(Resource, on_delete=models.PROTECT)

    class Meta:
        unique_together = ('event', 'resource')

class EndpointOperation(models.Model):
    """Operation to be performed on an endpoint"""
    resource = models.ForeignKey(Resource, on_delete=models.PROTECT)
    operation_type = models.CharField(max_length=100)  # e.g., 'send', 'update'
    status = models.CharField(max_length=100)  # e.g., 'pending', 'completed', 'failed'
    timestamp_sent = models.DateTimeField()  # When the operation was performed
    retransmit_counter = models.IntegerField(default=0)
    last_attempt = models.DateTimeField(auto_now=True)

class Firmware(models.Model):
    """Represents a firmware update file that can be downloaded by an endpoint."""
    version = models.CharField(max_length=100)
    file_name = models.CharField(max_length=255)
    download_url = models.URLField()
    created_at = models.DateTimeField(auto_now_add=True)
