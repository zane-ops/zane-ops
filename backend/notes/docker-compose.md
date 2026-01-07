# Docker Compose Stack Support - Backend Implementation Plan

## Overview

Implement backend support for deploying docker-compose stacks in ZaneOps. Stacks are file-based configurations managed by Docker Swarm with minimal ZaneOps intervention. Docker Swarm handles rolling updates, service orchestration, and production promotion automatically.


## Key Design Principles

1. **Minimal Control** - Docker Swarm handles orchestration, rolling updates, and production promotion
2. **File-Based** - ComposeStack represents a compose file, NOT a container/service
3. **No Manual Promotion** - Docker Swarm automatically updates services when `docker stack deploy` is run
4. **Resource Cleanup on Stack Deletion** - Volumes and configs deleted when stack is removed, not between deployments
5. **Label-Based URL Configuration** - Users configure routing via Docker labels in compose file
6. **Per-Service Status** - Each service in stack has individual health status
7. **Direct Editing** - Users can PATCH compose content; changes applied on next deployment

## Critical Insights from Exploration

### Docker Swarm Behavior
- **Rolling updates are automatic** - When you run `docker stack deploy` with updated compose, Swarm handles the rollout
- **No manual blue-green needed** - Swarm manages task creation/removal based on `update_config` in compose
- **Volumes/configs persist** - Docker Swarm does NOT auto-cleanup unused volumes or configs
- **Cleanup strategy**: Delete volumes/configs only when stack is deleted, not between deployments

### DNS Name Collision Prevention ⚠️
- **Problem**: Docker Swarm creates service names as `{stack_name}_{service_name}` for swarm management, BUT DNS aliases within networks use the original service names from the compose file
- **Impact**: Multiple stacks with `app` service will collide on DNS resolution within the shared `zane` network
- **Solution**: Hash service and volume names with stack ID prefix (e.g., `app` → `abc123_app`) to ensure unique DNS names
- **Implementation**: Applied in `ComposeSpecProcessor.process_compose_spec()` and reconciled in `generate_deployable_yaml()`

### URL Configuration via Caddy
- Uses Caddy Admin API (`http://zane.proxy:2019`) for dynamic route management
- Routes configured via HTTP/REST with JSON payloads
- Current services use `URL` model with `domain`, `base_path`, `strip_prefix`, `associated_port`
- For compose stacks: Users configure routing via **Docker labels** in their compose file

## Data Models

### 1. ComposeStack

**File**: `backend/zane_api/models/main.py`

```python
class ComposeStack(TimestampedModel):
    """Represents a docker-compose stack (file-based, NOT container-based)"""

    # Managers
    deployments: Manager["ComposeStackDeployment"]
    changes: Manager["ComposeStackChange"]
    env_overrides: Manager["ComposeStackEnvOverride"]
    urls: Manager[URL]  # M2M for stack-level URLs (optional)

    # Fields
    ID_PREFIX = "srv_cmp_"
    id = ShortUUIDField(length=11, max_length=255, primary_key=True, prefix=ID_PREFIX)
    slug = models.SlugField(max_length=38)
    project = models.ForeignKey(Project, on_delete=models.CASCADE, related_name="compose_stacks")
    environment = models.ForeignKey(Environment, on_delete=models.CASCADE, related_name="compose_stacks")
    deploy_token = models.CharField(max_length=35, null=True, unique=True)

    # Compose content
    user_compose_content = models.TextField(help_text="Original YAML from user")
    computed_compose_spec = models.JSONField(help_text="Processed spec as JSON")

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["slug", "project", "environment"],
                name="unique_compose_stack_per_env_and_project",
            ),
        ]
```

**Key points**:
- NOT inherited from BaseService - no `resource_limits`, `healthcheck`, `network_alias`, `ports`, `configs`
- Two representations: `user_compose_content` (YAML text) and `computed_compose_spec` (JSON for querying)
- `urls` field is optional - users primarily configure routing via Docker labels

### 2. ComposeStackDeployment

```python
class ComposeStackDeployment(TimestampedModel):
    """Tracks deployments of compose stacks"""

    HASH_PREFIX = "dpl_cmp_"
    hash = ShortUUIDField(length=11, max_length=255, primary_key=True, prefix=HASH_PREFIX)
    stack = models.ForeignKey(ComposeStack, on_delete=models.CASCADE, related_name="deployments")

    class DeploymentStatus(models.TextChoices):
        QUEUED = "QUEUED"
        CANCELLED = "CANCELLED"
        FAILED = "FAILED"
        DEPLOYING = "DEPLOYING"
        HEALTHY = "HEALTHY"
        UNHEALTHY = "UNHEALTHY"
        REMOVED = "REMOVED"

    status = models.CharField(max_length=10, choices=DeploymentStatus.choices, default=DeploymentStatus.QUEUED)
    status_reason = models.TextField(null=True, blank=True)

    # Per-service status (JSON)
    service_statuses = models.JSONField(default=dict)
    # Example:
    # {
    #     "web": {
    #         "status": "running",
    #         "desired_replicas": 2,
    #         "running_replicas": 2,
    #         "updated_at": "2025-12-26T10:30:00Z"
    #     },
    #     "db": {...}
    # }

    # Snapshot and metadata
    stack_snapshot = models.JSONField(null=True)
    commit_message = models.TextField(default="update stack")

    # Timing
    queued_at = models.DateTimeField(auto_now_add=True)
    started_at = models.DateTimeField(null=True)
    finished_at = models.DateTimeField(null=True)

    @property
    def workflow_id(self):
        return f"deploy-compose-{self.stack.id}-{self.hash}"
```

