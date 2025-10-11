from django.db import models
from typing import TYPE_CHECKING, Self
from zane_api.models.base import TimestampedModel
from shortuuid.django_fields import ShortUUIDField
from django.utils.translation import gettext_lazy as _

if TYPE_CHECKING:
    from django.db.models.manager import RelatedManager


# Create your models here.
