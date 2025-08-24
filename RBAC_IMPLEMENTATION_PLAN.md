# Plan d'Implémentation RBAC et Multi-Utilisateurs pour ZaneOps

## 📋 Contexte
Issue #498 - Implémentation d'un système complet de contrôle d'accès basé sur les rôles (RBAC) pour ZaneOps avec support multi-utilisateurs, invitations et tokens API.

## 🎯 Objectifs
- Implémenter 5 niveaux de rôles avec permissions granulaires
- Système d'invitations avec tokens sécurisés (sans email pour l'instant)
- Gestion de tokens API pour automatisation CI/CD
- Maintenir la rétrocompatibilité avec le système de `deploy_token` existant
- Support multi-utilisateurs par projet

## 📊 Matrice des Permissions Détaillée

### Rôles Définis
1. **GUEST** - Accès lecture seule minimal
2. **CONTRIBUTOR** - Peut contribuer et déployer
3. **MEMBER** - Membre actif avec permissions étendues
4. **ADMIN** - Administrateur du projet
5. **INSTANCE_OWNER** - Propriétaire de l'instance ZaneOps

### Tableau des Permissions (16 permissions)

| Permission                   | GUEST | CONTRIBUTOR | MEMBER | ADMIN | INSTANCE_OWNER |
|------------------------------|-------|-------------|--------|-------|----------------|
| View project                 | ✅    | ✅          | ✅     | ✅    | ✅             |
| View deployments             | ✅    | ✅          | ✅     | ✅    | ✅             |
| View logs                    | ❌    | ✅          | ✅     | ✅    | ✅             |
| Deploy service               | ❌    | ✅          | ✅     | ✅    | ✅             |
| Manage service settings      | ❌    | ❌          | ✅     | ✅    | ✅             |
| Delete service               | ❌    | ❌          | ✅     | ✅    | ✅             |
| Manage environment variables | ❌    | ❌          | ✅     | ✅    | ✅             |
| Manage volumes               | ❌    | ❌          | ✅     | ✅    | ✅             |
| Create/Delete environments   | ❌    | ❌          | ❌     | ✅    | ✅             |
| Manage project settings      | ❌    | ❌          | ❌     | ✅    | ✅             |
| Invite users to project      | ❌    | ❌          | ❌     | ✅    | ✅             |
| Remove users from project    | ❌    | ❌          | ❌     | ✅    | ✅             |
| Delete project               | ❌    | ❌          | ❌     | ✅    | ✅             |
| Create new projects          | ❌    | ❌          | ❌     | ❌    | ✅             |
| Manage instance settings     | ❌    | ❌          | ❌     | ❌    | ✅             |
| Manage all users             | ❌    | ❌          | ❌     | ❌    | ✅             |

## 🏗️ Architecture Technique

### 1. Nouveaux Modèles Django

