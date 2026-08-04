import { useQuery } from "@tanstack/react-query";
import {
  BookDashedIcon,
  BoxIcon,
  ChartNoAxesColumn,
  ContainerIcon,
  GlobeIcon,
  KeyRoundIcon,
  LayersPlusIcon,
  NetworkIcon,
  PackagePlusIcon,
  PauseIcon,
  PlayIcon,
  RocketIcon,
  SettingsIcon
} from "lucide-react";
import * as React from "react";
import { href, useFetcher, useParams } from "react-router";
import { toast } from "sonner";
import type { AuthedUserResponse, SearchResource } from "~/api/types";
import type {
  CommandBarActionGroup,
  RouteParams
} from "~/components/commandbar/commandbar-types";
import { filterGroupsByRole } from "~/components/commandbar/commandbar-utils";
import {
  composeStackQueries,
  environmentQueries,
  projectQueries,
  serviceQueries
} from "~/lib/queries";
import { useToggleStateQueueStore } from "~/lib/toggle-state-store";
import { useWorkspaceStore } from "~/lib/workspace-store";
import { toggleStackStateToast } from "~/routes/compose/components/compose-stack-actions-popover";
import type { ToggleStackState } from "~/routes/compose/toggle-compose-stack";
import { toggleServiceStateToast } from "~/routes/services/components/service-actions-popover";
import type { ToggleServiceState } from "~/routes/services/toggle-service-state";

export type ServiceSearchResource = Extract<
  SearchResource,
  { type: "service" }
>;

export type ComposeStackSearchResource = Extract<
  SearchResource,
  { type: "compose_stack" }
>;

/** `useFetcher().submit`, narrowed to what the actions below need */
export type SubmitAction = (
  body: Record<string, string>,
  options: { method: "post"; action: string }
) => void;

export type ResourceActionHandlers = {
  submit: SubmitAction;
  /**
   * Toggling is not instant, these keep a loading toast up until the resource
   * settles into its new state (or the timeout is reached).
   */
  toggleServiceState: (
    resource: ServiceSearchResource,
    desiredState: ToggleServiceState
  ) => void;
  toggleStackState: (
    resource: ComposeStackSearchResource,
    desiredState: ToggleStackState
  ) => void;
};

/**
 * What can be done with a resource once selected as the command bar context.
 * Titles, icons & roles mirror the sidebar & action bar of each resource layout.
 *
 * Actions needing an input (rename, clone, discard changes) or a confirmation
 * (archive) are left out, they can't run from a single `Enter`.
 */
