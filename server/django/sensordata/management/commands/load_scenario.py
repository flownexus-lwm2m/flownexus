#
# Copyright (c) 2026 Jonas Remmert
#
# SPDX-License-Identifier: Apache-2.0
#

from pathlib import Path
from typing import Any, cast

import yaml
from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from sensordata.models import Endpoint, Site, SiteMembership

User = get_user_model()


class Command(BaseCommand):
    help = "Load a scenario configuration into the database"

    def add_arguments(self, parser):
        parser.add_argument(
            "--config",
            type=str,
            default="default",
            help="Name of the scenario config file (without .yaml extension)",
        )
        parser.add_argument(
            "--config-dir",
            type=str,
            default=None,
            help="Directory containing scenario configs (default: devtools/mock/scenarios)",
        )

    def handle(self, *args, **options):
        config_name = options["config"]
        config = self._load_config(config_name, options["config_dir"])
        self._validate_config(config, config_name)
        with cast(Any, transaction.atomic)():
            self._apply_config(config)

        scenario_name = config.get("scenario_name", config_name)
        self.stdout.write(f"Successfully loaded scenario '{scenario_name}'")

    def _apply_config(self, config):
        sites_map = self._load_sites(config.get("sites", []))
        self._load_users(config.get("users", []), sites_map)
        self._assign_devices_to_sites(
            config.get("device_assignments", {}), sites_map, config.get("devices", {})
        )

    def _load_config(self, config_name, config_dir):
        if config_dir is None:
            config_dir = Path(__file__).resolve().parents[5] / "devtools" / "mock" / "scenarios"
        else:
            config_dir = Path(config_dir)

        config_file = config_dir / f"{config_name}.yaml"
        if not config_file.exists():
            raise CommandError(f"Config file not found: {config_file}")

        with config_file.open(encoding="utf-8") as handle:
            return yaml.safe_load(handle) or {}

    def _validate_config(self, config, config_name):
        if not isinstance(config, dict):
            raise CommandError("Scenario config must be a mapping")

        required_keys = ["devices", "sites", "users"]
        missing = [key for key in required_keys if key not in config]
        if missing:
            raise CommandError(f"Scenario '{config_name}' missing keys: {', '.join(missing)}")

        if not isinstance(config["sites"], list) or not config["sites"]:
            raise CommandError("Scenario must define at least one site")
        if not isinstance(config["users"], list) or not config["users"]:
            raise CommandError("Scenario must define at least one user")
        if not isinstance(config["devices"], dict):
            raise CommandError("Scenario 'devices' must be a mapping")

    def _load_sites(self, sites_config):
        sites_map = {}
        for site_data in sites_config:
            name = site_data.get("name")
            if not name:
                raise CommandError("Each site must define a name")

            site, _ = Site._default_manager.update_or_create(
                name=name,
                defaults={
                    "description": site_data.get("description", ""),
                    "is_active": True,
                },
            )
            sites_map[name] = site
            self.stdout.write(f"  Loaded site: {name}")
        return sites_map

    def _load_users(self, users_config, sites_map):
        for user_data in users_config:
            username = user_data.get("username")
            password = user_data.get("password")
            if not username or not password:
                raise CommandError("Each user must define username and password")

            is_superuser = bool(user_data.get("is_superuser", False))
            user, _ = User.objects.update_or_create(
                username=username,
                defaults={
                    "is_superuser": is_superuser,
                    "is_staff": is_superuser,
                },
            )
            user.set_password(password)
            user.save(update_fields=["password", "is_superuser", "is_staff"])
            self.stdout.write(f"  Loaded user: {username}")

            if is_superuser:
                SiteMembership._default_manager.filter(user=user).delete()
                continue

            desired_site_names = set()
            for membership_data in user_data.get("sites", []):
                site_name = membership_data.get("name")
                if site_name not in sites_map:
                    raise CommandError(f"Unknown site '{site_name}' for user '{username}'")

                desired_site_names.add(site_name)
                role = membership_data.get("role", SiteMembership.Role.USER)
                permissions = membership_data.get("permissions", {})
                SiteMembership._default_manager.update_or_create(
                    user=user,
                    site=sites_map[site_name],
                    defaults={
                        "role": role,
                        "can_view_overview": permissions.get("can_view_overview", True),
                        "can_view_firmware": permissions.get("can_view_firmware", True),
                        "can_view_data_analysis": permissions.get("can_view_data_analysis", True),
                        "can_manage_firmware": permissions.get(
                            "can_manage_firmware", role == SiteMembership.Role.ADMIN
                        ),
                        "can_perform_operations": permissions.get(
                            "can_perform_operations", role == SiteMembership.Role.ADMIN
                        ),
                        "can_manage_devices": permissions.get(
                            "can_manage_devices", role == SiteMembership.Role.ADMIN
                        ),
                    },
                )
                self.stdout.write(f"    Loaded membership: {username} -> {site_name} ({role})")

            SiteMembership._default_manager.filter(user=user).exclude(
                site__name__in=desired_site_names
            ).delete()

    def _assign_devices_to_sites(self, device_assignments, sites_map, devices_config):
        """Create placeholder endpoints and assign them to sites.

        Creates endpoints for all devices in the scenario, assigning some to sites
        and leaving others unassigned (site=None).

        device_assignments format:
            Site Name:
                - 1  # IMEI ID
                - 2
            Another Site:
                - 3
        """
        total_devices = devices_config.get("count", 0)
        if total_devices == 0:
            return

        # Build set of all assigned device IDs
        assigned_device_ids = set()
        if device_assignments:
            for device_ids in device_assignments.values():
                assigned_device_ids.update(device_ids)

        # Create endpoints for assigned devices with their sites
        total_assigned = 0
        if device_assignments:
            for site_name, device_ids in device_assignments.items():
                if site_name not in sites_map:
                    self.stdout.write(
                        f"  Unknown site '{site_name}' in device_assignments, skipping"
                    )
                    continue

                site = sites_map[site_name]
                for device_id in device_ids:
                    endpoint_id = f"urn:imei:{device_id}"
                    endpoint, created = Endpoint.objects.get_or_create(
                        endpoint=endpoint_id, defaults={"site": site, "registered": False}
                    )
                    if not created:
                        endpoint.site = site
                        endpoint.save(update_fields=["site"])
                    total_assigned += 1

                self.stdout.write(f"  Assigned {len(device_ids)} devices to {site_name}")

        # Create endpoints for unassigned devices (site=None)
        unassigned_count = 0
        for device_id in range(1, total_devices + 1):
            if device_id not in assigned_device_ids:
                endpoint_id = f"urn:imei:{device_id}"
                Endpoint.objects.get_or_create(
                    endpoint=endpoint_id, defaults={"site": None, "registered": False}
                )
                unassigned_count += 1

        self.stdout.write(
            f"  Total: {total_assigned} devices assigned, {unassigned_count} unassigned"
        )