#### **backend/zane_api/models/rbac.py**
```python
from django.db import models
from django.contrib.auth.models import User
from shortuuid.django_fields import ShortUUIDField
from django.utils import timezone
from datetime import timedelta
import secrets

class UserRole(models.TextChoices):
    GUEST = 'GUEST', 'Guest'
    CONTRIBUTOR = 'CONTRIBUTOR', 'Contributor'
    MEMBER = 'MEMBER', 'Member'
    ADMIN = 'ADMIN', 'Admin'
    INSTANCE_OWNER = 'INSTANCE_OWNER', 'Instance Owner'

class ProjectMembership(models.Model):
    """Relation many-to-many entre User et Project avec rôle"""
    id = ShortUUIDField(prefix="mbr_", length=11, primary_key=True)
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='project_memberships')
    project = models.ForeignKey('Project', on_delete=models.CASCADE, related_name='memberships')
    role = models.CharField(max_length=20, choices=UserRole.choices)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    invited_by = models.ForeignKey(
        User, 
        null=True, 
        blank=True, 
        on_delete=models.SET_NULL,
        related_name='invitations_sent'
    )
    
    class Meta:
        unique_together = ('user', 'project')
        indexes = [
            models.Index(fields=['project', 'role']),
            models.Index(fields=['user', 'role']),
        ]
        ordering = ['-created_at']
    
    def __str__(self):
        return f"{self.user.username} - {self.project.name} ({self.role})"

class UserInvitation(models.Model):
    """Invitations pour rejoindre un projet"""
    id = ShortUUIDField(prefix="inv_", length=11, primary_key=True)
    token = models.CharField(max_length=64, unique=True, db_index=True)
    email = models.EmailField()
    project = models.ForeignKey('Project', on_delete=models.CASCADE, related_name='invitations')
    role = models.CharField(max_length=20, choices=UserRole.choices)
    invited_by = models.ForeignKey(User, on_delete=models.CASCADE, related_name='invitations_created')
    expires_at = models.DateTimeField()
    accepted_at = models.DateTimeField(null=True, blank=True)
    accepted_by = models.ForeignKey(
        User, 
        null=True, 
        blank=True, 
        on_delete=models.SET_NULL,
        related_name='invitations_accepted'
    )
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        indexes = [
            models.Index(fields=['token']),
            models.Index(fields=['project', 'email']),
            models.Index(fields=['expires_at']),
        ]
        ordering = ['-created_at']
    
    def save(self, *args, **kwargs):
        if not self.token:
            self.token = secrets.token_urlsafe(48)
        if not self.expires_at:
            self.expires_at = timezone.now() + timedelta(days=7)
        super().save(*args, **kwargs)
    
    @property
    def is_expired(self):
        return timezone.now() > self.expires_at
    
    @property
    def is_valid(self):
        return not self.is_expired and self.accepted_at is None
    
    def __str__(self):
        return f"Invitation to {self.email} for {self.project.name}"

class APIToken(models.Model):
    """Tokens API pour l'automatisation CI/CD"""
    id = ShortUUIDField(prefix="tok_", length=11, primary_key=True)
    key = models.CharField(max_length=64, unique=True, db_index=True)
    name = models.CharField(max_length=255)
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='api_tokens')
    project = models.ForeignKey(
        'Project', 
        null=True, 
        blank=True,
        on_delete=models.CASCADE,
        related_name='api_tokens'
    )
    role = models.CharField(max_length=20, choices=UserRole.choices)
    last_used_at = models.DateTimeField(null=True, blank=True)
    expires_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    is_active = models.BooleanField(default=True)
    
    class Meta:
        indexes = [
            models.Index(fields=['key']),
            models.Index(fields=['user', 'is_active']),
            models.Index(fields=['project', 'is_active']),
        ]
        ordering = ['-created_at']
    
    def save(self, *args, **kwargs):
        if not self.key:
            self.key = f"zane_{secrets.token_urlsafe(48)}"
        super().save(*args, **kwargs)
    
    @property
    def is_expired(self):
        if self.expires_at:
            return timezone.now() > self.expires_at
        return False
    
    @property
    def is_valid(self):
        return self.is_active and not self.is_expired
    
    def __str__(self):
        return f"API Token: {self.name} ({self.user.username})"
```

### 2. Système de Permissions

