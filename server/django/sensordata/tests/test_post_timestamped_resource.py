#
# Copyright (c) 2024 Jonas Remmert
#
# SPDX-License-Identifier: Apache-2.0
#

from django.urls import reverse
from rest_framework import status
from django.test import TestCase
from sensordata.models import (
    ResourceType,
)

TEST_PAYLOAD = '''
{
  "ep": "urn:imei:100000000000000",
  "val": [
    {
      "null": {
        "nodes": {
          "/3303/0/5700": {
            "kind": "singleResource",
            "id": 5700,
            "type": "FLOAT",
            "value": "20.145982801948204"
          },
          "/3304/0/5700": {
            "kind": "singleResource",
            "id": 5700,
            "type": "FLOAT",
            "value": "51.200783720985235"
          }
        }
      }
    },
    {
      "2024-09-13T19:06:17.032059888Z": {
        "nodes": {
          "/10300/0/0": {
            "kind": "singleResource",
            "id": 0,
            "type": "INTEGER",
            "value": "8"
          }
        }
      }
    },
    {
      "2024-09-13T19:06:18.032059888Z": {
        "nodes": {
          "/10300/0/0": {
            "kind": "singleResource",
            "id": 0,
            "type": "INTEGER",
            "value": "9"
          }
        }
      }
    },
    {
      "2024-09-13T19:06:19.032059888Z": {
        "nodes": {
          "/10300/0/0": {
            "kind": "singleResource",
            "id": 0,
            "type": "INTEGER",
            "value": "10"
          }
        }
      }
    }
  ]
}
'''


class SensorDataTests(TestCase):

    def setUp(self):
        # Ensure that all ResourceTypes object exist
        ResourceType.objects.create(object_id=3303, resource_id=5700,
                                    name="temperature", data_type=ResourceType.FLOAT)
        ResourceType.objects.create(object_id=3304, resource_id=5700,
                                    name="humidity", data_type=ResourceType.FLOAT)
        ResourceType.objects.create(object_id=10300, resource_id=0,
                                    name="humidity", data_type=ResourceType.INTEGER)


    def test_post_composite_resource(self):

        url = reverse('post-timestamped-resource')

        response = self.client.post(url, TEST_PAYLOAD, content_type='application/json')

        # Check that the response is 201 Created
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
