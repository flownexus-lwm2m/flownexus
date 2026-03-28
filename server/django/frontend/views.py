#
# Copyright (c) 2026 Jonas Remmert
#
# SPDX-License-Identifier: Apache-2.0
#

from datetime import timedelta
from io import BytesIO
from typing import Any

from django.contrib.auth import get_user_model
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.db.models import Count, Max
from django.http import HttpResponse, HttpResponseForbidden, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.utils.dateparse import parse_datetime
from openpyxl import Workbook
from openpyxl.styles import Font

from core.middleware import UNASSIGNED_SITE_KEY
from core.permissions import get_site_filtered_endpoints, has_site_permission
from sensordata.models import Endpoint, Event, Firmware, Resource, ResourceType, SiteMembership

from .forms import (
    BulkDeviceAssignmentForm,
    DeviceAssignmentForm,
    DeviceTransferForm,
    FirmwareUpdateForm,
    FirmwareUploadForm,
    GlobalAdminUserCreationForm,
    ProfilePasswordChangeForm,
    SiteMembershipCreateForm,
    SiteMembershipUpdateForm,
)

User = get_user_model()


DEVICE_DETAIL_RESOURCES: dict[tuple[int, int], str] = {
    (3, 0): "manufacturer",
    (3, 1): "model_number",
    (3, 2): "serial_number",
    (3, 3): "firmware_version",
    (3, 7): "power_source_v",
    (3, 9): "battery_level",
}


def _get_site_filtered_endpoints(request):
    """Get endpoints filtered by the user's current site context."""
    return get_site_filtered_endpoints(request)


def _check_site_permission(request, permission_name):
    """Check if user has specific permission for the current site."""
    return has_site_permission(request.user, request, permission_name)


def _resource_display_value(resource: Resource) -> Any:
    value_field = resource.resource_type.get_value_field()
    if not value_field:
        return None

    value = getattr(resource, value_field)
    if value in (None, ""):
        return None

    return value


def _enrich_endpoints_with_details(endpoints: list[Any]) -> list[Any]:
    endpoint_ids = [endpoint.pk for endpoint in endpoints]
    if not endpoint_ids:
        return endpoints

    resources = (
        Resource.objects.filter(
            endpoint_id__in=endpoint_ids,
            resource_type__object_id__in={object_id for object_id, _ in DEVICE_DETAIL_RESOURCES},
            resource_type__resource_id__in={
                resource_id for _, resource_id in DEVICE_DETAIL_RESOURCES
            },
        )
        .select_related("resource_type")
        .order_by("endpoint_id", "resource_type__object_id", "resource_type__resource_id", "-id")
    )

    latest_values: dict[tuple[str, int, int], Any] = {}
    for resource in resources:
        key = (
            resource.endpoint_id,
            resource.resource_type.object_id,
            resource.resource_type.resource_id,
        )
        if key not in latest_values:
            latest_values[key] = _resource_display_value(resource)

    for endpoint in endpoints:
        for resource_key, attribute_name in DEVICE_DETAIL_RESOURCES.items():
            setattr(endpoint, attribute_name, latest_values.get((endpoint.pk, *resource_key)))

    return endpoints