#### **backend/zane_api/permissions.py**
```python
from rest_framework.permissions import BasePermission
from .models.rbac import ProjectMembership, UserRole, APIToken

class PermissionMatrix:
    """Matrice centralisée des permissions"""
    PERMISSIONS = {
        'view_project': [
            UserRole.GUEST, 
            UserRole.CONTRIBUTOR, 
            UserRole.MEMBER, 
            UserRole.ADMIN, 
            UserRole.INSTANCE_OWNER
        ],
        'view_deployments': [
            UserRole.GUEST, 
            UserRole.CONTRIBUTOR, 
            UserRole.MEMBER, 
            UserRole.ADMIN, 
            UserRole.INSTANCE_OWNER
        ],
        'view_logs': [
            UserRole.CONTRIBUTOR, 
            UserRole.MEMBER, 
            UserRole.ADMIN, 
            UserRole.INSTANCE_OWNER
        ],
        'deploy_service': [
            UserRole.CONTRIBUTOR, 
            UserRole.MEMBER, 
            UserRole.ADMIN, 
            UserRole.INSTANCE_OWNER
        ],
        'manage_service': [
            UserRole.MEMBER, 
            UserRole.ADMIN, 
            UserRole.INSTANCE_OWNER
        ],
        'delete_service': [
            UserRole.MEMBER, 
            UserRole.ADMIN, 
            UserRole.INSTANCE_OWNER
        ],
        'manage_env_vars': [
            UserRole.MEMBER, 
            UserRole.ADMIN, 
            UserRole.INSTANCE_OWNER
        ],
        'manage_volumes': [
            UserRole.MEMBER, 
            UserRole.ADMIN, 
            UserRole.INSTANCE_OWNER
        ],
        'manage_environments': [
            UserRole.ADMIN, 
            UserRole.INSTANCE_OWNER
        ],
        'manage_project_settings': [
            UserRole.ADMIN, 
            UserRole.INSTANCE_OWNER
        ],
        'invite_users': [
            UserRole.ADMIN, 
            UserRole.INSTANCE_OWNER
        ],
        'remove_users': [
            UserRole.ADMIN, 
            UserRole.INSTANCE_OWNER
        ],
        'delete_project': [
            UserRole.ADMIN, 
            UserRole.INSTANCE_OWNER
        ],
        'create_projects': [
            UserRole.INSTANCE_OWNER
        ],
        'manage_instance': [
            UserRole.INSTANCE_OWNER
        ],
        'manage_all_users': [
            UserRole.INSTANCE_OWNER
        ],
    }
    
    @classmethod
    def user_has_permission(cls, user, project, permission):
        """Vérifie si un utilisateur a une permission sur un projet"""
        # Instance owners ont tous les droits
        if hasattr(user, 'is_instance_owner') and user.is_instance_owner:
            return True
        
        # Vérifier le membership
        try:
            membership = ProjectMembership.objects.get(
                user=user,
                project=project
            )
            allowed_roles = cls.PERMISSIONS.get(permission, [])
            return membership.role in allowed_roles
        except ProjectMembership.DoesNotExist:
            return False

class HasProjectPermission(BasePermission):
    """Permission de base pour les opérations sur projet"""
    required_permission = None
    
    def has_permission(self, request, view):
        # Webhooks avec deploy_token passent toujours
        if hasattr(request, 'deploy_token_service'):
            return True
        
        # Authentification requise
        if not request.user.is_authenticated:
            # Vérifier si c'est un API token
            auth_header = request.headers.get('Authorization', '')
            if auth_header.startswith('Bearer zane_'):
                token_key = auth_header.replace('Bearer ', '')
                try:
                    token = APIToken.objects.get(key=token_key, is_active=True)
                    if token.is_valid:
                        request.user = token.user
                        request.api_token = token
                    else:
                        return False
                except APIToken.DoesNotExist:
                    return False
            else:
                return False
        
        # Instance owners ont tous les droits
        if hasattr(request.user, 'is_instance_owner') and request.user.is_instance_owner:
            return True
        
        # Récupérer le projet depuis les kwargs
        project_id = view.kwargs.get('project_id') or view.kwargs.get('project_slug')
        if not project_id:
            return True  # Sera vérifié dans has_object_permission
        
        try:
            from .models import Project
            project = Project.objects.get(slug=project_id)
            return PermissionMatrix.user_has_permission(
                request.user, 
                project, 
                self.required_permission
            )
        except Project.DoesNotExist:
            return False
    
    def has_object_permission(self, request, view, obj):
        # Pour les objets liés à un projet
        project = None
        if hasattr(obj, 'project'):
            project = obj.project
        elif hasattr(obj, 'service') and hasattr(obj.service, 'project'):
            project = obj.service.project
        elif obj.__class__.__name__ == 'Project':
            project = obj
        
        if project:
            return PermissionMatrix.user_has_permission(
                request.user,
                project,
                self.required_permission
            )
        return False

# Permissions spécifiques
class CanViewProject(HasProjectPermission):
    required_permission = 'view_project'

class CanViewDeployments(HasProjectPermission):
    required_permission = 'view_deployments'

class CanViewLogs(HasProjectPermission):
    required_permission = 'view_logs'

class CanDeployService(HasProjectPermission):
    required_permission = 'deploy_service'

class CanManageService(HasProjectPermission):
    required_permission = 'manage_service'

class CanDeleteService(HasProjectPermission):
    required_permission = 'delete_service'

class CanManageEnvVars(HasProjectPermission):
    required_permission = 'manage_env_vars'

class CanManageVolumes(HasProjectPermission):
    required_permission = 'manage_volumes'

class CanManageEnvironments(HasProjectPermission):
    required_permission = 'manage_environments'

class CanManageProjectSettings(HasProjectPermission):
    required_permission = 'manage_project_settings'

class CanInviteUsers(HasProjectPermission):
    required_permission = 'invite_users'

class CanRemoveUsers(HasProjectPermission):
    required_permission = 'remove_users'

class CanDeleteProject(HasProjectPermission):
    required_permission = 'delete_project'

class IsInstanceOwner(BasePermission):
    """Permission pour les actions niveau instance"""
    def has_permission(self, request, view):
        if not request.user.is_authenticated:
            return False
        return hasattr(request.user, 'is_instance_owner') and request.user.is_instance_owner
```