**Key changes from original plan**:
- **Removed `is_current_production`** - Docker Swarm handles this automatically
- **Removed `slot` field** - No manual blue-green deployment needed
- Simpler status choices - no PREPARING, BUILDING, STARTING (Docker Swarm handles these)

### 3. ComposeStackEnvOverride

```python
class ComposeStackEnvOverride(BaseEnvVariable):
    """
    Environment variable overrides at stack level.

    Stores both:
    - User-defined overrides (set via UI)
    - Auto-generated values from template expressions ({{ generate_* }})
    """

    ID_PREFIX = "env_cmp_"
    id = ShortUUIDField(length=11, max_length=255, primary_key=True, prefix=ID_PREFIX)
    stack = models.ForeignKey(ComposeStack, on_delete=models.CASCADE, related_name="env_overrides")

    # Service name this override applies to (e.g., "db", "web")
    # NULL means stack-level override (applies to all services)
    service_name = models.CharField(max_length=255, null=True)

    # Whether this was auto-generated from a template expression
    is_generated = models.BooleanField(default=False)

    class Meta:
        unique_together = ["stack", "service_name", "key"]
```

### 4. ComposeStackChange

```python
class ComposeStackChange(TimestampedModel):
    """Tracks unapplied changes to compose stacks"""

    ID_PREFIX = "chg_cmp_"
    id = ShortUUIDField(length=11, max_length=255, primary_key=True, prefix=ID_PREFIX)

    class ChangeField(models.TextChoices):
        COMPOSE_CONTENT = "compose_content"
        ENV_OVERRIDES = "env_overrides"
        URLS = "urls"  # Optional stack-level URLs

    class ChangeType(models.TextChoices):
        ADD = "ADD"
        UPDATE = "UPDATE"
        DELETE = "DELETE"

    stack = models.ForeignKey(ComposeStack, on_delete=models.CASCADE, related_name="changes")
    deployment = models.ForeignKey(ComposeStackDeployment, on_delete=models.CASCADE, null=True)
    field = models.CharField(max_length=255, choices=ChangeField.choices)
    type = models.CharField(max_length=10, choices=ChangeType.choices)
    item_id = models.CharField(max_length=255, null=True)
    old_value = models.JSONField(null=True)
    new_value = models.JSONField(null=True)
    applied = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
```

## Dataclasses (DTOs)

**File**: `backend/compose/dtos.py`

```python
@dataclass
class ComposeEnvVarSpec:
    key: str
    value: str

    def to_dict(self) -> Dict[str, Any]:
        return {self.key: self.value}

@dataclass
class ComposeVolumeSpec:
    """Volume in compose file"""
    name: str
    driver: str = "local"
    driver_opts: Dict[str, str] = field(default_factory=dict)
    external: bool = False
    labels: Dict[str, str] = field(default_factory=dict)

@dataclass
class ComposeServiceSpec:
    """
    Service in compose file.
    We only include values that we want to override,
    the rest will be reconciled from the original compose content.
    """
    name: str
    image: str
    environment: Dict[str, ComposeEnvVarSpec] = field(default_factory=dict)
    networks: Dict[str, Any] = field(default_factory=dict)
    deploy: Dict[str, Any] = field(default_factory=dict)
    logging: Optional[Dict[str, Any]] = None
    labels: Dict[str, str] = field(default_factory=dict)

@dataclass
class ComposeStackSpec:
    """
    Simple compose specification.
    We only include values that we want to override,
    the rest will be reconciled from the original compose content.
    """
    services: Dict[str, ComposeServiceSpec] = field(default_factory=dict)
    volumes: Dict[str, ComposeVolumeSpec] = field(default_factory=dict)
    networks: Dict[str, Any] = field(default_factory=dict)
```

## Compose File Processing

**File**: `backend/compose/procressor.py`

### Service and Volume Name Hashing

**IMPORTANT**: While Docker Swarm prefixes service names with the stack name for the swarm service itself (e.g., `zane-stack-id_app`), the DNS aliases within Docker networks use the original service names from the compose file. This causes collisions when multiple stacks share the `zane` network.

**Solution**: We hash service and volume names with the stack ID to ensure unique DNS names:
- Original service: `app`
- Hashed service: `abc123_app` (where `abc123` is derived from the stack ID)
- DNS resolution in the `zane` network: `abc123_app` instead of `app`

This prevents collisions where `curl http://app` from any service in the `zane` network would route to a random `app` service instead of the intended one.

### Template Expression Support

Users can use template expressions in environment variables for auto-generated values:

```yaml
services:
  db:
    image: postgres:16
    environment:
      POSTGRES_USER: {{ generate_user }}              # Random username slug
      POSTGRES_PASSWORD: {{ generate_secure_password }} # 64-char hex token
      POSTGRES_DB: {{ generate_random_slug }}          # Random database name
      API_TOKEN: {{ generate_random_chars_32 }}        # 32 alphanumeric chars
      SECRET_KEY: {{ generate_random_chars_64 }}       # 64 alphanumeric chars
```

**Template Functions**:
- `{{ generate_user }}` - Generates slug like "quiet_forest_42" (valid username)
- `{{ generate_secure_password }}` - Generates 64-char hex via `secrets.token_hex(32)`
- `{{ generate_random_slug }}` - Generates slug like "happy_tree_91"
- `{{ generate_random_chars_32 }}` - Generates 32 random alphanumeric chars
- `{{ generate_random_chars_64 }}` - Generates 64 random alphanumeric chars

**How Generated Values Work**:
1. **First encounter**: Template expression found → generate random value → save as `ComposeStackEnvOverride` with `is_generated=True`
2. **Subsequent deployments**: Override exists → use saved value (no regeneration)
3. **User regenerates**: Delete generated overrides with `is_generated=True` → new values generated and saved
4. **Rollback**: No special handling needed - overrides are versioned with deployments via change tracking

