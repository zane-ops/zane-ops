from rest_framework.generics import RetrieveUpdateAPIView
from ..serializers import SystemSettingsSerializer
from ..models import SystemSettings
from zane_api.permissions import IsInstanceOwner


class SystemSettingsAPIView(RetrieveUpdateAPIView):
    permission_classes = [IsInstanceOwner]
    serializer_class = SystemSettingsSerializer
    http_method_names = ["get", "put"]

    def get_object(self) -> SystemSettings:  # type: ignore
        return SystemSettings.get_or_create()

    def perform_update(self, serializer: SystemSettingsSerializer):
        return super().perform_update(serializer)
