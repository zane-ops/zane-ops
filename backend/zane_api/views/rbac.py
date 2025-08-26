from django.contrib.auth.models import User
from django.db import transaction, IntegrityError
from django.shortcuts import get_object_or_404
from drf_spectacular.utils import extend_schema, OpenApiParameter
from drf_spectacular.types import OpenApiTypes
from rest_framework import status, permissions
from rest_framework.decorators import action
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework.viewsets import ModelViewSet
from rest_framework.generics import ListCreateAPIView, RetrieveUpdateDestroyAPIView
import secrets
import hashlib

from ..models import (
    Project, ProjectMembership, UserInvitation, APIToken, UserRole
)
from ..permissions import (
    PermissionMatrix, require_project_permission, ProjectPermission,
    ProjectMemberPermission, ProjectTokenPermission
)
from .serializers.rbac import (
    ProjectMembershipSerializer, ProjectMembershipCreateSerializer,
    ProjectMembershipUpdateSerializer, UserInvitationSerializer, 
    UserInvitationCreateSerializer, UserInvitationResponseSerializer,
    UserInvitationWithPasswordSerializer, InvitationValidateSerializer,
    APITokenSerializer, APITokenCreateSerializer, APITokenResponseSerializer,
    UserProjectRolesSerializer, ProjectMembersListSerializer,
    PermissionCheckSerializer, PermissionCheckResponseSerializer
)
from .base import EMPTY_PAGINATED_RESPONSE, ResourceConflict


class ProjectMembershipViewSet(ModelViewSet):
    """ViewSet for managing project memberships"""
    serializer_class = ProjectMembershipSerializer
    permission_classes = [ProjectMemberPermission]
    
    def get_queryset(self):
        project_slug = self.kwargs.get('project_slug')
        if not project_slug:
            return ProjectMembership.objects.none()
            
        project = get_object_or_404(Project, slug=project_slug)
            
        return ProjectMembership.objects.filter(project=project).select_related(
            'user', 'project', 'added_by'
        )
    
    def get_serializer_class(self):
        if self.action == 'create':
            return ProjectMembershipCreateSerializer
        elif self.action in ['update', 'partial_update']:
            return ProjectMembershipUpdateSerializer
        return ProjectMembershipSerializer
    
    @extend_schema(
        summary="List project members",
        description="Get a list of all members in the project",
    )
    def list(self, request, *args, **kwargs):
        return super().list(request, *args, **kwargs)
    
    @extend_schema(
        summary="Add project member",
        description="Add a new member to the project",
        request=ProjectMembershipCreateSerializer,
        responses={201: ProjectMembershipSerializer}
    )
    def create(self, request, *args, **kwargs):
        project_slug = kwargs.get('project_slug')
        project = get_object_or_404(Project, slug=project_slug)
        
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        
        try:
            user = User.objects.get(username=serializer.validated_data['username'])
            
            # Check if user is already a member
            if ProjectMembership.objects.filter(user=user, project=project).exists():
                raise ResourceConflict("User is already a member of this project")
            
            membership = ProjectMembership.objects.create(
                user=user,
                project=project,
                role=serializer.validated_data['role'],
                added_by=request.user
            )
            
            response_serializer = ProjectMembershipSerializer(membership)
            return Response(response_serializer.data, status=status.HTTP_201_CREATED)
            
        except User.DoesNotExist:
            return Response(
                {"error": "User not found"}, 
                status=status.HTTP_404_NOT_FOUND
            )
    
    @extend_schema(
        summary="Update member role",
        description="Update a project member's role",
        request=ProjectMembershipUpdateSerializer,
        responses={200: ProjectMembershipSerializer}
    )
    def update(self, request, *args, **kwargs):
        return super().update(request, *args, **kwargs)
    
    @extend_schema(
        summary="Remove project member",
        description="Remove a member from the project",
    )
    def destroy(self, request, *args, **kwargs):
        membership = self.get_object()
        
        # Prevent removing the last admin/owner
        if membership.role in [UserRole.ADMIN, UserRole.INSTANCE_OWNER]:
            admin_count = ProjectMembership.objects.filter(
                project=membership.project,
                role__in=[UserRole.ADMIN, UserRole.INSTANCE_OWNER]
            ).count()
            
            if admin_count <= 1:
                return Response(
                    {"error": "Cannot remove the last admin from the project"},
                    status=status.HTTP_400_BAD_REQUEST
                )
        
        return super().destroy(request, *args, **kwargs)


