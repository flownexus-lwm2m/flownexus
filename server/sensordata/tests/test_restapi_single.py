from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase
from sensordata.models import SensorData
import binascii
import struct


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

    def convert_hex_to_double(self, hex_value):
        try:
            return struct.unpack('>d', binascii.unhexlify(hex_value))[0]
        except binascii.Error as e:
            raise ValueError(f"Hexadecimal to binary conversion failed: {e}")
        except struct.error as e:
            raise ValueError(f"Binary to double unpacking failed: {e}")

    def test_create_sensor_data_from_json_payloads(self):
        """
        Ensure we can create new sensor data objects using given JSON payloads.
        """
        url = reverse('add_sensor_data')

        for pl in TEST_PAYLOAD:
            response = self.client.post(url, pl, format='json')

            self.assertEqual(response.status_code, status.HTTP_201_CREATED)

            self.assertEqual(SensorData.objects.count(), 1)
            self.assertEqual(SensorData.objects.get().endpoint, pl['ep'])
            expected_temperature = self.convert_hex_to_double(pl['val']['value'])
            self.assertEqual(SensorData.objects.get().temperature, expected_temperature)

            SensorData.objects.all().delete()
