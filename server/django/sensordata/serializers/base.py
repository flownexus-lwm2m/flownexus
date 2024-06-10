from rest_framework import serializers
from ..models import ResourceType, Resource
from django.utils import timezone
from ..tasks import process_pending_operations
import logging

logger = logging.getLogger(__name__)


class ResourceDataSerializer(serializers.Serializer):
    KIND_CHOICES = [
        'singleResource',
        'multiResource',
    ]
    kind = serializers.ChoiceField(choices=KIND_CHOICES)
    id = serializers.IntegerField(help_text="Resource ID")
    type = serializers.ChoiceField(choices=ResourceType.TYPE_CHOICES)
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
        # Some LwM2M Resources are currently unsupported, we can skip them for now.
        if resource['kind'] == 'multiResource':
            logging.error(f"multiResource currently not supported, skipping...")
            return

        res_id = resource['id']
        # Fetch resource information from Database
        resource_type = ResourceType.objects.get(object_id=obj_id, resource_id=res_id)
        if not resource_type:
            err = f"Resource type {obj_id}/{res_id} not found"
            logger.error(err)
            raise serializers.ValidationError(err)

        # Validate that datatype is matching the resource type
        data_type = dict(ResourceType.TYPE_CHOICES).get(resource['type'])
        res_data_type = dict(ResourceType.TYPE_CHOICES).get(resource_type.data_type)
        if not data_type:
            err = f"Unsupported data type '{resource['type']}', skipping..."
            logger.error(err)
            raise serializers.ValidationError(err)
        if data_type != res_data_type:
            err = f"Mismatch between ResourceType.data_type '{res_data_type}' " \
                  f"and Resource value type '{data_type}'"
            logger.error(err)
            raise serializers.ValidationError(err)

        # Create the Resource instance based on value type
        logger.debug(f"Adding resource_type: {resource_type}")
        resource_data = {
            'endpoint': endpoint,
            'resource_type': resource_type,
            'timestamp': timezone.now(),
            data_type: resource['value']
        }

        Resource.objects.create(**resource_data)

        # Update the registration status if the resource is a registration resource
        if resource_type.name == 'ep_registered':
            endpoint.registered = True
            endpoint.save()
        elif resource_type.name == 'ep_unregistered':
            endpoint.registered = False
            endpoint.save()
        elif resource_type.name == 'ep_registration_update':
            # Check and process if there are pending messages that have not reached
            # the endpoint yet.
            process_pending_operations.delay(endpoint.endpoint)
