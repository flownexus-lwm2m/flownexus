#
# Copyright (c) 2026 Jonas Remmert
#
# SPDX-License-Identifier: Apache-2.0
#

from datetime import timedelta

from django.contrib.auth.decorators import login_required
from django.db.models import Count
from django.db.models.functions import TruncDay, TruncHour, TruncMinute
from django.http import JsonResponse
from django.shortcuts import render
from django.utils import timezone

from sensordata.models import Endpoint, Resource


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
        trunc_func = TruncDay
        date_format = "%Y-%m-%d"
        delta = timedelta(days=1)
    elif view_mode == "five_min":
        end_date = now.replace(second=0, microsecond=0)
        end_date = end_date.replace(minute=(end_date.minute // 5) * 5)
        num_steps = 48  # 4 hours / 5 minutes = 48
        start_date = end_date - timedelta(minutes=5 * (num_steps - 1))
        trunc_func = TruncMinute
        date_format = "%H:%M"
        delta = timedelta(minutes=5)
    else:  # default to hourly (last 48h)
        end_date = now.replace(minute=0, second=0, microsecond=0)
        num_steps = 48
        start_date = end_date - timedelta(hours=num_steps - 1)
        trunc_func = TruncHour
        date_format = "%Y-%m-%d %H:00"
        delta = timedelta(hours=1)

    # Query Resource objects (representing "values")
    chart_data_query = (
        Resource.objects.filter(timestamp_created__range=(start_date, now))
        .annotate(bucket=trunc_func("timestamp_created"))
        .values("bucket")
        .annotate(count=Count("id"))
        .order_by("bucket")
    )

    # Map results to buckets
    results_map = {entry["bucket"]: entry["count"] for entry in chart_data_query}

    labels = []
    data = []

    # Fill all steps from start_date to end_date
    current_step = start_date
    for _ in range(num_steps):
        if view_mode == "five_min":
            # Aggregate 5 minute buckets from 1-minute truncations
            val = sum(results_map.get(current_step + timedelta(minutes=i), 0) for i in range(5))
        else:
            val = results_map.get(current_step, 0)

        labels.append(current_step.strftime(date_format))
        data.append(val)
        current_step += delta

    if request.GET.get("format") == "json":
        return JsonResponse({"labels": labels, "data": data})

    context = {
        "total_devices": total_devices,
        "registered_devices": registered_devices,
        "offline_devices": offline_devices,
        "chart_labels": labels,
        "chart_data": data,
        "view_mode": view_mode,
    }

    if request.headers.get("HX-Request"):
        return render(request, "frontend/dashboard_stats.html", context)

    return render(request, "frontend/dashboard.html", context)
