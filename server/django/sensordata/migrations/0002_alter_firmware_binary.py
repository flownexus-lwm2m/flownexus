# Generated by Django 5.0.6 on 2024-08-20 08:46

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('sensordata', '0001_initial'),
    ]

    operations = [
        migrations.AlterField(
            model_name='firmware',
            name='binary',
            field=models.FileField(upload_to=''),
        ),
    ]