```python
import yaml
import re
import secrets
import random
from typing import Dict, List, Any, Optional
from django.core.exceptions import ValidationError


class ComposeProcessor:
    """
    Processes user compose files into ZaneOps-compatible deployable compose files.

    Pipeline:
    1. User YAML → Parse to dict
    2. Validate structure and constraints
    3. Process template expressions ({{ generate_* }})
    4. Inject ZaneOps configuration (networks, labels, env vars)
    5. Convert to ComposeStackSpec dataclass → JSON (for storage)
    6. Convert back to YAML (for deployment)
    """

    # Template expression regex
    TEMPLATE_PATTERN = re.compile(r'\{\{\s*(\w+)\s*\}\}')

    @staticmethod
    def parse_user_yaml(content: str) -> Dict[str, Any]:
        """
        Parse user YAML to dict.

        Raises:
            ValidationError: If YAML is invalid
        """
        try:
            parsed = yaml.safe_load(content)
            if parsed is None:
                raise ValidationError("Empty compose file")
            if not isinstance(parsed, dict):
                raise ValidationError("Compose file must be a YAML object/dictionary")
            return parsed
        except yaml.YAMLError as e:
            raise ValidationError(f"Invalid YAML syntax: {str(e)}")

    @staticmethod
    def validate_compose_spec(spec_dict: Dict[str, Any]) -> List[str]:
        """
        Validate compose file structure and ZaneOps constraints.

        Returns:
            List of validation error messages (empty if valid)
        """
        errors = []

        # Note: Version field is ignored (Docker Swarm handles compatibility)

        # Check services section
        services = spec_dict.get("services")
        if not services:
            errors.append("No services defined in compose file")
        elif not isinstance(services, dict):
            errors.append("'services' must be a dictionary")
        else:
            # Validate each service
            for service_name, service_config in services.items():
                # Validate service name (slug-safe for Docker)
                if not re.match(r'^[a-z0-9][a-z0-9_-]*$', service_name):
                    errors.append(
                        f"Invalid service name '{service_name}'. "
                        "Must start with a letter/digit and contain only lowercase letters, digits, hyphens, and underscores."
                    )

                if not isinstance(service_config, dict):
                    errors.append(f"Service '{service_name}' configuration must be a dictionary")
                    continue

                # Check that service has image (no build support for stacks)
                if "build" in service_config:
                    errors.append(
                        f"Service '{service_name}' has 'build' context. "
                        "Compose stacks don't support building images - use pre-built images only."
                    )

                if "image" not in service_config and "build" not in service_config:
                    errors.append(f"Service '{service_name}' must specify an 'image'")

                # Validate environment variables format
                env = service_config.get("environment")
                if env is not None:
                    if isinstance(env, list):
                        for env_var in env:
                            if not isinstance(env_var, str):
                                errors.append(
                                    f"Service '{service_name}': environment variables must be strings"
                                )
                    elif not isinstance(env, dict):
                        errors.append(
                            f"Service '{service_name}': 'environment' must be a list or dictionary"
                        )

                # Validate ports
                ports = service_config.get("ports")
                if ports is not None:
                    if not isinstance(ports, list):
                        errors.append(f"Service '{service_name}': 'ports' must be a list")

                # Validate volumes
                volumes = service_config.get("volumes")
                if volumes is not None:
                    if not isinstance(volumes, list):
                        errors.append(f"Service '{service_name}': 'volumes' must be a list")

                # Validate networks
                networks = service_config.get("networks")
                if networks is not None:
                    if not isinstance(networks, (list, dict)):
                        errors.append(f"Service '{service_name}': 'networks' must be a list or dictionary")

        # Validate volumes section (if present)
        volumes = spec_dict.get("volumes")
        if volumes is not None:
            if not isinstance(volumes, dict):
                errors.append("'volumes' must be a dictionary")
            else:
                for volume_name in volumes.keys():
                    if not re.match(r'^[a-z0-9][a-z0-9_-]*$', volume_name):
                        errors.append(
                            f"Invalid volume name '{volume_name}'. "
                            "Must start with a letter/digit and contain only lowercase letters, digits, hyphens, and underscores."
                        )

        # Validate networks section (if present)
        networks = spec_dict.get("networks")
        if networks is not None:
            if not isinstance(networks, dict):
                errors.append("'networks' must be a dictionary")

        # Check for secrets (not supported in simplified implementation)
        if "secrets" in spec_dict:
            errors.append(
                "Docker secrets are not supported yet. "
                "Use environment variables or configs for sensitive data."
            )

        return errors

    @staticmethod
    def generate_template_value(template_func: str) -> str:
        """
        Generate a random value for a template function.

        Args:
            template_func: Template function name (e.g., "generate_user")

        Returns:
            Generated random value
        """
        import secrets
        from zane_api.utils import random_word, generate_random_chars

        if template_func == "generate_user":
            # Generate slug like "quiet_forest_42"
            adjective = random_word(6)
            noun = random_word(6)
            number = random.randint(10, 99)
            return f"{adjective}_{noun}_{number}"

        elif template_func == "generate_secure_password":
            # Cryptographically secure 64-char hex token
            return secrets.token_hex(32)

        elif template_func == "generate_random_slug":
            # Generate slug like "happy_tree_91"
            adjective = random_word(6)
            noun = random_word(5)
            number = random.randint(10, 99)
            return f"{adjective}_{noun}_{number}"

        elif template_func == "generate_random_chars_32":
            # Generate 32 random alphanumeric chars
            return generate_random_chars(32)

        elif template_func == "generate_random_chars_64":
            # Generate 64 random alphanumeric chars
            return generate_random_chars(64)

        else:
            raise ValueError(f"Unknown template function: {template_func}")

    @staticmethod
    def extract_template_expressions(env_value: str) -> List[str]:
        """
        Extract template function names from environment variable value.

        Args:
            env_value: Environment variable value (may contain template expressions)

        Returns:
            List of template function names found (e.g., ["generate_user", "generate_secure_password"])
        """
        matches = ComposeProcessor.TEMPLATE_PATTERN.findall(env_value)
        return matches

    @staticmethod
    def validate_url_conflicts(
        service_urls: Dict[str, List[Dict[str, Any]]],
        stack_id: str,
        project_id: str,
        environment_id: str
    ) -> List[str]:
        """
        Validate that URLs from compose stack labels don't conflict with existing ZaneOps services.

        Args:
            service_urls: Dict mapping service names to list of route configs (from extract_service_urls)
            stack_id: ComposeStack ID (to exclude from conflict check)
            project_id: Project ID
            environment_id: Environment ID

        Returns:
            List of validation error messages (empty if no conflicts)
        """
        from zane_api.models import URL

        errors = []

        for service_name, routes in service_urls.items():
            for route in routes:
                domain = route["domain"]
                base_path = route.get("base_path", "/")

                # Check if URL already exists in ZaneOps
                existing_url = URL.objects.filter(
                    domain=domain,
                    base_path=base_path
                ).exclude(
                    # Exclude URLs from the same stack (allow updates)
                    compose_stacks__id=stack_id
                ).first()

                if existing_url:
                    # Determine what resource owns this URL
                    if hasattr(existing_url, 'service') and existing_url.service:
                        resource = f"service '{existing_url.service.slug}'"
                    elif hasattr(existing_url, 'compose_stacks') and existing_url.compose_stacks.exists():
                        stack = existing_url.compose_stacks.first()
                        resource = f"compose stack '{stack.slug}'"
                    else:
                        resource = "another resource"

                    errors.append(
                        f"Service '{service_name}': URL {domain}{base_path} is already used by {resource}"
                    )

        return errors

    @staticmethod
    def process_compose_spec(
        user_content: str,
        stack_id: str,
        stack_name: str,
        env_id: str,
        project_id: str,
    ) -> ComposeStackSpec:
        """
        Process user compose file into ZaneOps-compatible spec.

        Steps:
        1. Parse YAML
        2. Validate structure
        3. Hash service and volume names to prevent DNS collisions
        4. Inject zane and environment networks
        5. Add ZaneOps tracking labels
        6. Add logging configuration (Fluentd)
        7. Add safe update_config for rolling updates
        8. Inject default ZANE environment variable
        9. Return ComposeStackSpec

        Args:
            user_content: Raw YAML compose file from user
            stack_id: ComposeStack ID (e.g., "compose_stk_abc123")
            stack_name: Stack name for logging tags
            env_id: Environment ID
            project_id: Project ID

        Returns:
            ComposeStackSpec dataclass with hashed service/volume names

        Raises:
            ValidationError: If compose file is invalid
        """
        # Parse YAML
        spec_dict = ComposeSpecProcessor._parse_user_yaml(user_content)

        # Convert to dataclass
        spec = ComposeStackSpec.from_dict(spec_dict)

        # Extract stack hash from ID (e.g., "compose_stk_abc123" -> "abc123")
        stack_hash = stack_id.replace(ComposeStack.ID_PREFIX, "").lower()

        # CRITICAL: Rename services to prevent DNS collisions in shared `zane` network
        # Original: app -> Hashed: abc123_app
        renamed_services = {}
        for original_name, service in spec.services.items():
            hashed_name = f"{stack_hash}_{original_name}"
            service.name = hashed_name
            renamed_services[hashed_name] = service
        spec.services = renamed_services

        # TODO: Rename volumes similarly (commented out for now)
        # renamed_volumes = {}
        # for original_name, volume in spec.volumes.items():
        #     hashed_name = f"{stack_hash}_{original_name}"
        #     volume.name = hashed_name
        #     renamed_volumes[hashed_name] = volume
        # spec.volumes = renamed_volumes

        # Validate
        errors = ComposeProcessor.validate_compose_spec(spec_dict)
        if errors:
            raise ValidationError(errors)

        # Convert to dataclass (no hashing needed - Docker Swarm handles namespacing)
        spec = ComposeStackSpec.from_dict(spec_dict, stack_id, env_id)

        # Get zane network name
        zane_network_name = get_env_network_resource_name(env_id, project_id)

        # Inject zane network to networks section
        if "zane" not in spec.networks:
            spec.networks["zane"] = {
                "external": True,
                "name": zane_network_name,
            }

        # Process each service
        for service_name, service in spec.services.items():
            # 1. Add zane network
            if isinstance(service.networks, list):
                if "zane" not in service.networks:
                    service.networks.append("zane")
            elif isinstance(service.networks, dict):
                if "zane" not in service.networks:
                    service.networks["zane"] = None
            else:
                # No networks specified - add zane
                service.networks = ["zane"]

            # 2. Inject safe update_config for rolling updates
            if not service.deploy:
                service.deploy = {}

            if "update_config" not in service.deploy:
                service.deploy["update_config"] = {
                    "parallelism": 1,
                    "delay": "5s",
                    "order": "start-first",
                    "failure_action": "rollback"
                }

            # 3. Merge environment variable overrides
            env_dict = {}

            # First, add env vars from compose file
            if isinstance(service.environment, list):
                for env_var in service.environment:
                    if isinstance(env_var, str):
                        if "=" in env_var:
                            key, value = env_var.split("=", 1)
                            env_dict[key] = value
                        else:
                            # Variable without value - keep as-is
                            env_dict[env_var] = ""
            elif isinstance(service.environment, dict):
                env_dict.update(service.environment)

            # Then, apply service-specific overrides (includes generated values)
            service_overrides = env_overrides.get(service_name, {})
            env_dict.update(service_overrides)

            # Apply stack-level overrides (overrides for all services)
            stack_level_overrides = env_overrides.get(None, {})
            env_dict.update(stack_level_overrides)

            # Convert back to dict format (Docker Swarm prefers dict over list)
            service.environment = env_dict

            # 4. Add ZaneOps tracking labels
            if not isinstance(service.labels, dict):
                service.labels = {}

            service.labels.update({
                "zane-managed": "true",
                "zane-stack": stack_id,
                "zane-project": project_id,
                "zane-environment": env_id,
                "zane-service": service_name,
            })

            # 5. Add logging configuration (for Fluentd log collection)
            fluentd_address = os.getenv("FLUENTD_ADDRESS", "zane.fluentd:24224")
            service.logging = {
                "driver": "fluentd",
                "options": {
                    "fluentd-address": fluentd_address,
                    "tag": f"zane.stack.{stack_id}.{service_name}",
                    "fluentd-async": "true",  # Non-blocking logging
                },
            }

            # 6. Set restart policy to "any" (unless user explicitly specified one)
            if not service.restart_policy:
                service.restart_policy = "any"

        # Add labels to volumes for tracking
        if spec.volumes:
            for volume_name, volume_spec in spec.volumes.items():
                if not isinstance(volume_spec, dict):
                    spec.volumes[volume_name] = {}

                if "labels" not in spec.volumes[volume_name]:
                    spec.volumes[volume_name]["labels"] = {}

                spec.volumes[volume_name]["labels"].update({
                    "zane-managed": "true",
                    "zane-stack": stack_id,
                    "zane-project": project_id,
                    "zane-volume": volume_name,
                })

        return spec

    @staticmethod
    def generate_deployable_yaml(
        spec: ComposeStackSpec,
        user_content: str,
        stack_id: str,
    ) -> str:
        """
        Convert ComposeStackSpec back to YAML for docker stack deploy,
        reconciling hashed names with original user content.

        Args:
            spec: ComposeStackSpec dataclass (with hashed service/volume names)
            user_content: Original YAML from user (with original names)
            stack_id: Stack ID for extracting hash (e.g., "compose_stk_abc123")

        Returns:
            YAML string ready for deployment with hashed names

        Process:
        1. Extract stack hash from stack_id
        2. Parse user's original YAML
        3. Map original service names to hashed names
        4. Reconcile user fields (volumes, depends_on, etc.) with computed config
        5. Generate final YAML with hashed names
        """
        # Extract hash
        stack_hash = stack_id.replace(ComposeStack.ID_PREFIX, "").lower()

        # Parse user's original YAML
        user_spec_dict = ComposeSpecProcessor._parse_user_yaml(user_content)

        # Get computed config (has hashed names)
        compose_dict = spec.to_dict()

        # Reconcile services with hashed names
        # User dict: {"app": {...}} -> Computed dict: {"abc123_app": {...}}
        reconciled_services = {}
        for original_name, user_service in user_spec_dict.get("services", {}).items():
            hashed_name = f"{stack_hash}_{original_name}"
            computed_service = compose_dict["services"].get(hashed_name, {})

            # Copy user-specified fields we didn't process (volumes, depends_on, etc.)
            for key, value in user_service.items():
                if computed_service.get(key) is None:
                    computed_service[key] = value

            reconciled_services[hashed_name] = computed_service

        compose_dict["services"] = reconciled_services

        # TODO: Reconcile volumes with hashed names similarly

        # Generate YAML with nice formatting
        return yaml.safe_dump(
            compose_dict,
            default_flow_style=False,
            sort_keys=False,  # Preserve order
            allow_unicode=True,
        )

    @staticmethod
    def extract_service_urls(spec: ComposeStackSpec) -> Dict[str, List[Dict[str, Any]]]:
        """
        Extract URL routing configuration from service labels.

        Parses labels like:
        - zane.http.port: "80"
        - zane.http.routes.0.domain: "example.com"
        - zane.http.routes.0.base_path: "/"
        - zane.http.routes.0.strip_prefix: "false"

        Returns:
            Dict mapping service names to list of route configs:
            {
                "web": [
                    {
                        "domain": "example.com",
                        "base_path": "/",
                        "strip_prefix": False,
                        "port": 80,
                    }
                ]
            }
        """
        service_urls = {}

        for service_name, service in spec.services.items():
            if not service.deploy or not service.deploy.get("labels"):
                continue

            labels = service.deploy["labels"]

            # Get HTTP port
            http_port = labels.get("zane.http.port")
            if not http_port:
                continue

            try:
                http_port = int(http_port)
            except ValueError:
                continue

            # Extract routes
            routes = []
            route_index = 0

            while True:
                domain = labels.get(f"zane.http.routes.{route_index}.domain")
                if not domain:
                    break  # No more routes

                route = {
                    "domain": domain,
                    "base_path": labels.get(
                        f"zane.http.routes.{route_index}.base_path", "/"
                    ),
                    "strip_prefix": labels.get(
                        f"zane.http.routes.{route_index}.strip_prefix", "true"
                    ).lower() == "true",
                    "port": http_port,
                }

                routes.append(route)
                route_index += 1

            if routes:
                service_urls[service_name] = routes

        return service_urls
```

