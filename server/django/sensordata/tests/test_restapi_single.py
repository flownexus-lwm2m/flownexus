import binascii
import struct
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase
from sensordata.models import (
    Device,
    ResourceType,
    Resource,
)


TEST_PAYLOAD = [
    {
        "ep": "qemu_x86",
        "res": "/3303/0/5700",
        "val": {
            "kind": "singleResource",
            "id": 5700,
            "type": "OPAQUE",
            "value": "40370838ac4f0838"
        }
    },
]

class SensorDataTests(APITestCase):

    def test_create_sensor_data_from_json_payloads(self):
        """
        Ensure we can create new sensor data objects using given JSON payloads.
        """
        self.url = reverse('add_sensor_data')

        response = self.client.post(self.url, TEST_PAYLOAD, format='json')
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)

        for pl in TEST_PAYLOAD:
            ep = pl['ep']
            res = pl['res']
            val = pl['val']

            # Verify the Device was created
            device = Device.objects.get(device_id=ep)
            self.assertIsNotNone(device)
            self.assertEqual(device.name, ep)

            # Parse resource path to get object_id and resource_id
            resource_path_parts = res.strip('/').split('/')
            object_id = int(resource_path_parts[0])
            resource_id = int(resource_path_parts[2])

            # Verify the ResourceType was created
            resource_type = ResourceType.objects.get(object_id=object_id, resource_id=resource_id)
            self.assertIsNotNone(resource_type)

            # Verify the Resource was created
            resource = Resource.objects.get(device=device, resource_type=resource_type)
            self.assertIsNotNone(resource)

            # Check values based on the type
            self.assertEqual(resource.resource_type.data_type, 'float')
            decoded_value = struct.unpack('>d', binascii.unhexlify(val['value']))[0]
            self.assertEqual(resource.float_value, decoded_value)