def _build_permissions_context(
    *,
    user_creation_form: GlobalAdminUserCreationForm | None = None,
    membership_create_form: SiteMembershipCreateForm | None = None,
    device_assignment_form: DeviceAssignmentForm | None = None,
    bulk_assignment_form: BulkDeviceAssignmentForm | None = None,
    membership_update_forms: dict[int, SiteMembershipUpdateForm] | None = None,
    device_transfer_forms: dict[str, DeviceTransferForm] | None = None,
) -> dict[str, Any]:
    memberships = list(
        SiteMembership.objects.select_related("user", "site").order_by(
            "user__username", "site__name"
        )
    )
    membership_update_forms = membership_update_forms or {}
    for membership in memberships:
        membership.update_form = membership_update_forms.get(
            membership.pk,
            SiteMembershipUpdateForm(instance=membership, prefix=f"membership-{membership.pk}"),
        )

    assigned_endpoints = list(
        Endpoint.objects.select_related("site")
        .filter(site__isnull=False)
        .order_by("site__name", "endpoint")
    )
    device_transfer_forms = device_transfer_forms or {}
    for endpoint in assigned_endpoints:
        endpoint.transfer_form = device_transfer_forms.get(
            endpoint.pk,
            DeviceTransferForm(
                prefix=f"transfer-{endpoint.pk}", initial={"site": endpoint.site_id}
            ),
        )

    unassigned_endpoints = list(Endpoint.objects.filter(site__isnull=True).order_by("endpoint"))
    users = list(User.objects.order_by("username").prefetch_related("site_memberships__site"))

    return {
        "user_creation_form": user_creation_form
        or GlobalAdminUserCreationForm(prefix="create-user"),
        "membership_create_form": membership_create_form
        or SiteMembershipCreateForm(prefix="create-membership"),
        "device_assignment_form": device_assignment_form
        or DeviceAssignmentForm(prefix="assign-device"),
        "bulk_assignment_form": bulk_assignment_form
        or BulkDeviceAssignmentForm(prefix="bulk-assign"),
        "managed_users": users,
        "memberships": memberships,
        "assigned_endpoints": assigned_endpoints,
        "unassigned_endpoints": unassigned_endpoints,
    }


@login_required
def switch_site(request, site_id):
    """Switch the current site context for the user."""
    if not request.user.is_authenticated:
        return redirect("login")

    # Handle "all" devices option (available if user has access to >1 site)
    if site_id == "all":
        available_sites = getattr(request, "available_sites", [])
        if len(available_sites) > 1:
            request.session["current_site_id"] = "all"
    # Verify user has access to this site
    elif request.user.is_superuser and site_id == UNASSIGNED_SITE_KEY:
        request.session["current_site_id"] = UNASSIGNED_SITE_KEY
    elif request.user.is_superuser:
        # Global admin can switch to any site
        try:
            from sensordata.models import Site

            site = Site.objects.get(id=site_id, is_active=True)
            request.session["current_site_id"] = site.id
        except (Site.DoesNotExist, ValueError):
            pass
    else:
        # Check if user has membership to this site
        from sensordata.models import SiteMembership

        try:
            membership = SiteMembership.objects.get(
                user=request.user, site_id=site_id, site__is_active=True
            )
            request.session["current_site_id"] = membership.site.id
        except (SiteMembership.DoesNotExist, ValueError):
            pass

    # Redirect back to referring page or dashboard
    next_url = request.META.get("HTTP_REFERER", "/")
    return redirect(next_url)


