#
# Copyright (c) 2024 Jonas Remmert
#
# SPDX-License-Identifier: Apache-2.0
#

from django.contrib.auth.models import User
from django.test import Client, TestCase
from django.urls import reverse


class FrontendViewTests(TestCase):
    def setUp(self):
        self.client = Client()
        self.user = User.objects.create_user(username="testuser", password="testpassword")

    def test_admin_dashboard_requires_login(self):
        response = self.client.get(reverse("admin_dashboard"))
        self.assertEqual(response.status_code, 302)  # Should redirect to login

    def test_admin_dashboard_authenticated(self):
        self.client.login(username="testuser", password="testpassword")
        response = self.client.get(reverse("admin_dashboard"))
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "frontend/admin_dashboard.html")

    def test_device_dashboard_authenticated(self):
        self.client.login(username="testuser", password="testpassword")
        response = self.client.get(reverse("device_dashboard"))
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "frontend/device_dashboard.html")

    def test_event_dashboard_authenticated(self):
        self.client.login(username="testuser", password="testpassword")
        response = self.client.get(reverse("event_dashboard"))
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "frontend/event_dashboard.html")

    def test_firmware_dashboard_authenticated(self):
        self.client.login(username="testuser", password="testpassword")
        response = self.client.get(reverse("firmware_dashboard"))
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "frontend/firmware_dashboard.html")

    def test_license_dashboard_authenticated(self):
        self.client.login(username="testuser", password="testpassword")
        response = self.client.get(reverse("license_dashboard"))
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "frontend/license.html")
