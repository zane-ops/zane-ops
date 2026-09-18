from rest_framework.generics import RetrieveDestroyAPIView

from .serializers import (
    SSHKeySerializer,
)
from .models import SSHKey
from zane_api.permissions import IsInstanceOwner


class SSHKeyDetailsAPIView(RetrieveDestroyAPIView):
    permission_classes = [IsInstanceOwner]
    serializer_class = SSHKeySerializer
    queryset = SSHKey.objects.all()
    lookup_field = "slug"
