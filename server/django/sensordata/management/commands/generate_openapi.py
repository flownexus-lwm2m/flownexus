from django.core.management.base import BaseCommand
from drf_spectacular.generators import SchemaGenerator
import yaml
import os

class Command(BaseCommand):
    help = 'Generates the OpenAPI schema'

    def add_arguments(self, parser):
        parser.add_argument(
            '-o',
            type=str,
            help='File path where the OpenAPI schema should be saved',
            default='openapi-schema.yaml'
        )

    def handle(self, *args, **options):
        output_path = options['o']

        # Ensure the directory exists
        os.makedirs(os.path.dirname(output_path), exist_ok=True)

        # Generate the OpenAPI schema
        generator = SchemaGenerator()
        schema = generator.get_schema(request=None, public=True)
        schema_yaml = yaml.dump(schema, default_flow_style=False)

        # Write the schema to the specified file
        with open(output_path, 'w') as file:
            file.write(schema_yaml)

        self.stdout.write(self.style.SUCCESS(f'Exported OpenAPI schema to {output_path}'))
