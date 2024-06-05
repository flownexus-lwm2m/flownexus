from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from .serializers.single_resource_serializer import SingleResourceSerializer
from .serializers.composite_resource_serializer import CompositeResourceSerializer
import logging

logger = logging.getLogger(__name__)


class PostSingleResourceView(APIView):
    serializer_class = SingleResourceSerializer

    def post(self, request):
        serializer = SingleResourceSerializer(data=request.data, many=False)
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.validated_data, status=status.HTTP_201_CREATED)
        logger.error(serializer.errors)
        logger.error(request.data)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class PostCompositeResourceView(APIView):
    serializer_class = CompositeResourceSerializer

    def post(self, request):
        serializer = CompositeResourceSerializer(data=request.data, many=False)
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.validated_data, status=status.HTTP_201_CREATED)
        logger.error(serializer.errors)
        logger.error(request.data)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