@login_required
def dashboard(request):
    # Check permission
    if not _check_site_permission(request, "can_view_overview"):
        return HttpResponseForbidden("You don't have permission to view this page.")

    # Device Statistics - filtered by site
    endpoints_qs = get_site_filtered_endpoints(request, "can_view_overview")
    total_devices = endpoints_qs.count()
    registered_devices = endpoints_qs.filter(registered=True).count()
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
    site_endpoints = get_site_filtered_endpoints(request, "can_view_overview")
    for _ in range(num_steps):
        next_step = current_step + delta
        # Optimized: Iterative range count is significantly faster than Trunc/GroupBy on SQLite
        val = Resource.objects.filter(
            timestamp_created__gte=current_step,
            timestamp_created__lt=next_step,
            endpoint__in=site_endpoints,
        ).count()

        labels.append(current_step.strftime(date_format))
        data.append(val)
        current_step += delta

    # Firmware Distribution (latest version for devices in current site)
    # Get the latest firmware version (Object 3, Resource 3) for each device
    site_endpoints = get_site_filtered_endpoints(request, "can_view_overview")
    latest_firmware_ids = (
        Resource.objects.filter(
            resource_type__object_id=3,
            resource_type__resource_id=3,
            endpoint__in=site_endpoints,
        )
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
def devices(request):
    if not _check_site_permission(request, "can_view_overview"):
        return HttpResponseForbidden("You don't have permission to view this page.")

    selected_endpoint_id = request.GET.get("selected")

    endpoints = list(
        get_site_filtered_endpoints(request, "can_view_overview")
        .select_related("site")
        .annotate(last_seen=Max("resource__timestamp_created"), telemetry_count=Count("resource"))
        .order_by("endpoint")
    )

    endpoints = _enrich_endpoints_with_details(endpoints)
    selected_endpoint = next(
        (endpoint for endpoint in endpoints if endpoint.endpoint == selected_endpoint_id),
        endpoints[0] if endpoints else None,
    )

    return render(
        request,
        "frontend/devices.html",
        {
            "endpoints": endpoints,
            "selected_endpoint": selected_endpoint,
            "selected_endpoint_id": selected_endpoint.endpoint if selected_endpoint else None,
        },
    )


@login_required
def firmware_list(request):
    # Check permission
    if not _check_site_permission(request, "can_view_firmware"):
        return HttpResponseForbidden("You don't have permission to view this page.")

    from sensordata.models import FirmwareUpdate
    from sensordata.tasks import process_pending_operations

    can_manage_firmware = _check_site_permission(request, "can_manage_firmware")
    can_perform_operations = _check_site_permission(request, "can_perform_operations")

    upload_form = FirmwareUploadForm()
    update_form = FirmwareUpdateForm()

    if request.method == "POST":
        if "upload_fw" in request.POST:
            if not can_manage_firmware:
                return HttpResponseForbidden("You don't have permission to manage firmware.")
            upload_form = FirmwareUploadForm(request.POST, request.FILES)
            if upload_form.is_valid():
                upload_form.save()
                return redirect("frontend:firmware_list")
        elif "start_update" in request.POST:
            if not can_perform_operations:
                return HttpResponseForbidden("You don't have permission to perform operations.")
            update_form = FirmwareUpdateForm(request.POST)
            # Ensure the endpoint belongs to the user's site
            site_endpoints = get_site_filtered_endpoints(request, "can_perform_operations")
            update_form.fields["endpoint"].queryset = site_endpoints

            if update_form.is_valid():
                fw_update = update_form.save()
                process_pending_operations.delay(fw_update.endpoint.endpoint)
                return redirect("frontend:firmware_list")
        elif "delete_fw" in request.POST:
            if not can_manage_firmware:
                return HttpResponseForbidden("You don't have permission to manage firmware.")
            firmware_id = request.POST.get("firmware_id")
            if firmware_id:
                try:
                    firmware = Firmware.objects.get(pk=firmware_id)
                    # Soft delete: just mark as deleted
                    firmware.is_deleted = True
                    firmware.save()
                except Firmware.DoesNotExist:
                    pass
            return redirect("frontend:firmware_list")
        else:
            # Handle cases where hidden fields are missing (e.g. legacy tests)
            # Try to guess which form it is
            if "version" in request.POST:
                if not can_manage_firmware:
                    return HttpResponseForbidden("You don't have permission to manage firmware.")
                upload_form = FirmwareUploadForm(request.POST, request.FILES)
                if upload_form.is_valid():
                    upload_form.save()
                    return redirect("frontend:firmware_list")
            elif "endpoint" in request.POST:
                if not can_perform_operations:
                    return HttpResponseForbidden("You don't have permission to perform operations.")
                update_form = FirmwareUpdateForm(request.POST)
                # Ensure the endpoint belongs to the user's site
                site_endpoints = get_site_filtered_endpoints(request, "can_perform_operations")
                update_form.fields["endpoint"].queryset = site_endpoints

                if update_form.is_valid():
                    fw_update = update_form.save()
                    process_pending_operations.delay(fw_update.endpoint.endpoint)
                    return redirect("frontend:firmware_list")

    # Filter out soft-deleted firmwares for the frontend list
    firmwares = Firmware.objects.filter(is_deleted=False).order_by("-created_at")
    # Check file existence for each firmware
    for fw in firmwares:
        fw.file_exists = fw.binary.storage.exists(fw.binary.name) if fw.binary else False

    # Filter update form to only show non-deleted firmwares with existing files
    existing_firmware_ids = [fw.id for fw in firmwares if fw.file_exists]
    update_form.fields["firmware"].queryset = Firmware.objects.filter(id__in=existing_firmware_ids)

    # Filter endpoints by current site
    site_endpoints = get_site_filtered_endpoints(request, "can_perform_operations")
    update_form.fields["endpoint"].queryset = site_endpoints

    # Filter updates by site (via endpoint)
    updates = (
        FirmwareUpdate.objects.filter(
            endpoint__in=get_site_filtered_endpoints(request, "can_view_firmware")
        )
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
            "can_manage_firmware": can_manage_firmware,
        },
    )


