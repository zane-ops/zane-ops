from rest_framework import serializers
from django.contrib.auth.models import User
from ...models import ProjectMembership, UserInvitation, APIToken, UserRole
from ...serializers import UserSerializer


class ProjectMembershipSerializer(serializers.ModelSerializer):
    """Serializer for project membership management"""
    user = UserSerializer(read_only=True)
    added_by = UserSerializer(read_only=True)
    
    class Meta:
        model = ProjectMembership
        fields = ['id', 'user', 'project', 'role', 'added_by', 'created_at', 'updated_at']
        read_only_fields = ['id', 'project', 'added_by', 'created_at', 'updated_at']


class ProjectMembershipCreateSerializer(serializers.Serializer):
    """Serializer for creating new project memberships"""
    username = serializers.CharField(max_length=150)
    role = serializers.ChoiceField(choices=UserRole.choices)
    
    def validate_username(self, value):
        """Validate that the username exists"""
        try:
            User.objects.get(username=value)
        except User.DoesNotExist:
            raise serializers.ValidationError("User with this username does not exist.")
        return value


class ProjectMembershipUpdateSerializer(serializers.ModelSerializer):
    """Serializer for updating project memberships"""
    
    class Meta:
        model = ProjectMembership
        fields = ['role']


class UserInvitationSerializer(serializers.ModelSerializer):
    """Serializer for user invitations"""
    invited_by = UserSerializer(read_only=True)
    accepted_by = UserSerializer(read_only=True)
    is_expired = serializers.BooleanField(read_only=True)
    
    class Meta:
        model = UserInvitation
        fields = [
            'id', 'username', 'project', 'role', 'status', 'expires_at',
            'invited_by', 'accepted_by', 'is_expired', 'created_at', 'updated_at'
        ]
        read_only_fields = [
            'id', 'project', 'status', 'invited_by', 'accepted_by', 
            'created_at', 'updated_at', 'token'
        ]


class UserInvitationCreateSerializer(serializers.ModelSerializer):
    """Serializer for creating user invitations"""
    
    class Meta:
        model = UserInvitation
        fields = ['username', 'role']
        
    def validate_username(self, value):
        """Validate username and check for existing users"""
        # Check if user already exists
        if User.objects.filter(username=value).exists():
            raise serializers.ValidationError("User with this username already exists.")
        
        # Check if there's already a pending invitation
        project = self.context.get('project')
        if project and UserInvitation.objects.filter(
            username=value, 
            project=project, 
            status=UserInvitation.InvitationStatus.PENDING
        ).exists():
            raise serializers.ValidationError("There is already a pending invitation for this username.")
            
        return value


class InvitationValidateSerializer(serializers.Serializer):
    """Serializer for invitation validation response"""
    username = serializers.CharField(read_only=True)
    project_slug = serializers.CharField(read_only=True) 
    project_name = serializers.CharField(read_only=True)
    role = serializers.CharField(read_only=True)
    invited_by = serializers.CharField(read_only=True)
    expires_at = serializers.DateTimeField(read_only=True)
    user_exists = serializers.BooleanField(read_only=True)
    is_valid = serializers.BooleanField(read_only=True)
    error = serializers.CharField(read_only=True, required=False)


class UserInvitationResponseSerializer(serializers.Serializer):
    """Serializer for responding to invitations (existing users)"""
    action = serializers.ChoiceField(choices=['accept', 'decline'])
    
    def validate_action(self, value):
        invitation = self.context.get('invitation')
        if invitation and invitation.status != UserInvitation.InvitationStatus.PENDING:
            raise serializers.ValidationError("This invitation has already been responded to.")
        if invitation and invitation.is_expired:
            raise serializers.ValidationError("This invitation has expired.")
        return value


class UserInvitationWithPasswordSerializer(serializers.Serializer):
    """Serializer for responding to invitations with account creation"""
    action = serializers.ChoiceField(choices=['accept', 'decline'])
    password = serializers.CharField(write_only=True, required=False, min_length=8)
    email = serializers.EmailField(required=False)
    first_name = serializers.CharField(max_length=150, required=False, allow_blank=True)
    last_name = serializers.CharField(max_length=150, required=False, allow_blank=True)
    
    def validate(self, attrs):
        if attrs.get('action') == 'accept' and not attrs.get('password'):
            raise serializers.ValidationError({
                'password': 'Password is required when accepting an invitation for a new account.'
            })
        return attrs
    
    def validate_action(self, value):
        invitation = self.context.get('invitation')
        if invitation and invitation.status != UserInvitation.InvitationStatus.PENDING:
            raise serializers.ValidationError("This invitation has already been responded to.")
        if invitation and invitation.is_expired:
            raise serializers.ValidationError("This invitation has expired.")
        return value


class APITokenSerializer(serializers.ModelSerializer):
    """Serializer for API tokens (without sensitive data)"""
    user = UserSerializer(read_only=True)
    is_expired = serializers.BooleanField(read_only=True)
    
    class Meta:
        model = APIToken
        fields = [
            'id', 'name', 'token_prefix', 'user', 'project', 'role',
            'is_active', 'last_used_at', 'expires_at', 'is_expired',
            'allowed_ips', 'created_at', 'updated_at'
        ]
        read_only_fields = [
            'id', 'token_prefix', 'user', 'project', 'last_used_at',
            'created_at', 'updated_at'
        ]


class APITokenCreateSerializer(serializers.ModelSerializer):
    """Serializer for creating API tokens"""
    
    class Meta:
        model = APIToken
        fields = ['name', 'role', 'expires_at', 'allowed_ips']
        
    def validate_name(self, value):
        """Validate token name uniqueness within project"""
        user = self.context.get('user')
        project = self.context.get('project')
        
        if user and project and APIToken.objects.filter(
            name=value, 
            user=user, 
            project=project
        ).exists():
            raise serializers.ValidationError("You already have a token with this name in this project.")
            
        return value


class APITokenResponseSerializer(serializers.ModelSerializer):
    """Serializer for API token creation response (includes full token)"""
    token = serializers.CharField(read_only=True)
    
    class Meta:
        model = APIToken
        fields = [
            'id', 'name', 'token', 'token_prefix', 'role', 'expires_at',
            'allowed_ips', 'created_at'
        ]
        read_only_fields = ['id', 'token', 'token_prefix', 'created_at']


class UserRoleInfoSerializer(serializers.Serializer):
    """Serializer for user role information in projects"""
    project_id = serializers.CharField()
    project_slug = serializers.CharField()
    role = serializers.ChoiceField(choices=UserRole.choices)
    permissions = serializers.ListField(child=serializers.CharField())


class UserProjectRolesSerializer(serializers.Serializer):
    """Serializer for user's roles across all projects"""
    user = UserSerializer(read_only=True)
    is_instance_owner = serializers.BooleanField()
    project_roles = UserRoleInfoSerializer(many=True)


class ProjectMembersListSerializer(serializers.Serializer):
    """Serializer for listing all project members"""
    project = serializers.CharField(source='project.slug', read_only=True)
    members = ProjectMembershipSerializer(many=True, read_only=True)
    pending_invitations = UserInvitationSerializer(many=True, read_only=True)


class PermissionCheckSerializer(serializers.Serializer):
    """Serializer for permission checking requests"""
    permission = serializers.CharField()
    project_slug = serializers.CharField()
    
    
class PermissionCheckResponseSerializer(serializers.Serializer):
    """Serializer for permission checking responses"""
    has_permission = serializers.BooleanField()
    user_role = serializers.ChoiceField(choices=UserRole.choices, allow_null=True)
    permission = serializers.CharField()
    project_slug = serializers.CharField()