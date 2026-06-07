from drf_spectacular.utils import extend_schema


from rest_framework.response import Response
from rest_framework.generics import (
    ListAPIView,
)


from django.contrib.auth.models import User
from rest_framework import exceptions
from zane_api.permissions import IsInstanceOwner, HasWorkspace
from zane_api.serializers import UserSerializer

from zane_api.views import EMPTY_PAGINATED_RESPONSE
from .serializers import InstanceUserPagination


class ListInstanceUsersAPIView(ListAPIView):
    permission_classes = [HasWorkspace, IsInstanceOwner]
    serializer_class = UserSerializer
    queryset = User.objects.all()
    pagination_class = InstanceUserPagination

    @extend_schema(
        summary="List all users in ZaneOps installation",
    )
    def get(self, request, *args, **kwargs):
        try:
            return super().get(request, *args, **kwargs)
        except exceptions.NotFound as e:
            if "Invalid page" in str(e.detail):
                return Response(EMPTY_PAGINATED_RESPONSE)
            raise e
