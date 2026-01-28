#
# Copyright (c) 2024 Jonas Remmert
#
# SPDX-License-Identifier: Apache-2.0
#

import factory
from django.contrib.auth.models import User
from factory.django import DjangoModelFactory

from .models import Endpoint, EndpointOperation, Event, Resource, ResourceType


class UserFactory(DjangoModelFactory):
    class Meta:
        model = User
        skip_postgeneration_save = True

    username = factory.Faker("user_name")
    email = factory.Faker("email")

    @factory.post_generation
    def password(self, create, extracted, **kwargs):
        if not create:
            return
        self.set_password(extracted or "password123")
        self.save()


class EndpointFactory(DjangoModelFactory):
    class Meta:
        model = Endpoint

    endpoint = factory.Sequence(lambda n: f"urn:imei:10000000000000{n}")
    registered = True


class ResourceTypeFactory(DjangoModelFactory):
    class Meta:
        model = ResourceType
        django_get_or_create = ("object_id", "resource_id")

    object_id = 3303
    resource_id = 5700
    name = "Temperature"
    data_type = ResourceType.FLOAT


class ResourceFactory(DjangoModelFactory):
    class Meta:
        model = Resource

    endpoint = factory.SubFactory(EndpointFactory)
    resource_type = factory.SubFactory(ResourceTypeFactory)
    float_value = factory.Faker(
        "pyfloat", left_digits=2, right_digits=1, min_value=15.0, max_value=30.0
    )


class EventFactory(DjangoModelFactory):
    class Meta:
        model = Event

    endpoint = factory.SubFactory(EndpointFactory)
    event_type = "DATA_UPDATE"


class EndpointOperationFactory(DjangoModelFactory):
    class Meta:
        model = EndpointOperation

    resource = factory.SubFactory(ResourceFactory)
    operation_type = "send"
    status = EndpointOperation.Status.QUEUED