### 3. API Endpoints

#### Nouveaux Endpoints
```
# Invitations
POST   /api/projects/{project_id}/invitations/          # Créer invitation
GET    /api/projects/{project_id}/invitations/          # Lister invitations
DELETE /api/projects/{project_id}/invitations/{id}/     # Révoquer invitation
GET    /api/invitations/{token}/validate/               # Valider token (public)
POST   /api/invitations/{token}/accept/                 # Accepter invitation

# Membres
GET    /api/projects/{project_id}/members/              # Lister membres
PUT    /api/projects/{project_id}/members/{id}/         # Modifier rôle
DELETE /api/projects/{project_id}/members/{id}/         # Retirer membre
GET    /api/projects/{project_id}/members/me/           # Mon membership

# Tokens API
GET    /api/tokens/                                     # Lister mes tokens
POST   /api/tokens/                                     # Créer token
DELETE /api/tokens/{id}/                                # Révoquer token
POST   /api/tokens/{id}/regenerate/                     # Régénérer token
GET    /api/tokens/{id}/                                # Détails d'un token

# Instance (INSTANCE_OWNER only)
GET    /api/instance/users/                             # Lister tous les users
DELETE /api/instance/users/{id}/                        # Supprimer un user
GET    /api/instance/stats/                             # Statistiques globales
PUT    /api/instance/settings/                          # Paramètres instance
```

## 🔄 Stratégie de Migration

### Migration des Données Existantes

