from typing import Any

from django.contrib.auth import authenticate, login, logout
from django.utils.decorators import method_decorator
from django.utils.translation import gettext_lazy as _
from django.views.decorators.csrf import ensure_csrf_cookie
from drf_spectacular.utils import extend_schema
# from rest_framework.views import exception_handler
from drf_standardized_errors.handler import exception_handler
from rest_framework import status, permissions
from rest_framework.exceptions import NotAuthenticated, PermissionDenied, Throttled
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from .. import serializers

EMPTY_RESPONSE: dict = {}


class CustomPermissionDenied(PermissionDenied):
    status_code = status.HTTP_401_UNAUTHORIZED


class CustomNotAuthenticated(NotAuthenticated):
    default_detail = _(
        "Authentication required. Please log in to access this resource."
    )


def custom_exception_handler(exception: Any, context: Any) -> Response:
    if isinstance(exception, Throttled):
        return Response(
            {
                "errors": {
                    "root": [
                        f"You made too Many requests in a short amount of time, "
                        f"Please wait for {exception.wait} seconds before retrying your action.",
                    ]
                }
            },
            status=status.HTTP_429_TOO_MANY_REQUESTS,
            headers={"Retry-After": exception.wait},
        )

    if isinstance(exception, NotAuthenticated):
        response = serializers.ForbiddenResponseSerializer(
            {
                "errors": {
                    "root": [
                        "Authentication required. Please log in to access this resource."
                    ]
                }
            }
        )
        return Response(
            response.data,
            status=status.HTTP_401_UNAUTHORIZED,
        )
    if isinstance(exception, PermissionDenied):
        exception = CustomPermissionDenied()
    return exception_handler(exception, context)


class LoginSuccessResponseSerializer(serializers.Serializer):
    success = serializers.BooleanField()


class LoginRequestSerializer(serializers.Serializer):
    username = serializers.CharField(
        required=True, min_length=1, max_length=255, trim_whitespace=True
    )
    password = serializers.CharField(required=True, min_length=1, max_length=255)


class LoginErrorSerializer(serializers.BaseErrorSerializer):
    username = serializers.StringListField(required=False)
    password = serializers.StringListField(required=False)


class LoginErrorResponseSerializer(serializers.Serializer):
    errors = LoginErrorSerializer()


class LoginView(APIView):
    permission_classes = [permissions.AllowAny]
    success_serializer_class = LoginSuccessResponseSerializer
    error_serializer_class = LoginErrorResponseSerializer

    @extend_schema(
        request=LoginRequestSerializer,
        responses={
            201: success_serializer_class,
            422: error_serializer_class,
            401: error_serializer_class,
            429: error_serializer_class,
        },
        operation_id="login",
    )
    def post(self, request: Request) -> Response:
        form = LoginRequestSerializer(data=request.data)
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
                    {
                        "errors": {
                            "root": [
                                "Invalid username or password",
                            ]
                        },
                    }
                )
                return Response(
                    response.data,
                    status=status.HTTP_401_UNAUTHORIZED,
                )
        else:
            response = self.error_serializer_class({"errors": form.errors})
            return Response(
                response.data,
                status=status.HTTP_422_UNPROCESSABLE_ENTITY,
            )


class AuthedSuccessResponseSerializer(serializers.Serializer):
    user = serializers.UserSerializer(read_only=True, many=False)


class AuthedView(APIView):
    serializer_class = AuthedSuccessResponseSerializer
    error_serializer_class = serializers.ForbiddenResponseSerializer

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


class AuthLogoutView(APIView):
    error_serializer_class = serializers.ForbiddenResponseSerializer

    @extend_schema(
        responses={
            204: None,
            403: error_serializer_class,
        },
        operation_id="logout",
    )
    def delete(self, request: Request):
        logout(request)
        return Response(EMPTY_RESPONSE, status=status.HTTP_204_NO_CONTENT)


class CSRFSerializer(serializers.Serializer):
    details = serializers.CharField()


class CSRFCookieView(APIView):
    """
    CSRF cookie view for retrieving CSRF before doing requests
    """

    serializer_class = CSRFSerializer

    permission_classes = [permissions.AllowAny]

    @method_decorator(ensure_csrf_cookie)
    def get(self, _: Request) -> Response:
        response = CSRFSerializer(data={"details": "CSRF cookie set"})

        if response.is_valid():
            return Response(response.data)

        return Response(
            status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            data={"errors": {"root": response.errors}},
        )
