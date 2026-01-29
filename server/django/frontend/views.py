#
# Copyright (c) 2026 Jonas Remmert
#
# SPDX-License-Identifier: Apache-2.0
#

from datetime import timedelta

from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.db.models import Count, Max
from django.http import JsonResponse
from django.shortcuts import redirect, render
from django.utils import timezone

from sensordata.models import Endpoint, Event, Firmware, Resource, ResourceType


@login_required
def dashboard(request):
    # Device Statistics
    total_devices = Endpoint.objects.count()
    registered_devices = Endpoint.objects.filter(registered=True).count()
    offline_devices = total_devices - registered_devices

    # Graph Data: Added values over time
    view_mode = request.GET.get("view", "hourly")  # 'hourly', 'daily', or 'five_min'
    now = timezone.now()

    if view_mode == "daily":
        end_date = now.replace(hour=0, minute=0, second=0, microsecond=0)
        num_steps = 10
        start_date = end_date - timedelta(days=num_steps - 1)
        date_format = "%Y-%m-%d"
        delta = timedelta(days=1)
    elif view_mode == "five_min":
        end_date = now.replace(second=0, microsecond=0)
        end_date = end_date.replace(minute=(end_date.minute // 5) * 5)
        num_steps = 48  # 4 hours / 5 minutes = 48
        start_date = end_date - timedelta(minutes=5 * (num_steps - 1))
        date_format = "%H:%M"
        delta = timedelta(minutes=5)
    else:  # default to hourly (last 48h)
        end_date = now.replace(minute=0, second=0, microsecond=0)
        num_steps = 48
        start_date = end_date - timedelta(hours=num_steps - 1)
        date_format = "%Y-%m-%d %H:00"
        delta = timedelta(hours=1)

    labels = []
    data = []

    # Fill all steps from start_date to end_date
    current_step = start_date
    for _ in range(num_steps):
        next_step = current_step + delta
        # Optimized: Iterative range count is significantly faster than Trunc/GroupBy on SQLite
        val = Resource.objects.filter(
            timestamp_created__gte=current_step, timestamp_created__lt=next_step
        ).count()

        labels.append(current_step.strftime(date_format))
        data.append(val)
        current_step += delta

    # Firmware Distribution (latest version for all devices)
    # Get the latest firmware version (Object 3, Resource 3) for each device
    latest_firmware_ids = (
        Resource.objects.filter(resource_type__object_id=3, resource_type__resource_id=3)
        .values("endpoint")
        .annotate(max_id=Max("id"))
        .values_list("max_id", flat=True)
    )

    firmware_distribution = (
        Resource.objects.filter(id__in=latest_firmware_ids)
        .values("str_value")
        .annotate(count=Count("str_value"))
        .order_by("-count")
    )

    fw_labels = [item["str_value"] for item in firmware_distribution]
    fw_data = [item["count"] for item in firmware_distribution]

    if request.GET.get("format") == "json":
        return JsonResponse(
            {"labels": labels, "data": data, "fw_labels": fw_labels, "fw_data": fw_data}
        )

    context = {
        "total_devices": total_devices,
        "registered_devices": registered_devices,
        "offline_devices": offline_devices,
        "chart_labels": labels,
        "chart_data": data,
        "fw_labels": fw_labels,
        "fw_data": fw_data,
        "view_mode": view_mode,
    }

    if request.headers.get("HX-Request"):
        return render(request, "frontend/dashboard_stats.html", context)

    return render(request, "frontend/dashboard.html", context)


@login_required
def firmware_list(request):
    from sensordata.models import FirmwareUpdate
    from sensordata.tasks import process_pending_operations

    from .forms import FirmwareUpdateForm, FirmwareUploadForm

    upload_form = FirmwareUploadForm()
    update_form = FirmwareUpdateForm()

    if request.method == "POST":
        if "upload_fw" in request.POST:
            upload_form = FirmwareUploadForm(request.POST, request.FILES)
            if upload_form.is_valid():
                upload_form.save()
                return redirect("frontend:firmware_list")
        elif "start_update" in request.POST:
            update_form = FirmwareUpdateForm(request.POST)
            if update_form.is_valid():
                fw_update = update_form.save()
                process_pending_operations.delay(fw_update.endpoint.endpoint)
                return redirect("frontend:firmware_list")
        else:
            # Handle cases where hidden fields are missing (e.g. legacy tests)
            # Try to guess which form it is
            if "version" in request.POST:
                upload_form = FirmwareUploadForm(request.POST, request.FILES)
                if upload_form.is_valid():
                    upload_form.save()
                    return redirect("frontend:firmware_list")
            elif "endpoint" in request.POST:
                update_form = FirmwareUpdateForm(request.POST)
                if update_form.is_valid():
                    fw_update = update_form.save()
                    process_pending_operations.delay(fw_update.endpoint.endpoint)
                    return redirect("frontend:firmware_list")

    firmwares = Firmware.objects.all().order_by("-created_at")
    updates = (
        FirmwareUpdate.objects.all()
        .select_related("endpoint", "firmware")
        .order_by("-timestamp_created")
    )

    return render(
        request,
        "frontend/firmware.html",
        {
            "upload_form": upload_form,
            "update_form": update_form,
            "firmwares": firmwares,
            "updates": updates,
        },
    )


@login_required
def data_analysis(request):
    endpoints = Endpoint.objects.all()
    resource_types = ResourceType.objects.all().order_by("name")

    # Filters
    endpoint_id = request.GET.get("endpoint")
    resource_type_id = request.GET.get("resource_type")
    time_range = request.GET.get("time_range", "24h")
    mode = request.GET.get("mode", "values")  # 'values' or 'events'

    now = timezone.now()
    if time_range == "1h":
        start_date = now - timedelta(hours=1)
    elif time_range == "7d":
        start_date = now - timedelta(days=7)
    elif time_range == "30d":
        start_date = now - timedelta(days=30)
    elif time_range == "all":
        start_date = None
    else:  # default 24h
        start_date = now - timedelta(hours=24)

    if request.GET.get("format") == "json":
        if mode == "values":
            resources = Resource.objects.all().order_by("timestamp_created")
            if start_date:
                resources = resources.filter(timestamp_created__gte=start_date)
            if endpoint_id:
                resources = resources.filter(endpoint_id=endpoint_id)
            if resource_type_id:
                resources = resources.filter(resource_type_id=resource_type_id)

            # Limit to 1000 points for performance
            resources = resources[:1000]

            data = []
            resource_type_obj = None
            if resource_type_id:
                resource_type_obj = ResourceType.objects.get(id=resource_type_id)

            for r in resources:
                val = r.get_value()
                data.append(
                    {
                        "t": r.timestamp_created.isoformat(),
                        "y": val,
                    }
                )

            return JsonResponse(
                {
                    "data": data,
                    "is_numeric": resource_type_obj.data_type
                    in ["INTEGER", "FLOAT", "TIME", "BOOLEAN"]
                    if resource_type_obj
                    else False,
                }
            )

        elif mode == "events":
            sort_col = request.GET.get("sort", "time")
            sort_dir = request.GET.get("dir", "desc")
            order_string = f"{'' if sort_dir == 'asc' else '-'}{sort_col}"

            events = (
                Event.objects.all()
                .select_related("endpoint")
                .prefetch_related("resources__resource__resource_type")
                .order_by(order_string)
            )
            if start_date:
                events = events.filter(time__gte=start_date)
            if endpoint_id:
                events = events.filter(endpoint_id=endpoint_id)

            paginator = Paginator(events, 50)
            page_number = request.GET.get("page", 1)
            page_obj = paginator.get_page(page_number)

            event_list = []
            for e in page_obj:
                res_data = {}
                for er in e.resources.all():
                    res = er.resource
                    res_data[res.resource_type.name] = res.get_value()

                event_list.append(
                    {
                        "id": e.id,
                        "endpoint": e.endpoint.endpoint,
                        "type": e.event_type,
                        "time": e.time.isoformat(),
                        "data": res_data,
                    }
                )

            return JsonResponse(
                {
                    "events": event_list,
                    "has_next": page_obj.has_next(),
                    "has_previous": page_obj.has_previous(),
                    "number": page_obj.number,
                    "num_pages": paginator.num_pages,
                }
            )

    context = {
        "endpoints": endpoints,
        "resource_types": resource_types,
        "selected_endpoint": endpoint_id,
        "selected_resource_type": resource_type_id,
        "selected_time_range": time_range,
        "selected_mode": mode,
    }

    return render(request, "frontend/data_analysis.html", context)