export function getResourceActionGroups(
  resource: SearchResource,
  { submit, toggleServiceState, toggleStackState }: ResourceActionHandlers
): CommandBarActionGroup[] {
  switch (resource.type) {
    case "project": {
      const params = {
        projectSlug: resource.slug,
        envSlug: "production"
      };

      return [
        {
          heading: "Jump to",
          items: [
            {
              id: "project-production",
              title: "Production Environment",
              href: href("/workspace/project/:projectSlug/:envSlug", params),
              icon: ContainerIcon
            },
            {
              id: "project-settings",
              title: "General Settings",
              href: href("/workspace/project/:projectSlug/settings", params),
              icon: SettingsIcon
            },
            {
              id: "project-environments",
              title: "Environments",
              href: href(
                "/workspace/project/:projectSlug/settings/environments",
                params
              ),
              icon: NetworkIcon,
              minRole: "Member"
            },
            {
              id: "project-preview-templates",
              title: "Preview Templates",
              href: href(
                "/workspace/project/:projectSlug/settings/preview-templates",
                params
              ),
              icon: BookDashedIcon,
              minRole: "Admin"
            }
          ]
        },
        {
          heading: "Actions",
          items: [
            {
              id: "create-service",
              title: "Create Service In Production Env",
              href: href(
                "/workspace/project/:projectSlug/:envSlug/create-service",
                params
              ),
              icon: PackagePlusIcon,
              minRole: "Member"
            },
            {
              id: "create-compose-stack",
              title: "Create Compose Stack In Production Env",
              href: href(
                "/workspace/project/:projectSlug/:envSlug/create-compose-stack",
                params
              ),
              icon: LayersPlusIcon,
              minRole: "Member"
            }
          ]
        }
      ];
    }
    case "environment": {
      const params = {
        projectSlug: resource.project_slug,
        envSlug: resource.name
      };

      return [
        {
          heading: "Jump to",
          items: [
            {
              id: "environment-services",
              title: "Services",
              href: href("/workspace/project/:projectSlug/:envSlug", params),
              icon: ContainerIcon
            },
            {
              id: "environment-variables",
              title: "Variables",
              href: href(
                "/workspace/project/:projectSlug/:envSlug/variables",
                params
              ),
              icon: KeyRoundIcon,
              minRole: "Member"
            },
            {
              id: "environment-settings",
              title: "Settings",
              href: href(
                "/workspace/project/:projectSlug/:envSlug/settings",
                params
              ),
              icon: SettingsIcon
            }
          ]
        },
        {
          heading: "Actions",
          items: [
            {
              id: "create-service",
              title: "Create Service",
              href: href(
                "/workspace/project/:projectSlug/:envSlug/create-service",
                params
              ),
              icon: PackagePlusIcon,
              minRole: "Member"
            },
            {
              id: "create-compose-stack",
              title: "Create Compose Stack",
              href: href(
                "/workspace/project/:projectSlug/:envSlug/create-compose-stack",
                params
              ),
              icon: LayersPlusIcon,
              minRole: "Member"
            }
          ]
        }
      ];
    }
    case "service": {
      const params = {
        projectSlug: resource.project_slug,
        envSlug: resource.environment,
        serviceSlug: resource.slug
      };
      // where every action lands the user, so they can follow what it did
      const home = href(
        "/workspace/project/:projectSlug/:envSlug/services/:serviceSlug",
        params
      );

      return [
        {
          heading: "Jump to",
          items: [
            {
              id: "service-deployments",
              title: "Deployments",
              href: home,
              icon: RocketIcon
            },
            {
              id: "service-env-variables",
              title: "Env Variables",
              href: href(
                "/workspace/project/:projectSlug/:envSlug/services/:serviceSlug/env-variables",
                params
              ),
              icon: KeyRoundIcon,
              minRole: "Member"
            },
            {
              id: "service-settings",
              title: "Settings",
              href: href(
                "/workspace/project/:projectSlug/:envSlug/services/:serviceSlug/settings",
                params
              ),
              icon: SettingsIcon
            },
            {
              id: "service-http-logs",
              title: "Http logs",
              href: href(
                "/workspace/project/:projectSlug/:envSlug/services/:serviceSlug/http-logs",
                params
              ),
              icon: GlobeIcon,
              minRole: "Member"
            },
            {
              id: "service-metrics",
              title: "Metrics",
              href: href(
                "/workspace/project/:projectSlug/:envSlug/services/:serviceSlug/metrics",
                params
              ),
              icon: ChartNoAxesColumn
            }
          ]
        },
        {
          heading: "Run",
          minRole: "Member",
          items: [
            {
              id: "service-deploy",
              title: "Deploy Service",
              icon: RocketIcon,
              href: home,
              // every field of the deploy form is optional
              onSelect: () =>
                submit(
                  {},
                  {
                    method: "post",
                    action:
                      resource.kind === "DOCKER_REGISTRY"
                        ? href(
                            "/workspace/project/:projectSlug/:envSlug/services/:serviceSlug/deploy-docker-service",
                            params
                          )
                        : href(
                            "/workspace/project/:projectSlug/:envSlug/services/:serviceSlug/deploy-git-service",
                            params
                          )
                  }
                )
            },
            {
              id: "service-start",
              title: "Start Service",
              icon: PlayIcon,
              onSelect: () => toggleServiceState(resource, "start")
            },
            {
              id: "service-stop",
              title: "Stop Service",
              icon: PauseIcon,
              onSelect: () => toggleServiceState(resource, "stop")
            }
          ]
        }
      ];
    }
    case "compose_stack": {
      const params = {
        projectSlug: resource.project_slug,
        envSlug: resource.environment,
        composeStackSlug: resource.slug
      };

      // where every action lands the user, so they can follow what it did
      const home = href(
        "/workspace/project/:projectSlug/:envSlug/compose-stacks/:composeStackSlug",
        params
      );

      return [
        {
          heading: "Jump to",
          items: [
            {
              id: "stack-services",
              title: "Services",
              href: home,
              icon: BoxIcon
            },
            {
              id: "stack-deployments",
              title: "Deployments",
              href: href(
                "/workspace/project/:projectSlug/:envSlug/compose-stacks/:composeStackSlug/deployments",
                params
              ),
              icon: RocketIcon
            },
            {
              id: "stack-settings",
              title: "Settings",
              href: href(
                "/workspace/project/:projectSlug/:envSlug/compose-stacks/:composeStackSlug/settings",
                params
              ),
              icon: SettingsIcon,
              minRole: "Member"
            },
            {
              id: "stack-http-logs",
              title: "Http logs",
              href: href(
                "/workspace/project/:projectSlug/:envSlug/compose-stacks/:composeStackSlug/http-logs",
                params
              ),
              icon: GlobeIcon,
              minRole: "Member"
            },
            {
              id: "stack-metrics",
              title: "Metrics",
              href: href(
                "/workspace/project/:projectSlug/:envSlug/compose-stacks/:composeStackSlug/metrics",
                params
              ),
              icon: ChartNoAxesColumn
            }
          ]
        },
        {
          heading: "Run",
          minRole: "Member",
          items: [
            {
              id: "stack-deploy",
              title: "Deploy Stack",
              icon: RocketIcon,
              href: home,
              // `commit_message` is the only field & it is optional
              onSelect: () =>
                submit(
                  {},
                  {
                    method: "post",
                    action: href(
                      "/workspace/project/:projectSlug/:envSlug/compose-stacks/:composeStackSlug/deploy",
                      params
                    )
                  }
                )
            },
            {
              id: "stack-start",
              title: "Start Stack",
              icon: PlayIcon,
              onSelect: () => toggleStackState(resource, "start")
            },
            {
              id: "stack-stop",
              title: "Stop Stack",
              icon: PauseIcon,
              onSelect: () => toggleStackState(resource, "stop")
            }
          ]
        }
      ];
    }
  }
}