@login_required
def permissions(request):
    if not request.user.is_superuser:
        return HttpResponseForbidden("You don't have permission to view this page.")

    context_overrides: dict[str, Any] = {}

    if request.method == "POST":
        if "create_user" in request.POST:
            user_creation_form = GlobalAdminUserCreationForm(request.POST, prefix="create-user")
            if user_creation_form.is_valid():
                user_creation_form.save()
                return redirect("frontend:permissions")
            context_overrides["user_creation_form"] = user_creation_form

        elif "create_membership" in request.POST:
            membership_create_form = SiteMembershipCreateForm(
                request.POST, prefix="create-membership"
            )
            if membership_create_form.is_valid():
                membership_create_form.save()
                return redirect("frontend:permissions")
            context_overrides["membership_create_form"] = membership_create_form

        elif "update_membership" in request.POST:
            membership = get_object_or_404(SiteMembership, pk=request.POST.get("membership_id"))
            membership_form = SiteMembershipUpdateForm(
                request.POST,
                instance=membership,
                prefix=f"membership-{membership.pk}",
            )
            if membership_form.is_valid():
                membership_form.save()
                return redirect("frontend:permissions")
            context_overrides["membership_update_forms"] = {membership.pk: membership_form}

        elif "revoke_membership" in request.POST:
            membership = get_object_or_404(SiteMembership, pk=request.POST.get("membership_id"))
            membership.delete()
            return redirect("frontend:permissions")

        elif "assign_device" in request.POST:
            device_assignment_form = DeviceAssignmentForm(request.POST, prefix="assign-device")
            if device_assignment_form.is_valid():
                endpoint = device_assignment_form.cleaned_data["endpoint"]
                endpoint.site = device_assignment_form.cleaned_data["site"]
                endpoint.save(update_fields=["site"])
                return redirect("frontend:permissions")
            context_overrides["device_assignment_form"] = device_assignment_form

        elif "transfer_device" in request.POST:
            endpoint = get_object_or_404(
                Endpoint.objects.select_related("site"),
                pk=request.POST.get("endpoint_id"),
            )
            transfer_form = DeviceTransferForm(request.POST, prefix=f"transfer-{endpoint.pk}")
            if transfer_form.is_valid():
                endpoint.site = transfer_form.cleaned_data["site"]
                endpoint.save(update_fields=["site"])
                return redirect("frontend:permissions")
            context_overrides["device_transfer_forms"] = {endpoint.pk: transfer_form}

        elif "bulk_assign" in request.POST:
            bulk_assignment_form = BulkDeviceAssignmentForm(request.POST, prefix="bulk-assign")
            if bulk_assignment_form.is_valid():
                site = bulk_assignment_form.cleaned_data["site"]
                endpoint_ids = [
                    endpoint.pk for endpoint in bulk_assignment_form.cleaned_data["endpoints"]
                ]
                Endpoint.objects.filter(pk__in=endpoint_ids, site__isnull=True).update(site=site)
                return redirect("frontend:permissions")
            context_overrides["bulk_assignment_form"] = bulk_assignment_form

        else:
            return HttpResponseForbidden("Unknown permissions action.")

    return render(
        request, "frontend/permissions.html", _build_permissions_context(**context_overrides)
    )