**Key points**:
- **No custom hashing** - Docker Swarm uses stack name (`zane-{stack_id}`) for namespacing
- **Version field ignored** - Docker Swarm handles compatibility, no validation needed
- **Comprehensive validation** - Checks services, resource names, build contexts
- **URL conflict checking** - Validates URLs don't conflict with existing ZaneOps services
- **Label extraction** - Parses `zane.*` labels for URL configuration
- **Environment merging** - Overrides from database take precedence over compose file
- **Logging injection** - All services get Fluentd logging for centralized log collection
- **Safe update_config injection** - Always uses start-first strategy with rollback on failure

**Usage in API views**:
```python
# In views/compose_stacks.py - when creating or updating a stack

def deploy_compose_stack(request, project_slug, env_slug, stack_slug):
    # 1. Parse compose file to find template expressions
    spec_dict = ComposeProcessor.parse_user_yaml(stack.user_compose_content)
    errors = ComposeProcessor.validate_compose_spec(spec_dict)
    if errors:
        return Response({"errors": errors}, status=400)

    # 2. Handle template expression generation
    regenerate_values = request.data.get('regenerate_values', False)

    if regenerate_values:
        # Delete all auto-generated overrides
        stack.env_overrides.filter(is_generated=True).delete()

    # Find all template expressions in the compose file
    for service_name, service_config in spec_dict.get('services', {}).items():
        env_vars = service_config.get('environment', {})
        if isinstance(env_vars, list):
            env_vars = {k: v for item in env_vars for k, v in [item.split('=', 1)] if '=' in item}

        for key, value in env_vars.items():
            if not isinstance(value, str):
                continue

            # Extract template expressions
            template_funcs = ComposeProcessor.extract_template_expressions(value)

            for template_func in template_funcs:
                # Check if override already exists (skip if it does)
                existing = stack.env_overrides.filter(
                    service_name=service_name,
                    key=key
                ).first()

                if not existing:
                    # Generate value and save as override
                    generated_value = ComposeProcessor.generate_template_value(template_func)
                    stack.env_overrides.create(
                        key=key,
                        value=generated_value,
                        service_name=service_name,
                        is_generated=True
                    )

    # 3. Build env_overrides dict grouped by service
    env_overrides = {}
    for override in stack.env_overrides.all():
        service_key = override.service_name  # None for stack-level
        if service_key not in env_overrides:
            env_overrides[service_key] = {}
        env_overrides[service_key][override.key] = override.value

    # 4. Process compose spec (inject ZaneOps config)
    spec = ComposeProcessor.process_compose_spec(
        user_content=stack.user_compose_content,
        stack_id=stack.id,
        env_id=environment.id,
        project_id=project.id,
        env_overrides=env_overrides
    )

    # 5. Extract and validate URLs
    service_urls = ComposeProcessor.extract_service_urls(spec)
    url_errors = ComposeProcessor.validate_url_conflicts(
        service_urls=service_urls,
        stack_id=stack.id,
        project_id=project.id,
        environment_id=environment.id
    )
    if url_errors:
        return Response({"errors": url_errors}, status=400)

    # 6. Create deployment
    deployment = ComposeStackDeployment.objects.create(
        stack=stack,
        stack_snapshot=spec.to_dict()
    )

    # 7. Trigger workflow
    # ... start temporal workflow
```

