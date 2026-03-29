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


LEGACY_VIEW_OVERVIEW_PERMISSIONS = {
    "view_endpoint",
    "view_event",
    "view_resource",
    "view_resourcetype",
}
LEGACY_VIEW_FIRMWARE_PERMISSIONS = {
    "view_firmware",
    "view_firmwareupdate",
}
LEGACY_MANAGE_FIRMWARE_PERMISSIONS = {
    "add_firmware",
    "change_firmware",
    "delete_firmware",
}
LEGACY_FIRMWARE_UPDATE_PERMISSIONS = {
    "add_firmwareupdate",
    "change_firmwareupdate",
    "delete_firmwareupdate",
}
LEGACY_OPERATION_PERMISSIONS = {
    "add_endpointoperation",
    "change_endpointoperation",
    "delete_endpointoperation",
}
DEFAULT_SITE_NAME = "Default Site"
DEFAULT_SITE_DESCRIPTION = "Default site for existing devices"


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


def build_membership_fields(permission_codenames):
    can_view_overview = bool(permission_codenames & LEGACY_VIEW_OVERVIEW_PERMISSIONS)
    can_view_firmware = bool(
        permission_codenames
        & (
            LEGACY_VIEW_FIRMWARE_PERMISSIONS
            | LEGACY_MANAGE_FIRMWARE_PERMISSIONS
            | LEGACY_FIRMWARE_UPDATE_PERMISSIONS
            | LEGACY_OPERATION_PERMISSIONS
        )
    )
    can_view_data_analysis = can_view_overview
    can_manage_firmware = bool(permission_codenames & LEGACY_MANAGE_FIRMWARE_PERMISSIONS)
    can_perform_operations = bool(
        permission_codenames & (LEGACY_FIRMWARE_UPDATE_PERMISSIONS | LEGACY_OPERATION_PERMISSIONS)
    )

    if not any(
        [
            can_view_overview,
            can_view_firmware,
            can_view_data_analysis,
            can_manage_firmware,
            can_perform_operations,
        ]
    ):
        return None

    return {
        "role": "ADMIN" if can_manage_firmware or can_perform_operations else "USER",
        "can_view_overview": can_view_overview,
        "can_view_firmware": can_view_firmware,
        "can_view_data_analysis": can_view_data_analysis,
        "can_manage_firmware": can_manage_firmware,
        "can_perform_operations": can_perform_operations,
        "can_manage_devices": False,
    }


def get_target_site(Site):
    active_sites = list(Site.objects.filter(is_active=True).order_by("pk"))
    if len(active_sites) == 1:
        return active_sites[0]

    default_site, _ = Site.objects.get_or_create(
        name=DEFAULT_SITE_NAME,
        defaults={
            "description": DEFAULT_SITE_DESCRIPTION,
            "is_active": True,
        },
    )
    if not default_site.is_active:
        default_site.is_active = True
        default_site.save(update_fields=["is_active"])
    if default_site.description != DEFAULT_SITE_DESCRIPTION and not default_site.description:
        default_site.description = DEFAULT_SITE_DESCRIPTION
        default_site.save(update_fields=["description"])
    return default_site


def backfill_legacy_site_memberships(apps, schema_editor):
    User = apps.get_model("auth", "User")
    Site = apps.get_model("sensordata", "Site")
    SiteMembership = apps.get_model("sensordata", "SiteMembership")

    eligible_users = []
    for user in User.objects.filter(is_superuser=False).prefetch_related("user_permissions"):
        if SiteMembership.objects.filter(user_id=user.pk).exists():
            continue

        permission_codenames = {
            permission.codename
            for permission in user.user_permissions.all()
            if permission.content_type.app_label == "sensordata"
        }
        membership_fields = build_membership_fields(permission_codenames)
        if membership_fields is None:
            continue
        eligible_users.append((user.pk, membership_fields))

    if not eligible_users:
        return

    target_site = get_target_site(Site)
    for user_id, membership_fields in eligible_users:
        SiteMembership.objects.create(user_id=user_id, site_id=target_site.pk, **membership_fields)


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
        migrations.RunPython(
            backfill_legacy_site_memberships,
            reverse_code=migrations.RunPython.noop,
        ),
    ]