/**
 * Builds the actions available for the resource currently selected as the
 * command bar context, already filtered down to what the user can do.
 */
export function useResourceActionGroups(
  resource: SearchResource | null,
  user: AuthedUserResponse | null | undefined
): CommandBarActionGroup[] {
  const workspaceId = useWorkspaceStore((s) => s.workspace?.id);
  const { submit } = useFetcher();

  const { queue, queueToggleItem, dequeueToggleItem } =
    useToggleStateQueueStore();

  const toggleServiceState = React.useCallback(
    async (
      resource: ServiceSearchResource,
      desiredState: ToggleServiceState
    ) => {
      if (queue.has(resource.id)) {
        toast.info("The service is already being toggled in the background.");
        return;
      }

      await submit(
        { desired_state: desiredState },
        {
          method: "post",
          action: href(
            "/workspace/project/:projectSlug/:envSlug/services/:serviceSlug/toggle-service-state",
            {
              projectSlug: resource.project_slug,
              envSlug: resource.environment,
              serviceSlug: resource.slug
            }
          )
        }
      );

      queueToggleItem(resource.id);
      toggleServiceStateToast({
        workspaceId: workspaceId ?? "",
        desiredState,
        projectSlug: resource.project_slug,
        serviceSlug: resource.slug,
        envSlug: resource.environment
      }).finally(() => dequeueToggleItem(resource.id));
    },
    [queue, queueToggleItem, dequeueToggleItem, submit, workspaceId]
  );

  const toggleStackState = React.useCallback(
    async (
      resource: ComposeStackSearchResource,
      desiredState: ToggleStackState
    ) => {
      if (queue.has(resource.id)) {
        toast.info("The stack is already being toggled in the background.");
        return;
      }

      await submit(
        // no `service_name` => the whole stack
        { desired_state: desiredState },
        {
          method: "post",
          action: href(
            "/workspace/project/:projectSlug/:envSlug/compose-stacks/:composeStackSlug/toggle",
            {
              projectSlug: resource.project_slug,
              envSlug: resource.environment,
              composeStackSlug: resource.slug
            }
          )
        }
      );

      queueToggleItem(resource.id);
      toggleStackStateToast({
        workspaceId: workspaceId ?? "",
        desiredState,
        projectSlug: resource.project_slug,
        stackSlug: resource.slug,
        envSlug: resource.environment
      }).finally(() => dequeueToggleItem(resource.id));
    },
    [queue, queueToggleItem, dequeueToggleItem, submit, workspaceId]
  );

  return React.useMemo(
    () =>
      filterGroupsByRole(
        resource
          ? getResourceActionGroups(resource, {
              submit,
              toggleServiceState,
              toggleStackState
            })
          : [],
        user
      ),
    [resource, user, submit, toggleServiceState, toggleStackState]
  );
}

