#
# Copyright (c) 2024 Jonas Remmert
#
# SPDX-License-Identifier: Apache-2.0
#

import logging
import os

import requests
from celery import shared_task
from django.utils import timezone
from requests import RequestException

from .models import Endpoint, EndpointOperation, FirmwareUpdate

# Check if we run in a container or locally
LESHAN_URI = os.getenv("LESHAN_URI", "http://0.0.0.0:8080") + "/api"


logger = logging.getLogger(__name__)


# Seconds the gateway waits for the device; HTTP waits a little longer
DEVICE_TIMEOUT = 5
MAX_ATTEMPTS = 3


def _device_rejection(response) -> str | None:
    """Return the CoAP error code if the device rejected the request.

    The gateway answers 502 with the CoAP code in the body for a device error
    (doc/source/architecture/gateway_contract.rst).
    """
    if response.status_code != 502:
        return None
    try:
        return response.json().get("code")
    except ValueError:
        return None


@shared_task
def send_operation(endpointOperation_id: int) -> None:
    try:
        e_ops = EndpointOperation.objects.get(id=endpointOperation_id)
    except EndpointOperation.DoesNotExist:
        logger.error(f"Operation {endpointOperation_id} does not exist.")
        return

    resource = e_ops.resource
    resource_type = resource.resource_type
    ep = resource.endpoint.endpoint
    logger.debug(f"Sending data to endpoint {ep}")

    path = f"{resource_type.object_id}/{e_ops.instance_id}/{resource_type.resource_id}"
    url = f"{LESHAN_URI}/clients/{ep}/{path}"
    params = {"timeout": DEVICE_TIMEOUT, "format": "CBOR"}
    headers = {"Content-Type": "application/json"}
    data = {
        "id": resource_type.resource_id,
        "kind": "singleResource",
        "value": resource.get_value(),
        "type": resource_type.data_type,
    }

    # Store the current attempt in the database as the request may take a while
    e_ops.last_attempt = timezone.now()
    e_ops.status = e_ops.Status.SENDING
    e_ops.save()

    # NONE type means this resource is an execute command. An execute command
    # is send with a POST instead of PUT. It does not have data.
    response = None
    try:
        if resource_type.data_type == "NONE":
            response = requests.post(
                url, params=params, headers=headers, timeout=DEVICE_TIMEOUT + 5
            )
        else:
            response = requests.put(
                url, params=params, headers=headers, json=data, timeout=DEVICE_TIMEOUT + 5
            )
    except RequestException as e:
        logger.error(f"Gateway request for operation {e_ops.id} failed: {e}")

    status_code = response.status_code if response is not None else None
    if status_code is not None and 200 <= status_code < 300:
        logger.debug(f"Operation {e_ops.id} confirmed by {ep}")
        e_ops.status = e_ops.Status.CONFIRMED
    elif response is not None and (code := _device_rejection(response)):
        logger.error(f"Operation {e_ops.id} rejected by {ep} with CoAP {code}")
        e_ops.transmit_counter += 1
        e_ops.status = e_ops.Status.FAILED
    else:
        logger.error(f"Operation {e_ops.id} not delivered: {status_code}")
        e_ops.transmit_counter += 1

        if e_ops.transmit_counter >= MAX_ATTEMPTS:
            e_ops.status = e_ops.Status.FAILED
        else:
            e_ops.status = e_ops.Status.QUEUED

    e_ops.save()

    if e_ops.status == EndpointOperation.Status.FAILED:
        _propagate_failure_to_firmware_update(e_ops)


@shared_task
def read_device_object(endpoint_id: str) -> None:
    """Read the Device object (3) after a registration and store it."""

    from .serializers.composite_resource_serializer import CompositeResourceSerializer

    url = f"{LESHAN_URI}/clients/{endpoint_id}/3"
    try:
        response = requests.get(url, params={"timeout": DEVICE_TIMEOUT}, timeout=DEVICE_TIMEOUT + 5)
    except RequestException as e:
        logger.error(f"Reading /3 from {endpoint_id} failed: {e}")
        return
    if response.status_code != 200:
        logger.error(
            f"Reading /3 from {endpoint_id} failed: {response.status_code} {response.text}"
        )
        return

    serializer = CompositeResourceSerializer(
        data={"ep": endpoint_id, "val": {"/3": response.json()["content"]}}
    )
    if not serializer.is_valid():
        logger.error(f"Invalid /3 content from {endpoint_id}: {serializer.errors}")
        return
    serializer.save()


def _propagate_failure_to_firmware_update(e_ops: EndpointOperation) -> None:
    """If a failed operation belongs to a FirmwareUpdate, mark the update as failed."""
    fw_update = (
        FirmwareUpdate.objects.filter(send_uri_operation=e_ops)
        | FirmwareUpdate.objects.filter(execute_operation=e_ops)
    ).first()
    if fw_update and fw_update.result == FirmwareUpdate.Result.RESULT_DEFAULT:
        logger.warning(
            f"Operation {e_ops.id} failed -- marking FirmwareUpdate {fw_update.id} as failed."
        )
        fw_update.result = FirmwareUpdate.Result.RESULT_UPDATE_FAILED
        fw_update.state = FirmwareUpdate.State.STATE_IDLE
        fw_update.save()


@shared_task
def process_pending_operations(endpoint_id):
    try:
        endpoint = Endpoint.objects.get(endpoint=endpoint_id)
    except Endpoint.DoesNotExist:
        logger.error(f"Endpoint {endpoint_id} does not exist.")
        return

    # Get all pending operations for the endpoint
    pending_operations = EndpointOperation.objects.filter(
        resource__endpoint=endpoint, status=EndpointOperation.Status.QUEUED
    )
    logger.info(f"Found {pending_operations.count()} pending operations for {endpoint.endpoint}")
    logger.info(f"Pending operations: {pending_operations}")

    for operation in pending_operations:
        logger.debug(f"Processing operation {operation.id}")

        # Call the send_operation task asynchronously
        send_operation.delay(operation.id)
