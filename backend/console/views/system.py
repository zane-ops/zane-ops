from rest_framework.generics import RetrieveUpdateAPIView
from ..serializers import SystemSettingsSerializer
from ..models import SystemSettings
from zane_api.permissions import IsInstanceOwner
from django.db import transaction
from asgiref.sync import async_to_sync
from temporal.client import TemporalClient
from temporal.workflows import CleanupAppDataWorkflow, DockerSystemPruneWorkflow
from django.conf import settings


class SystemSettingsAPIView(RetrieveUpdateAPIView):
    permission_classes = [IsInstanceOwner]
    serializer_class = SystemSettingsSerializer
    http_method_names = ["get", "put"]

    def get_object(self) -> SystemSettings:  # type: ignore
        return SystemSettings.get_or_create()

    @transaction.atomic()
    def perform_update(self, serializer: SystemSettingsSerializer):
        super().perform_update(serializer)

        instance = self.get_object()

        async def on_commit():
            await TemporalClient.create_or_update_schedule(
                schedule_id=settings.APP_DATA_CLEANUP_SCHEDULE_ID,
                workflow=CleanupAppDataWorkflow.run,
                schedule_cron=instance.app_data_cleanup_cron_schedule,
            )
            # Only in production
            if settings.ENVIRONMENT == settings.PRODUCTION_ENV:
                await TemporalClient.create_or_update_schedule(
                    schedule_id=settings.DOCKER_SYSTEM_PRUNE_SCHEDULE_ID,
                    workflow=DockerSystemPruneWorkflow.run,
                    schedule_cron=instance.docker_system_prune_cron_schedule,
                )

        transaction.on_commit(async_to_sync(on_commit))
