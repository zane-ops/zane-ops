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
        for log in log_data:
            if log["service"] != "proxy":
                continue
            print(f"{log=}")
        return Response({"status": "success"}, status=status.HTTP_200_OK)