#### **backend/zane_api/migrations/0xxx_add_rbac_system.py**
```python
from django.db import migrations
from django.contrib.auth import get_user_model

def migrate_existing_users_and_projects(apps, schema_editor):
    User = get_user_model()
    Project = apps.get_model('zane_api', 'Project')
    ProjectMembership = apps.get_model('zane_api', 'ProjectMembership')
    
    # 1. Premier utilisateur devient INSTANCE_OWNER
    first_user = User.objects.first()
    if first_user:
        first_user.is_instance_owner = True
        first_user.save()
        print(f"✅ User {first_user.username} is now INSTANCE_OWNER")
    
    # 2. Créer ProjectMembership pour tous les projets existants
    for project in Project.objects.all():
        # L'owner actuel devient ADMIN du projet
        if hasattr(project, 'owner') and project.owner:
            membership, created = ProjectMembership.objects.get_or_create(
                user=project.owner,
                project=project,
                defaults={'role': 'ADMIN'}
            )
            if created:
                print(f"✅ Created ADMIN membership for {project.owner.username} on {project.name}")
    
    # 3. deploy_token reste inchangé - Les webhooks continuent de fonctionner
    print("✅ deploy_token preserved for webhook compatibility")

def reverse_migration(apps, schema_editor):
    # Suppression des memberships (les modèles seront supprimés automatiquement)
    ProjectMembership = apps.get_model('zane_api', 'ProjectMembership')
    ProjectMembership.objects.all().delete()
    
    # Retirer le flag instance_owner
    User = get_user_model()
    User.objects.update(is_instance_owner=False)

class Migration(migrations.Migration):
    dependencies = [
        ('zane_api', 'previous_migration'),
    ]
    
    operations = [
        migrations.RunPython(
            migrate_existing_users_and_projects,
            reverse_migration
        ),
    ]
```

### Ordre des Migrations Django
1. `0001_create_rbac_models.py` - Créer les nouveaux modèles
2. `0002_add_instance_owner_field.py` - Ajouter is_instance_owner sur User
3. `0003_migrate_existing_data.py` - Migration des données
4. `0004_add_indexes.py` - Optimisation avec indexes

## 📝 Modifications des Vues Existantes

### Exemple: ProjectsListAPIView
```python
# backend/zane_api/views/projects.py

from rest_framework import viewsets
from rest_framework.decorators import action
from .permissions import (
    CanViewProject, 
    CanManageProjectSettings, 
    CanDeleteProject,
    IsInstanceOwner
)

class ProjectViewSet(viewsets.ModelViewSet):
    serializer_class = ProjectSerializer
    lookup_field = 'slug'
    
    def get_queryset(self):
        """Retourne les projets visibles par l'utilisateur"""
        user = self.request.user
        
        # Instance owner voit tout
        if hasattr(user, 'is_instance_owner') and user.is_instance_owner:
            return Project.objects.all()
        
        # Autres utilisateurs voient leurs projets via membership
        return Project.objects.filter(
            memberships__user=user
        ).distinct()
    
    def get_permissions(self):
        """Permissions basées sur l'action"""
        if self.action == 'create':
            # Seul INSTANCE_OWNER peut créer des projets
            return [IsInstanceOwner()]
        elif self.action in ['retrieve', 'list']:
            # GUEST et plus peuvent voir
            return [CanViewProject()]
        elif self.action in ['update', 'partial_update']:
            # ADMIN et plus peuvent modifier
            return [CanManageProjectSettings()]
        elif self.action == 'destroy':
            # ADMIN et plus peuvent supprimer
            return [CanDeleteProject()]
        return super().get_permissions()
    
    def perform_create(self, serializer):
        """Créer le projet et ajouter le créateur comme ADMIN"""
        project = serializer.save()
        ProjectMembership.objects.create(
            user=self.request.user,
            project=project,
            role=UserRole.ADMIN
        )
```

## 🧪 Plan de Tests

### Tests Unitaires

