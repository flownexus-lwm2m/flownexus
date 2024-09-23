#
# Copyright (c) 2024 Jonas Remmert
#
# SPDX-License-Identifier: Apache-2.0
#
import traceback
import logging
import numpy as np
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from django.shortcuts import render, get_object_or_404
from django.contrib.auth.decorators import login_required
from rest_framework.exceptions import ValidationError
from .models import Endpoint, Resource, Firmware, EndpointOperation, FirmwareUpdate, ResourceType, Event, EventResource
from .serializers.single_resource_serializer import SingleResourceSerializer
from .serializers.composite_resource_serializer import CompositeResourceSerializer
from .serializers.timestamped_resource_serializer import TimestampedResourceSerializer
from .serializers.generic_serializer import EndpointSerializer, FirmwareSerializer, EndpointOperationSerializer, FirmwareUpdateSerializer
from django.db.models import Count
from django.db.models.functions import TruncDay, TruncMonth
from django.utils import timezone
from datetime import timedelta
from itertools import chain
from django.http import JsonResponse
import csv
from django.http import HttpResponse


logger = logging.getLogger(__name__)

# API Views

class PostSingleResourceView(APIView):
    """API View for posting a single resource."""
    serializer_class = SingleResourceSerializer

    def post(self, request):
        serializer = self.serializer_class(data=request.data)
        try:
            if serializer.is_valid(raise_exception=True):
                serializer.save()
                return Response(serializer.validated_data, status=status.HTTP_201_CREATED)
        except ValidationError as e:
            logger.error("Validation error: %s", e)
            logger.error("Request data: %s", request.data)
            logger.error("Backtrace: %s", traceback.format_exc())
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

class PostCompositeResourceView(APIView):
    """API View for posting a composite resource."""
    serializer_class = CompositeResourceSerializer

    def post(self, request):
        serializer = self.serializer_class(data=request.data)
        try:
            if serializer.is_valid(raise_exception=True):
                serializer.save()
                return Response(serializer.validated_data, status=status.HTTP_201_CREATED)
        except ValidationError as e:
            logger.error("Validation error: %s", e)
            logger.error("Request data: %s", request.data)
            logger.error("Backtrace: %s", traceback.format_exc())
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

class PostTimestampedResourceView(APIView):
    serializer_class = TimestampedResourceSerializer

    def post(self, request):
        serializer = TimestampedResourceSerializer(data=request.data, many=False)
        try:
            if serializer.is_valid(raise_exception=True):
                serializer.save()
                return Response(serializer.validated_data, status=status.HTTP_201_CREATED)
        except ValidationError as e:
            logger.error("Validation error: %s", e)
            logger.error("Request data: %s", request.data)
            logger.error("Backtrace: %s", traceback.format_exc())
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

class EndpointView(APIView):
    """API View for retrieving endpoint data."""
    def get(self, request, endpoint_id=None):
        if endpoint_id:
            endpoint = get_object_or_404(Endpoint, endpoint=endpoint_id)
            serializer = EndpointSerializer(endpoint)
        else:
            endpoints = Endpoint.objects.all()
            serializer = EndpointSerializer(endpoints, many=True)
        return Response(serializer.data)

class EndpointResourceView(APIView):
    """API View for retrieving resources associated with an endpoint."""
    def get(self, request, endpoint_id, resource_id=None):
        endpoint = get_object_or_404(Endpoint, endpoint=endpoint_id)
        if resource_id:
            resource = get_object_or_404(Resource, endpoint=endpoint, id=resource_id)
            data = {
                'resource_id': resource.id,
                'resource_type': str(resource.resource_type),
                'value': resource.get_value(),
                'timestamp_created': resource.timestamp_created,
            }
            return Response(data)
        else:
            resources = Resource.objects.filter(endpoint=endpoint)
            data = [{
                'resource_id': r.id,
                'resource_type': str(r.resource_type),
                'value': r.get_value(),
                'timestamp_created': r.timestamp_created,
            } for r in resources]
            return Response(data)

class EndpointFirmwareView(APIView):
    """API View for retrieving and posting firmware updates for an endpoint."""
    def get(self, request, endpoint_id):
        endpoint = get_object_or_404(Endpoint, endpoint=endpoint_id)
        firmware_updates = FirmwareUpdate.objects.filter(endpoint=endpoint)
        serializer = FirmwareUpdateSerializer(firmware_updates, many=True)
        return Response(serializer.data)

    def post(self, request, endpoint_id):
        endpoint = get_object_or_404(Endpoint, endpoint=endpoint_id)
        firmware_serializer = FirmwareSerializer(data=request.data)
        if firmware_serializer.is_valid():
            firmware = firmware_serializer.save()
            firmware_update = FirmwareUpdate.objects.create(endpoint=endpoint, firmware=firmware)
            update_serializer = FirmwareUpdateSerializer(firmware_update)
            return Response(update_serializer.data, status=status.HTTP_201_CREATED)
        return Response(firmware_serializer.errors, status=status.HTTP_400_BAD_REQUEST)

