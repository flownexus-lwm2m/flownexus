from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from .serializers import LwM2MSerializer
import logging

logger = logging.getLogger(__name__)


class PostResourceView(APIView):
    serializer_class = LwM2MSerializer

    def post(self, request):
        serializer = LwM2MSerializer(data=request.data, many=False)
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.validated_data, status=status.HTTP_201_CREATED)
        logger.error(serializer.errors)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