**Template Expression Workflow**:

1. **First Deployment**:
   - User creates stack with `POSTGRES_PASSWORD: {{ generate_secure_password }}`
   - Parse compose file, find template expression
   - Check if `ComposeStackEnvOverride` exists for `db.POSTGRES_PASSWORD` → doesn't exist
   - Generate random value via `ComposeProcessor.generate_template_value("generate_secure_password")`
   - Save as `ComposeStackEnvOverride(service_name="db", key="POSTGRES_PASSWORD", value="<generated>", is_generated=True)`
   - Use this override value in deployment

2. **Subsequent Deployments**:
   - Parse compose file, find template expression
   - Check if override exists → it does!
   - Use existing override value (no generation needed)
   - Same password used in deployment

3. **User Edits Compose File** (changes `POSTGRES_PASSWORD` to `POSTGRES_PASS`):
   - Parse compose file, find template at new key `POSTGRES_PASS`
   - Check if override exists for `db.POSTGRES_PASS` → doesn't exist
   - Generate new value and save
   - Old override for `POSTGRES_PASSWORD` remains (user can delete manually)

4. **Regenerate Values**:
   - User checks "Regenerate values" checkbox
   - Delete all overrides with `is_generated=True`
   - Find template expressions again
   - Generate and save new values
   - New random values used in deployment

