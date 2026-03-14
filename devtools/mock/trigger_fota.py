#
# Trigger a FOTA update for a mock device
#
from sensordata.models import Endpoint, Firmware, FirmwareUpdate
from sensordata.tasks import process_pending_operations


def trigger():
    ep = Endpoint.objects.get(endpoint="urn:imei:1")
    fw = Firmware.objects.first()
    if not fw:
        print("No firmware found in DB!")
        return

    # Clean up old updates first to avoid ValidationError
    FirmwareUpdate.objects.filter(endpoint=ep).delete()

    print(f"Triggering update for {ep} to version {fw.version}")
    FirmwareUpdate.objects.create(endpoint=ep, firmware=fw)
    process_pending_operations.delay(ep.endpoint)
    print("Update triggered and task queued.")


if __name__ == "__main__":
    import os

    import django

    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "core.settings")
    # Add server/django to path
    import sys

    sys.path.append(os.path.join(os.getcwd(), "server/django"))
    django.setup()
    trigger()
