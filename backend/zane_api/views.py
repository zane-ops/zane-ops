from typing import Any
from . import serializers, forms

from rest_framework.views import APIView
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework import status, permissions
from django.contrib.auth import authenticate, login
from django_ratelimit.decorators import ratelimit
from django.utils.decorators import method_decorator
from django_ratelimit.exceptions import Ratelimited
from rest_framework.views import exception_handler


def custom_exception_handler(exception: Any, context: Any):
    if isinstance(exception, Ratelimited):
        return Response(
            {
                "error": {
                    ".": [
                        "Too Many Requests",
                    ]
                }
            },
            status=status.HTTP_429_TOO_MANY_REQUESTS,
        )

    # Call REST framework's default exception handler first,
    # to get the standard error exception.
    return exception_handler(exception, context)


class LoginView(APIView):
    permission_classes = [permissions.AllowAny]

    @method_decorator(ratelimit(key="ip", rate="5/m"))
    @method_decorator(ratelimit(key="post:username", rate="5/m"))
    def post(self, request: Request):
        # raise Ratelimited
        form = forms.PasswordLoginForm(request.data)
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
                        "error": {
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
                    "error": form.errors,
                },
                status=status.HTTP_422_UNPROCESSABLE_ENTITY,
            )


class AuthedView(APIView):
    def get(self, request: Request):
        serializer = serializers.UserSerializer(request.user)
        return Response({"user": serializer.data})