## Temporal Workflow

**File**: `backend/temporal/workflows/compose_stacks.py` (new)

```python
@workflow.defn(name="deploy-compose-stack-workflow")
class DeployComposeStackWorkflow:
    """
    Simplified workflow - Docker Swarm handles most orchestration.
    No manual blue-green or production promotion needed.
    """

    @workflow.run
    async def run(self, deployment: ComposeStackDeploymentDetails) -> DeploymentResult:
        # Step 1: Set status to DEPLOYING
        await workflow.execute_activity_method(
            ComposeStackActivities.prepare_deployment,
            deployment,
            start_to_close_timeout=timedelta(seconds=5),
        )

        # Step 2: Generate deployable YAML
        compose_yaml = await workflow.execute_activity_method(
            ComposeStackActivities.generate_compose_yaml,
            deployment,
            start_to_close_timeout=timedelta(seconds=30),
        )

        # Step 3: Deploy to Docker Swarm (docker stack deploy)
        await workflow.execute_activity_method(
            ComposeStackActivities.deploy_stack,
            deployment,
            compose_yaml,
            start_to_close_timeout=timedelta(minutes=10),
        )

        # Step 4: Monitor service health
        await workflow.execute_activity_method(
            ComposeStackActivities.monitor_stack_health,
            deployment,
            start_to_close_timeout=timedelta(minutes=5),
        )

        # Step 5: Mark as HEALTHY
        await workflow.execute_activity_method(
            ComposeStackActivities.finalize_deployment,
            deployment,
            start_to_close_timeout=timedelta(seconds=5),
        )

        return DeploymentResult(success=True, deployment_hash=deployment.hash)
```

