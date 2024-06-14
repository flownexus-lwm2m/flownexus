from rest_framework import serializers
from .base import HandleResourceMixin, ResourceDataSerializer
from ..models import Endpoint
import logging

logger = logging.getLogger(__name__)


class InstanceSerializer(serializers.Serializer):
    resources = ResourceDataSerializer(many=True)
    KIND_CHOICES = [
        'instance',
    ]
    kind = serializers.ChoiceField(choices=KIND_CHOICES)
    id = serializers.IntegerField(help_text="Instance Counter")


class ObjectSerializer(serializers.Serializer):
    instances = InstanceSerializer(many=True, required=False)
    KIND_CHOICES = [
        'obj',
    ]
    kind = serializers.ChoiceField(choices=KIND_CHOICES)
    id = serializers.IntegerField(help_text="Object ID")


class ValueSerializer(serializers.Serializer):
    # Annotation for Django Rest Framework for documentation generation
    objects = serializers.ListField(
        child=ObjectSerializer(),
        help_text="List of LwM2M objects"
    )

    def to_representation(self, instance):
        ret = {}
        for key, value in instance.items():
            serializer = ObjectSerializer(value, context=self.context)
            ret[key] = serializer.data
        return ret

    def to_internal_value(self, data):
        ret = {}
        for key, value in data.items():
            serializer = ObjectSerializer(data=value, context=self.context)
            serializer.is_valid(raise_exception=True)
            ret[key] = serializer.validated_data
        return ret


class CompositeResourceSerializer(HandleResourceMixin, serializers.Serializer):
    ep = serializers.CharField(max_length=255, help_text="Unique LwM2M Endpoint")
    val = ValueSerializer()

    def create(self, validated_data):
        ep = validated_data['ep']
        val = validated_data['val']

        endpoint, _ = Endpoint.objects.get_or_create(endpoint=ep)

        for _, obj in val.items():
            obj_id = obj.get('id')
            self.create_event(endpoint, obj_id)
            for instance in obj['instances']:
                for resource in instance['resources']:
                    try:
                        self.handle_resource(endpoint, obj_id, resource)
                    except serializers.ValidationError as e:
                        # Re-raise the validation error to be handled by
                        # Django's validation system
                        raise e

        return endpoint