@login_required
def data_analysis(request):
    # Check permission
    if not _check_site_permission(request, "can_view_data_analysis"):
        return HttpResponseForbidden("You don't have permission to view this page.")

    # Filter endpoints by current site
    endpoints = get_site_filtered_endpoints(request, "can_view_data_analysis")
    resource_types = ResourceType.objects.all().order_by("name")

    # Filters — treat "all" sentinel (from UI placeholder) as no filter
    endpoint_id = request.GET.get("endpoint") or None
    if endpoint_id == "all":
        endpoint_id = None
    resource_type_id = request.GET.get("resource_type") or None
    if resource_type_id == "all":
        resource_type_id = None
    time_range = request.GET.get("time_range", "24h")
    mode = request.GET.get("mode", "values")  # 'values' or 'events'

    now = timezone.now()
    start_date = None
    end_date = None
    if time_range == "1h":
        start_date = now - timedelta(hours=1)
    elif time_range == "7d":
        start_date = now - timedelta(days=7)
    elif time_range == "30d":
        start_date = now - timedelta(days=30)
    elif time_range == "custom":
        time_from_str = request.GET.get("time_from")
        time_to_str = request.GET.get("time_to")
        if time_from_str:
            try:
                parsed = parse_datetime(time_from_str)
                if parsed:
                    start_date = (
                        timezone.make_aware(parsed) if timezone.is_naive(parsed) else parsed
                    )
            except (ValueError, TypeError):
                pass
        if time_to_str:
            try:
                parsed = parse_datetime(time_to_str)
                if parsed:
                    end_date = timezone.make_aware(parsed) if timezone.is_naive(parsed) else parsed
                    # Flatpickr resolution is 1 minute; extend end by 1 minute so that
                    # "12:00 – 12:01" includes readings timestamped at 12:01:xx.
                    end_date = end_date + timedelta(minutes=1)
            except (ValueError, TypeError):
                pass
    elif time_range == "all":
        start_date = None
    else:  # default 24h
        start_date = now - timedelta(hours=24)

    if request.GET.get("format") == "json":
        if mode == "values":
            # Filter resources by site through endpoints
            site_endpoints = get_site_filtered_endpoints(request, "can_view_data_analysis")
            resources = (
                Resource.objects.filter(endpoint__in=site_endpoints)
                .order_by("timestamp_created")
                .select_related("endpoint")
            )
            if start_date:
                resources = resources.filter(timestamp_created__gte=start_date)
            if end_date:
                resources = resources.filter(timestamp_created__lte=end_date)
            if endpoint_id:
                resources = resources.filter(endpoint_id=endpoint_id)
            if resource_type_id:
                resources = resources.filter(resource_type_id=resource_type_id)

            resource_type_obj = None
            if resource_type_id:
                resource_type_obj = ResourceType.objects.get(id=resource_type_id)

            paginator = Paginator(resources, 100)
            page_number = request.GET.get("page", 1)
            page_obj = paginator.get_page(page_number)

            data = []
            for r in page_obj:
                val = r.get_value()
                data.append(
                    {
                        "t": r.timestamp_created.isoformat(),
                        "y": val,
                        "endpoint": r.endpoint.endpoint,
                    }
                )

            return JsonResponse(
                {
                    "data": data,
                    "multi_endpoint": not bool(endpoint_id),
                    "is_numeric": resource_type_obj.data_type
                    in ["INTEGER", "FLOAT", "TIME", "BOOLEAN"]
                    if resource_type_obj
                    else False,
                    "has_next": page_obj.has_next(),
                    "has_previous": page_obj.has_previous(),
                    "number": page_obj.number,
                    "num_pages": paginator.num_pages,
                    "count": paginator.count,
                }
            )

        elif mode == "events":
            sort_col = request.GET.get("sort", "time")
            sort_dir = request.GET.get("dir", "desc")
            order_string = f"{'' if sort_dir == 'asc' else '-'}{sort_col}"

            # Filter events by site through endpoints
            site_endpoints = get_site_filtered_endpoints(request, "can_view_data_analysis")
            events = (
                Event.objects.filter(endpoint__in=site_endpoints)
                .select_related("endpoint")
                .prefetch_related("resources__resource__resource_type")
                .order_by(order_string)
            )
            if start_date:
                events = events.filter(time__gte=start_date)
            if end_date:
                events = events.filter(time__lte=end_date)
            if endpoint_id:
                events = events.filter(endpoint_id=endpoint_id)
            event_type_filter = request.GET.get("event_type") or None
            if event_type_filter:
                events = events.filter(event_type=event_type_filter)

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

    # Get distinct event types for the filter dropdown (scoped to user's site)
    event_types = (
        Event.objects.filter(endpoint__in=endpoints)
        .values_list("event_type", flat=True)
        .distinct()
        .order_by("event_type")
    )

    context = {
        "endpoints": endpoints,
        "resource_types": resource_types,
        "event_types": event_types,
        "selected_endpoint": request.GET.get("endpoint", ""),
        "selected_resource_type": request.GET.get("resource_type", ""),
        "selected_event_type": request.GET.get("event_type", ""),
        "selected_time_range": time_range,
        "selected_time_from": request.GET.get("time_from", ""),
        "selected_time_to": request.GET.get("time_to", ""),
        "selected_mode": mode,
    }

    return render(request, "frontend/data_analysis.html", context)