**Key simplifications**:
- No "scale down previous deployment" step - Docker Swarm handles rolling updates
- No "promote to production" step - Swarm automatically routes to updated services
- No volume/config creation step - `docker stack deploy` handles this
- Finalize step only marks deployment as HEALTHY, no production flag updates

## Temporal Activities

**File**: `backend/temporal/activities/compose_activities.py` (new)

```python
class ComposeStackActivities:

    @activity.defn
    async def deploy_stack(
        self,
        deployment: ComposeStackDeploymentDetails,
        compose_yaml: str,
    ):
        """
        Deploy using docker stack deploy CLI.
        Docker Swarm automatically handles:
        - Rolling updates
        - Service creation/update
        - Volume and config creation
        - Task lifecycle management
        """
        import tempfile
        import subprocess

        with tempfile.NamedTemporaryFile(mode='w', suffix='.yml', delete=False) as f:
            f.write(compose_yaml)
            compose_file_path = f.name

        try:
            stack_name = f"zane-{deployment.stack_id}"

            result = subprocess.run(
                ["docker", "stack", "deploy", "-c", compose_file_path, "--with-registry-auth", stack_name],
                capture_output=True,
                text=True,
                timeout=300,
            )

            if result.returncode != 0:
                raise ApplicationError(f"Stack deployment failed: {result.stderr}")

        finally:
            os.unlink(compose_file_path)

    @activity.defn
    async def monitor_stack_health(self, deployment: ComposeStackDeploymentDetails):
        """
        Monitor individual service health.
        Poll docker stack services until all are running.
        """
        stack_name = f"zane-{deployment.stack_id}"
        max_wait = 300  # 5 minutes
        start_time = time.time()

        while time.time() - start_time < max_wait:
            activity.heartbeat()

            service_statuses = await self._get_stack_service_statuses(stack_name)

            # Update deployment
            dpl = await ComposeStackDeployment.objects.aget(hash=deployment.hash)
            dpl.service_statuses = service_statuses
            await dpl.asave()

            # Check if all healthy
            all_healthy = all(
                s["running_replicas"] >= s["desired_replicas"]
                for s in service_statuses.values()
            )

            if all_healthy:
                return

            await asyncio.sleep(5)

        raise ApplicationError("Services did not become healthy in time")

    async def _get_stack_service_statuses(self, stack_name: str) -> Dict[str, Dict]:
        """Query: docker stack services <stack_name> --format json"""
        result = subprocess.run(
            ["docker", "stack", "services", stack_name, "--format", "{{json .}}"],
            capture_output=True,
            text=True
        )

        service_statuses = {}
        for line in result.stdout.strip().split('\n'):
            if not line:
                continue

            svc = json.loads(line)
            service_name = svc["Name"].replace(f"{stack_name}_", "")
            replicas_str = svc.get("Replicas", "0/0")
            running, desired = map(int, replicas_str.split('/'))

            service_statuses[service_name] = {
                "status": "running" if running >= desired else "starting",
                "desired_replicas": desired,
                "running_replicas": running,
                "updated_at": timezone.now().isoformat(),
            }

        return service_statuses
```

## Resource Cleanup Strategy

**When to clean up volumes and configs**:

### Cleanup on Stack Deletion (Recommended)

When a stack is deleted via API:
1. Run `docker stack rm zane-{stack_id}` to remove all services
2. Wait for services to be fully removed
3. Query all volumes with label `zane-stack={stack_id}`
4. Query all configs with label `zane-stack={stack_id}`
5. Delete volumes and configs explicitly

**Implementation**:
```python
# In temporal/activities/compose_activities.py

@activity.defn
async def delete_stack_resources(self, stack_id: str):
    """
    Delete all volumes and configs associated with a stack.
    Called after stack removal.
    """
    client = get_docker_client()

    # Remove stack (services, networks, etc.)
    subprocess.run(["docker", "stack", "rm", f"zane-{stack_id}"], check=True)

    # Wait for services to be removed (they must be gone before volumes can be deleted)
    await self._wait_for_stack_removal(f"zane-{stack_id}")

    # Delete volumes
    volumes = client.volumes.list(filters={"label": f"zane-stack={stack_id}"})
    for volume in volumes:
        try:
            volume.remove(force=True)
        except docker.errors.APIError:
            pass

    # Delete configs
    configs = client.configs.list(filters={"label": f"zane-stack={stack_id}"})
    for config in configs:
        try:
            config.remove()
        except docker.errors.APIError:
            pass
```

## URL Configuration Examples

Users configure routing via **Docker labels** in their compose file:

### Example 1: Basic HTTP Service

```yaml
version: "3.8"

services:
  web:
    image: nginx:latest
    deploy:
      labels:
        # Enable HTTP exposure
        zane.http.port: "80"

        # Route configuration
        zane.http.routes.0.domain: "myapp.example.com"
        zane.http.routes.0.base_path: "/"
        zane.http.routes.0.strip_prefix: "false"

networks:
  zane:
    external: true
```

### Example 2: Multiple Routes for Same Service

```yaml
services:
  api:
    image: myapi:latest
    deploy:
      labels:
        zane.http.port: "3000"

        # Primary domain
        zane.http.routes.0.domain: "api.example.com"
        zane.http.routes.0.base_path: "/"
        zane.http.routes.0.strip_prefix: "false"

        # Secondary path on different domain
        zane.http.routes.1.domain: "example.com"
        zane.http.routes.1.base_path: "/api"
        zane.http.routes.1.strip_prefix: "true"
```


