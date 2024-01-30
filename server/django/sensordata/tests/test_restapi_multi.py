from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase
from sensordata.models import SensorData
from sensordata.models import Endpoint
import binascii
import struct

TEST_PAYLOAD = [
    {
        "ep": "qemu_x86",
        "res": "3",
        "val": {
            "instances": [
                {
                    "kind": "instance",
                    "resources": [
                        {
                            "kind": "singleResource",
                            "id": 0,
                            "type": "STRING",
                            "value": "Zephyr"
                        },
                        {
                            "kind": "singleResource",
                            "id": 1,
                            "type": "STRING",
                            "value": "OMA-LWM2M Sample Client"
                        },
                        {
                            "kind": "singleResource",
                            "id": 2,
                            "type": "STRING",
                            "value": "345000123"
                        },
                        {
                            "kind": "singleResource",
                            "id": 3,
                            "type": "STRING",
                            "value": "1.0"
                        },
                        {
                            "kind": "multiResource",
                            "values": {
                                "0": "1",
                                "1": "5"
                            },
                            "id": 6,
                            "type": "INTEGER"
                        },
                        {
                            "kind": "multiResource",
                            "values": {
                                "0": "3800",
                                "1": "5000"
                            },
                            "id": 7,
                            "type": "INTEGER"
                        },
                        {
                            "kind": "multiResource",
                            "values": {
                                "0": "125",
                                "1": "900"
                            },
                            "id": 8,
                            "type": "INTEGER"
                        },
                        {
                            "kind": "singleResource",
                            "id": 9,
                            "type": "INTEGER",
                            "value": "95"
                        },
                        {
                            "kind": "singleResource",
                            "id": 10,
                            "type": "INTEGER",
                            "value": "15"
                        },
                        {
                            "kind": "multiResource",
                            "values": {
                                "0": "0"
                            },
                            "id": 11,
                            "type": "INTEGER"
                        },
                        {
                            "kind": "singleResource",
                            "id": 13,
                            "type": "TIME",
                            "value": 1000
                        },
                        {
                            "kind": "singleResource",
                            "id": 14,
                            "type": "STRING",
                            "value": ""
                        },
                        {
                            "kind": "singleResource",
                            "id": 15,
                            "type": "STRING",
                            "value": ""
                        },
                        {
                            "kind": "singleResource",
                            "id": 16,
                            "type": "STRING",
                            "value": "U"
                        },
                        {
                            "kind": "singleResource",
                            "id": 17,
                            "type": "STRING",
                            "value": "qemu_x86"
                        },
                        {
                            "kind": "singleResource",
                            "id": 18,
                            "type": "STRING",
                            "value": "1.0.1"
                        },
                        {
                            "kind": "singleResource",
                            "id": 19,
                            "type": "STRING",
                            "value": ""
                        },
                        {
                            "kind": "singleResource",
                            "id": 20,
                            "type": "INTEGER",
                            "value": "1"
                        },
                        {
                            "kind": "singleResource",
                            "id": 21,
                            "type": "INTEGER",
                            "value": "25"
                        }
                    ],
                    "id": 0
                }
            ],
            "kind": "obj",
            "id": 3
        }
    }
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
            #self.assertEqual(Endpoint.objects.count(), 1)

            self.assertEqual(Endpoint.objects.get().endpoint, pl['ep'])
            self.assertEqual(Endpoint.objects.get().manufacturer, pl['val']['instances'][0]['resources'][0]['value'])
            self.assertEqual(Endpoint.objects.get().model_number, pl['val']['instances'][0]['resources'][1]['value'])
            self.assertEqual(Endpoint.objects.get().serial_number, pl['val']['instances'][0]['resources'][2]['value'])
            self.assertEqual(Endpoint.objects.get().firmware_version, pl['val']['instances'][0]['resources'][3]['value'])
            self.assertEqual(Endpoint.objects.get().battery_level, (int)(pl['val']['instances'][0]['resources'][7]['value']))

            Endpoint.objects.all().delete()
