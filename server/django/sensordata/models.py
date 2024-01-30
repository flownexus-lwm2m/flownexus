from django.contrib import admin
from django.db import models

class Endpoint(models.Model):
    endpoint = models.CharField(max_length=100, default='', unique=True)
    manufacturer = models.CharField(max_length=100, default='')
    model_number = models.CharField(max_length=100, default='')
    serial_number = models.CharField(max_length=100, default='')
    firmware_version = models.CharField(max_length=100, default='')
    reboot = models.IntegerField(default=0)
    factory_reset = models.IntegerField(default=0)
    battery_level = models.IntegerField(default=0)
    last_updated = models.DateTimeField(auto_now=True)

class SensorData(models.Model):
    endpoint = models.CharField(max_length=100, default='')
    time = models.DateTimeField(auto_now_add=True)
    temperature = models.FloatField()

@admin.register(SensorData)
class SensorDataAdmin(admin.ModelAdmin):
    list_display = [
        'time',
        'endpoint',
        'temperature',
    ]

@admin.register(Endpoint)
class EndpointAdmin(admin.ModelAdmin):
    list_display = [
        'endpoint',
        'serial_number',
        'model_number',
        'firmware_version',
        'reboot',
        'last_updated',
    ]
