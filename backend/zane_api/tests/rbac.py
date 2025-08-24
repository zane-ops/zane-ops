from django.test import TestCase
from django.contrib.auth.models import User
from django.urls import reverse
from django.utils import timezone
from rest_framework.test import APITestCase
from rest_framework import status
from datetime import timedelta
import hashlib

from ..models import (
    Project, ProjectMembership, UserInvitation, APIToken, UserRole
)
from ..permissions import PermissionMatrix


class PermissionMatrixTestCase(TestCase):
    """Test the permission matrix logic"""
    
    def setUp(self):
        self.user = User.objects.create_user(
            username='testuser', 
            email='test@example.com',
            password='testpass123'
        )
        self.project = Project.objects.create(
            slug='test-project',
            owner=self.user
        )
        
    def test_role_hierarchy(self):
        """Test that roles have correct hierarchy"""
        self.assertEqual(PermissionMatrix.ROLE_HIERARCHY[UserRole.INSTANCE_OWNER], 0)
        self.assertEqual(PermissionMatrix.ROLE_HIERARCHY[UserRole.ADMIN], 1)
        self.assertEqual(PermissionMatrix.ROLE_HIERARCHY[UserRole.MEMBER], 2)
        self.assertEqual(PermissionMatrix.ROLE_HIERARCHY[UserRole.CONTRIBUTOR], 3)
        self.assertEqual(PermissionMatrix.ROLE_HIERARCHY[UserRole.GUEST], 4)
    
    def test_instance_owner_permissions(self):
        """Test that instance owner has all permissions"""
        all_permissions = {
            'view_project', 'edit_project', 'delete_project', 'manage_members',
            'view_services', 'create_services', 'edit_services', 'delete_services',
            'deploy_services', 'view_deployments', 'cancel_deployments',
            'view_environments', 'create_environments', 'edit_environments',
            'delete_environments', 'manage_tokens'
        }
        
        instance_owner_permissions = PermissionMatrix.PERMISSIONS[UserRole.INSTANCE_OWNER]
        self.assertEqual(instance_owner_permissions, all_permissions)
        
    def test_guest_permissions(self):
        """Test that guest has only read permissions"""
        expected_permissions = {
            'view_project', 'view_services', 'view_deployments', 'view_environments'
        }
        
        guest_permissions = PermissionMatrix.PERMISSIONS[UserRole.GUEST]
        self.assertEqual(guest_permissions, expected_permissions)
        
    def test_superuser_is_instance_owner(self):
        """Test that superuser is treated as instance owner"""
        superuser = User.objects.create_superuser(
            username='admin',
            email='admin@example.com',
            password='adminpass'
        )
        
        role = PermissionMatrix.get_user_role_in_project(superuser, self.project)
        self.assertEqual(role, UserRole.INSTANCE_OWNER)
        
    def test_project_owner_is_admin(self):
        """Test backward compatibility - project owner is admin"""
        role = PermissionMatrix.get_user_role_in_project(self.user, self.project)
        self.assertEqual(role, UserRole.ADMIN)
        
    def test_project_membership_role(self):
        """Test that project membership determines role"""
        member_user = User.objects.create_user(
            username='member',
            email='member@example.com',
            password='memberpass'
        )
        
        ProjectMembership.objects.create(
            user=member_user,
            project=self.project,
            role=UserRole.MEMBER,
            added_by=self.user
        )
        
        role = PermissionMatrix.get_user_role_in_project(member_user, self.project)
        self.assertEqual(role, UserRole.MEMBER)


