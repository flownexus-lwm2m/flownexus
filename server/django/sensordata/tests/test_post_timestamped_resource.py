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
class TestPostTimestampedResource:
    @pytest.fixture
    def setup_resource_types(self):
        ResourceTypeFactory(
            object_id=3303, resource_id=5700, name="temperature", data_type=ResourceType.FLOAT
        )
        ResourceTypeFactory(
            object_id=3304, resource_id=5700, name="humidity", data_type=ResourceType.FLOAT
        )
        ResourceTypeFactory(
            object_id=10300, resource_id=0, name="counter", data_type=ResourceType.INTEGER
        )

    def test_post_timestamped_resource(self, client, setup_resource_types):
        payload = {
            "ep": "urn:imei:100000000000000",
            "val": [
                {
                    "null": {
                        "nodes": {
                            "/3303/0/5700": {
                                "kind": "singleResource",
                                "id": 5700,
                                "type": "FLOAT",
                                "value": "20.14",
                            }
                        }
                    }
                }
            ],
        }

        url = reverse("post-timestamped-resource")
        response = client.post(url, payload, content_type="application/json")

        assert response.status_code == status.HTTP_201_CREATED
        assert Resource.objects.filter(endpoint__endpoint="urn:imei:100000000000000").count() == 1