#### **backend/zane_api/tests/test_rbac.py**
```python
from django.test import TestCase
from django.contrib.auth import get_user_model
from rest_framework.test import APIClient
from ..models import Project, ProjectMembership, UserRole

User = get_user_model()

class RBACPermissionTests(TestCase):
    def setUp(self):
        # Créer les utilisateurs de test
        self.instance_owner = User.objects.create_user(
            username='owner',
            email='owner@test.com',
            password='testpass123',
            is_instance_owner=True
        )
        self.admin = User.objects.create_user(
            username='admin',
            email='admin@test.com',
            password='testpass123'
        )
        self.member = User.objects.create_user(
            username='member',
            email='member@test.com',
            password='testpass123'
        )
        self.contributor = User.objects.create_user(
            username='contributor',
            email='contributor@test.com',
            password='testpass123'
        )
        self.guest = User.objects.create_user(
            username='guest',
            email='guest@test.com',
            password='testpass123'
        )
        
        # Créer un projet de test
        self.project = Project.objects.create(
            name='Test Project',
            slug='test-project'
        )
        
        # Créer les memberships
        ProjectMembership.objects.create(
            user=self.admin,
            project=self.project,
            role=UserRole.ADMIN
        )
        ProjectMembership.objects.create(
            user=self.member,
            project=self.project,
            role=UserRole.MEMBER
        )
        ProjectMembership.objects.create(
            user=self.contributor,
            project=self.project,
            role=UserRole.CONTRIBUTOR
        )
        ProjectMembership.objects.create(
            user=self.guest,
            project=self.project,
            role=UserRole.GUEST
        )
        
        self.client = APIClient()
    
    def test_guest_cannot_deploy(self):
        """GUEST ne peut pas déployer"""
        self.client.force_authenticate(user=self.guest)
        response = self.client.post(
            f'/api/projects/{self.project.slug}/services/test-service/deploy/'
        )
        self.assertEqual(response.status_code, 403)
    
    def test_contributor_can_deploy(self):
        """CONTRIBUTOR peut déployer"""
        self.client.force_authenticate(user=self.contributor)
        response = self.client.post(
            f'/api/projects/{self.project.slug}/services/test-service/deploy/'
        )
        self.assertNotEqual(response.status_code, 403)
    
    def test_member_can_manage_service(self):
        """MEMBER peut gérer les services"""
        self.client.force_authenticate(user=self.member)
        response = self.client.patch(
            f'/api/projects/{self.project.slug}/services/test-service/',
            {'name': 'Updated Service'}
        )
        self.assertNotEqual(response.status_code, 403)
    
    def test_admin_can_invite_users(self):
        """ADMIN peut inviter des utilisateurs"""
        self.client.force_authenticate(user=self.admin)
        response = self.client.post(
            f'/api/projects/{self.project.slug}/invitations/',
            {
                'email': 'newuser@test.com',
                'role': UserRole.MEMBER
            }
        )
        self.assertEqual(response.status_code, 201)
    
    def test_instance_owner_can_create_projects(self):
        """INSTANCE_OWNER peut créer des projets"""
        self.client.force_authenticate(user=self.instance_owner)
        response = self.client.post(
            '/api/projects/',
            {
                'name': 'New Project',
                'slug': 'new-project'
            }
        )
        self.assertEqual(response.status_code, 201)
    
    def test_regular_user_cannot_create_projects(self):
        """Les utilisateurs normaux ne peuvent pas créer de projets"""
        self.client.force_authenticate(user=self.admin)
        response = self.client.post(
            '/api/projects/',
            {
                'name': 'New Project',
                'slug': 'new-project'
            }
        )
        self.assertEqual(response.status_code, 403)
```

#### **backend/zane_api/tests/test_invitations.py**
```python
class InvitationFlowTests(TestCase):
    def test_create_invitation(self):
        """Test de création d'invitation"""
        # ...
    
    def test_invitation_expiration(self):
        """Test d'expiration des invitations"""
        # ...
    
    def test_accept_invitation(self):
        """Test d'acceptation d'invitation"""
        # ...
    
    def test_revoke_invitation(self):
        """Test de révocation d'invitation"""
        # ...
    
    def test_invalid_token(self):
        """Test avec token invalide"""
        # ...
```

#### **backend/zane_api/tests/test_api_tokens.py**
```python
class APITokenTests(TestCase):
    def test_token_creation(self):
        """Test de création de token API"""
        # ...
    
    def test_token_authentication(self):
        """Test d'authentification par token"""
        # ...
    
    def test_token_permissions(self):
        """Test des permissions avec token"""
        # ...
    
    def test_token_revocation(self):
        """Test de révocation de token"""
        # ...
```

