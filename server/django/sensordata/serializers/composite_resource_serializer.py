from rest_framework import serializers
from .base import HandleResourceMixin, ResourceDataSerializer
from ..models import Device
import logging

logger = logging.getLogger(__name__)


class InstanceSerializer(serializers.Serializer):
    resources = ResourceDataSerializer(many=True)
    KIND_CHOICES = [
        'instance',
    ]
    kind = serializers.ChoiceField(choices=KIND_CHOICES)
    id = serializers.IntegerField(help_text="Instance Counter")


class ValueSerializer(serializers.Serializer):
    instances = InstanceSerializer(many=True, required=False)
    KIND_CHOICES = [
        'obj',
    ]
    kind = serializers.ChoiceField(choices=KIND_CHOICES)
    id = serializers.IntegerField(help_text="Object ID")


class CompositeResourceSerializer(HandleResourceMixin, serializers.Serializer):
    ep = serializers.CharField(max_length=255, help_text="Unique LwM2M Endpoint")
    val = ValueSerializer()

    def create(self, validated_data):
        ep = validated_data['ep']
        val = validated_data['val']

        # ep maps to Device.endpoint
        device, _ = Device.objects.get_or_create(endpoint=ep)

        # Check if value is an object with instances (Composite resource)
        if val['kind'] == 'obj':
            obj_id = val.get('id')
            for instance in val['instances']:
                for resource in instance['resources']:
                    self.handle_resource(device, obj_id, resource)
        else:
            logger.error("Expected composite resource data.")
            raise serializers.ValidationError("Expected composite resource data.")

        return device
