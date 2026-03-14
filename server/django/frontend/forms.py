#
# Copyright (c) 2026 Jonas Remmert
#
# SPDX-License-Identifier: Apache-2.0
#

from django import forms
from django.contrib.auth import get_user_model
from django.contrib.auth.forms import PasswordChangeForm, UserCreationForm

from sensordata.models import Endpoint, Firmware, FirmwareUpdate, Site, SiteMembership

User = get_user_model()


class TablerStyledFormMixin:
    def _apply_tabler_styles(self) -> None:
        for field in getattr(self, "fields", {}).values():
            widget = field.widget
            if isinstance(widget, forms.HiddenInput):
                continue
            if isinstance(widget, forms.CheckboxInput):
                css_class = "form-check-input"
            elif isinstance(widget, forms.Select | forms.SelectMultiple):
                css_class = "form-select"
            else:
                css_class = "form-control"
            widget.attrs["class"] = css_class


class GlobalAdminUserCreationForm(TablerStyledFormMixin, UserCreationForm):
    email = forms.EmailField(required=False)

    class Meta(UserCreationForm.Meta):
        model = User
        fields = ("username", "email", "password1", "password2")

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._apply_tabler_styles()

    def save(self, commit: bool = True):
        user = super().save(commit=False)
        user.email = self.cleaned_data.get("email", "")
        if commit:
            user.save()
        return user


class SiteMembershipCreateForm(TablerStyledFormMixin, forms.ModelForm):
    class Meta:
        model = SiteMembership
        fields = [
            "user",
            "site",
            "role",
            "can_view_overview",
            "can_view_firmware",
            "can_view_data_analysis",
            "can_manage_firmware",
            "can_perform_operations",
        ]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["can_view_overview"].label = "Overview"
        self.fields["can_view_firmware"].label = "Firmware"
        self.fields["can_view_data_analysis"].label = "Data"
        self.fields["can_manage_firmware"].label = "Manage firmware"
        self.fields["can_perform_operations"].label = "Perform operations"
        self.fields["user"].queryset = User.objects.order_by("username")
        self.fields["site"].queryset = Site.objects.filter(is_active=True).order_by("name")
        self._apply_tabler_styles()

    def clean(self):
        cleaned_data = super().clean()
        user = cleaned_data.get("user")
        site = cleaned_data.get("site")
        if user and site and SiteMembership.objects.filter(user=user, site=site).exists():
            raise forms.ValidationError("This user already has a membership for the selected site.")
        return cleaned_data

    def save(self, commit: bool = True):
        membership = super().save(commit=False)
        membership._explicit_permission_fields = set(membership.PERMISSION_FIELDS)
        if commit:
            membership.save()
        return membership


class SiteMembershipUpdateForm(TablerStyledFormMixin, forms.ModelForm):
    class Meta:
        model = SiteMembership
        fields = [
            "role",
            "can_view_overview",
            "can_view_firmware",
            "can_view_data_analysis",
            "can_manage_firmware",
            "can_perform_operations",
        ]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["can_view_overview"].label = "Overview"
        self.fields["can_view_firmware"].label = "Firmware"
        self.fields["can_view_data_analysis"].label = "Data"
        self.fields["can_manage_firmware"].label = "Manage firmware"
        self.fields["can_perform_operations"].label = "Perform operations"
        self._apply_tabler_styles()


class DeviceAssignmentForm(TablerStyledFormMixin, forms.Form):
    endpoint = forms.ModelChoiceField(queryset=Endpoint.objects.none(), label="Unassigned device")
    site = forms.ModelChoiceField(queryset=Site.objects.none())

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["endpoint"].queryset = Endpoint.objects.filter(site__isnull=True).order_by(
            "endpoint"
        )
        self.fields["site"].queryset = Site.objects.filter(is_active=True).order_by("name")
        self._apply_tabler_styles()


class DeviceTransferForm(TablerStyledFormMixin, forms.Form):
    site = forms.ModelChoiceField(queryset=Site.objects.none(), label="Destination site")

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["site"].queryset = Site.objects.filter(is_active=True).order_by("name")
        self._apply_tabler_styles()


class BulkDeviceAssignmentForm(TablerStyledFormMixin, forms.Form):
    endpoints = forms.ModelMultipleChoiceField(
        queryset=Endpoint.objects.none(),
        widget=forms.SelectMultiple(attrs={"size": 15}),
        label="Unassigned devices",
    )
    site = forms.ModelChoiceField(queryset=Site.objects.none())

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["endpoints"].queryset = Endpoint.objects.filter(site__isnull=True).order_by(
            "endpoint"
        )
        self.fields["site"].queryset = Site.objects.filter(is_active=True).order_by("name")
        self._apply_tabler_styles()


class FirmwareUploadForm(forms.ModelForm):
    class Meta:
        model = Firmware
        fields = ["version", "binary"]
        widgets = {
            "version": forms.TextInput(attrs={"class": "form-control", "placeholder": "v1.0.0"}),
            "binary": forms.FileInput(attrs={"class": "form-control"}),
        }


class FirmwareUpdateForm(forms.ModelForm):
    class Meta:
        model = FirmwareUpdate
        fields = ["endpoint", "firmware"]
        widgets = {
            "endpoint": forms.Select(attrs={"class": "form-select"}),
            "firmware": forms.Select(attrs={"class": "form-select"}),
        }


class ProfilePasswordChangeForm(TablerStyledFormMixin, PasswordChangeForm):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["old_password"].label = "Current Password"
        self.fields["new_password1"].label = "New Password"
        self.fields["new_password2"].label = "Confirm New Password"
        self._apply_tabler_styles()
