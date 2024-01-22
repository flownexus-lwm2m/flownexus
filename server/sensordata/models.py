from django.contrib import admin
from django.db import models

class TimeTemperature(models.Model):
    time = models.DateTimeField(auto_now_add=True)
    temperature = models.FloatField()

@admin.register(TimeTemperature)
class TimeTemperatureAdmin(admin.ModelAdmin):
   list_display = ['time', 'temperature']
