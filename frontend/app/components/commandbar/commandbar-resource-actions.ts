import {
  BookDashedIcon,
  BoxIcon,
  ChartNoAxesColumn,
  ContainerIcon,
  GlobeIcon,
  KeyRoundIcon,
  NetworkIcon,
  RocketIcon,
  SettingsIcon
} from "lucide-react";
import { href } from "react-router";
import type { SearchResource } from "~/api/types";
import type { CommandBarActionGroup } from "~/components/commandbar/commandbar";

/**
 * Where a resource can be navigated to once selected as the command bar
 * context. Titles, icons & roles mirror the sidebar of each resource layout.
 *
 * Only navigations for now: actions needing an input (rename, clone) or a
 * confirmation (archive) can't run from a single `Enter`.
 */
export function getResourceActionGroups(
  resource: SearchResource
): CommandBarActionGroup[] {
  switch (resource.type) {
    case "project": {
      const projectSlug = resource.slug;

      return [
        {
          heading: "Jump to",
          items: [
            {
              id: "project-production",
              title: "Production Environment",
              href: href("/workspace/project/:projectSlug/:envSlug", {
                projectSlug,
                envSlug: "production"
              }),
              icon: ContainerIcon
            },
            {
              id: "project-settings",
              title: "General Settings",
              href: href("/workspace/project/:projectSlug/settings", {
                projectSlug
              }),
              icon: SettingsIcon
            },
            {
              id: "project-environments",
              title: "Environments",
              href: href(
                "/workspace/project/:projectSlug/settings/environments",
                { projectSlug }
              ),
              icon: NetworkIcon,
              minRole: "Member"
            },
            {
              id: "project-preview-templates",
              title: "Preview Templates",
              href: href(
                "/workspace/project/:projectSlug/settings/preview-templates",
                { projectSlug }
              ),
              icon: BookDashedIcon,
              minRole: "Admin"
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
          heading: "Go to",
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
        }
      ];
    }
    case "service": {
      const params = {
        projectSlug: resource.project_slug,
        envSlug: resource.environment,
        serviceSlug: resource.slug
      };

      return [
        {
          heading: "Go to",
          items: [
            {
              id: "service-deployments",
              title: "Deployments",
              href: href(
                "/workspace/project/:projectSlug/:envSlug/services/:serviceSlug",
                params
              ),
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
        }
      ];
    }
    case "compose_stack": {
      const params = {
        projectSlug: resource.project_slug,
        envSlug: resource.environment,
        composeStackSlug: resource.slug
      };

      return [
        {
          heading: "Go to",
          items: [
            {
              id: "stack-services",
              title: "Services",
              href: href(
                "/workspace/project/:projectSlug/:envSlug/compose-stacks/:composeStackSlug",
                params
              ),
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
        }
      ];
    }
  }
}