EXPORT_ROW_LIMIT = 50_000


def _parse_export_filters(request: Any) -> dict[str, Any]:
    """Parse and normalise the shared filter parameters used by both the data_analysis
    view and the export view so the logic lives in exactly one place."""
    endpoint_id = request.GET.get("endpoint") or None
    if endpoint_id == "all":
        endpoint_id = None
    resource_type_id = request.GET.get("resource_type") or None
    if resource_type_id == "all":
        resource_type_id = None
    event_type_filter = request.GET.get("event_type") or None
    time_range = request.GET.get("time_range", "24h")
    mode = request.GET.get("mode", "values")

    now = timezone.now()
    start_date = None
    end_date = None
    if time_range == "1h":
        start_date = now - timedelta(hours=1)
    elif time_range == "7d":
        start_date = now - timedelta(days=7)
    elif time_range == "30d":
        start_date = now - timedelta(days=30)
    elif time_range == "custom":
        time_from_str = request.GET.get("time_from")
        time_to_str = request.GET.get("time_to")
        if time_from_str:
            try:
                parsed = parse_datetime(time_from_str)
                if parsed:
                    start_date = (
                        timezone.make_aware(parsed) if timezone.is_naive(parsed) else parsed
                    )
            except (ValueError, TypeError):
                pass
        if time_to_str:
            try:
                parsed = parse_datetime(time_to_str)
                if parsed:
                    end_date = timezone.make_aware(parsed) if timezone.is_naive(parsed) else parsed
                    end_date = end_date + timedelta(minutes=1)
            except (ValueError, TypeError):
                pass
    elif time_range == "all":
        start_date = None
    else:  # default 24h
        start_date = now - timedelta(hours=24)

    return {
        "endpoint_id": endpoint_id,
        "resource_type_id": resource_type_id,
        "event_type_filter": event_type_filter,
        "mode": mode,
        "start_date": start_date,
        "end_date": end_date,
    }


