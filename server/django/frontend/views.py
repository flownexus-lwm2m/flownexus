#
# Copyright (c) 2026 Jonas Remmert
#
# SPDX-License-Identifier: Apache-2.0
#

from django.contrib.auth.decorators import login_required
from django.shortcuts import render

from sensordata.models import Endpoint


@login_required
def dashboard(request):
    endpoints = Endpoint.objects.all()
    context = {
        "endpoints": endpoints,
    }
    return render(request, "frontend/dashboard.html", context)
