from rest_framework import serializers
from .models import SensorData, Endpoint
import binascii
import struct
import logging
import json

logger = logging.getLogger(__name__)

class GenericLWM2MSerializer(serializers.Serializer):
    """
    A serializer for generic handling and persistence of sensor data received from an
    LwM2M server. Primarily designed to iterate over the varying data representation
    sent by different types of sensors and store them in the SensorData model.

    Check test_restapi.py for example payloads.
    """

    ep = serializers.CharField()
    res = serializers.CharField()
    val = serializers.JSONField()

    # Define the path to property and type mapping. Others will be ignored.
    path_mapping = {
        '3': {  # Device Object ID
            '0': {'field': 'manufacturer', 'type': 'string'},
            '1': {'field': 'model_number', 'type': 'string'},
            '2': {'field': 'serial_number', 'type': 'string'},
            '3': {'field': 'firmware_version', 'type': 'string'},
            '4': {'field': 'reboot', 'type': 'int'},
            '5': {'field': 'factory_reset', 'type': 'int'},
            '9': {'field': 'battery_level', 'type': 'int'},
            '10': {'field': 'memory_free', 'type': 'int'},
        },
        '3303': {  # Temperature Object ID
            '5700': {'field': 'temperature', 'type': 'float'},
        },
    }

    def deserialize_sensor_data(self, json_string):
        logger.info("deserializer: deserialize_sensor_data")
        # Pretty print
        logger.debug(json_string)

        data = json.loads(json_string)
        sensor_data = {}

        sensor_data['endpoint'] = data['ep']

        resource_path = data['res']

        if '/' in resource_path:
            paths = resource_path.strip('/').split('/')
            object_id = paths[0]
            # Handle possible index, e.g., /3303/0/5700 -> Object ID: 3303, Index: 0, Resource ID: 5700
            resource_id = paths[-1]
        else:
            object_id = resource_path

        object_path_mapping = self.path_mapping.get(object_id, {})

        if 'val' in data and isinstance(data['val'], dict):
            data_resources = data['val'].get('instances', [data['val']])
            #logger.debug(f"deserializer: Data resources: {data_resources}")

            for instance in data_resources:
                resources = instance.get('resources', []) if instance.get('resources') else [instance]
                for resource in resources:
                    resource_id = str(resource['id'])
                    if resource_id in object_path_mapping:
                        field_info = object_path_mapping[resource_id]
                        field_name = field_info['field']
                        # If the resource kind is 'singleResource' or the value is directly available
                        if resource.get('kind') == 'singleResource' or 'value' in resource:
                            if field_info['type'] == 'float':
                                sensor_data[field_name] = self.decode_value(resource['value'],
                                                                            field_info['type'])
                            elif field_info['type'] == 'int':
                                sensor_data[field_name] = (int)(resource['value'])
                            else:
                                sensor_data[field_name] = resource['value']

        return sensor_data


    def decode_value(self, hex_value, data_type):
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
        else:
            raise ValueError(f"Unsupported data type: {data_type}")


    def create(self, data):
        data_deser = self.deserialize_sensor_data(json.dumps(data, indent=4))

        sensor_data = {}
        endpoint_data = {}

        # Decide based on the individual field name whether it is  a SensorData or
        # Endpoint object and create it. Generic method to handle both types of objects.
        sensor_data_field_names = [field.name for field in SensorData._meta.get_fields()]
        endpoint_data_field_names = [field.name for field in Endpoint._meta.get_fields()]

        for field_name, field_value in data_deser.items():
            if field_name in sensor_data_field_names:
                sensor_data[field_name] = field_value
            if field_name in endpoint_data_field_names:
                endpoint_data[field_name] = field_value

        # Only add if more than the endpoint could be mapped (actual sensor data)
        if len(endpoint_data) > 1:
            logger.debug(f"deserializer: Endpoint data: {json.dumps(endpoint_data, indent=4)}")

            unique_field = 'endpoint'
            unique_field_value = endpoint_data.pop(unique_field)

            ep_ret = Endpoint.objects.update_or_create(
                **{unique_field: unique_field_value},
                defaults=endpoint_data
            )
        else:
            ep_ret = None

        # Only add if more than the endpoint could be mapped (actual sensor data)
        if len(sensor_data) > 1:
            sd_ret = SensorData.objects.create(**sensor_data)
            logger.debug(f"deserializer: Sensor data: {json.dumps(sensor_data, indent=4)}")
        else:
            sd_ret = None

        return (sd_ret, ep_ret)
