from rest_framework import serializers
from .base import HandleResourceMixin, ResourceDataSerializer
from ..models import Device


class SingleResourceSerializer(HandleResourceMixin, serializers.Serializer):
    ep = serializers.CharField(max_length=255, help_text="Unique LwM2M Endpoint")
    obj_id = serializers.IntegerField(help_text="Object ID")
    val = ResourceDataSerializer()

    def create(self, validated_data):
        ep = validated_data['ep']
        obj_id = validated_data['obj_id']
        val = validated_data['val']

        # ep maps to Device.endpoint
        device, _ = Device.objects.get_or_create(endpoint=ep)
        self.handle_resource(device, obj_id, val)

        return device
