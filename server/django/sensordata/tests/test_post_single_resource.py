from django.urls import reverse
from rest_framework import status
from django.test import TestCase
from sensordata.models import (
    ResourceType,
    Resource,
)

TEST_PAYLOAD = {
        "ep": "qemu_x86",
        "obj_id": 3303,
        "val": {
            "kind": "singleResource",
            "id": 5700,
            "type": "FLOAT",
            "value": "24.899181214836236"
        }
}

class SensorDataTests(TestCase):

    def setUp(self):
        # Ensure that the ResourceType object exists
        ResourceType.objects.create(object_id=3303, resource_id=5700,
                                    name="temperature", data_type="float_value")

    def test_post_single_resource(self):
        url = reverse('post-single-resource')

        response = self.client.post(url, TEST_PAYLOAD, content_type='application/json')

        # Check that the response is 201 Created
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)

        # Query the database to retrieve the created object
        created_object = Resource.objects.get(
            resource_type__object_id = TEST_PAYLOAD["obj_id"],
            resource_type__resource_id = TEST_PAYLOAD["val"]["id"],
            endpoint__endpoint= TEST_PAYLOAD["ep"]
        )

        # Compare the retrieved object's attributes to the expected values
        self.assertEqual(created_object.endpoint.endpoint, TEST_PAYLOAD["ep"])
        self.assertEqual(created_object.resource_type.object_id, TEST_PAYLOAD["obj_id"])
        self.assertEqual(created_object.resource_type.resource_id, TEST_PAYLOAD["val"]["id"])

        self.assertEqual(created_object.resource_type.data_type, "float_value")
        self.assertEqual(created_object.float_value, float(TEST_PAYLOAD["val"]["value"]))
