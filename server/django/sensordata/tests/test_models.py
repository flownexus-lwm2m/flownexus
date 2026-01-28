#
# Copyright (c) 2024 Jonas Remmert
#
# SPDX-License-Identifier: Apache-2.0
#

import pytest
from django.db import IntegrityError

from sensordata.factories import EndpointFactory, ResourceFactory, ResourceTypeFactory
from sensordata.models import ResourceType


@pytest.mark.django_db
class TestModels:
    def test_endpoint_str(self):
        endpoint = EndpointFactory(endpoint="urn:imei:12345")
        assert str(endpoint) == "urn:imei:12345"

    def test_resource_type_str(self):
        rt = ResourceTypeFactory(object_id=3303, resource_id=5700, name="Temp")
        assert str(rt) == "3303/5700 - Temp"

    def test_resource_creation(self):
        resource = ResourceFactory(float_value=25.5)
        assert resource.get_value() == 25.5
        assert resource.timestamp_created is not None

    def test_resource_type_unique_together(self):
        ResourceTypeFactory(object_id=3303, resource_id=5700)
        with pytest.raises(IntegrityError):
            ResourceType.objects.create(
                object_id=3303, resource_id=5700, name="Duplicate", data_type=ResourceType.FLOAT
            )
