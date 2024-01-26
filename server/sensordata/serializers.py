from rest_framework import serializers
from .models import SensorData
import binascii
import struct
import logging

logger = logging.getLogger(__name__)

class GenericLWM2MSerializer(serializers.Serializer):
    """
    A serializer for generic handling and persistence of sensor data received from an
    LwM2M server. Primarily designed to iterate over the varying data representation
    sent by different types of sensors and store them in the SensorData model.

    Example:
        DataSenderRest: {"ep":"qemu_x86","kind":"single","res":"/3303/0/5700","val":{
         "kind" : "singleResource",
         "id" : 5700,
         "type" : "OPAQUE",
         "value" : "4037d66b8376d66b"
        }},
    """

    ep = serializers.CharField()
    res = serializers.CharField()
    val = serializers.JSONField()

    # Define the path to property and type mapping
    path_mapping = {
        '/3303/0/5700': {'field': 'temperature', 'type': 'float'},
        # Add more paths with corresponding field names and types here...
    }

    def decode_value(self, hex_value, data_type):
        # Decode value based on its expected type
        if data_type == 'float':
            # Assuming 8 bytes for double precision, big-endian byte order
            decoded = binascii.unhexlify(hex_value)
            return struct.unpack('>d', decoded)[0]
        elif data_type == 'long':
            # Assuming 4 bytes for long int, big-endian byte order
            decoded = binascii.unhexlify(hex_value)
            return struct.unpack('>l', decoded)[0]
        elif data_type == 'string':
            # Assuming hex-encoded ASCII string
            return binascii.unhexlify(hex_value).decode('ascii')
        # More types can be added here as needed
        else:
            raise ValueError(f"Unsupported data type: {data_type}")

    def create(self, validated_data):
        logger.info("serializer: create")
        val_data = validated_data.pop('val')
        resource_path = self.path_mapping.get(validated_data.get('res'), None)

        if not resource_path:
            raise ValueError(f"No mapping found for resource path: {validated_data.get('res')}")

        value_type = resource_path['type']
        field_name = resource_path['field']
        value = val_data.get('value')
        if val_data.get('type') == 'OPAQUE' and isinstance(value, str):
            # Decode the value using the type specified in the path_mapping
            value = self.decode_value(value, value_type)

        # Assuming `SensorData` has a specific field for each data type
        # Given field_name, we set the value dynamically
        data = {
            'ep': validated_data.get('ep'),
            field_name: value,
        }

        # We directly pass 'data' here to unpack field and value.
        time_temperature = SensorData.objects.create(**data)
        return time_temperature
