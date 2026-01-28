#
# Copyright (c) 2024 Jonas Remmert
#
# SPDX-License-Identifier: Apache-2.0
#


import pytest
from django.urls import reverse
from rest_framework import status

from sensordata.factories import ResourceTypeFactory
from sensordata.models import Resource, ResourceType


@pytest.mark.django_db
class TestPostCompositeResource:
    @pytest.fixture
    def setup_resource_types(self):
        resources = [
            (0, "Manufacturer", ResourceType.STRING),
            (1, "Model Number", ResourceType.STRING),
            (2, "Serial Number", ResourceType.STRING),
            (3, "Firmware Version", ResourceType.STRING),
            (6, "Supported Objects", ResourceType.INTEGER),
            (7, "Supported Resources", ResourceType.INTEGER),
            (8, "Manufacturer ID", ResourceType.INTEGER),
            (9, "Memory Free", ResourceType.INTEGER),
            (10, "Error Code", ResourceType.INTEGER),
            (11, "Current Time", ResourceType.INTEGER),
            (13, "UTC Offset", ResourceType.INTEGER),
            (14, "Timezone", ResourceType.STRING),
            (15, "Supported Binding and Modes", ResourceType.STRING),
            (16, "Device Type", ResourceType.STRING),
            (17, "Hardware Version", ResourceType.STRING),
            (18, "Software Version", ResourceType.STRING),
            (19, "Battery Level", ResourceType.STRING),
            (20, "Battery Status", ResourceType.INTEGER),
            (21, "Memory Total", ResourceType.INTEGER),
        ]
        for rid, name, dtype in resources:
            ResourceTypeFactory(object_id=3, resource_id=rid, name=name, data_type=dtype)

    def test_post_composite_resource(self, client, setup_resource_types):
        payload = {
            "ep": "urn:imei:100000000000000",
            "val": {
                "/3": {
                    "instances": [
                        {
                            "kind": "instance",
                            "resources": [
                                {
                                    "kind": "singleResource",
                                    "id": 0,
                                    "type": "STRING",
                                    "value": "Zephyr",
                                },
                                {
                                    "kind": "singleResource",
                                    "id": 21,
                                    "type": "INTEGER",
                                    "value": "25",
                                },
                            ],
                            "id": 0,
                        }
                    ],
                    "kind": "obj",
                    "id": 3,
                }
            },
        }

        url = reverse("post-composite-resource")
        response = client.post(url, payload, content_type="application/json")

        assert response.status_code == status.HTTP_201_CREATED
        assert Resource.objects.filter(endpoint__endpoint="urn:imei:100000000000000").count() == 2
