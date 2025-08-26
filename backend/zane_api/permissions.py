from rest_framework import permissions
from django.contrib.auth.models import User, AnonymousUser
from functools import wraps
from typing import Dict, Set, Optional
from .models import Project, ProjectMembership, UserRole


class PermissionMatrix:
    """Central permission matrix defining what each role can do"""
    
    # Role hierarchy (lower number = higher permissions)
    ROLE_HIERARCHY = {
        UserRole.INSTANCE_OWNER: 0,
        UserRole.ADMIN: 1,
        UserRole.MEMBER: 2,
        UserRole.CONTRIBUTOR: 3,
        UserRole.GUEST: 4,
    }
    
    # Permission definitions for each role
    PERMISSIONS = {
        # Instance Owner - Full control over everything
        UserRole.INSTANCE_OWNER: {
            'view_project', 'edit_project', 'delete_project', 'manage_members',
            'view_services', 'create_services', 'edit_services', 'delete_services',
            'deploy_services', 'view_deployments', 'cancel_deployments',
            'view_environments', 'create_environments', 'edit_environments',
            'delete_environments', 'manage_tokens'
        },
        
        # Admin - Project management + all service operations including project deletion
        UserRole.ADMIN: {
            'view_project', 'edit_project', 'delete_project', 'manage_members',
            'view_services', 'create_services', 'edit_services', 'delete_services',
            'deploy_services', 'view_deployments', 'cancel_deployments',
            'view_environments', 'create_environments', 'edit_environments',
            'delete_environments', 'manage_tokens'
        },
        
        # Member - Service operations without project management
        UserRole.MEMBER: {
            'view_project', 'view_services', 'create_services', 'edit_services',
            'deploy_services', 'view_deployments', 'cancel_deployments',
            'view_environments', 'create_environments', 'edit_environments'
        },
        
        # Contributor - Limited service operations
        UserRole.CONTRIBUTOR: {
            'view_project', 'view_services', 'edit_services', 'deploy_services',
            'view_deployments', 'view_environments'
        },
        
        # Guest - Read-only access
        UserRole.GUEST: {
            'view_project', 'view_services', 'view_deployments', 'view_environments'
        }
    }
    
    @classmethod
    def has_permission(cls, user_role: str, permission: str) -> bool:
        """Check if a role has a specific permission"""
        return permission in cls.PERMISSIONS.get(user_role, set())
    
    @classmethod
    def get_user_role_in_project(cls, user: User, project: Project) -> Optional[str]:
        """Get the user's role in a specific project"""
        if isinstance(user, AnonymousUser):
            return None
            
        # Check if user is instance owner (superuser)
        if user.is_superuser:
            return UserRole.INSTANCE_OWNER
            
        # Check if user is project owner (backward compatibility)
        if hasattr(project, 'owner') and project.owner == user:
            return UserRole.ADMIN
            
        # Check project membership
        try:
            membership = ProjectMembership.objects.get(user=user, project=project)
            return membership.role
        except ProjectMembership.DoesNotExist:
            return None
    
    @classmethod
    def can_user_perform_action(cls, user: User, project: Project, permission: str) -> bool:
        """Check if user can perform a specific action on a project"""
        user_role = cls.get_user_role_in_project(user, project)
        if not user_role:
            return False
        return cls.has_permission(user_role, permission)
    
    # Convenience methods for common permission checks
    @classmethod
    def can_view_project(cls, user: User, project: Project) -> bool:
        return cls.can_user_perform_action(user, project, 'view_project')
    
    @classmethod
    def can_edit_project(cls, user: User, project: Project) -> bool:
        return cls.can_user_perform_action(user, project, 'edit_project')
    
    @classmethod
    def can_delete_project(cls, user: User, project: Project) -> bool:
        return cls.can_user_perform_action(user, project, 'delete_project')
    
    @classmethod
    def can_manage_members(cls, user: User, project: Project) -> bool:
        return cls.can_user_perform_action(user, project, 'manage_members')
    
    @classmethod
    def can_view_services(cls, user: User, project: Project) -> bool:
        return cls.can_user_perform_action(user, project, 'view_services')
    
    @classmethod
    def can_create_services(cls, user: User, project: Project) -> bool:
        return cls.can_user_perform_action(user, project, 'create_services')
    
    @classmethod
    def can_edit_services(cls, user: User, project: Project) -> bool:
        return cls.can_user_perform_action(user, project, 'edit_services')
    
    @classmethod
    def can_delete_services(cls, user: User, project: Project) -> bool:
        return cls.can_user_perform_action(user, project, 'delete_services')
    
    @classmethod
    def can_deploy_services(cls, user: User, project: Project) -> bool:
        return cls.can_user_perform_action(user, project, 'deploy_services')
    
    @classmethod
    def can_view_deployments(cls, user: User, project: Project) -> bool:
        return cls.can_user_perform_action(user, project, 'view_deployments')
    
    @classmethod
    def can_cancel_deployments(cls, user: User, project: Project) -> bool:
        return cls.can_user_perform_action(user, project, 'cancel_deployments')
    
    @classmethod
    def can_view_environments(cls, user: User, project: Project) -> bool:
        return cls.can_user_perform_action(user, project, 'view_environments')
    
    @classmethod
    def can_create_environments(cls, user: User, project: Project) -> bool:
        return cls.can_user_perform_action(user, project, 'create_environments')
    
    @classmethod
    def can_edit_environments(cls, user: User, project: Project) -> bool:
        return cls.can_user_perform_action(user, project, 'edit_environments')
    
    @classmethod
    def can_delete_environments(cls, user: User, project: Project) -> bool:
        return cls.can_user_perform_action(user, project, 'delete_environments')
    
    @classmethod
    def can_manage_tokens(cls, user: User, project: Project) -> bool:
        return cls.can_user_perform_action(user, project, 'manage_tokens')