class ProjectInvitationViewSet(ModelViewSet):
    """ViewSet for managing project invitations"""
    serializer_class = UserInvitationSerializer
    permission_classes = [ProjectMemberPermission]
    
    def get_queryset(self):
        project_slug = self.kwargs.get('project_slug')
        if not project_slug:
            return UserInvitation.objects.none()
            
        project = get_object_or_404(Project, slug=project_slug)
            
        return UserInvitation.objects.filter(project=project).select_related(
            'project', 'invited_by', 'accepted_by'
        )
    
    def get_serializer_class(self):
        if self.action == 'create':
            return UserInvitationCreateSerializer
        return UserInvitationSerializer
    
    @extend_schema(
        summary="List project invitations",
        description="Get all pending and processed invitations for the project",
    )
    def list(self, request, *args, **kwargs):
        return super().list(request, *args, **kwargs)
    
    @extend_schema(
        summary="Send project invitation",
        description="Send an invitation to join the project",
        request=UserInvitationCreateSerializer,
        responses={201: UserInvitationSerializer}
    )
    def create(self, request, *args, **kwargs):
        project_slug = kwargs.get('project_slug')
        project = get_object_or_404(Project, slug=project_slug)
        
        serializer = self.get_serializer(
            data=request.data,
            context={'project': project}
        )
        serializer.is_valid(raise_exception=True)
        
        invitation = UserInvitation.objects.create(
            username=serializer.validated_data['username'],
            project=project,
            role=serializer.validated_data['role'],
            invited_by=request.user
        )
        
        # TODO: Send email notification
        
        response_serializer = UserInvitationSerializer(invitation)
        return Response(response_serializer.data, status=status.HTTP_201_CREATED)
    
    @extend_schema(
        summary="Delete invitation",
        description="Delete a pending project invitation",
    )
    def destroy(self, request, *args, **kwargs):
        invitation = self.get_object()
        
        if invitation.status != UserInvitation.InvitationStatus.PENDING:
            return Response(
                {"error": "Cannot delete a non-pending invitation"},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        invitation.delete()
        
        return Response(status=status.HTTP_204_NO_CONTENT)


class InvitationResponseView(APIView):
    """View for users to respond to invitations"""
    
    def get_permissions(self):
        """Override permissions - Both GET and POST don't require auth for invitation responses"""
        return []  # No authentication required for invitation validation and response
    
    @extend_schema(
        summary="Validate invitation",
        description="Check if an invitation token is valid and get invitation details",
        responses={200: InvitationValidateSerializer}
    )
    def get(self, request, token):
        """Validate invitation without requiring authentication"""
        try:
            invitation = UserInvitation.objects.select_related(
                'project', 'invited_by'
            ).get(token=token)
        except UserInvitation.DoesNotExist:
            return Response({
                'is_valid': False,
                'error': 'Invalid invitation token'
            }, status=status.HTTP_404_NOT_FOUND)
        
        # Check invitation status
        if invitation.status != UserInvitation.InvitationStatus.PENDING:
            return Response({
                'is_valid': False,
                'error': 'This invitation has already been processed'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        # Check expiration
        if invitation.is_expired:
            invitation.status = UserInvitation.InvitationStatus.EXPIRED
            invitation.save()
            return Response({
                'is_valid': False,
                'error': 'This invitation has expired'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        # Check if user already exists
        user_exists = User.objects.filter(username=invitation.username).exists()
        
        data = {
            'username': invitation.username,
            'project_slug': invitation.project.slug,
            'project_name': invitation.project.slug,  # Using slug as name since Project doesn't have a name field
            'role': invitation.role,
            'invited_by': invitation.invited_by.username if invitation.invited_by else None,
            'expires_at': invitation.expires_at,
            'user_exists': user_exists,
            'is_valid': True
        }
        
        serializer = InvitationValidateSerializer(data)
        return Response(serializer.data, status=status.HTTP_200_OK)
    
    @extend_schema(
        summary="Respond to invitation",
        description="Accept or decline a project invitation (creates account if user doesn't exist)",
        request=UserInvitationWithPasswordSerializer,
        responses={200: ProjectMembershipSerializer}
    )
    def post(self, request, token):
        try:
            invitation = UserInvitation.objects.get(token=token)
        except UserInvitation.DoesNotExist:
            return Response(
                {"error": "Invalid invitation token"}, 
                status=status.HTTP_404_NOT_FOUND
            )
        
        if invitation.status != UserInvitation.InvitationStatus.PENDING:
            return Response(
                {"error": "This invitation has already been processed"},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        if invitation.is_expired:
            invitation.status = UserInvitation.InvitationStatus.EXPIRED
            invitation.save()
            return Response(
                {"error": "This invitation has expired"},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Check if user exists
        user_exists = User.objects.filter(username=invitation.username).exists()
        
        # For existing users, check authentication and username match
        if user_exists:
            if not request.user.is_authenticated:
                return Response(
                    {"error": "Authentication required for existing users"},
                    status=status.HTTP_401_UNAUTHORIZED
                )
            
            if request.user.username != invitation.username:
                return Response(
                    {"error": "This invitation is for a different user"},
                    status=status.HTTP_403_FORBIDDEN
                )
            
            # Use simple response serializer for existing users
            serializer = UserInvitationResponseSerializer(
                data=request.data,
                context={'invitation': invitation}
            )
            serializer.is_valid(raise_exception=True)
            action = serializer.validated_data['action']
            user = request.user
            
        else:
            # For new users, use password serializer
            serializer = UserInvitationWithPasswordSerializer(
                data=request.data,
                context={'invitation': invitation}
            )
            serializer.is_valid(raise_exception=True)
            action = serializer.validated_data['action']
            
            if action == 'accept':
                # Create new user account
                try:
                    user = User.objects.create_user(
                        username=invitation.username,
                        email=serializer.validated_data.get('email', ''),
                        password=serializer.validated_data['password'],
                        first_name=serializer.validated_data.get('first_name', ''),
                        last_name=serializer.validated_data.get('last_name', '')
                    )
                except IntegrityError:
                    return Response(
                        {"error": "Username already exists"},
                        status=status.HTTP_400_BAD_REQUEST
                    )
            else:
                user = None  # No user creation for decline
        
        with transaction.atomic():
            if action == 'accept':
                # Create membership
                membership, created = ProjectMembership.objects.get_or_create(
                    user=user,
                    project=invitation.project,
                    defaults={
                        'role': invitation.role,
                        'added_by': invitation.invited_by
                    }
                )
                
                invitation.status = UserInvitation.InvitationStatus.ACCEPTED
                invitation.accepted_by = user
                invitation.save()
                
                response_serializer = ProjectMembershipSerializer(membership)
                return Response(response_serializer.data, status=status.HTTP_200_OK)
                
            else:  # decline
                invitation.status = UserInvitation.InvitationStatus.DECLINED
                invitation.save()
                
                return Response(
                    {"message": "Invitation declined"}, 
                    status=status.HTTP_200_OK
                )


class APITokenViewSet(ModelViewSet):
    """ViewSet for managing API tokens"""
    serializer_class = APITokenSerializer
    permission_classes = [ProjectTokenPermission]
    
    def get_queryset(self):
        project_slug = self.kwargs.get('project_slug')
        if not project_slug:
            return APIToken.objects.none()
            
        project = get_object_or_404(Project, slug=project_slug)
            
        return APIToken.objects.filter(
            project=project,
            user=self.request.user
        ).select_related('user', 'project')
    
    def get_serializer_class(self):
        if self.action == 'create':
            return APITokenCreateSerializer
        return APITokenSerializer
    
    @extend_schema(
        summary="List API tokens",
        description="Get all API tokens for the current user in this project",
    )
    def list(self, request, *args, **kwargs):
        return super().list(request, *args, **kwargs)
    
    @extend_schema(
        summary="Create API token",
        description="Create a new API token for programmatic access",
        request=APITokenCreateSerializer,
        responses={201: APITokenResponseSerializer}
    )
    def create(self, request, *args, **kwargs):
        project_slug = kwargs.get('project_slug')
        project = get_object_or_404(Project, slug=project_slug)
        
        serializer = self.get_serializer(
            data=request.data,
            context={'user': request.user, 'project': project}
        )
        serializer.is_valid(raise_exception=True)
        
        # Generate token
        raw_token = secrets.token_urlsafe(32)
        token_hash = hashlib.sha256(raw_token.encode()).hexdigest()
        token_prefix = raw_token[:8]
        
        token = APIToken.objects.create(
            name=serializer.validated_data['name'],
            token_hash=token_hash,
            token_prefix=token_prefix,
            user=request.user,
            project=project,
            role=serializer.validated_data['role'],
            expires_at=serializer.validated_data.get('expires_at'),
            allowed_ips=serializer.validated_data.get('allowed_ips')
        )
        
        # Return token with full value (only time it's shown)
        token.token = raw_token  # Temporary assignment for serialization
        response_serializer = APITokenResponseSerializer(token)
        return Response(response_serializer.data, status=status.HTTP_201_CREATED)
    
    @extend_schema(
        summary="Delete API token",
        description="Delete an API token",
    )
    def destroy(self, request, *args, **kwargs):
        return super().destroy(request, *args, **kwargs)


class UserRolesView(APIView):
    """View to get user's roles across all projects"""
    permission_classes = [permissions.IsAuthenticated]
    
    @extend_schema(
        summary="Get user roles",
        description="Get current user's roles and permissions across all projects",
        responses={200: UserProjectRolesSerializer}
    )
    def get(self, request):
        user = request.user
        
        # Check if user is instance owner
        is_instance_owner = user.is_superuser
        
        # Get all project memberships
        memberships = ProjectMembership.objects.filter(user=user).select_related('project')
        
        project_roles = []
        for membership in memberships:
            permissions_list = list(PermissionMatrix.PERMISSIONS.get(membership.role, set()))
            project_roles.append({
                'project_id': membership.project.id,
                'project_slug': membership.project.slug,
                'role': membership.role,
                'permissions': permissions_list
            })
        
        # Add projects where user is owner (backward compatibility)
        owned_projects = Project.objects.filter(owner=user).exclude(
            id__in=[m.project.id for m in memberships]
        )
        
        for project in owned_projects:
            permissions_list = list(PermissionMatrix.PERMISSIONS.get(UserRole.ADMIN, set()))
            project_roles.append({
                'project_id': project.id,
                'project_slug': project.slug,
                'role': UserRole.ADMIN,
                'permissions': permissions_list
            })
        
        data = {
            'user': user,
            'is_instance_owner': is_instance_owner,
            'project_roles': project_roles
        }
        
        serializer = UserProjectRolesSerializer(data)
        return Response(serializer.data)


class PermissionCheckView(APIView):
    """View to check specific permissions"""
    permission_classes = [permissions.IsAuthenticated]
    
    @extend_schema(
        summary="Check permission",
        description="Check if current user has a specific permission for a project",
        request=PermissionCheckSerializer,
        responses={200: PermissionCheckResponseSerializer}
    )
    def post(self, request):
        serializer = PermissionCheckSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        
        permission = serializer.validated_data['permission']
        project_slug = serializer.validated_data['project_slug']
        
        try:
            project = Project.objects.get(slug=project_slug)
        except Project.DoesNotExist:
            return Response(
                {"error": "Project not found"}, 
                status=status.HTTP_404_NOT_FOUND
            )
        
        user_role = PermissionMatrix.get_user_role_in_project(request.user, project)
        has_permission = PermissionMatrix.can_user_perform_action(
            request.user, project, permission
        )
        
        response_data = {
            'has_permission': has_permission,
            'user_role': user_role,
            'permission': permission,
            'project_slug': project_slug
        }
        
        response_serializer = PermissionCheckResponseSerializer(response_data)
        return Response(response_serializer.data)