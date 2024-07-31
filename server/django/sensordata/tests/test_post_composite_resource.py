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

TEST_PAYLOAD = {
  "ep" : "qemu_x86",
  "val" : {
    "instances" : [ {
      "kind" : "instance",
      "resources" : [ {
        "kind" : "singleResource",
        "id" : 0,
        "type" : "STRING",
        "value" : "Zephyr"
      }, {
        "kind" : "singleResource",
        "id" : 1,
        "type" : "STRING",
        "value" : "OMA-LWM2M Sample Client"
      }, {
        "kind" : "singleResource",
        "id" : 2,
        "type" : "STRING",
        "value" : "345000123"
      }, {
        "kind" : "singleResource",
        "id" : 3,
        "type" : "STRING",
        "value" : "1.0"
      }, {
        "kind" : "multiResource",
        "values" : {
          "0" : "1",
          "1" : "5"
        },
        "id" : 6,
        "type" : "INTEGER"
      }, {
        "kind" : "multiResource",
        "values" : {
          "0" : "3800",
          "1" : "5000"
        },
        "id" : 7,
        "type" : "INTEGER"
      }, {
        "kind" : "multiResource",
        "values" : {
          "0" : "125",
          "1" : "900"
        },
        "id" : 8,
        "type" : "INTEGER"
      }, {
        "kind" : "singleResource",
        "id" : 9,
        "type" : "INTEGER",
        "value" : "95"
      }, {
        "kind" : "singleResource",
        "id" : 10,
        "type" : "INTEGER",
        "value" : "15"
      }, {
        "kind" : "multiResource",
        "values" : {
          "0" : "0"
        },
        "id" : 11,
        "type" : "INTEGER"
      }, {
        "kind" : "singleResource",
        "id" : 13,
        "type" : "TIME",
        "value" : 2000
      }, {
        "kind" : "singleResource",
        "id" : 14,
        "type" : "STRING",
        "value" : ""
      }, {
        "kind" : "singleResource",
        "id" : 15,
        "type" : "STRING",
        "value" : ""
      }, {
        "kind" : "singleResource",
        "id" : 16,
        "type" : "STRING",
        "value" : "U"
      }, {
        "kind" : "singleResource",
        "id" : 17,
        "type" : "STRING",
        "value" : "qemu_x86"
      }, {
        "kind" : "singleResource",
        "id" : 18,
        "type" : "STRING",
        "value" : "1.0.1"
      }, {
        "kind" : "singleResource",
        "id" : 19,
        "type" : "STRING",
        "value" : ""
      }, {
        "kind" : "singleResource",
        "id" : 20,
        "type" : "INTEGER",
        "value" : "1"
      }, {
        "kind" : "singleResource",
        "id" : 21,
        "type" : "INTEGER",
        "value" : "25"
      } ],
      "id" : 0
    } ],
    "kind" : "obj",
    "id" : 3
  }
}

class SensorDataTests(TestCase):

    def setUp(self):
        # Ensure that all ResourceTypes object exist
        ResourceType.objects.create(object_id=3, resource_id=0,
                                    name="Manufacturer", data_type="str_value")

        ResourceType.objects.create(object_id=3, resource_id=1,
                                    name="Model Number", data_type="str_value")

        ResourceType.objects.create(object_id=3, resource_id=2,
                                    name="Serial Number", data_type="str_value")

        ResourceType.objects.create(object_id=3, resource_id=3,
                                    name="Firmware Version", data_type="str_value")

        ResourceType.objects.create(object_id=3, resource_id=6,
                                    name="Supported Objects", data_type="int_value")

        ResourceType.objects.create(object_id=3, resource_id=7,
                                    name="Supported Resources", data_type="int_value")

        ResourceType.objects.create(object_id=3, resource_id=8,
                                    name="Manufacturer ID", data_type="int_value")

        ResourceType.objects.create(object_id=3, resource_id=9,
                                    name="Memory Free", data_type="int_value")

        ResourceType.objects.create(object_id=3, resource_id=10,
                                    name="Error Code", data_type="int_value")

        ResourceType.objects.create(object_id=3, resource_id=11,
                                    name="Current Time", data_type="int_value")

        ResourceType.objects.create(object_id=3, resource_id=13,
                                    name="UTC Offset", data_type="int_value")

        ResourceType.objects.create(object_id=3, resource_id=14,
                                    name="Timezone", data_type="str_value")

        ResourceType.objects.create(object_id=3, resource_id=15,
                                    name="Supported Binding and Modes", data_type="str_value")

        ResourceType.objects.create(object_id=3, resource_id=16,
                                    name="Device Type", data_type="str_value")

        ResourceType.objects.create(object_id=3, resource_id=17,
                                    name="Hardware Version", data_type="str_value")

        ResourceType.objects.create(object_id=3, resource_id=18,
                                    name="Software Version", data_type="str_value")

        ResourceType.objects.create(object_id=3, resource_id=19,
                                    name="Battery Level", data_type="str_value")

        ResourceType.objects.create(object_id=3, resource_id=20,
                                    name="Battery Status", data_type="int_value")

        ResourceType.objects.create(object_id=3, resource_id=21,
                                    name="Memory Total", data_type="int_value")


    def test_post_composite_resource(self):

        url = reverse('post-composite-resource')

        response = self.client.post(url, TEST_PAYLOAD, content_type='application/json')

        # Check that the response is 201 Created
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
