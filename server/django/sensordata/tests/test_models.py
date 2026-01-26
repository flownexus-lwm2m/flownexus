#
# Copyright (c) 2024 Jonas Remmert
#
# SPDX-License-Identifier: Apache-2.0
#

from django.test import TestCase
from django.core.exceptions import ValidationError
from sensordata.models import Endpoint, ResourceType, Resource

class ModelTests(TestCase):
    def setUp(self):
        self.endpoint = Endpoint.objects.create(endpoint="test_device", registered=True)
        self.resource_type = ResourceType.objects.create(
            object_id=3303, 
            resource_id=5700, 
            name="Temperature", 
            data_type=ResourceType.FLOAT
        )

    def test_endpoint_str(self):
        self.assertEqual(str(self.endpoint), "test_device")

    def test_resource_type_str(self):
        self.assertEqual(str(self.resource_type), "3303/5700 - Temperature")

    def test_resource_creation(self):
        resource = Resource.objects.create(
            endpoint=self.endpoint,
            resource_type=self.resource_type,
            float_value=25.5
        )
        self.assertEqual(resource.get_value(), 25.5)
        self.assertIsNotNone(resource.timestamp_created)

    def test_resource_type_unique_together(self):
        with self.assertRaises(Exception): # IntegrityError
            ResourceType.objects.create(
                object_id=3303, 
                resource_id=5700, 
                name="Duplicate", 
                data_type=ResourceType.FLOAT
            )
