#
# Copyright (c) 2024 Jonas Remmert
#
# SPDX-License-Identifier: Apache-2.0
#
"""Single migration that advances any 0001_initial database to the current model state.

Handles two database situations:

Old-style databases (previously migrated via the original 4-step history):
  0001_initial / 0002_alter_firmware_binary /
  0003_alter_resource_timestamp_created /
  0004_resource_binary_value_alter_resourcetype_data_type

  These already have:
    - Resource.timestamp_created as nullable + indexed
    - Resource.binary_value BLOB column (with live data)
    - ResourceType.data_type allowing 'OPAQUE'
  But they lack:
    - Firmware.is_deleted
    - Site / SiteMembership tables
    - Endpoint.site FK

Fresh databases (only 0001_initial applied):
  All of the above is absent and must be created.

Every operation is written to be safe/idempotent against both cases.
"""

import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


def add_binary_value_if_missing(apps, schema_editor):
    """Add Resource.binary_value only when the column is not already present.

    Old-style databases already have this column with live data; fresh 0001
    databases do not.
    """
    connection = schema_editor.connection
    columns = {
        col.name
        for col in connection.introspection.get_table_description(
            connection.cursor(), "sensordata_resource"
        )
    }
    if "binary_value" not in columns:
        schema_editor.execute("ALTER TABLE sensordata_resource ADD COLUMN binary_value BLOB NULL")


class Migration(migrations.Migration):
    dependencies = [
        ("sensordata", "0001_initial"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        # ------------------------------------------------------------------
        # 1. Pre-register binary_value in Django's migration *state* before
        #    the AlterField on Resource.timestamp_created (step 2).
        #
        #    On SQLite, AlterField triggers a full table recreation and Django
        #    copies only columns present in its state at that moment.  Without
        #    this, old-style databases that already carry binary_value data
        #    would silently lose it during the rebuild.
        #
        #    database_operations=[] because:
        #      - old-style DBs already have the column  → no DDL needed here
        #      - fresh DBs don't have it yet            → step 3 adds it
        # ------------------------------------------------------------------
        migrations.SeparateDatabaseAndState(
            database_operations=[],
            state_operations=[
                migrations.AddField(
                    model_name="resource",
                    name="binary_value",
                    field=models.BinaryField(blank=True, null=True),
                ),
            ],
        ),
        # ------------------------------------------------------------------
        # 2. Make Resource.timestamp_created nullable and indexed.
        #    Old-style DBs already have this; Django's AlterField on SQLite
        #    triggers a table rebuild — binary_value is preserved because
        #    step 1 already registered it in the state.
        # ------------------------------------------------------------------
        migrations.AlterField(
            model_name="resource",
            name="timestamp_created",
            field=models.DateTimeField(blank=True, db_index=True, null=True),
        ),
        # ------------------------------------------------------------------
        # 3. Physically add binary_value on fresh databases.
        #    Old-style DBs already have the column; RunPython skips the DDL.
        #    state_operations=[] because the column is already in state from
        #    step 1.
        # ------------------------------------------------------------------
        migrations.SeparateDatabaseAndState(
            database_operations=[
                migrations.RunPython(
                    add_binary_value_if_missing,
                    reverse_code=migrations.RunPython.noop,
                ),
            ],
            state_operations=[],
        ),
        # ------------------------------------------------------------------
        # 4. Register OPAQUE in ResourceType.data_type choices.
        #    SQLite stores no CHECK constraint for CharField choices so this
        #    AlterField is always safe to apply.
        # ------------------------------------------------------------------
        migrations.AlterField(
            model_name="resourcetype",
            name="data_type",
            field=models.CharField(
                choices=[
                    ("TIME", "int_value"),
                    ("STRING", "str_value"),
                    ("INTEGER", "int_value"),
                    ("FLOAT", "float_value"),
                    ("BOOLEAN", "int_value"),
                    ("OPAQUE", "binary_value"),
                ],
                max_length=50,
            ),
        ),
        # ------------------------------------------------------------------
        # 5. Firmware: fix upload_to path and add is_deleted soft-delete flag.
        # ------------------------------------------------------------------
        migrations.AlterField(
            model_name="firmware",
            name="binary",
            field=models.FileField(upload_to=""),
        ),
        migrations.AddField(
            model_name="firmware",
            name="is_deleted",
            field=models.BooleanField(default=False, help_text="Soft delete flag"),
        ),
        # ------------------------------------------------------------------
        # 6–8. Site, Endpoint.site FK, SiteMembership — all new on every
        #       existing database.
        # ------------------------------------------------------------------
        migrations.CreateModel(
            name="Site",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True, primary_key=True, serialize=False, verbose_name="ID"
                    ),
                ),
                ("name", models.CharField(max_length=255, unique=True)),
                ("description", models.TextField(blank=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("is_active", models.BooleanField(default=True)),
            ],
            options={
                "ordering": ["name"],
            },
        ),
        migrations.AddField(
            model_name="endpoint",
            name="site",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.PROTECT,
                related_name="endpoints",
                to="sensordata.site",
            ),
        ),
        migrations.CreateModel(
            name="SiteMembership",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True, primary_key=True, serialize=False, verbose_name="ID"
                    ),
                ),
                (
                    "role",
                    models.CharField(
                        choices=[("ADMIN", "Site Admin"), ("USER", "Site User")],
                        default="USER",
                        max_length=20,
                    ),
                ),
                ("can_view_overview", models.BooleanField(default=True)),
                ("can_view_firmware", models.BooleanField(default=False)),
                ("can_view_data_analysis", models.BooleanField(default=True)),
                ("can_manage_firmware", models.BooleanField(default=False)),
                ("can_perform_operations", models.BooleanField(default=False)),
                ("can_manage_devices", models.BooleanField(default=False)),
                ("joined_at", models.DateTimeField(auto_now_add=True)),
                (
                    "site",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="memberships",
                        to="sensordata.site",
                    ),
                ),
                (
                    "user",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="site_memberships",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
            ],
            options={
                "ordering": ["-joined_at"],
                "unique_together": {("user", "site")},
            },
        ),
    ]