## 🚀 Phases d'Implémentation

### Phase 1: Infrastructure (2-3h)
- [ ] Créer `backend/zane_api/models/rbac.py`
- [ ] Créer `backend/zane_api/permissions.py`
- [ ] Créer `backend/zane_api/authentication.py`
- [ ] Mettre à jour `backend/zane_api/models/__init__.py`
- [ ] Créer les migrations Django

### Phase 2: APIs (3-4h)
- [ ] Créer `backend/zane_api/views/invitations.py`
- [ ] Créer `backend/zane_api/views/members.py`
- [ ] Créer `backend/zane_api/views/api_tokens.py`
- [ ] Créer `backend/zane_api/serializers/rbac.py`
- [ ] Mettre à jour `backend/zane_api/urls.py`

### Phase 3: Intégration (4-5h)
- [ ] Modifier `views/projects.py`
- [ ] Modifier `views/services.py`
- [ ] Modifier `views/deployments.py`
- [ ] Modifier `views/environments.py`
- [ ] Ajouter permissions sur chaque endpoint
- [ ] Implémenter filtrage par membership
- [ ] Garder webhooks publics (deploy_token)

### Phase 4: Migration & Tests (2-3h)
- [ ] Créer script de migration des données
- [ ] Écrire tests unitaires complets
- [ ] Écrire tests d'intégration
- [ ] Tester rétrocompatibilité deploy_token

### Phase 5: Validation (1-2h)
- [ ] Test manuel de tous les endpoints
- [ ] Vérifier flow invitation complet
- [ ] Tester tokens API avec Postman/Insomnia
- [ ] Vérifier webhooks deploy_token
- [ ] Test de performance des permissions

## 🔐 Considérations de Sécurité

### 1. Génération de tokens sécurisés
```python
import secrets

# Pour les invitations
invitation_token = secrets.token_urlsafe(48)  # 64 caractères

# Pour les tokens API
api_token = f"zane_{secrets.token_urlsafe(48)}"
```

### 2. Expiration des invitations
```python
from datetime import timedelta
from django.utils import timezone

expires_at = timezone.now() + timedelta(days=7)
```

### 3. Prévention d'escalade de privilèges
- Un user ne peut pas modifier son propre rôle
- Seuls ADMIN et INSTANCE_OWNER peuvent inviter
- Validation stricte des transitions de rôles
- Audit log de tous les changements de permissions

### 4. Webhooks publics maintenus
```python
# Le deploy_token reste sans authentification
# Endpoint: /api/services/webhook/{deploy_token}/deploy/

def webhook_deploy(request, deploy_token):
    try:
        service = Service.objects.get(deploy_token=deploy_token)
        # Pas de vérification de permissions ici
        return deploy_service(service)
    except Service.DoesNotExist:
        return Response(status=404)
```

### 5. Protection CSRF
- Toutes les mutations protégées par CSRF tokens
- Sessions sécurisées avec HttpOnly cookies
- API tokens exemptés de CSRF (Bearer auth)

### 6. Rate Limiting
```python
# Limiter les tentatives d'invitation
from django_ratelimit.decorators import ratelimit

@ratelimit(key='user', rate='10/h', method='POST')
def create_invitation(request):
    # ...
```

## ✅ Critères de Succès

