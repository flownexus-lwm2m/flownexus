#
# Copyright (c) 2024 Jonas Remmert
#
# SPDX-License-Identifier: Apache-2.0
#

import pytest
from django.urls import reverse

from sensordata.factories import EndpointFactory, UserFactory


@pytest.mark.django_db
class TestFrontendViews:
    def test_dashboard_requires_login(self, client):
        url = reverse("frontend:dashboard")
        response = client.get(url)
        assert response.status_code == 302

    def test_dashboard_with_data(self, client):
        user = UserFactory()
        client.force_login(user)

        # Create synthetic data
        EndpointFactory.create_batch(5)

        url = reverse("frontend:dashboard")
        response = client.get(url)

        assert response.status_code == 200
        # Check if endpoints are in context
        assert len(response.context["endpoints"]) == 5
        # Check for Tabler specific elements or just basic content
        assert b"Dashboard" in response.content