class ProjectMembershipModelTestCase(TestCase):
    """Test ProjectMembership model"""
    
    def setUp(self):
        self.owner = User.objects.create_user(
            username='owner',
            email='owner@example.com',
            password='ownerpass'
        )
        self.member = User.objects.create_user(
            username='member',
            email='member@example.com',
            password='memberpass'
        )
        self.project = Project.objects.create(
            slug='test-project',
            owner=self.owner
        )
        
    def test_create_membership(self):
        """Test creating a project membership"""
        membership = ProjectMembership.objects.create(
            user=self.member,
            project=self.project,
            role=UserRole.CONTRIBUTOR,
            added_by=self.owner
        )
        
        self.assertEqual(membership.user, self.member)
        self.assertEqual(membership.project, self.project)
        self.assertEqual(membership.role, UserRole.CONTRIBUTOR)
        self.assertEqual(membership.added_by, self.owner)
        
    def test_unique_constraint(self):
        """Test that user can only have one membership per project"""
        ProjectMembership.objects.create(
            user=self.member,
            project=self.project,
            role=UserRole.CONTRIBUTOR,
            added_by=self.owner
        )
        
        with self.assertRaises(Exception):  # IntegrityError
            ProjectMembership.objects.create(
                user=self.member,
                project=self.project,
                role=UserRole.MEMBER,
                added_by=self.owner
            )


class UserInvitationModelTestCase(TestCase):
    """Test UserInvitation model"""
    
    def setUp(self):
        self.owner = User.objects.create_user(
            username='owner',
            email='owner@example.com',
            password='ownerpass'
        )
        self.project = Project.objects.create(
            slug='test-project',
            owner=self.owner
        )
        
    def test_create_invitation(self):
        """Test creating an invitation"""
        invitation = UserInvitation.objects.create(
            username='newuser',
            project=self.project,
            role=UserRole.CONTRIBUTOR,
            invited_by=self.owner
        )
        
        self.assertEqual(invitation.username, 'newuser')
        self.assertEqual(invitation.project, self.project)
        self.assertEqual(invitation.role, UserRole.CONTRIBUTOR)
        self.assertEqual(invitation.invited_by, self.owner)
        self.assertEqual(invitation.status, UserInvitation.InvitationStatus.PENDING)
        self.assertIsNotNone(invitation.token)
        self.assertIsNotNone(invitation.expires_at)
        
    def test_invitation_expiration(self):
        """Test invitation expiration logic"""
        # Create expired invitation
        invitation = UserInvitation.objects.create(
            username='newuser',
            project=self.project,
            role=UserRole.CONTRIBUTOR,
            invited_by=self.owner
        )
        
        # Manually set expiration to past
        invitation.expires_at = timezone.now() - timedelta(days=1)
        invitation.save()
        
        self.assertTrue(invitation.is_expired)
        
    def test_automatic_token_generation(self):
        """Test that token is generated automatically"""
        invitation = UserInvitation.objects.create(
            username='newuser',
            project=self.project,
            role=UserRole.CONTRIBUTOR,
            invited_by=self.owner
        )
        
        self.assertIsNotNone(invitation.token)
        self.assertTrue(len(invitation.token) > 20)  # Should be a long secure token


class APITokenModelTestCase(TestCase):
    """Test APIToken model"""
    
    def setUp(self):
        self.user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='testpass'
        )
        self.project = Project.objects.create(
            slug='test-project',
            owner=self.user
        )
        
    def test_create_api_token(self):
        """Test creating an API token"""
        raw_token = 'test-token-123'
        token_hash = hashlib.sha256(raw_token.encode()).hexdigest()
        
        token = APIToken.objects.create(
            name='Test Token',
            token_hash=token_hash,
            token_prefix='test-tok',
            user=self.user,
            project=self.project,
            role=UserRole.CONTRIBUTOR
        )
        
        self.assertEqual(token.name, 'Test Token')
        self.assertEqual(token.token_hash, token_hash)
        self.assertEqual(token.token_prefix, 'test-tok')
        self.assertEqual(token.user, self.user)
        self.assertEqual(token.project, self.project)
        self.assertEqual(token.role, UserRole.CONTRIBUTOR)
        self.assertTrue(token.is_active)
        
    def test_token_expiration(self):
        """Test token expiration logic"""
        token = APIToken.objects.create(
            name='Test Token',
            token_hash='dummy-hash',
            token_prefix='test-tok',
            user=self.user,
            project=self.project,
            role=UserRole.CONTRIBUTOR,
            expires_at=timezone.now() - timedelta(days=1)
        )
        
        self.assertTrue(token.is_expired)
        
    def test_unique_constraint(self):
        """Test that token names must be unique per user/project"""
        APIToken.objects.create(
            name='Test Token',
            token_hash='hash1',
            token_prefix='test-1',
            user=self.user,
            project=self.project,
            role=UserRole.CONTRIBUTOR
        )
        
        with self.assertRaises(Exception):  # IntegrityError
            APIToken.objects.create(
                name='Test Token',  # Same name
                token_hash='hash2',
                token_prefix='test-2',
                user=self.user,
                project=self.project,
                role=UserRole.CONTRIBUTOR
            )


