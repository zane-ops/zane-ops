from django.contrib import admin

from .models import Project, DockerRegistryService, GitRepositoryService


# Register your models here.
@admin.register(Project)
class Project(admin.ModelAdmin):
    pass


# Register your models here.
@admin.register(DockerRegistryService)
class DockerRegistryService(admin.ModelAdmin):
    pass


@admin.register(GitRepositoryService)
class GitRepositoryService(admin.ModelAdmin):
    pass