- [ ] 100% des tests passent
- [ ] Rétrocompatibilité maintenue
- [ ] deploy_token fonctionne toujours pour webhooks
- [ ] Permissions appliquées sur tous les endpoints
- [ ] Invitations fonctionnelles (sans email pour l'instant)
- [ ] Tokens API opérationnels
- [ ] Performance < 100ms pour vérifications de permissions
- [ ] Migration réversible des données existantes
- [ ] Documentation API mise à jour (OpenAPI)
- [ ] Pas de régression sur les fonctionnalités existantes

## 📚 Notes pour l'Implémentation Future

### Phase 2: Email/Notifications
- Intégration avec système de notifications (Celery)
- Templates d'emails pour invitations
- Notifications de changements de rôle
- Rappels d'expiration d'invitation

### Phase 3: Audit Logs
```python
class AuditLog(models.Model):
    user = models.ForeignKey(User, on_delete=models.SET_NULL, null=True)
    action = models.CharField(max_length=100)
    object_type = models.CharField(max_length=50)
    object_id = models.CharField(max_length=100)
    changes = models.JSONField()
    ip_address = models.GenericIPAddressField()
    user_agent = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)
```

### Phase 4: SSO/OAuth
- Support Google OAuth
- Support GitHub OAuth
- Support GitLab OAuth
- SAML pour entreprises

## 🛠️ Commandes Utiles

```bash
# Créer migrations
python backend/manage.py makemigrations

# Appliquer migrations
make migrate

# Créer superuser pour tests
python backend/manage.py createsuperuser

# Lancer tests RBAC
python backend/manage.py test zane_api.tests.test_rbac -v 2
python backend/manage.py test zane_api.tests.test_invitations -v 2
python backend/manage.py test zane_api.tests.test_api_tokens -v 2

# Vérifier coverage
coverage run --source='backend/zane_api' backend/manage.py test
coverage report
coverage html  # Génère un rapport HTML

# Formatter code Python
black backend/zane_api/
isort backend/zane_api/

# Linter
pylint backend/zane_api/
flake8 backend/zane_api/

# Générer OpenAPI schema mis à jour
python backend/manage.py spectacular --file openapi/schema.yml
```

## 📈 Métriques de Performance

### Objectifs
- Vérification de permission: < 10ms
- Récupération des memberships: < 50ms
- Création d'invitation: < 100ms
- Acceptation d'invitation: < 200ms
- Liste des projets avec filtrage: < 100ms

### Optimisations
```python
# Utiliser select_related et prefetch_related
projects = Project.objects.filter(
    memberships__user=user
).select_related('owner').prefetch_related('memberships__user')

# Cache des permissions
from django.core.cache import cache

def get_user_permissions(user, project):
    cache_key = f"perms_{user.id}_{project.id}"
    perms = cache.get(cache_key)
    if not perms:
        perms = calculate_permissions(user, project)
        cache.set(cache_key, perms, 300)  # 5 minutes
    return perms
```

## 🔄 Rollback Plan

En cas de problème après déploiement:

1. **Rollback rapide des migrations**
```bash
python backend/manage.py migrate zane_api 0xxx_previous_migration
```

2. **Restauration des permissions originales**
```python
# Script de rollback
def restore_original_permissions():
    Project.objects.update(owner=F('memberships__user'))
    ProjectMembership.objects.all().delete()
```

3. **Désactivation du système RBAC**
```python
# settings.py
RBAC_ENABLED = False  # Feature flag
```

---

## 📞 Points de Discussion avec FredKiss

### Questions Techniques
1. Préférence pour la structure des permissions (matrice vs décorateurs) ?
2. Stratégie de cache pour les permissions ?
3. Gestion des sessions vs tokens pour l'API ?
4. Format préféré pour les tokens (JWT vs random) ?

### Décisions d'Architecture
1. Séparer les modèles RBAC dans une app Django dédiée ?
2. Utiliser Django Guardian pour les permissions objet ?
3. Middleware custom pour l'injection des permissions ?
4. GraphQL ou REST pour les nouveaux endpoints ?

### Priorités d'Implémentation
1. Commencer par quelle phase ?
2. MVP avec quelles fonctionnalités minimum ?
3. Tests: coverage minimum acceptable ?
4. Documentation: format préféré ?

---

*Document préparé pour @FredKiss - Issue #498*
*Date: 2024*
*Status: Ready for implementation review*