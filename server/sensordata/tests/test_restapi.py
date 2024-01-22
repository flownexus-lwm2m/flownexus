from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase
from sensordata.models import TimeTemperature

class TimeTemperatureTests(APITestCase):

    def test_create_timetemperature(self):
        """
        Ensure we can create a new time and temperature object.
        """
        url = reverse('timetemperature-list')
        data = {'temperature': 22.5}
        response = self.client.post(url, data, format='json')

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(TimeTemperature.objects.count(), 1)
        self.assertEqual(TimeTemperature.objects.get().temperature, 22.5)
