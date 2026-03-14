#
# Copyright (c) 2026 Jonas Remmert
#
# SPDX-License-Identifier: Apache-2.0
#

import json
from pathlib import Path

from django.core.management.base import BaseCommand, CommandError

from sensordata.models import ResourceType


class Command(BaseCommand):
    help = "Load initial resource types required for mock/testing"

    def handle(self, *args, **options):
        fixture_path = Path(__file__).resolve().parents[3] / "db_initial_resource_types.json"

        if not fixture_path.exists():
            raise CommandError(f"Fixture file not found: {fixture_path}")

        with fixture_path.open(encoding="utf-8") as handle:
            fixture_data = json.load(handle)

        loaded = 0
        for entry in fixture_data:
            fields = entry["fields"]
            ResourceType._default_manager.update_or_create(
                object_id=fields["object_id"],
                resource_id=fields["resource_id"],
                defaults={
                    "name": fields["name"],
                    "data_type": fields["data_type"],
                },
            )
            loaded += 1

        self.stdout.write(f"Loaded {loaded} resource types")
