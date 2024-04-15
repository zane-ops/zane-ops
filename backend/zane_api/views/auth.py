from django.contrib.auth import authenticate, login, logout
from django.utils.decorators import method_decorator
from django.views.decorators.csrf import ensure_csrf_cookie
from drf_spectacular.utils import extend_schema
from rest_framework import exceptions
from rest_framework import status, permissions
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from .base import EMPTY_RESPONSE
from .. import serializers


class LoginSuccessResponseSerializer(serializers.Serializer):
    success = serializers.BooleanField()


class LoginRequestSerializer(serializers.Serializer):
    username = serializers.CharField(
        required=True, min_length=1, max_length=255, trim_whitespace=True
    )
    password = serializers.CharField(required=True, min_length=1, max_length=255)


class LoginView(APIView):
    permission_classes = [permissions.AllowAny]
    serializer_class = LoginSuccessResponseSerializer

    @extend_schema(
        request=LoginRequestSerializer,
        responses={
            201: LoginSuccessResponseSerializer,
        },
        operation_id="login",
    )
    def post(self, request: Request) -> Response:
        form = LoginRequestSerializer(data=request.data)
        if form.is_valid(raise_exception=True):
            data = form.data
            user = authenticate(
                username=data.get("username"), password=data.get("password")
            )
            if user is not None:
                login(request, user)
                response = LoginSuccessResponseSerializer(data={"success": True})
                if response.is_valid():
                    return Response(response.data, status=status.HTTP_201_CREATED)
            raise exceptions.AuthenticationFailed(detail="Invalid username or password")


class AuthedSuccessResponseSerializer(serializers.Serializer):
    user = serializers.UserSerializer(read_only=True, many=False)


class AuthedView(APIView):
    serializer_class = AuthedSuccessResponseSerializer

    @extend_schema(
        operation_id="getAuthedUser",
    )
    def get(self, request: Request):
        response = self.serializer_class({"user": request.user})
        return Response(
            response.data,
        )


class AuthLogoutView(APIView):
    @extend_schema(
        responses={
            204: None,
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