class ProjectPermission(permissions.BasePermission):
    """Django REST Framework permission class for project-based access control"""
    
    def has_permission(self, request, view):
        """Check if user is authenticated"""
        return request.user and request.user.is_authenticated
    
    def has_object_permission(self, request, view, obj):
        """Check if user has permission for specific project object"""
        project = obj if isinstance(obj, Project) else getattr(obj, 'project', None)
        
        if not project:
            return False
            
        # Map HTTP methods to permissions
        permission_map = {
            'GET': 'view_project',
            'HEAD': 'view_project',
            'OPTIONS': 'view_project',
            'POST': 'edit_project',
            'PUT': 'edit_project',
            'PATCH': 'edit_project',
            'DELETE': 'delete_project',
        }
        
        required_permission = permission_map.get(request.method, 'view_project')
        return PermissionMatrix.can_user_perform_action(request.user, project, required_permission)


class ServicePermission(permissions.BasePermission):
    """Permission class for service-based operations"""
    
    def has_permission(self, request, view):
        return request.user and request.user.is_authenticated
    
    def has_object_permission(self, request, view, obj):
        # Get project from service
        project = getattr(obj, 'project', None)
        if not project:
            return False
            
        # Map HTTP methods to service permissions
        permission_map = {
            'GET': 'view_services',
            'HEAD': 'view_services', 
            'OPTIONS': 'view_services',
            'POST': 'create_services',
            'PUT': 'edit_services',
            'PATCH': 'edit_services',
            'DELETE': 'delete_services',
        }
        
        required_permission = permission_map.get(request.method, 'view_services')
        return PermissionMatrix.can_user_perform_action(request.user, project, required_permission)


def require_project_permission(permission: str):
    """Decorator to check project permissions on view functions"""
    def decorator(view_func):
        @wraps(view_func)
        def wrapper(self, request, *args, **kwargs):
            # Get project from URL parameters
            project_slug = kwargs.get('slug') or kwargs.get('project_slug')
            if not project_slug:
                return Response(
                    {"error": "Project not found"}, 
                    status=status.HTTP_404_NOT_FOUND
                )
            
            try:
                project = Project.objects.get(slug=project_slug)
            except Project.DoesNotExist:
                return Response(
                    {"error": "Project not found"}, 
                    status=status.HTTP_404_NOT_FOUND
                )
            
            if not PermissionMatrix.can_user_perform_action(request.user, project, permission):
                return Response(
                    {"error": "Permission denied"}, 
                    status=status.HTTP_403_FORBIDDEN
                )
            
            # Add project to kwargs for view function
            kwargs['project'] = project
            return view_func(self, request, *args, **kwargs)
        
        return wrapper
    return decorator


class ProjectNestedResourcePermission(permissions.BasePermission):
    """Permission class for resources nested under projects (like members, tokens, invitations)"""
    
    def has_permission(self, request, view):
        """Check basic authentication and project-level permissions"""
        if not request.user or not request.user.is_authenticated:
            return False
            
        # Get project from URL kwargs
        project_slug = getattr(view, 'kwargs', {}).get('project_slug')
        if not project_slug:
            return False
            
        try:
            project = Project.objects.get(slug=project_slug)
        except Project.DoesNotExist:
            return False
            
        # Check what permission is needed based on the resource type and method
        permission_map = self.get_permission_map(view)
        required_permission = permission_map.get(request.method, 'view_project')
        
        return PermissionMatrix.can_user_perform_action(request.user, project, required_permission)
    
    def get_permission_map(self, view):
        """Get the permission mapping for the specific resource type"""
        # Default to member management permissions for RBAC resources
        return {
            'GET': 'manage_members',
            'HEAD': 'manage_members',
            'OPTIONS': 'manage_members',
            'POST': 'manage_members',
            'PUT': 'manage_members',
            'PATCH': 'manage_members',
            'DELETE': 'manage_members',
        }


class ProjectMemberPermission(ProjectNestedResourcePermission):
    """Permission class specifically for project member management"""
    pass  # Uses default member management permissions


class ProjectTokenPermission(ProjectNestedResourcePermission):
    """Permission class specifically for project token management"""
    
    def get_permission_map(self, view):
        return {
            'GET': 'manage_tokens',
            'HEAD': 'manage_tokens',
            'OPTIONS': 'manage_tokens',
            'POST': 'manage_tokens',
            'PUT': 'manage_tokens',
            'PATCH': 'manage_tokens',
            'DELETE': 'manage_tokens',
        }


def require_service_permission(permission: str):
    """Decorator to check service permissions on view functions"""
    def decorator(view_func):
        @wraps(view_func)
        def wrapper(self, request, *args, **kwargs):
            from .models import Service
            
            # Get service from URL parameters
            service_slug = kwargs.get('service_slug') or kwargs.get('slug')
            project_slug = kwargs.get('project_slug')
            
            if not all([service_slug, project_slug]):
                return Response(
                    {"error": "Service or project not found"}, 
                    status=status.HTTP_404_NOT_FOUND
                )
            
            try:
                service = Service.objects.select_related('project').get(
                    slug=service_slug,
                    project__slug=project_slug
                )
            except Service.DoesNotExist:
                return Response(
                    {"error": "Service not found"}, 
                    status=status.HTTP_404_NOT_FOUND
                )
            
            if not PermissionMatrix.can_user_perform_action(request.user, service.project, permission):
                return Response(
                    {"error": "Permission denied"}, 
                    status=status.HTTP_403_FORBIDDEN
                )
            
            # Add service to kwargs for view function
            kwargs['service'] = service
            return view_func(self, request, *args, **kwargs)
        
        return wrapper
    return decorator