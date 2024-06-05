from rest_framework import serializers
from ..models import ResourceType, Resource
from django.utils import timezone
import binascii
import struct
import logging

logger = logging.getLogger(__name__)


def decode_opaque_data(hex_value, data_type):
    if hex_value == '':
        return None
    if data_type == 'float':
        decoded = binascii.unhexlify(hex_value)
        return struct.unpack('>d', decoded)[0]
    elif data_type == 'long':
        decoded = binascii.unhexlify(hex_value)
        return struct.unpack('>l', decoded)[0]
    elif data_type == 'int':
        decoded = binascii.unhexlify(hex_value)
        return struct.unpack('>h', decoded)[0]
    elif data_type == 'string':
        return hex_value
    else:
        logger.error(f"Unsupported data type: {data_type}, data: {hex_value}")
        raise ValueError(f"Unsupported data type: {data_type}")


class ResourceDataSerializer(serializers.Serializer):
    KIND_CHOICES = [
        'singleResource',
        'multiResource',
    ]
    kind = serializers.ChoiceField(choices=KIND_CHOICES)
    id = serializers.IntegerField(help_text="Resource ID")
    TYPE_CHOICES = [
        ('TIME', 'Timestamp as integer'),
        ('STRING', 'String'),
        ('OPAQUE', 'Undefined data type'),
        ('INTEGER', 'Integer'),
        ('FLOAT', 'Float'),
        ('BOOLEAN', 'Boolean, internally stored as integer'),
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
    def handle_resource(self, device, obj_id, resource):
        res_id = resource['id']
        # Fetch resource information from Database
        resource_type = ResourceType.objects.get(object_id=obj_id, resource_id=res_id)
        if not resource_type:
            raise serializers.ValidationError(f"Resource type {obj_id}/{res_id} not found")

        logger.debug(f"Adding resource_type: {resource_type}")
        data_type = resource_type.data_type

        # Some LwM2M Resources have a OPAQUE type, which needs decoding
        if resource['kind'] == 'singleResource':
            if resource['type'] == 'OPAQUE':
                decoded_value = decode_opaque_data(resource['value'], data_type)
            else:
                decoded_value = resource['value']
        elif resource['kind'] == 'multiResource':
            logging.error(f"multiResource currently not supported, skipping...")
            decoded_value = None
        else:
            # TODO: Handle multiResource (Maybe json field in DB)
            logger.error(f"Unsupported resource kind: {resource['kind']}")
            raise serializers.ValidationError(f"Unsupported resource kind: {resource['kind']}")

        # Create the Resource instance based on value type
        resource_data = {
            'device': device,
            'resource_type': resource_type,
            'timestamp': timezone.now()
        }

        # Assign the decoded value to the appropriate field
        if data_type == 'float':
            resource_data['float_value'] = decoded_value
        elif data_type == 'integer':
            resource_data['int_value'] = decoded_value
        elif data_type == 'string':
            resource_data['str_value'] = decoded_value
        elif data_type == 'time':
            resource_data['int_value'] = decoded_value
        elif data_type == 'boolean':
            resource_data['int_value'] = decoded_value
        else:
            logger.error(f"Unsupported data type: {data_type}")
            raise serializers.ValidationError(f"Unsupported data type")

        Resource.objects.create(**resource_data)