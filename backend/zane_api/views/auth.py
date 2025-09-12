from datetime import timedelta
from typing import cast

from django.conf import settings
from django.contrib.auth import authenticate, login, logout, get_user_model, update_session_auth_hash
from django.contrib.auth.models import AnonymousUser
from django.contrib.sessions.models import Session
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
from rest_framework.throttling import ScopedRateThrottle
from rest_framework.utils.serializer_helpers import ReturnDict

from rest_framework import serializers
from .serializers import (
    UserCreationRequestSerializer,
    UserCreatedResponseSerializer,
    UserExistenceResponseSerializer,
)
from .serializers.common import ChangePasswordSerializer, ChangePasswordResponseSerializer
from ..serializers import UserSerializer


User = get_user_model()


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
            302: None,
        },
        operation_id="login",
        summary="Login",
        description="Authenticate User, what is returned is a cookie named `sessionid` "
        "that will be used for authentication of the next requests.",
    )
    def post(self, request: Request):
        form = LoginRequestSerializer(data=request.data)
        if form.is_valid(raise_exception=True):
            data = cast(ReturnDict, form.data)
            user = authenticate(
                username=data.get("username"), password=data.get("password")
            )
            if user is not None:
                login(request, user)  # type: ignore
                token, _ = Token.objects.get_or_create(
                    user=user
                )  # this is fine, Token is only used to authenticated internally
                response = LoginSuccessResponseSerializer({"success": True})
                query_params = request.query_params.dict()
                redirect_uri = query_params.get("redirect_to")
                if redirect_uri is not None:
                    return redirect(iri_to_uri(redirect_uri))  # type: ignore
                return Response(response.data, status=status.HTTP_201_CREATED)
            raise exceptions.AuthenticationFailed(detail="Invalid username or password")


class AuthedSuccessResponseSerializer(serializers.Serializer):
    user = UserSerializer(read_only=True, many=False)


class AuthedView(APIView):
    serializer_class = AuthedSuccessResponseSerializer

    @extend_schema(
        operation_id="getAuthedUser",
        summary="Get current user",
        description="Get current authenticated user.",
    )
    def get(self, request: Request):
        now = timezone.now()

        if request.session.get_expiry_date() < (
            now + timedelta(days=settings.SESSION_EXPIRE_THRESHOLD)
        ):
            request.session.set_expiry(
                now + timedelta(seconds=settings.SESSION_EXTEND_PERIOD)
            )

        response = AuthedSuccessResponseSerializer({"user": request.user})
        return Response(
            response.data,
        )


@extend_schema(exclude=True)
class TokenAuthedView(APIView):
    authentication_classes = [TokenAuthentication, SessionAuthentication]
    serializer_class = AuthedSuccessResponseSerializer
    permission_classes = [permissions.AllowAny]

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
        summary="Logout",
    )
    def delete(self, request: Request):
        logout(request)  # type: ignore
        return Response(status=status.HTTP_204_NO_CONTENT)


class CSRFSerializer(serializers.Serializer):
    details = serializers.CharField()


class CSRFCookieView(APIView):
    serializer_class = CSRFSerializer
    permission_classes = [permissions.AllowAny]

    @extend_schema(
        responses={
            401: None,
        },
        operation_id="getCSRF",
        summary="Get CSRF cookie",
        description="CSRF cookie endpoint for retrieving a CSRF token before doing mutative requests (`DELETE`, `POST`, `PUT`, `PATCH`)."
        "You need to pass the cookie named `csrftoken` to all requests alongside a `X-CSRFToken` with the value of the token.",
    )
    @method_decorator(ensure_csrf_cookie)
    def get(self, _: Request) -> Response:
        response = CSRFSerializer({"details": "CSRF cookie set"})
        return Response(response.data)


class AnonScopedRateThrottle(ScopedRateThrottle):
    scope = "initial_registration"

    def allow_request(self, request: Request, view: APIView):
        if request.user and request.user.is_authenticated:
            return True  # always allow authenticated users
        return super().allow_request(request, view)


class CheckUserExistenceView(APIView):
    permission_classes = [permissions.AllowAny]
    serializer_class = UserExistenceResponseSerializer
    throttle_scope = "initial_registration"
    throttle_classes = [AnonScopedRateThrottle]

    @extend_schema(
        summary="Check if a user exists",
        description="Returns whether a single user already exists in the system.",
    )
    def get(self, request: Request) -> Response:
        exists = User.objects.exists()
        serializer = UserExistenceResponseSerializer({"exists": exists})
        return Response(serializer.data, status=status.HTTP_200_OK)


class CreateUserView(APIView):
    permission_classes = [permissions.AllowAny]
    throttle_scope = "initial_registration"
    throttle_classes = [ScopedRateThrottle]

    @extend_schema(
        request=UserCreationRequestSerializer,
        responses={201: UserCreatedResponseSerializer},
        summary="Create a user",
        description="Creates a new user if no user exists.",
    )
    def post(self, request: Request) -> Response:
        if User.objects.exists():
            raise exceptions.PermissionDenied("A user already exists.")

        serializer = UserCreationRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        user = User.objects.create_superuser(
            username=serializer.validated_data["username"],  # type: ignore
            password=serializer.validated_data["password"],  # type: ignore
        )  # type: ignore

        login(request, user)  # type: ignore
        serializer = UserCreatedResponseSerializer(
            {"detail": "User created and logged in successfully."}
        )
        return Response(
            serializer.data,
            status=status.HTTP_201_CREATED,
        )

class ChangePasswordView(APIView):
    permission_classes = [permissions.IsAuthenticated]
    throttle_classes = [AnonScopedRateThrottle]
    throttle_scope = "password_change"
    serializer_class = ChangePasswordResponseSerializer

    @extend_schema(
        request=ChangePasswordSerializer,
        responses={200: ChangePasswordResponseSerializer},
        operation_id="changePassword",
        summary="Change user password",
        description="Change the authenticated user's password. Requires current password verification and validates new password strength.",
    )
    def post(self, request: Request) -> Response:
        form = ChangePasswordSerializer(data=request.data, context={'request': request})
        
        form.is_valid(raise_exception=True)

        user = request.user
        data = cast(ReturnDict, form.data)
        new_password = data.get("new_password")
        
        try:
            user.set_password(new_password)
            user.save()
            
            current_session_key = request.session.session_key
            if current_session_key:
                user_sessions = Session.objects.filter(
                    expire_date__gte=timezone.now()
                )
                
                for session in user_sessions:
                    session_data = session.get_decoded()
                    if session_data.get('_auth_user_id') == str(user.id):
                        if session.session_key != current_session_key:
                            session.delete()

                update_session_auth_hash(request._request, user)
            
            response_serializer = ChangePasswordResponseSerializer({
                'success': True,
                'message': 'Password changed successfully.'
            })
            return Response(response_serializer.data, status=status.HTTP_200_OK)
            
        except Exception as e:
            return Response(
                {'detail': 'An error occurred while changing your password. Please try again.'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
