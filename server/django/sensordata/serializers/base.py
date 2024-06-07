from rest_framework import serializers
from ..models import ResourceType, Resource
from django.utils import timezone
import logging

logger = logging.getLogger(__name__)


class ResourceDataSerializer(serializers.Serializer):
    KIND_CHOICES = [
        'singleResource',
        'multiResource',
    ]
    kind = serializers.ChoiceField(choices=KIND_CHOICES)
    id = serializers.IntegerField(help_text="Resource ID")
    TYPE_CHOICES = [
        ('TIME', 'int_value'),
        ('STRING', 'str_value'),
        ('OPAQUE', 'Undefined data type'),
        ('INTEGER', 'int_value'),
        ('FLOAT', 'float_value'),
        ('BOOLEAN', 'int_value'),
    ]
    type = serializers.ChoiceField(choices=TYPE_CHOICES)
    value = serializers.CharField(max_length=255,
                                  required=False,
                                  allow_blank=True,
                                  help_text="The value associated with the resource,\
                                             type-dependent. Provide either the field\
                                             value or values"
    )
    values = serializers.DictField(child=serializers.CharField(max_length=255),
                                   required=False,
                                   allow_empty=True,
                                   help_text="The list of values associated with the resource.\
                                              Provide either the field value or values."
    )


class HandleResourceMixin:

    def handle_resource(self, endpoint, obj_id, resource):
        # Some LwM2M Resources are currently unsupported
        if resource['type'] == 'OPAQUE':
            logger.error(f"OPAQUE data type not supported, skipping...")
            return
        if resource['kind'] == 'multiResource':
            logging.error(f"multiResource currently not supported, skipping...")
            return

        res_id = resource['id']
        # Fetch resource information from Database
        resource_type = ResourceType.objects.get(object_id=obj_id, resource_id=res_id)
        if not resource_type:
            raise serializers.ValidationError(f"Resource type {obj_id}/{res_id} not found")

        data_type = resource_type.data_type

        # Convert TYPE_CHOICES to a dictionary for easy lookup
        type_to_field_map = dict(ResourceDataSerializer.TYPE_CHOICES)

        # Validate that datatype is matching the resource type
        lwm2m_type = type_to_field_map.get(resource['type'])
        if not lwm2m_type:
            logger.error(f"Unsupported data type '{resource['type']}', skipping...")
            return
        if lwm2m_type != data_type:
            raise serializers.ValidationError(
                f"Expected data type '{data_type}' for resource type "
                f"'{resource['type']}' but got '{lwm2m_type}'"
            )

        # Create the Resource instance based on value type
        logger.debug(f"Adding resource_type: {resource_type}")
        resource_data = {
            'endpoint': endpoint,
            'resource_type': resource_type,
            'timestamp': timezone.now(),
            data_type: resource['value']
        }

        # Update the registration status if the resource is a registration resource
        if resource_type.name == 'ep_registered':
            endpoint.registered = True
            endpoint.save()
        elif resource_type.name == 'ep_unregistered':
            endpoint.registered = False
            endpoint.save()

        Resource.objects.create(**resource_data)
