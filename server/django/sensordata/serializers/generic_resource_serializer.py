from rest_framework import serializers
from ..models import Resource
from drf_spectacular.utils import extend_schema_field

class GenericResourceSerializer(serializers.ModelSerializer):
    resource_type = serializers.CharField(source='resource_type.name', read_only=True)
    value = serializers.SerializerMethodField()

    class Meta:
        model = Resource
        fields = ['timestamp_created', 'value', 'resource_type']

    @extend_schema_field(serializers.FloatField)
    def get_value(self, obj) -> float:
        return obj.get_value()