class EndpointOperationView(APIView):
    """API View for retrieving and posting operations to be performed on an endpoint."""
    def get(self, request, endpoint_id):
        endpoint = get_object_or_404(Endpoint, endpoint=endpoint_id)
        operations = EndpointOperation.objects.filter(resource__endpoint=endpoint)
        serializer = EndpointOperationSerializer(operations, many=True)
        return Response(serializer.data)

    def post(self, request, endpoint_id):
        endpoint = get_object_or_404(Endpoint, endpoint=endpoint_id)
        serializer = EndpointOperationSerializer(data=request.data)
        if serializer.is_valid():
            serializer.save(resource__endpoint=endpoint)
            return Response(serializer.data, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

# Dashboard Views
@login_required
def admin_dashboard_view(request):
    total_devices = Endpoint.objects.count()

    registered_devices = Endpoint.objects.filter(registered=True).count()
    unregistered_devices = total_devices - registered_devices

    time_range = request.GET.get('time_range', 'week')

    selected_event_type = request.GET.get('event_type', 'all')
    event_time_range = request.GET.get('event_time_range', 'week')
    end_date = timezone.now()
    if time_range == 'week':
        start_date = end_date - timedelta(days=7)
        trunc_func = TruncDay
        date_format = '%Y-%m-%d'
    elif time_range == 'month':
        start_date = end_date - timedelta(days=30)
        trunc_func = TruncDay
        date_format = '%Y-%m-%d'
    elif time_range == 'year':
        start_date = end_date - timedelta(days=365)
        trunc_func = TruncMonth
        date_format = '%Y-%m'
    else:
        start_date = end_date - timedelta(days=7)
        trunc_func = TruncDay
        date_format = '%Y-%m-%d'

    def get_counts(model, date_field):
        return model.objects.filter(**{f'{date_field}__range': (start_date, end_date)}).annotate(
            date=trunc_func(date_field)
        ).values('date').annotate(count=Count('id')).order_by('date')


    resource_counts = get_counts(Resource, 'timestamp_created')
    event_counts = get_counts(Event, 'time')
    operation_counts = get_counts(EndpointOperation, 'timestamp_created')
    firmware_update_counts = get_counts(FirmwareUpdate, 'timestamp_created')
    all_counts = list(chain(resource_counts, event_counts, operation_counts, firmware_update_counts))

    date_counts = {}
    for item in all_counts:
        date = item['date'].strftime(date_format)
        date_counts[date] = date_counts.get(date, 0) + item['count']

    sorted_dates = sorted(date_counts.keys())
    counts = [date_counts[date] for date in sorted_dates]

    event_start_date = end_date
    if event_time_range == 'week':
        event_start_date = end_date - timedelta(days=7)
        event_trunc_func = TruncDay
    elif event_time_range == 'month':
        event_start_date = end_date - timedelta(days=30)
        event_trunc_func = TruncDay
    elif event_time_range == 'year':
        event_start_date = end_date - timedelta(days=365)
        event_trunc_func = TruncMonth

    events = Event.objects.filter(time__range=(event_start_date, end_date))
    if selected_event_type != 'all':
        events = events.filter(event_type=selected_event_type)

    event_data = events.annotate(date=event_trunc_func('time')).values('date').annotate(count=Count('id')).order_by('date')

    event_date_counts = {}
    for event in event_data:
        date_str = event['date'].strftime(date_format)
        event_date_counts[date_str] = event_date_counts.get(date_str, 0) + event['count']

    event_sorted_dates = sorted(event_date_counts.keys())
    event_counts = [event_date_counts[date] for date in event_sorted_dates]

    event_types = Event.objects.values_list('event_type', flat=True).distinct()

    firmware_updates_in_progress = FirmwareUpdate.objects.exclude(state=FirmwareUpdate.State.STATE_IDLE).count()

    firmware_state_idle = FirmwareUpdate.objects.filter(state=FirmwareUpdate.State.STATE_IDLE).count()
    firmware_state_downloading = FirmwareUpdate.objects.filter(state=FirmwareUpdate.State.STATE_DOWNLOADING).count()
    firmware_state_downloaded = FirmwareUpdate.objects.filter(state=FirmwareUpdate.State.STATE_DOWNLOADED).count()
    firmware_state_updating = FirmwareUpdate.objects.filter(state=FirmwareUpdate.State.STATE_UPDATING).count()

    firmware_result_default = FirmwareUpdate.objects.filter(result=FirmwareUpdate.Result.RESULT_DEFAULT).count()
    firmware_result_success = FirmwareUpdate.objects.filter(result=FirmwareUpdate.Result.RESULT_SUCCESS).count()
    firmware_result_no_storage = FirmwareUpdate.objects.filter(result=FirmwareUpdate.Result.RESULT_NO_STORAGE).count()
    firmware_result_out_of_memory = FirmwareUpdate.objects.filter(result=FirmwareUpdate.Result.RESULT_OUT_OF_MEM).count()
    firmware_result_connection_lost = FirmwareUpdate.objects.filter(result=FirmwareUpdate.Result.RESULT_CONNECTION_LOST).count()
    firmware_result_integrity_failed = FirmwareUpdate.objects.filter(result=FirmwareUpdate.Result.RESULT_INTEGRITY_FAILED).count()
    firmware_result_unsupported_firmware = FirmwareUpdate.objects.filter(result=FirmwareUpdate.Result.RESULT_UNSUP_FW).count()
    firmware_result_invalid_uri = FirmwareUpdate.objects.filter(result=FirmwareUpdate.Result.RESULT_INVALID_URI).count()
    firmware_result_update_failed = FirmwareUpdate.objects.filter(result=FirmwareUpdate.Result.RESULT_UPDATE_FAILED).count()
    firmware_result_unsupported_protocol = FirmwareUpdate.objects.filter(result=FirmwareUpdate.Result.RESULT_UNSUP_PROTO).count()

    context = {
        'title': 'Admin Dashboard',
        'total_devices': total_devices,
        'registered_devices': registered_devices,
        'unregistered_devices': unregistered_devices,
        'time_range': time_range,
        'added_values_dates': sorted_dates,
        'added_values_counts': counts,
        'event_types': event_types,
        'selected_event_type': selected_event_type,
        'event_time_range': event_time_range,
        'event_dates': event_sorted_dates,
        'event_counts': event_counts,
        'firmware_updates_in_progress': firmware_updates_in_progress,
        'firmware_state_idle': firmware_state_idle,
        'firmware_state_downloading': firmware_state_downloading,
        'firmware_state_downloaded': firmware_state_downloaded,
        'firmware_state_updating': firmware_state_updating,
        'firmware_result_default': firmware_result_default,
        'firmware_result_success': firmware_result_success,
        'firmware_result_no_storage': firmware_result_no_storage,
        'firmware_result_out_of_memory': firmware_result_out_of_memory,
        'firmware_result_connection_lost': firmware_result_connection_lost,
        'firmware_result_integrity_failed': firmware_result_integrity_failed,
        'firmware_result_unsupported_firmware': firmware_result_unsupported_firmware,
        'firmware_result_invalid_uri': firmware_result_invalid_uri,
        'firmware_result_update_failed': firmware_result_update_failed,
        'firmware_result_unsupported_protocol': firmware_result_unsupported_protocol,
    }

    pending_communications_count = EndpointOperation.objects.exclude(status=EndpointOperation.Status.CONFIRMED).count()

    status_sending = EndpointOperation.objects.filter(status=EndpointOperation.Status.SENDING).count()
    status_queued = EndpointOperation.objects.filter(status=EndpointOperation.Status.QUEUED).count()
    status_confirmed = EndpointOperation.objects.filter(status=EndpointOperation.Status.CONFIRMED).count()
    status_failed = EndpointOperation.objects.filter(status=EndpointOperation.Status.FAILED).count()

    context.update({
        'pending_communications_count': pending_communications_count,
        'status_sending': status_sending,
        'status_queued': status_queued,
        'status_confirmed': status_confirmed,
        'status_failed': status_failed,
    })

    return render(request, 'admin_dashboard.html', context)

@login_required
def device_dashboard_view(request):
    """View to display the device dashboard with detailed information and graphs."""
    REGISTRATION_OBJECT_ID = 10240
    REGISTRATION_UPDATE_OBJECT_ID = 10240
    FIRMWARE_OBJECT_ID = 3
    BATTERY_VOLTAGE_OBJECT_ID = 3

    endpoints = Endpoint.objects.all()  # Fetch all endpoints
    selected_endpoint = None
    selected_resource_type = None
    graph_data = None

    timestamps = []
    values = []

    # Handle endpoint selection
    if 'endpoint' in request.GET:
        endpoint_id = request.GET['endpoint']
        selected_endpoint = get_object_or_404(Endpoint, endpoint=endpoint_id)

        last_registered = Resource.objects.filter(
            endpoint=selected_endpoint,
            resource_type__object_id=REGISTRATION_OBJECT_ID,
            resource_type__resource_id=0
        ).order_by('-timestamp_created').first()

        last_registration_update = Resource.objects.filter(
            endpoint=selected_endpoint,
            resource_type__object_id=REGISTRATION_UPDATE_OBJECT_ID,
            resource_type__resource_id=2
        ).order_by('-timestamp_created').first()

        current_firmware = Resource.objects.filter(
            endpoint=selected_endpoint,
            resource_type__object_id=FIRMWARE_OBJECT_ID,
            resource_type__resource_id=3
        ).order_by('-timestamp_created').first()

        battery_voltage = Resource.objects.filter(
            endpoint=selected_endpoint,
            resource_type__object_id=BATTERY_VOLTAGE_OBJECT_ID,
            resource_type__resource_id=9
        ).order_by('-timestamp_created').first()

        selected_endpoint.last_registered = last_registered.timestamp_created if last_registered else None
        selected_endpoint.last_registration_update = last_registration_update.timestamp_created if last_registration_update else None
        selected_endpoint.current_firmware = current_firmware.str_value if current_firmware else None
        selected_endpoint.battery_voltage = battery_voltage.int_value if battery_voltage else None

        if 'resource_type' in request.GET:
            if 'event_type' in request.GET and request.GET['event_type'] is not '':
                selected_resource_type = get_object_or_404(ResourceType,
                                                           id=request.GET['resource_type'])
                last_event = Event.objects.filter(
                    endpoint=selected_endpoint,
                    event_type=request.GET['event_type']
                ).order_by('-time').first()

                evt_resources = EventResource.objects.filter(
                    event=last_event
                ).order_by('resource__timestamp_created')

                resources = []
                for evt_resource in evt_resources:
                    if evt_resource.resource.resource_type == selected_resource_type:
                        resources.append(evt_resource.resource)

            else:
                selected_resource_type = get_object_or_404(ResourceType,
                                                           id=request.GET['resource_type'])
                last_seven_days = timezone.now() - timedelta(days=30)
                resources = Resource.objects.filter(
                    endpoint=selected_endpoint,
                    resource_type=selected_resource_type,
                    timestamp_created__gte=last_seven_days
                ).order_by('timestamp_created')

            timestamps = [resource.timestamp_created.strftime('%Y-%m-%d %H:%M:%S') for resource in resources]
            values = [
                resource.int_value if selected_resource_type.data_type == 'INTEGER'
                else resource.float_value if selected_resource_type.data_type == 'FLOAT'
                else resource.int_value if selected_resource_type.data_type == 'TIME'
                else None for resource in resources
            ]
            graph_data = {
                'timestamps': timestamps,
                'values': values
            }

    resource_types = ResourceType.objects.filter(data_type__in=['INTEGER', 'FLOAT', 'TIME'])
    event_types = Event.objects.values_list('event_type', flat=True).distinct()

    if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        return JsonResponse({
                'timestamps': timestamps,
                'values': values,
                'resource_name': selected_resource_type.name,
            })

    context = {
        'endpoints': endpoints,
        'selected_endpoint': selected_endpoint,
        'resource_types': resource_types,
        'event_types': event_types,
        'selected_resource_type': selected_resource_type,
        'graph_data': graph_data,
    }

    return render(request, 'device_dashboard.html', context)

@login_required
def license_dashboard_view(request):
    """View to display project information and licenses."""
    return render(request, 'license.html', {'title': 'Project Information and Licenses'})

@login_required
def firmware_dashboard_view(request):
    # Get all devices (endpoints)
    devices = Endpoint.objects.all()

    # Fetch the current firmware version for each device
    for device in devices:
        firmware_resource = Resource.objects.filter(
            endpoint=device,
            resource_type__object_id=3,
            resource_type__resource_id=3
        ).order_by('-timestamp_created').first()

        device.current_firmware = firmware_resource.str_value if firmware_resource else "Unknown"

    firmware_versions = Firmware.objects.values_list('version', flat=True).distinct()

    ongoing_updates = FirmwareUpdate.objects.exclude(
        state=FirmwareUpdate.State.STATE_IDLE
    ).select_related('endpoint', 'firmware')

    if request.method == 'POST':
        selected_devices = request.POST.getlist('device_ids')
        firmware_id = request.POST.get('firmware_id')

        firmware = get_object_or_404(Firmware, id=firmware_id)

        for device_id in selected_devices:
            endpoint = get_object_or_404(Endpoint, id=device_id)
            FirmwareUpdate.objects.create(endpoint=endpoint, firmware=firmware)

        return JsonResponse({'status': 'success', 'message': 'Firmware update initiated for selected devices'})

    context = {
        'devices': devices,
        'firmware_versions': firmware_versions,
        'ongoing_updates': ongoing_updates,
        'title': 'Firmware Update Dashboard',
    }

    return render(request, 'firmware_dashboard.html', context)

@login_required
def event_dashboard_view(request):
    """View to display all significant events and event resources related to devices."""
    events = Event.objects.all().order_by('-time')
    event_resources = EventResource.objects.all().select_related('event', 'resource', 'resource__resource_type')

    endpoints = Event.objects.values_list('endpoint', flat=True).distinct()
    event_types = Event.objects.values_list('event_type', flat=True).distinct()
    resource_types = ResourceType.objects.all()

    return render(request, 'event_dashboard.html', {
        'events': events,
        'event_resources': event_resources,
        'endpoints': endpoints,
        'event_types': event_types,
        'resource_types': resource_types,
        'title': 'Event Dashboard'
    })

def download_csv(request):
    """View to generate and download CSV file for selected resource data or event data."""
    endpoint_id = request.GET.get('endpoint')
    resource_type_id = request.GET.get('resource_type')
    event_type = request.GET.get('event_type')

    if not endpoint_id:
        return HttpResponse("Missing endpoint parameter", status=400)

    endpoint = get_object_or_404(Endpoint, endpoint=endpoint_id)

    # Create the HTTP response with CSV content type
    response = HttpResponse(content_type='text/csv')

    if resource_type_id:
        # Download data for a specific resource
        resource_type = get_object_or_404(ResourceType, id=resource_type_id)
        response['Content-Disposition'] = f'attachment; filename="{resource_type.name}_data.csv"'
        writer = csv.writer(response)
        writer.writerow(['Timestamp', 'Value'])

        last_thirty_days = timezone.now() - timedelta(days=30)
        resources = Resource.objects.filter(
            endpoint=endpoint,
            resource_type=resource_type,
            timestamp_created__gte=last_thirty_days
        ).order_by('timestamp_created')

        for resource in resources:
            if resource_type.data_type == 'INTEGER':
                value = resource.int_value
            elif resource_type.data_type == 'FLOAT':
                value = resource.float_value
            elif resource_type.data_type == 'TIME':
                value = resource.int_value  # Assuming TIME is stored as int
            else:
                value = resource.str_value

            writer.writerow([resource.timestamp_created.strftime('%Y-%m-%d %H:%M:%S'), value])

    elif event_type:
        # Download data for a specific event type
        response['Content-Disposition'] = f'attachment; filename="{event_type}_event_data.csv"'
        writer = csv.writer(response)
        writer.writerow(['Timestamp', 'Resource Type', 'Value'])

        events = Event.objects.filter(endpoint=endpoint, event_type=event_type).order_by('-time')
        for event in events:
            event_resources = EventResource.objects.filter(event=event).select_related('resource', 'resource__resource_type')
            for event_resource in event_resources:
                resource = event_resource.resource
                resource_type = resource.resource_type
                if resource_type.data_type == 'INTEGER':
                    value = resource.int_value
                elif resource_type.data_type == 'FLOAT':
                    value = resource.float_value
                elif resource_type.data_type == 'TIME':
                    value = resource.int_value  # Assuming TIME is stored as int
                else:
                    value = resource.str_value

                writer.writerow([
                    event.time.strftime('%Y-%m-%d %H:%M:%S'),
                    resource_type.name,
                    value
                ])

    else:
        # Download all resource data for the endpoint
        response['Content-Disposition'] = f'attachment; filename="all_resource_data.csv"'
        writer = csv.writer(response)
        writer.writerow(['Timestamp', 'Resource Type', 'Value'])

        last_thirty_days = timezone.now() - timedelta(days=30)
        resources = Resource.objects.filter(
            endpoint=endpoint,
            timestamp_created__gte=last_thirty_days
        ).select_related('resource_type').order_by('timestamp_created')

        for resource in resources:
            if resource.resource_type.data_type == 'INTEGER':
                value = resource.int_value
            elif resource.resource_type.data_type == 'FLOAT':
                value = resource.float_value
            elif resource.resource_type.data_type == 'TIME':
                value = resource.int_value  # Assuming TIME is stored as int
            else:
                value = resource.str_value

            writer.writerow([
                resource.timestamp_created.strftime('%Y-%m-%d %H:%M:%S'),
                resource.resource_type.name,
                value
            ])

    return response