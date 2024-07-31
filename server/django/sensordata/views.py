#
# Copyright (c) 2024 Jonas Remmert
#
# SPDX-License-Identifier: Apache-2.0
#

from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from rest_framework.exceptions import ValidationError
from .serializers.single_resource_serializer import SingleResourceSerializer
from .serializers.composite_resource_serializer import CompositeResourceSerializer
import traceback
import logging

logger = logging.getLogger(__name__)


class PostSingleResourceView(APIView):
    serializer_class = SingleResourceSerializer

    def post(self, request):
        serializer = SingleResourceSerializer(data=request.data, many=False)
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
    serializer_class = CompositeResourceSerializer

    def post(self, request):
        serializer = CompositeResourceSerializer(data=request.data, many=False)
        try:
            if serializer.is_valid(raise_exception=True):
                serializer.save()
                return Response(serializer.validated_data, status=status.HTTP_201_CREATED)
        except ValidationError as e:
            logger.error("Validation error: %s", e)
            logger.error("Request data: %s", request.data)
            logger.error("Backtrace: %s", traceback.format_exc())
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
