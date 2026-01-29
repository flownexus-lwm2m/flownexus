#
# Copyright (c) 2024 Jonas Remmert
#
# SPDX-License-Identifier: Apache-2.0
#
import os
import sys

# Add project root to sys.path to find simulation package
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "../../../../")))


from django.test import LiveServerTestCase, override_settings

from sensordata.models import Endpoint, Resource
from simulation.backend.mock import MockBackend


@override_settings(CELERY_TASK_ALWAYS_EAGER=True, CELERY_TASK_EAGER_PROPAGATES=True)
class MockSimulationIntegrationTest(LiveServerTestCase):
    fixtures = ["db_initial_resource_types.json"]

    def test_mock_simulation_ingestion(self):
        """
        Verify that the MockBackend can register devices and push telemetry
        to a live Django server.
        """
        config = {
            "type": "mock",
            "url": f"{self.live_server_url}/flownexus/ingest",
            "device_count": 2,
            "interval": 0.1,
            "duration": 0.5,  # Run for 0.5 seconds
        }

        backend = MockBackend(config)

        # This will block until duration is reached or keyboard interrupt
        # Since we set duration=0.5, it should return fairly quickly.
        backend.start()

        # Verify Endpoints were created
        self.assertEqual(Endpoint.objects.count(), 2)

        # Verify Resources (Telemetry) were created
        # Each device sends 2 resources per interval.
        # With 0.5s duration and 0.1s interval, we expect ~5-6 ticks.
        # Plus 1 registration resource per device.
        # We just check if at least some resources exist.
        self.assertGreater(Resource.objects.count(), 4)

        # Verify specific resource types (3303 and 3304)
        temp_resources = Resource.objects.filter(resource_type__object_id=3303)
        self.assertGreater(temp_resources.count(), 0)

        hum_resources = Resource.objects.filter(resource_type__object_id=3304)
        self.assertGreater(hum_resources.count(), 0)

        print(
            f"Verified {Endpoint.objects.count()} endpoints and "
            f"{Resource.objects.count()} resources."
        )
