"""
This module contains the DeploymentService class, which encapsulates the logic for
setting up and triggering deployments.
"""
from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING, Any, List, Optional, Tuple, cast

from django.conf import settings
from django.db import transaction
from rest_framework.utils.serializer_helpers import ReturnDict


from zane_api.models import (
    Deployment,
    Service,
    DeploymentChange,
    DeploymentURL,
    Environment,
    Project, # Assuming Project might be needed for user context/permissions
)
from zane_api.serializers import ServiceSerializer # For service_snapshot
from temporal.client import TemporalClient
from temporal.shared import (
    DeploymentDetails as DeploymentDetailsDto, # Renaming to avoid clash
    CancelDeploymentSignalInput,
)
from temporal.workflows import DeployDockerServiceWorkflow, DeployGitServiceWorkflow
from zane_api.git_client import GitClient

if TYPE_CHECKING:
    from django.contrib.auth.models import User # For type hinting user

class DeploymentSetupError(Exception):
    """Custom exception for errors during deployment setup."""
    pass

class DeploymentService:
    """
    Service class to handle the setup and triggering of deployments.
    """

    def _get_service_for_deployment(
        self,
        project_slug: str,
        service_slug: str,
        env_slug: str,
        service_type: Service.ServiceType,
        user: User,
    ) -> Service:
        """Fetches and validates the service instance."""
        try:
            project = Project.objects.get(slug=project_slug.lower(), owner=user)
            environment = Environment.objects.get(name=env_slug.lower(), project=project)
            service = Service.objects.filter(
                slug=service_slug,
                project=project,
                environment=environment,
                type=service_type,
            ).select_related(
                "project", "healthcheck", "environment", "git_app", "git_app__github", "git_app__gitlab"
            ).prefetch_related(
                "volumes", "ports", "urls", "env_variables", "changes", "configs"
            ).get()
            return service
        except Project.DoesNotExist:
            raise DeploymentSetupError(f"Project with slug `{project_slug}` does not exist for user.")
        except Environment.DoesNotExist:
            raise DeploymentSetupError(f"Environment `{env_slug}` does not exist in project `{project_slug}`.")
        except Service.DoesNotExist:
            raise DeploymentSetupError(f"Service `{service_slug}` (type: {service_type}) does not exist in environment `{env_slug}` of project `{project_slug}`.")


    def _prepare_common_deployment_fields(
        self,
        service: Service,
        commit_message: Optional[str],
        trigger_method: Deployment.DeploymentTriggerMethod,
        is_redeploy_of: Optional[Deployment] = None,
        ignore_build_cache: bool = False,
    ) -> Deployment:
        """Handles common fields for a new Deployment instance."""
        new_deployment = Deployment(
            service=service,
            commit_message=commit_message,
            trigger_method=trigger_method,
            is_redeploy_of=is_redeploy_of,
            ignore_build_cache=ignore_build_cache,
        )
        service.apply_pending_changes(deployment=new_deployment)

        # Generate DeploymentURLs
        # Correctly query for ports that should have URLs generated
        # This typically means ports associated with a URL configuration that implies HTTP/S exposure
        # For simplicity, let's assume any URL config implies a need for DeploymentURL if port is set.
        # The original code filters for `associated_port__isnull=False` on `service.urls`.
        # This means a URL object must exist on the service with an associated port.

        # Get distinct ports from URL configurations that have an associated port
        url_ports = service.urls.filter(associated_port__isnull=False).values_list("associated_port", flat=True).distinct()
        for port_number in url_ports:
            DeploymentURL.generate_for_deployment(
                deployment=new_deployment,
                service=service,
                port=port_number, # Ensure port is an integer
            )

        latest_production_deployment = service.latest_production_deployment
        new_deployment.slot = Deployment.get_next_deployment_slot(latest_production_deployment)
        new_deployment.service_snapshot = ServiceSerializer(service).data # type: ignore
        # Note: new_deployment.save() will be called by the caller after any type-specific fields are set.
        return new_deployment

    def setup_docker_deployment(
        self,
        service: Service, # Service instance already fetched by the view
        request_data: ReturnDict, # Validated data from the request serializer
        trigger_method: Deployment.DeploymentTriggerMethod = Deployment.DeploymentTriggerMethod.MANUAL,
        webhook_new_image: Optional[str] = None, # For webhook-triggered image updates
        is_redeploy_of_hash: Optional[str] = None, # For redeploys
    ) -> Tuple[Deployment, List[Deployment]]:
        """
        Sets up a new Docker deployment, creating the Deployment instance
        and preparing it for the workflow trigger.
        """
        if service.type != Service.ServiceType.DOCKER_REGISTRY:
            raise DeploymentSetupError("Invalid service type for Docker deployment.")

        commit_message = request_data.get("commit_message") or "Update service"
        cleanup_queue = request_data.get("cleanup_queue", False)

        deployments_to_cancel: List[Deployment] = []
        if cleanup_queue:
            deployments_to_cancel = list(Deployment.flag_deployments_for_cancellation(
                service, include_running_deployments=True
            ))

        redeploy_target_deployment: Optional[Deployment] = None
        if is_redeploy_of_hash:
            try:
                redeploy_target_deployment = service.deployments.get(hash=is_redeploy_of_hash)
                commit_message = f"Redeploy of {is_redeploy_of_hash[:7]}" # Override commit message for redeploy
            except Deployment.DoesNotExist:
                raise DeploymentSetupError(f"Redeploy target deployment {is_redeploy_of_hash} not found.")


        if webhook_new_image: # Specific to webhook
            source_change = service.unapplied_changes.filter(
                field=DeploymentChange.ChangeField.SOURCE
            ).first()
            if source_change:
                source_change.new_value["image"] = webhook_new_image # type: ignore
                source_change.save()
            else:
                service.add_change(
                    DeploymentChange(
                        type=DeploymentChange.ChangeType.UPDATE,
                        field=DeploymentChange.ChangeField.SOURCE,
                        old_value={"image": service.image, "credentials": service.credentials},
                        new_value={"image": webhook_new_image, "credentials": service.credentials},
                        service=service,
                    )
                )

        new_deployment = self._prepare_common_deployment_fields(
            service=service,
            commit_message=commit_message,
            trigger_method=trigger_method,
            is_redeploy_of=redeploy_target_deployment,
        )
        # Docker-specific fields (if any before saving) could be set here.
        # For now, common fields cover it.
        new_deployment.save()
        return new_deployment, deployments_to_cancel


    def setup_git_deployment(
        self,
        service: Service, # Service instance already fetched by the view
        request_data: ReturnDict, # Validated data from the request serializer
        trigger_method: Deployment.DeploymentTriggerMethod = Deployment.DeploymentTriggerMethod.MANUAL,
        webhook_new_commit_sha: Optional[str] = None, # For webhook-triggered commit updates
        is_redeploy_of_hash: Optional[str] = None, # For redeploys
    ) -> Tuple[Deployment, List[Deployment]]:
        """
        Sets up a new Git repository deployment.
        """
        if service.type != Service.ServiceType.GIT_REPOSITORY:
            raise DeploymentSetupError("Invalid service type for Git deployment.")

        commit_message = "-" # Default for Git, often overridden by actual commit later
        ignore_build_cache = request_data.get("ignore_build_cache", False)
        cleanup_queue = request_data.get("cleanup_queue", False)

        deployments_to_cancel: List[Deployment] = []
        if cleanup_queue:
            deployments_to_cancel = list(Deployment.flag_deployments_for_cancellation(
                service, include_running_deployments=True
            ))

        redeploy_target_deployment: Optional[Deployment] = None
        if is_redeploy_of_hash:
            try:
                redeploy_target_deployment = service.deployments.get(hash=is_redeploy_of_hash)
                commit_message = redeploy_target_deployment.commit_message # Use original commit message
                # For redeploy, actual commit_sha will be from the redeploy_target_deployment
            except Deployment.DoesNotExist:
                raise DeploymentSetupError(f"Redeploy target deployment {is_redeploy_of_hash} not found.")

        if webhook_new_commit_sha: # Specific to webhook
            if webhook_new_commit_sha != service.commit_sha: # Only add change if different
                source_change = service.unapplied_changes.filter(
                    field=DeploymentChange.ChangeField.GIT_SOURCE
                ).first()
                new_source_value = {
                    "repository_url": service.repository_url,
                    "branch_name": service.branch_name,
                    "commit_sha": webhook_new_commit_sha,
                    # git_app details should be preserved or re-fetched if necessary
                    "git_app": ServiceSerializer(service).data.get("git_source", {}).get("git_app")
                }
                if source_change:
                    source_change.new_value["commit_sha"] = webhook_new_commit_sha # type: ignore
                    source_change.save()
                else:
                    service.add_change(
                        DeploymentChange(
                            type=DeploymentChange.ChangeType.UPDATE,
                            field=DeploymentChange.ChangeField.GIT_SOURCE,
                            old_value={
                                "repository_url": service.repository_url,
                                "branch_name": service.branch_name,
                                "commit_sha": service.commit_sha,
                                "git_app": ServiceSerializer(service).data.get("git_source", {}).get("git_app")
                            },
                            new_value=new_source_value,
                            service=service,
                        )
                    )


        new_deployment = self._prepare_common_deployment_fields(
            service=service,
            commit_message=commit_message,
            trigger_method=trigger_method,
            is_redeploy_of=redeploy_target_deployment,
            ignore_build_cache=ignore_build_cache,
        )

        # Determine actual commit SHA for the new deployment
        if redeploy_target_deployment:
            new_deployment.commit_sha = redeploy_target_deployment.commit_sha
        elif webhook_new_commit_sha:
            new_deployment.commit_sha = webhook_new_commit_sha
        else: # Standard deploy or manual trigger
            current_commit_sha_on_service = service.commit_sha
            if current_commit_sha_on_service == "HEAD":
                git_client = GitClient() # Consider making GitClient injectable or a member
                repo_url = cast(str, service.repository_url)
                if service.git_app:
                    if service.git_app.github:
                        repo_url = service.git_app.github.get_authenticated_repository_url(repo_url)
                    elif service.git_app.gitlab:
                        repo_url = service.git_app.gitlab.get_authenticated_repository_url(repo_url)
                resolved_sha = git_client.resolve_commit_sha_for_branch(repo_url, cast(str, service.branch_name))
                new_deployment.commit_sha = resolved_sha or "HEAD" # Fallback if resolution fails
            else:
                new_deployment.commit_sha = current_commit_sha_on_service

        new_deployment.save()
        return new_deployment, deployments_to_cancel

    async def trigger_deployment_workflow(
        self,
        deployment_id: str, # Changed from hash to ID for direct model fetching
        deployments_to_cancel_ids: Optional[List[str]] = None,
    ) -> None:
        """
        Fetches a saved Deployment by ID, prepares its DTO,
        and triggers the appropriate Temporal workflow.
        Also handles signaling for deployments to be cancelled.
        """
        try:
            deployment_instance = await Deployment.objects.select_related(
                "service", "service__project", "service__environment", "service__healthcheck",
                "service__git_app__github", "service__git_app__gitlab"
            ).prefetch_related(
                "service__volumes", "service__ports", "service__urls", "service__env_variables", "service__configs"
            ).aget(id=deployment_id)
        except Deployment.DoesNotExist:
            # Log this error, though it shouldn't happen if called from on_commit correctly
            print(f"[DeploymentService] Error: Deployment with ID {deployment_id} not found for triggering workflow.")
            return

        payload = await DeploymentDetailsDto.afrom_deployment(deployment_instance)

        # Handle cancellations
        if deployments_to_cancel_ids:
            # Fetch workflow IDs for deployments to cancel
            # This requires that the workflow_id is populated on the Deployment model when a workflow *starts*.
            # For now, assuming `flag_deployments_for_cancellation` sets a flag, and another process
            # picks up these flags to find workflow_ids if the workflow has already started.
            # If workflow_id is not yet set (workflow hasn't started for them), signaling might not be possible.
            # The original code signals DeployDockerServiceWorkflow/DeployGitServiceWorkflow.
            # This implies the workflow_id on the Deployment object `dpl` is already set.
            for dpl_id_to_cancel in deployments_to_cancel_ids:
                try:
                    dpl_to_cancel_instance = await Deployment.objects.aget(id=dpl_id_to_cancel)
                    if dpl_to_cancel_instance.workflow_id: # Only signal if workflow_id exists
                        target_workflow_class = (
                            DeployDockerServiceWorkflow if dpl_to_cancel_instance.service.type == Service.ServiceType.DOCKER_REGISTRY
                            else DeployGitServiceWorkflow
                        )
                        TemporalClient.workflow_signal(
                            workflow=target_workflow_class.run,  # type: ignore
                            input=CancelDeploymentSignalInput(deployment_hash=dpl_to_cancel_instance.hash),
                            signal=target_workflow_class.cancel_deployment, # type: ignore
                            workflow_id=dpl_to_cancel_instance.workflow_id,
                        )
                except Deployment.DoesNotExist:
                    print(f"[DeploymentService] Warning: Deployment ID {dpl_id_to_cancel} for cancellation not found.")
                except Exception as e: # Catch other errors during signaling
                    print(f"[DeploymentService] Error signaling cancellation for {dpl_id_to_cancel}: {e}")


        # Start the main workflow
        workflow_class = (
            DeployDockerServiceWorkflow if deployment_instance.service.type == Service.ServiceType.DOCKER_REGISTRY
            else DeployGitServiceWorkflow
        )

        # Ensure workflow_id is generated for the new deployment before starting
        # The DTO's from_deployment should handle this.
        if not payload.workflow_id:
             # This should ideally be set when the Deployment object is created or by from_deployment
            payload.workflow_id = f"{workflow_class.__name__}-{deployment_instance.service.slug}-{payload.hash}"
            print(f"[DeploymentService] Warning: workflow_id was not pre-set on DTO, generated: {payload.workflow_id}")


        TemporalClient.start_workflow(
            workflow=workflow_class.run, # type: ignore
            arg=payload,
            id=payload.workflow_id,
            task_queue=settings.TEMPORALIO_MAIN_TASK_QUEUE, # Ensure task queue is specified
        )
        print(f"[DeploymentService] Started Temporal workflow {payload.workflow_id} for deployment {payload.hash}")

    async def trigger_bulk_deployment_workflows(
        self,
        deployment_task_details: List[Tuple[str, Service.ServiceType, bool]] # (deployment_id, service_type, ignore_cache)
    ) -> None:
        """
        Triggers multiple deployment workflows for bulk operations.
        """
        tasks_to_gather = []
        for dep_id, service_type, ignore_cache_flag in deployment_task_details:
            # We need to fetch the deployment instance to build the payload
            try:
                deployment_instance = await Deployment.objects.select_related(
                    "service", "service__project", "service__environment", "service__healthcheck",
                     "service__git_app__github", "service__git_app__gitlab"
                ).prefetch_related(
                     "service__volumes", "service__ports", "service__urls", "service__env_variables", "service__configs"
                ).aget(id=dep_id)

                # Update ignore_build_cache on the instance if it's a Git service and flag is true
                # This ensures the DTO picks it up correctly.
                if service_type == Service.ServiceType.GIT_REPOSITORY and ignore_cache_flag:
                    deployment_instance.ignore_build_cache = True
                    # No need to save here as DTO is built from this instance state.

                payload = await DeploymentDetailsDto.afrom_deployment(deployment_instance)

                # Manually ensure ignore_build_cache is on the DTO if not automatically handled by from_deployment
                if service_type == Service.ServiceType.GIT_REPOSITORY:
                    payload.ignore_build_cache = ignore_cache_flag


                workflow_class = (
                    DeployDockerServiceWorkflow if service_type == Service.ServiceType.DOCKER_REGISTRY
                    else DeployGitServiceWorkflow
                )

                if not payload.workflow_id:
                    payload.workflow_id = f"{workflow_class.__name__}-{deployment_instance.service.slug}-{payload.hash}"

                # Using start_workflow directly as it's synchronous.
                # If we wanted truly parallel starts from an async context, we'd use asyncio.to_thread
                # or ensure TemporalClient has an async interface for starting workflows.
                # For on_commit, direct calls are fine.
                TemporalClient.start_workflow(
                    workflow=workflow_class.run, #type: ignore
                    arg=payload,
                    id=payload.workflow_id,
                    task_queue=settings.TEMPORALIO_MAIN_TASK_QUEUE,
                )
                print(f"[DeploymentService-Bulk] Started Temporal workflow {payload.workflow_id} for deployment {payload.hash}")

            except Deployment.DoesNotExist:
                print(f"[DeploymentService-Bulk] Error: Deployment with ID {dep_id} not found.")
            except Exception as e:
                print(f"[DeploymentService-Bulk] Error processing deployment ID {dep_id}: {e}")

        # No asyncio.gather needed here as TemporalClient.start_workflow is typically non-blocking (sends a command)
        # The actual workflows run in parallel on Temporal workers.
        print(f"[DeploymentService-Bulk] All {len(deployment_task_details)} deployment triggers issued.")
