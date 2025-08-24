from django.contrib.auth.models import User
from django.core.validators import MinLengthValidator
from django.db import models
from django.utils.translation import gettext_lazy as _
from django.utils import timezone
from shortuuid.django_fields import ShortUUIDField
from .base import TimestampedModel
from .main import Project
import secrets
from datetime import timedelta


class UserRole(models.TextChoices):
    """Role hierarchy for project access control"""
    GUEST = "GUEST", _("Guest")
    CONTRIBUTOR = "CONTRIBUTOR", _("Contributor")
    MEMBER = "MEMBER", _("Member")
    ADMIN = "ADMIN", _("Admin")
    INSTANCE_OWNER = "INSTANCE_OWNER", _("Instance Owner")


class ProjectMembership(TimestampedModel):
    """Links users to projects with specific roles"""
    ID_PREFIX = "mbr_"
    id = ShortUUIDField(
        length=11,
        max_length=255,
        primary_key=True,
        prefix=ID_PREFIX,
    )
    
    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name="project_memberships"
    )
    
    project = models.ForeignKey(
        Project,
        on_delete=models.CASCADE,
        related_name="memberships"
    )
    
    role = models.CharField(
        max_length=20,
        choices=UserRole.choices,
        default=UserRole.GUEST
    )
    
    # Metadata
    added_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        related_name="added_memberships"
    )
    
    def __str__(self):
        return f"ProjectMembership({self.user.username} -> {self.project.slug} as {self.role})"
    
    class Meta:
        unique_together = ['user', 'project']
        indexes = [
            models.Index(fields=['user']),
            models.Index(fields=['project']),
            models.Index(fields=['role']),
        ]


class UserInvitation(TimestampedModel):
    """Manages invitations for users to join projects"""
    ID_PREFIX = "inv_"
    id = ShortUUIDField(
        length=11,
        max_length=255,
        primary_key=True,
        prefix=ID_PREFIX,
    )
    
    class InvitationStatus(models.TextChoices):
        PENDING = "PENDING", _("Pending")
        ACCEPTED = "ACCEPTED", _("Accepted")
        DECLINED = "DECLINED", _("Declined")
        EXPIRED = "EXPIRED", _("Expired")
        CANCELLED = "CANCELLED", _("Cancelled")
    
    # Invitation details
    username = models.CharField(max_length=150)
    project = models.ForeignKey(
        Project,
        on_delete=models.CASCADE,
        related_name="invitations"
    )
    role = models.CharField(
        max_length=20,
        choices=UserRole.choices,
        default=UserRole.GUEST
    )
    
    # Status tracking
    status = models.CharField(
        max_length=20,
        choices=InvitationStatus.choices,
        default=InvitationStatus.PENDING
    )
    
    # Expiration
    expires_at = models.DateTimeField()
    
    # Relations
    invited_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        related_name="sent_invitations"
    )
    accepted_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="accepted_invitations"
    )
    
    # Unique token for secure invitation links
    token = models.CharField(max_length=64, unique=True)
    
    def save(self, *args, **kwargs):
        if not self.token:
            self.token = secrets.token_urlsafe(32)
        if not self.expires_at:
            self.expires_at = timezone.now() + timedelta(days=7)  # 7 days expiration
        super().save(*args, **kwargs)
    
    @property
    def is_expired(self):
        return timezone.now() > self.expires_at
    
    def __str__(self):
        return f"UserInvitation({self.username} -> {self.project.slug} as {self.role})"
    
    class Meta:
        unique_together = ['username', 'project', 'status']
        indexes = [
            models.Index(fields=['username']),
            models.Index(fields=['project']),
            models.Index(fields=['status']),
            models.Index(fields=['token']),
            models.Index(fields=['expires_at']),
        ]


class APIToken(TimestampedModel):
    """API tokens for programmatic access (CI/CD, service accounts)"""
    ID_PREFIX = "tok_"
    id = ShortUUIDField(
        length=11,
        max_length=255,
        primary_key=True,
        prefix=ID_PREFIX,
    )
    
    name = models.CharField(
        max_length=255,
        validators=[MinLengthValidator(limit_value=1)],
        help_text="Human-readable name for the token"
    )
    
    # The actual token (hashed in production)
    token_hash = models.CharField(max_length=128, unique=True)
    
    # Token prefix for identification (first 8 chars shown to user)
    token_prefix = models.CharField(max_length=8)
    
    # Permissions
    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name="api_tokens"
    )
    
    project = models.ForeignKey(
        Project,
        on_delete=models.CASCADE,
        related_name="api_tokens"
    )
    
    role = models.CharField(
        max_length=20,
        choices=UserRole.choices,
        default=UserRole.CONTRIBUTOR
    )
    
    # Status and metadata
    is_active = models.BooleanField(default=True)
    last_used_at = models.DateTimeField(null=True, blank=True)
    expires_at = models.DateTimeField(null=True, blank=True)
    
    # IP restrictions (optional)
    allowed_ips = models.JSONField(
        null=True,
        blank=True,
        help_text="List of allowed IP addresses/CIDR blocks"
    )
    
    def __str__(self):
        return f"APIToken({self.name} - {self.token_prefix}****)"
    
    @property
    def is_expired(self):
        if self.expires_at:
            return timezone.now() > self.expires_at
        return False
    
    class Meta:
        unique_together = ['name', 'project', 'user']
        indexes = [
            models.Index(fields=['token_hash']),
            models.Index(fields=['token_prefix']),
            models.Index(fields=['user']),
            models.Index(fields=['project']),
            models.Index(fields=['is_active']),
            models.Index(fields=['expires_at']),
        ]