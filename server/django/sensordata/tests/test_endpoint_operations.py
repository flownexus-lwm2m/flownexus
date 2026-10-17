#
# Copyright (c) 2026 Jonas Remmert
#
# SPDX-License-Identifier: Apache-2.0
#

import pytest
from django.urls import reverse
from rest_framework import status

from sensordata.factories import EndpointFactory, ResourceFactory, ResourceTypeFactory
from sensordata.models import EndpointOperation


@pytest.mark.django_db
class TestEndpointOperations:
    @pytest.fixture
    def resource(self):
        resource_type = ResourceTypeFactory(object_id=3, resource_id=14, name="utc_offset")
        return ResourceFactory(
            endpoint=EndpointFactory(endpoint="urn:imei:operation-device"),
            resource_type=resource_type,
            str_value="+02:00",
        )

    def test_create_operation_is_queued(self, client, resource):
        url = reverse("endpoint-operations", args=[resource.endpoint.endpoint])
        payload = {"resource": resource.id, "operation_type": "send"}

        response = client.post(url, payload, content_type="application/json")

        assert response.status_code == status.HTTP_201_CREATED
        operation = EndpointOperation.objects.get()
        assert operation.resource_id == resource.id
        assert operation.status == EndpointOperation.Status.QUEUED

    def test_create_operation_rejects_resource_from_another_endpoint(self, client, resource):
        other_resource = ResourceFactory(
            endpoint=EndpointFactory(endpoint="urn:imei:other-operation-device"),
            resource_type=resource.resource_type,
            str_value="+03:00",
        )
        url = reverse("endpoint-operations", args=[resource.endpoint.endpoint])

        response = client.post(
            url,
            {"resource": other_resource.id, "operation_type": "send"},
            content_type="application/json",
        )

        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert response.json() == {"resource": "Resource does not belong to this endpoint."}
        assert not EndpointOperation.objects.exists()
