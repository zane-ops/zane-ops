from . import serializers

from .models import Project
from .forms import PasswordLoginForm
from rest_framework.views import APIView
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework import status, permissions
from django.contrib.auth import authenticate, login


class LoginView(APIView):
    permission_classes = [permissions.AllowAny]

    def post(self, request: Request):
        form = PasswordLoginForm(request.data)
        if form.is_valid():
            data = form.data
            user = authenticate(
                username=data.get("username"), password=data.get("password")
            )
            if user is not None:
                login(request, user)
                return Response({"success": True})
            else:
                return Response(
                    {
                        "error": True,
                        "message": {
                            ".": [
                                "Invalid username or password",
                            ]
                        },
                    },
                    status=status.HTTP_401_UNAUTHORIZED,
                )
        else:
            return Response(
                {
                    "error": True,
                    "message": form.errors,
                },
                status=status.HTTP_422_UNPROCESSABLE_ENTITY,
            )


class AuthedView(APIView):
    def get(self, request: Request):
        serializer = serializers.UserSerializer(request.user)
        return Response({"user": serializer.data})