class RBACAPITestCase(APITestCase):
    """Test RBAC API endpoints"""
    
    def setUp(self):
        self.owner = User.objects.create_user(
            username='owner',
            email='owner@example.com',
            password='ownerpass'
        )
        self.member = User.objects.create_user(
            username='member',
            email='member@example.com',
            password='memberpass'
        )
        self.project = Project.objects.create(
            slug='test-project',
            owner=self.owner
        )
        
    def test_list_project_members_as_owner(self):
        """Test that project owner can list members"""
        # Create membership for member
        ProjectMembership.objects.create(
            user=self.member,
            project=self.project,
            role=UserRole.CONTRIBUTOR,
            added_by=self.owner
        )
        
        self.client.force_authenticate(user=self.owner)
        url = reverse('zane_api:project.members-list', args=[self.project.slug])
        
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data), 1)
        self.assertEqual(response.data[0]['user']['username'], 'member')
        
    def test_list_project_members_as_guest_forbidden(self):
        """Test that guests cannot list members"""
        guest = User.objects.create_user(
            username='guest',
            email='guest@example.com',
            password='guestpass'
        )
        
        ProjectMembership.objects.create(
            user=guest,
            project=self.project,
            role=UserRole.GUEST,
            added_by=self.owner
        )
        
        self.client.force_authenticate(user=guest)
        url = reverse('zane_api:project.members-list', args=[self.project.slug])
        
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data), 0)  # No results due to lack of permission
        
    def test_add_project_member(self):
        """Test adding a new project member"""
        new_user = User.objects.create_user(
            username='newuser',
            email='newuser@example.com',
            password='newuserpass'
        )
        
        self.client.force_authenticate(user=self.owner)
        url = reverse('zane_api:project.members-list', args=[self.project.slug])
        
        data = {
            'username': 'newuser',
            'role': UserRole.CONTRIBUTOR
        }
        
        response = self.client.post(url, data)
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        
        # Verify membership was created
        membership = ProjectMembership.objects.get(user=new_user, project=self.project)
        self.assertEqual(membership.role, UserRole.CONTRIBUTOR)
        self.assertEqual(membership.added_by, self.owner)
        
    def test_add_nonexistent_user_fails(self):
        """Test that adding nonexistent user fails"""
        self.client.force_authenticate(user=self.owner)
        url = reverse('zane_api:project.members-list', args=[self.project.slug])
        
        data = {
            'username': 'nonexistent',
            'role': UserRole.CONTRIBUTOR
        }
        
        response = self.client.post(url, data)
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        
    def test_send_invitation(self):
        """Test sending a project invitation"""
        self.client.force_authenticate(user=self.owner)
        url = reverse('zane_api:project.invitations-list', args=[self.project.slug])
        
        data = {
            'username': 'newuser',
            'role': UserRole.CONTRIBUTOR
        }
        
        response = self.client.post(url, data)
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        
        # Verify invitation was created
        invitation = UserInvitation.objects.get(
            username='newuser',
            project=self.project
        )
        self.assertEqual(invitation.role, UserRole.CONTRIBUTOR)
        self.assertEqual(invitation.invited_by, self.owner)
        self.assertEqual(invitation.status, UserInvitation.InvitationStatus.PENDING)
        
    def test_accept_invitation(self):
        """Test accepting an invitation"""
        invited_user = User.objects.create_user(
            username='invited',
            email='invited@example.com',
            password='invitedpass'
        )
        
        # Create invitation
        invitation = UserInvitation.objects.create(
            username='invited',
            project=self.project,
            role=UserRole.CONTRIBUTOR,
            invited_by=self.owner
        )
        
        self.client.force_authenticate(user=invited_user)
        url = reverse('zane_api:invitations.respond', args=[invitation.token])
        
        data = {'action': 'accept'}
        
        response = self.client.post(url, data)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        
        # Verify membership was created
        membership = ProjectMembership.objects.get(
            user=invited_user,
            project=self.project
        )
        self.assertEqual(membership.role, UserRole.CONTRIBUTOR)
        
        # Verify invitation status updated
        invitation.refresh_from_db()
        self.assertEqual(invitation.status, UserInvitation.InvitationStatus.ACCEPTED)
        self.assertEqual(invitation.accepted_by, invited_user)
        
    def test_decline_invitation(self):
        """Test declining an invitation"""
        invited_user = User.objects.create_user(
            username='invited',
            email='invited@example.com',
            password='invitedpass'
        )
        
        # Create invitation
        invitation = UserInvitation.objects.create(
            username='invited',
            project=self.project,
            role=UserRole.CONTRIBUTOR,
            invited_by=self.owner
        )
        
        self.client.force_authenticate(user=invited_user)
        url = reverse('zane_api:invitations.respond', args=[invitation.token])
        
        data = {'action': 'decline'}
        
        response = self.client.post(url, data)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        
        # Verify no membership was created
        self.assertFalse(
            ProjectMembership.objects.filter(
                user=invited_user,
                project=self.project
            ).exists()
        )
        
        # Verify invitation status updated
        invitation.refresh_from_db()
        self.assertEqual(invitation.status, UserInvitation.InvitationStatus.DECLINED)
        
    def test_get_user_roles(self):
        """Test getting user roles across projects"""
        # Create membership
        ProjectMembership.objects.create(
            user=self.member,
            project=self.project,
            role=UserRole.CONTRIBUTOR,
            added_by=self.owner
        )
        
        self.client.force_authenticate(user=self.member)
        url = reverse('zane_api:auth.user_roles')
        
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        
        data = response.data
        self.assertEqual(data['user']['username'], 'member')
        self.assertFalse(data['is_instance_owner'])
        self.assertEqual(len(data['project_roles']), 1)
        
        project_role = data['project_roles'][0]
        self.assertEqual(project_role['project_slug'], 'test-project')
        self.assertEqual(project_role['role'], UserRole.CONTRIBUTOR)
        self.assertIn('view_project', project_role['permissions'])
        
    def test_check_permission(self):
        """Test permission checking endpoint"""
        # Create membership
        ProjectMembership.objects.create(
            user=self.member,
            project=self.project,
            role=UserRole.CONTRIBUTOR,
            added_by=self.owner
        )
        
        self.client.force_authenticate(user=self.member)
        url = reverse('zane_api:auth.check_permission')
        
        # Test permission user has
        data = {
            'permission': 'view_project',
            'project_slug': 'test-project'
        }
        
        response = self.client.post(url, data)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        
        result = response.data
        self.assertTrue(result['has_permission'])
        self.assertEqual(result['user_role'], UserRole.CONTRIBUTOR)
        
        # Test permission user doesn't have
        data = {
            'permission': 'delete_project',
            'project_slug': 'test-project'
        }
        
        response = self.client.post(url, data)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        
        result = response.data
        self.assertFalse(result['has_permission'])
        self.assertEqual(result['user_role'], UserRole.CONTRIBUTOR)
    
    def test_validate_invitation_valid_token(self):
        """Test validating a valid invitation token"""
        invited_user = User.objects.create_user(
            username='inviteduser',
            email='invited@example.com',
            password='invitedpass'
        )
        
        # Create invitation
        invitation = UserInvitation.objects.create(
            username='inviteduser',
            project=self.project,
            role=UserRole.CONTRIBUTOR,
            invited_by=self.owner
        )
        
        url = reverse('zane_api:invitations.respond', args=[invitation.token])
        
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        
        result = response.data
        self.assertTrue(result['is_valid'])
        self.assertEqual(result['username'], 'inviteduser')
        self.assertEqual(result['project_slug'], self.project.slug)
        self.assertEqual(result['role'], UserRole.CONTRIBUTOR)
        self.assertTrue(result['user_exists'])
    
    def test_validate_invitation_new_user(self):
        """Test validating invitation for non-existing user"""
        # Create invitation for user that doesn't exist
        invitation = UserInvitation.objects.create(
            username='newuser',
            project=self.project,
            role=UserRole.CONTRIBUTOR,
            invited_by=self.owner
        )
        
        url = reverse('zane_api:invitations.respond', args=[invitation.token])
        
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        
        result = response.data
        self.assertTrue(result['is_valid'])
        self.assertEqual(result['username'], 'newuser')
        self.assertFalse(result['user_exists'])
    
    def test_validate_invitation_invalid_token(self):
        """Test validating with invalid token"""
        url = reverse('zane_api:invitations.respond', args=['invalid-token'])
        
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)
        
        result = response.data
        self.assertFalse(result['is_valid'])
        self.assertEqual(result['error'], 'Invalid invitation token')
    
    def test_validate_invitation_expired(self):
        """Test validating expired invitation"""
        invitation = UserInvitation.objects.create(
            username='expireduser',
            project=self.project,
            role=UserRole.CONTRIBUTOR,
            invited_by=self.owner
        )
        
        # Manually expire the invitation
        invitation.expires_at = timezone.now() - timedelta(days=1)
        invitation.save()
        
        url = reverse('zane_api:invitations.respond', args=[invitation.token])
        
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        
        result = response.data
        self.assertFalse(result['is_valid'])
        self.assertEqual(result['error'], 'This invitation has expired')
    
    def test_accept_invitation_with_new_account(self):
        """Test accepting invitation with new account creation"""
        # Create invitation for user that doesn't exist
        invitation = UserInvitation.objects.create(
            username='newaccount',
            project=self.project,
            role=UserRole.CONTRIBUTOR,
            invited_by=self.owner
        )
        
        url = reverse('zane_api:invitations.respond', args=[invitation.token])
        
        data = {
            'action': 'accept',
            'password': 'newpassword123',
            'email': 'newaccount@example.com',
            'first_name': 'New',
            'last_name': 'User'
        }
        
        response = self.client.post(url, data)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        
        # Verify user was created
        user = User.objects.get(username='newaccount')
        self.assertEqual(user.email, 'newaccount@example.com')
        self.assertEqual(user.first_name, 'New')
        self.assertEqual(user.last_name, 'User')
        
        # Verify membership was created
        membership = ProjectMembership.objects.get(
            user=user,
            project=self.project
        )
        self.assertEqual(membership.role, UserRole.CONTRIBUTOR)
        
        # Verify invitation status updated
        invitation.refresh_from_db()
        self.assertEqual(invitation.status, UserInvitation.InvitationStatus.ACCEPTED)
        self.assertEqual(invitation.accepted_by, user)
    
    def test_accept_invitation_new_account_without_password_fails(self):
        """Test that accepting invitation without password fails for new accounts"""
        invitation = UserInvitation.objects.create(
            username='failuser',
            project=self.project,
            role=UserRole.CONTRIBUTOR,
            invited_by=self.owner
        )
        
        url = reverse('zane_api:invitations.respond', args=[invitation.token])
        
        data = {
            'action': 'accept'
            # No password provided
        }
        
        response = self.client.post(url, data)
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        
        # Verify user was not created
        self.assertFalse(User.objects.filter(username='failuser').exists())
    
    def test_decline_invitation_new_user(self):
        """Test declining invitation for new user (no account creation)"""
        invitation = UserInvitation.objects.create(
            username='declineuser',
            project=self.project,
            role=UserRole.CONTRIBUTOR,
            invited_by=self.owner
        )
        
        url = reverse('zane_api:invitations.respond', args=[invitation.token])
        
        data = {'action': 'decline'}
        
        response = self.client.post(url, data)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        
        # Verify user was not created
        self.assertFalse(User.objects.filter(username='declineuser').exists())
        
        # Verify invitation status updated
        invitation.refresh_from_db()
        self.assertEqual(invitation.status, UserInvitation.InvitationStatus.DECLINED)