from rest_framework import serializers
from .base import HandleResourceMixin, ResourceDataSerializer
from ..models import Endpoint


class SingleResourceSerializer(HandleResourceMixin, serializers.Serializer):
    ep = serializers.CharField(max_length=255, help_text="Unique LwM2M Endpoint")
    obj_id = serializers.IntegerField(help_text="Object ID")
    val = ResourceDataSerializer()

    def create(self, validated_data):
        ep = validated_data['ep']
        obj_id = validated_data['obj_id']
        val = validated_data['val']

        endpoint, _ = Endpoint.objects.get_or_create(endpoint=ep)
        try:
            self.handle_resource(endpoint, obj_id, val)
        except serializers.ValidationError as e:
            # Re-raise the validation error to be handled by Django's validation system
            raise e

        return endpoint
