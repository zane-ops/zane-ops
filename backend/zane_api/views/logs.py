from rest_framework import status, permissions
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.throttling import ScopedRateThrottle
from rest_framework.views import APIView


class LogCollectorAPIView(APIView):
    permission_classes = [permissions.AllowAny]
    throttle_scope = "log_collect"
    throttle_classes = [ScopedRateThrottle]

    def post(self, request: Request):
        log_data = request.data
        query = request.query_params
        print(f"{log_data=} {query=}")
        return Response({"status": "success"}, status=status.HTTP_200_OK)