@login_required
def data_analysis_export(request):
    """Stream an Excel (.xlsx) export of all rows matching the current filter.

    Returns HTTP 400 JSON if the result set would exceed EXPORT_ROW_LIMIT rows.
    """
    if not _check_site_permission(request, "can_view_data_analysis"):
        return HttpResponseForbidden("You don't have permission to view this page.")

    filters = _parse_export_filters(request)
    endpoint_id = filters["endpoint_id"]
    resource_type_id = filters["resource_type_id"]
    event_type_filter = filters["event_type_filter"]
    mode = filters["mode"]
    start_date = filters["start_date"]
    end_date = filters["end_date"]

    site_endpoints = get_site_filtered_endpoints(request, "can_view_data_analysis")

    wb = Workbook()
    ws = wb.active
    bold = Font(bold=True)

    if mode == "values":
        resources = (
            Resource.objects.filter(endpoint__in=site_endpoints)
            .order_by("timestamp_created")
            .select_related("endpoint", "resource_type")
        )
        if start_date:
            resources = resources.filter(timestamp_created__gte=start_date)
        if end_date:
            resources = resources.filter(timestamp_created__lte=end_date)
        if endpoint_id:
            resources = resources.filter(endpoint_id=endpoint_id)
        if resource_type_id:
            resources = resources.filter(resource_type_id=resource_type_id)

        count = resources.count()
        if count > EXPORT_ROW_LIMIT:
            msg = f"Export exceeds {EXPORT_ROW_LIMIT:,} rows. Narrow your filter and try again."
            return JsonResponse({"error": msg}, status=400)

        multi_endpoint = not bool(endpoint_id)
        if multi_endpoint:
            headers = ["Time", "Endpoint", "Resource Type", "Value"]
        else:
            headers = ["Time", "Resource Type", "Value"]

        ws.append(headers)
        for cell in ws[1]:
            cell.font = bold

        for r in resources:
            ts = r.timestamp_created.strftime("%Y-%m-%d %H:%M:%S") if r.timestamp_created else ""
            val = r.get_value()
            rt_name = r.resource_type.name if r.resource_type else ""
            if multi_endpoint:
                ws.append([ts, r.endpoint.endpoint, rt_name, val])
            else:
                ws.append([ts, rt_name, val])

        ws.title = "Sensor Values"

    else:  # events mode
        events = (
            Event.objects.filter(endpoint__in=site_endpoints)
            .select_related("endpoint")
            .prefetch_related("resources__resource__resource_type")
            .order_by("-time")
        )
        if start_date:
            events = events.filter(time__gte=start_date)
        if end_date:
            events = events.filter(time__lte=end_date)
        if endpoint_id:
            events = events.filter(endpoint_id=endpoint_id)
        if event_type_filter:
            events = events.filter(event_type=event_type_filter)

        count = events.count()
        if count > EXPORT_ROW_LIMIT:
            msg = f"Export exceeds {EXPORT_ROW_LIMIT:,} rows. Narrow your filter and try again."
            return JsonResponse({"error": msg}, status=400)

        # Two-pass: collect all resource names first, then write rows
        event_list = list(events)
        resource_names: dict[str, None] = {}
        for e in event_list:
            for er in e.resources.all():
                resource_names[er.resource.resource_type.name] = None
        extra_cols = list(resource_names.keys())

        headers = ["Time", "Endpoint", "Event Type"] + extra_cols
        ws.append(headers)
        for cell in ws[1]:
            cell.font = bold

        for e in event_list:
            res_data: dict[str, Any] = {}
            for er in e.resources.all():
                res = er.resource
                res_data[res.resource_type.name] = res.get_value()
            ts = e.time.strftime("%Y-%m-%d %H:%M:%S")
            row = [ts, e.endpoint.endpoint, e.event_type]
            row += [res_data.get(name, "") for name in extra_cols]
            ws.append(row)

        ws.title = "Events"

    buffer = BytesIO()
    wb.save(buffer)
    buffer.seek(0)

    response = HttpResponse(
        buffer.read(),
        content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    )
    response["Content-Disposition"] = 'attachment; filename="flownexus_export.xlsx"'
    return response


def profile(request):
    """Display user profile with memberships and password change form."""
    memberships = (
        SiteMembership.objects.filter(user=request.user)
        .select_related("site")
        .order_by("site__name")
    )

    password_form = ProfilePasswordChangeForm(user=request.user)
    password_success = False

    if request.method == "POST":
        password_form = ProfilePasswordChangeForm(user=request.user, data=request.POST)
        if password_form.is_valid():
            password_form.save()
            password_success = True
            password_form = ProfilePasswordChangeForm(user=request.user)

    context = {
        "memberships": memberships,
        "password_form": password_form,
        "password_success": password_success,
    }

    return render(request, "frontend/profile.html", context)
