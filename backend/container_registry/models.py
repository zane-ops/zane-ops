from django.db import models


# Create your models here.
class ContainerRegistry:
    url = models.URLField(blank=False)
    password = models.TextField(blank=False)
    username = models.CharField(max_length=1024, null=True, blank=False)
