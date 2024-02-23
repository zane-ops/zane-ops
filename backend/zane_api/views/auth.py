from typing import Any
from .. import serializers, forms

from rest_framework.views import APIView
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework import status, permissions
from django.contrib.auth import authenticate, login
from django_ratelimit.decorators import ratelimit
from django.utils.decorators import method_decorator
from django_ratelimit.exceptions import Ratelimited
from rest_framework.views import exception_handler
from drf_spectacular.utils import extend_schema


def custom_exception_handler(exception: Any, context: Any):
    if isinstance(exception, Ratelimited):
        return Response(
            {
                "errors": {
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


class LoginSuccessResponseSerializer(serializers.Serializer):
    success = serializers.BooleanField()


class LoginErrorResponseSerializer(serializers.ErrorResponseSerializer):
    pass


class LoginRequestSerializer(serializers.Serializer):
    username = serializers.CharField()
    password = serializers.CharField()


class LoginView(APIView):
    permission_classes = [permissions.AllowAny]
    success_serializer_class = LoginSuccessResponseSerializer
    error_serializer_class = LoginErrorResponseSerializer

    @extend_schema(
        responses={
            201: success_serializer_class,
            422: error_serializer_class,
            401: error_serializer_class,
            429: error_serializer_class,
        },
        request=LoginRequestSerializer,
        operation_id="login",
    )
    @method_decorator(ratelimit(key="ip", rate="5/m"))
    @method_decorator(ratelimit(key="post:username", rate="5/m"))
    def post(self, request: Request):
        form = forms.PasswordLoginForm(request.data)
        if form.is_valid():
            data = form.data
            user = authenticate(
                username=data.get("username"), password=data.get("password")
            )
            if user is not None:
                login(request, user)
                response = self.success_serializer_class(data={"success": True})
                if response.is_valid():
                    return Response(response.data, status=status.HTTP_201_CREATED)
            else:
                response = self.error_serializer_class(
                    data={
                        "errors": {
                            ".": [
                                "Invalid username or password",
                            ]
                        },
                    }
                )
                if response.is_valid():
                    return Response(
                        response.initial_data,
                        status=status.HTTP_401_UNAUTHORIZED,
                    )
        else:
            response = self.error_serializer_class(
                data={
                    "errors": form.errors,
                }
            )
            if response.is_valid():
                return Response(
                    response.initial_data,
                    status=status.HTTP_422_UNPROCESSABLE_ENTITY,
                )

        return Response(
            status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            data={"errors": {".": response.errors}},
        )


class AuthedSuccessResponseSerializer(serializers.Serializer):
    user = serializers.UserSerializer(read_only=True, many=False)


class AuthedForbiddenResponseSerializer(serializers.Serializer):
    detail = serializers.CharField()


class AuthedView(APIView):
    serializer_class = AuthedSuccessResponseSerializer
    error_serializer_class = AuthedForbiddenResponseSerializer

    @extend_schema(
        responses={
            200: serializer_class,
            403: error_serializer_class,
        },
        operation_id="getAuthedUser",
    )
    def get(self, request: Request):
        response = self.serializer_class({"user": request.user})
        return Response(
            response.data,
        )
