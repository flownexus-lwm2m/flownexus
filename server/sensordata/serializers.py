from rest_framework import serializers
from .models import TimeTemperature

class TimeTemperatureSerializer(serializers.ModelSerializer):
    class Meta:
        model = TimeTemperature
        fields = ['id', 'time', 'temperature']
