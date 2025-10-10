"""
URL configuration for backend project.

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/5.0/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  path('', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  path('', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.urls import include, path
    2. Add a URL to urlpatterns:  path('blog/', include('blog.urls'))
"""

from django.contrib import admin
from django.urls import include, path
from django.conf import settings

urlpatterns = []

# Don't activate admin site on production
if settings.DEBUG:
    urlpatterns += [
        path("admin/", admin.site.urls),
    ]

urlpatterns += [
    path("api/registry/", include("container_registry.urls")),
    path("api/shell/", include("webshell.urls")),
    path("api/connectors/", include("git_connectors.urls")),
    path("api/", include("zane_api.urls")),
]
