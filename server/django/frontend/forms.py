#
# Copyright (c) 2026 Jonas Remmert
#
# SPDX-License-Identifier: Apache-2.0
#

from django import forms

from sensordata.models import Firmware


class FirmwareUploadForm(forms.ModelForm):
    class Meta:
        model = Firmware
        fields = ["version", "binary"]
        widgets = {
            "version": forms.TextInput(attrs={"class": "form-control", "placeholder": "v1.0.0"}),
            "binary": forms.FileInput(attrs={"class": "form-control"}),
        }
