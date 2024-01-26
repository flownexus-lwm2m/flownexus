from django.contrib import admin
from django.db import models

class SensorData(models.Model):
    ep = models.CharField(max_length=100, default='')
    time = models.DateTimeField(auto_now_add=True)
    temperature = models.FloatField()

@admin.register(SensorData)
class SensorDataAdmin(admin.ModelAdmin):
   list_display = ['time', 'ep', 'temperature']
