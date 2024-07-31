# Generated by Django 5.0.6 on 2024-07-31 14:21

import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('sensordata', '0009_remove_firmware_download_url_and_more'),
    ]

    operations = [
        migrations.CreateModel(
            name='FirmwareUpdate',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('state', models.IntegerField(choices=[(0, 'IDLE'), (1, 'DOWNLOADING'), (2, 'DOWNLOADED'), (3, 'UPDATING')], default=0)),
                ('result', models.IntegerField(choices=[(0, 'DEFAULT'), (1, 'SUCCESS'), (2, 'NO STORAGE'), (3, 'OUT OF MEMORY'), (4, 'CONNECTION LOST'), (5, 'INTEGRITY FAILED'), (6, 'UNSUPPORTED FIRMWARE'), (7, 'INVALID URI'), (8, 'UPDATE FAILED'), (9, 'UNSUPPORTED PROTOCOL')], default=0)),
                ('timestamp_created', models.DateTimeField(auto_now_add=True)),
                ('timestamp_updated', models.DateTimeField(auto_now=True)),
                ('endpoint', models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, to='sensordata.endpoint')),
                ('execute_operation', models.ForeignKey(null=True, on_delete=django.db.models.deletion.PROTECT, related_name='execute_operation', to='sensordata.endpointoperation')),
                ('firmware', models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, to='sensordata.firmware')),
                ('send_uri_operation', models.ForeignKey(null=True, on_delete=django.db.models.deletion.PROTECT, related_name='send_uri_operation', to='sensordata.endpointoperation')),
            ],
        ),
    ]
