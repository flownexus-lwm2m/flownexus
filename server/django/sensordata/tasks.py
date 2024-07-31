#
# Copyright (c) 2024 Jonas Remmert
#
# SPDX-License-Identifier: Apache-2.0
#

from celery import shared_task
import requests
from .models import Endpoint, EndpointOperation
import logging
import os
from django.utils import timezone

# Check if we run in a container or locally
LESHAN_URI = os.getenv('LESHAN_URI', 'http://0.0.0.0:8080') + '/api'


logger = logging.getLogger(__name__)


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

    # Construct the URL based on the endpoint, object_id, and resource_id
    url = (
        f'{LESHAN_URI}/clients/{ep}/'
        f'{resource_type.object_id}/0/{resource_type.resource_id}'
    )
    params = {'timeout': 5, 'format': 'CBOR'}
    headers = {'Content-Type': 'application/json'}
    data = {
        "id": resource_type.resource_id,
        "kind": "singleResource",
        "value": resource.get_value(),
        "type": resource_type.data_type
    }

    # Store the current attempt in the database as the request may take a while
    e_ops.last_attempt = timezone.now()
    e_ops.status = e_ops.Status.SENDING
    e_ops.save()

    # NONE type means this resource is an execute command. An execute command
    # is send with a POST instead of PUT. It does not have data.
    if resource_type.data_type == 'NONE':
        response = requests.post(url, params=params, headers=headers)
    else:
        response = requests.put(url, params=params, headers=headers, json=data)
    if response.status_code == 200:
        logger.debug(f'Data sent to endpoint {ep} successfully')
        logger.debug(f'Response: {response.status_code} - {response.json()}')
        e_ops.status = e_ops.Status.CONFIRMED
    else:
        logger.error(f'Failed to send data: {response.status_code}')
        e_ops.transmit_counter += 1

        if e_ops.transmit_counter >= 3:
            e_ops.status = e_ops.Status.FAILED
        else:
            e_ops.status = e_ops.Status.QUEUED

    e_ops.save()


@shared_task
def process_pending_operations(endpoint_id):
    try:
        endpoint = Endpoint.objects.get(endpoint=endpoint_id)
    except Endpoint.DoesNotExist:
        logger.error(f"Endpoint {endpoint_id} does not exist.")
        return

    # Get all pending operations for the endpoint
    pending_operations = EndpointOperation.objects.filter(
        resource__endpoint=endpoint,
        status=EndpointOperation.Status.QUEUED
    )
    logger.info(f"Found {pending_operations.count()} pending operations for {endpoint.endpoint}")
    logger.info(f"Pending operations: {pending_operations}")

    for operation in pending_operations:
        logger.debug(f"Processing operation {operation.id}")

        # Call the send_operation task asynchronously
        send_operation.delay(operation.id)