### Example 3: Multi-Service Stack (e.g., WordPress)

```yaml
version: "3.8"

services:
  wordpress:
    image: wordpress:latest
    environment:
      WORDPRESS_DB_HOST: db
      WORDPRESS_DB_USER: ${DB_USER}
      WORDPRESS_DB_PASSWORD: ${DB_PASSWORD}
    networks:
      - zane
    volumes:
      - wordpress_data:/var/www/html
    deploy:
      labels:
        zane.http.port: "80"
        zane.http.routes.0.domain: "myblog.example.com"
        zane.http.routes.0.base_path: "/"

  db:
    image: mysql:8
    environment:
      MYSQL_ROOT_PASSWORD: ${DB_ROOT_PASSWORD}
      MYSQL_DATABASE: wordpress
      MYSQL_USER: ${DB_USER}
      MYSQL_PASSWORD: ${DB_PASSWORD}
    networks:
      - zane
    volumes:
      - db_data:/var/lib/mysql
    # No zane.http.port - database not exposed to internet

volumes:
  wordpress_data:
  db_data:

networks:
  zane:
    external: true
```

**Note**: ZaneOps will:
1. Parse these labels during stack creation
2. Configure Caddy proxy via Admin API to route traffic
3. Only expose services with `zane.http.routes.port:=<number>` label

## Label Schema Reference

```
zane.http.port={port}                        # Service port
zane.http.routes.{N}.domain={domain}         # Route domain
zane.http.routes.{N}.base_path={path}        # Route base path (default: /)
zane.http.routes.{N}.strip_prefix={bool}     # Strip base_path (default: true)
```

## API Endpoints

**File**: `backend/zane_api/views/compose_stacks.py` (new)

```http
POST   /api/projects/{project_slug}/environments/{env_slug}/compose-stacks/
       Create new compose stack

GET    /api/projects/{project_slug}/environments/{env_slug}/compose-stacks/{stack_slug}/
       Get stack details

PATCH  /api/projects/{project_slug}/environments/{env_slug}/compose-stacks/{stack_slug}/
       Update compose content

DELETE /api/projects/{project_slug}/environments/{env_slug}/compose-stacks/{stack_slug}/
       Delete stack (triggers volume/config cleanup)

POST   /api/projects/{project_slug}/environments/{env_slug}/compose-stacks/{stack_slug}/deploy/
       Trigger deployment

GET    /api/projects/{project_slug}/environments/{env_slug}/compose-stacks/{stack_slug}/deployments/
       List deployments

GET    /api/projects/{project_slug}/environments/{env_slug}/compose-stacks/{stack_slug}/deployments/{hash}/
       Get deployment details (includes per-service statuses)

POST   /api/projects/{project_slug}/environments/{env_slug}/compose-stacks/{stack_slug}/env-overrides/
       Add environment override

PATCH  /api/projects/{project_slug}/environments/{env_slug}/compose-stacks/{stack_slug}/env-overrides/{id}/
       Update environment override

DELETE /api/projects/{project_slug}/environments/{env_slug}/compose-stacks/{stack_slug}/env-overrides/{id}/
       Delete environment override
```

## Implementation Sequence

1. **Data Models** (1-2 days)
   - Create 4 models + migrations
   - Add to Django admin

2. **Dataclasses & DTOs** (1 day)
   - ComposeStackSpec and related dataclasses
   - Volume hashing utility

3. **Compose Processor** (2 days)
   - YAML parsing and validation
   - Volume hashing, network injection, env merging
   - Label parsing for URL configuration

4. **Temporal Workflow & Activities** (2-3 days)
   - DeployComposeStackWorkflow (simplified)
   - ComposeStackActivities (deploy, monitor, cleanup)
   - Stack resource cleanup on deletion

5. **Caddy Integration** (2 days)
   - Parse Docker labels from deployed services
   - Configure Caddy routes via Admin API
   - Handle service discovery and health checks

6. **API Endpoints** (2-3 days)
   - CRUD for stacks
   - Deployment trigger
   - Status endpoints
   - Serializers

7. **Testing** (2-3 days)
   - Unit tests for processor
   - Integration tests for workflow
   - API endpoint tests

**Total estimate**: 12-16 days

## Critical Files

### New Files
- `backend/zane_api/compose_processor.py` - Compose processing
- `backend/temporal/workflows/compose_stacks.py` - Workflow
- `backend/temporal/activities/compose_activities.py` - Activities
- `backend/zane_api/views/compose_stacks.py` - API views

### Modified Files
- `backend/zane_api/models/main.py` - Add 4 models
- `backend/zane_api/dtos.py` - Add dataclasses
- `backend/zane_api/serializers.py` - Add serializers
- `backend/zane_api/urls.py` - Add routing
- `backend/temporal/helpers.py` - Add Caddy route generation for compose services

## Key Technical Points

1. **No manual production promotion** - Docker Swarm handles this via `docker stack deploy`
2. **Resource cleanup on deletion** - Not between deployments
3. **Label-based routing** - Users configure via Docker labels, ZaneOps parses and configures Caddy
4. **Volume name hashing** - Deterministic collision prevention
5. **Per-service status** - Tracked in `service_statuses` JSON field
6. **Simplified workflow** - Docker Swarm does the heavy lifting
7. **Template expressions for env vars** - Auto-generate values, stored as `ComposeStackEnvOverride`
   - `{{ generate_user }}`, `{{ generate_secure_password }}`, `{{ generate_random_slug }}`, etc.
   - Generated values saved to database with `is_generated=True`
   - Values persist across deployments unless user checks "Regenerate values"
   - Change tracking ensures rollback restores old override values automatically
