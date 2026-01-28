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
class TestPostSingleResource:
    def test_post_single_resource(self, client):
        # Setup ResourceType
        ResourceTypeFactory(
            object_id=3303, resource_id=5700, name="temperature", data_type=ResourceType.FLOAT
        )

        payload = {
            "ep": "qemu_x86",
            "obj_id": 3303,
            "val": {"kind": "singleResource", "id": 5700, "type": "FLOAT", "value": "24.899"},
        }

        url = reverse("post-single-resource")
        response = client.post(url, payload, content_type="application/json")

        assert response.status_code == status.HTTP_201_CREATED

        # Verify DB
        created_resource = Resource.objects.get(
            endpoint__endpoint="qemu_x86",
            resource_type__object_id=3303,
            resource_type__resource_id=5700,
        )
        assert created_resource.float_value == 24.899
