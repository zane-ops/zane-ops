import {
  BookDashedIcon,
  BoxIcon,
  BoxesIcon,
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
import { href, useFetcher } from "react-router";
import { toast } from "sonner";
import type { AuthedUserResponse, SearchResource } from "~/api/types";
import type { CommandBarActionGroup } from "~/components/commandbar/commandbar-types";
import { filterGroupsByRole } from "~/components/commandbar/commandbar-utils";
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
              title: "Deploy",
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
              href: home,
              onSelect: () => toggleServiceState(resource, "start")
            },
            {
              id: "service-stop",
              title: "Stop Service",
              icon: PauseIcon,
              href: home,
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
              title: "Deploy",
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
              href: home,
              onSelect: () => toggleStackState(resource, "start")
            },
            {
              id: "stack-stop",
              title: "Stop Stack",
              icon: PauseIcon,
              href: home,
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
