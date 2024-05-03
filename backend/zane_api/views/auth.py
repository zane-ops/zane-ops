from datetime import timedelta

from django.conf import settings
from django.conf import settings
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.models import AnonymousUser
from django.http import QueryDict
from django.shortcuts import redirect
from django.urls import reverse
from django.utils import timezone
from django.utils.decorators import method_decorator
from django.utils.encoding import iri_to_uri
from django.views.decorators.csrf import ensure_csrf_cookie
from drf_spectacular.utils import extend_schema
from rest_framework import exceptions
from rest_framework import status, permissions
from rest_framework.authentication import TokenAuthentication, SessionAuthentication
from rest_framework.authtoken.models import Token
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from .base import EMPTY_RESPONSE
from .. import serializers


class LoginSuccessResponseSerializer(serializers.Serializer):
    success = serializers.BooleanField()
    token = serializers.CharField(required=False)


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
            302: None,
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
                token, _ = Token.objects.get_or_create(
                    user=user
                )  # this is fine, Token is only used to authenticated internally
                response = LoginSuccessResponseSerializer(
                    {"success": True, "token": token.key if settings.DEBUG else None}
                )
                query_params = request.query_params.dict()
                redirect_uri = query_params.get("redirect_to")
                if redirect_uri is not None:
                    return redirect(iri_to_uri(redirect_uri))
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
        now = timezone.now()

        if request.session.get_expiry_date() < (
            now + timedelta(days=settings.SESSION_EXPIRE_THRESHOLD)
        ):
            request.session.set_expiry(
                now + timedelta(seconds=settings.SESSION_COOKIE_AGE)
            )

        response = AuthedSuccessResponseSerializer({"user": request.user})
        return Response(
            response.data,
        )


class TokenAuthedView(APIView):
    authentication_classes = [TokenAuthentication, SessionAuthentication]
    serializer_class = AuthedSuccessResponseSerializer
    permission_classes = [permissions.AllowAny]

    @extend_schema(
        operation_id="getAuthedUserWithToken",
    )
    def get(self, request: Request):
        if isinstance(request.user, AnonymousUser):
            accept_header = request.headers.get("accept")
            if accept_header is not None and "text/html" in accept_header:
                params = QueryDict(mutable=True)
                host = request.headers.get("Host", None)
                uri = request.headers.get("X-Forwared-Uri", None)
                proto = request.headers.get("X-Forwared-Proto", "https")

                redirect_path = ""
                if host is not None:
                    redirect_path = f"{proto}://{host}"
                if uri is not None:
                    redirect_path += uri
                if len(redirect_path.strip()) > 0:
                    params["redirect_to"] = redirect_path

                return redirect(
                    f"{reverse('zane_api:auth.login')}?{params.urlencode()}"
                )
            raise exceptions.NotAuthenticated()

        response = AuthedSuccessResponseSerializer({"user": request.user})
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

    @extend_schema(
        responses={
            401: None,
        },
        operation_id="getCSRF",
    )
    @method_decorator(ensure_csrf_cookie)
    def get(self, _: Request) -> Response:
        response = CSRFSerializer(data={"details": "CSRF cookie set"})

        if response.is_valid():
            return Response(response.data)
