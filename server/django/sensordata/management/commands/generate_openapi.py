#
# Copyright (c) 2024 Jonas Remmert
#
# SPDX-License-Identifier: Apache-2.0
#

from pathlib import Path

import yaml
from django.core.management.base import BaseCommand
from drf_spectacular.generators import SchemaGenerator


class Command(BaseCommand):
    help = "Generates the OpenAPI schema"

    def add_arguments(self, parser):
        parser.add_argument(
            "-o",
            type=str,
            help="File path where the OpenAPI schema should be saved",
            default="openapi-schema.yaml",
        )

    def handle(self, *args, **options):
        output_path = Path(options["o"])

        # Ensure the directory exists
        output_path.parent.mkdir(parents=True, exist_ok=True)

        # Generate the OpenAPI schema
        generator = SchemaGenerator()
        schema = generator.get_schema(request=None, public=True)
        schema_yaml = yaml.dump(schema, default_flow_style=False)

        # Write the schema to the specified file
        with output_path.open("w") as file:
            file.write(schema_yaml)

        self.stdout.write(self.style.SUCCESS(f"Exported OpenAPI schema to {output_path}"))