export function useCurrentSelectedResourceInRouteContext(): SearchResource | null {
  const workspaceId = useWorkspaceStore((s) => s.workspace?.id);
  const params = useParams() as RouteParams;

  const inProjectRoutes = Boolean(workspaceId && params.projectSlug);
  const inEnvRoutes = Boolean(
    workspaceId && params.projectSlug && params.envSlug
  );
  const inServiceRoutes = Boolean(
    workspaceId && params.projectSlug && params.envSlug && params.serviceSlug
  );
  const inComposeStackRoutes = Boolean(
    workspaceId &&
      params.projectSlug &&
      params.envSlug &&
      params.composeStackSlug
  );

  const { data: project } = useQuery({
    ...projectQueries.single(workspaceId ?? "", params.projectSlug ?? ""),
    enabled: inProjectRoutes
  });

  const { data: environment } = useQuery({
    ...environmentQueries.single(
      workspaceId ?? "",
      params.projectSlug ?? "",
      params.envSlug ?? ""
    ),
    enabled: inEnvRoutes
  });

  const { data: service } = useQuery({
    ...serviceQueries.single({
      workspaceId: workspaceId ?? "",
      project_slug: params.projectSlug ?? "",
      env_slug: params.envSlug ?? "",
      service_slug: params.serviceSlug ?? ""
    }),
    enabled: inServiceRoutes
  });

  const { data: composeStack } = useQuery({
    ...composeStackQueries.single({
      workspaceId: workspaceId ?? "",
      project_slug: params.projectSlug ?? "",
      env_slug: params.envSlug ?? "",
      stack_slug: params.composeStackSlug ?? ""
    }),
    enabled: inComposeStackRoutes
  });

  if (composeStack && inComposeStackRoutes) {
    return {
      type: "compose_stack",
      id: composeStack.id,
      project_slug: params.projectSlug ?? "",
      environment: params.envSlug ?? "",
      slug: params.composeStackSlug ?? "",
      created_at: composeStack.created_at
    };
  }

  if (service && inServiceRoutes) {
    return {
      type: "service",
      id: service.id,
      project_slug: params.projectSlug ?? "",
      environment: params.envSlug ?? "",
      slug: params.serviceSlug ?? "",
      created_at: service.created_at,
      kind: service.type,
      git_provider: service.git_app?.github
        ? "github"
        : service.git_app?.gitlab
          ? "gitlab"
          : null
    };
  }

  if (environment && inEnvRoutes) {
    return {
      type: "environment",
      id: environment.id,
      project_slug: params.projectSlug ?? "",
      name: params.envSlug ?? "",
      created_at: environment.created_at
    };
  }

  if (project && inProjectRoutes) {
    return {
      type: "project",
      id: project.id,
      slug: params.projectSlug ?? "",
      created_at: project.created_at
    };
  }

  return null;
}
