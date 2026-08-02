import { useQuery } from "@tanstack/react-query";
import {
  BoxesIcon,
  ContainerIcon,
  FolderIcon,
  GithubIcon,
  GitlabIcon,
  NetworkIcon
} from "lucide-react";
import * as React from "react";
import { href } from "react-router";
import type { SearchResource } from "~/api/types";
import type {
  CommandBarSearchGroup,
  CommandBarSearchItem
} from "~/components/commandbar/commandbar-types";
import { resourceQueries } from "~/lib/queries";
import { useWorkspaceStore } from "~/lib/workspace-store";

const SEARCH_GROUP_HEADINGS: Record<SearchResource["type"], string> = {
  service: "Services",
  compose_stack: "Compose Stacks",
  project: "Projects",
  environment: "Environments"
};

export function getNavItemFromSearchResource(
  resource: SearchResource
): Omit<CommandBarSearchItem, "resource"> {
  switch (resource.type) {
    case "project":
      return {
        title: resource.slug,
        href: href("/workspace/project/:projectSlug/:envSlug", {
          projectSlug: resource.slug,
          envSlug: "production"
        }),
        icon: FolderIcon,
        parents: []
      };
    case "environment":
      return {
        title: resource.name,
        href: href("/workspace/project/:projectSlug/:envSlug", {
          projectSlug: resource.project_slug,
          envSlug: resource.name
        }),
        icon: NetworkIcon,
        parents: [resource.project_slug]
      };
    case "service":
      return {
        title: resource.slug,
        href: href(
          "/workspace/project/:projectSlug/:envSlug/services/:serviceSlug",
          {
            projectSlug: resource.project_slug,
            envSlug: resource.environment,
            serviceSlug: resource.slug
          }
        ),
        icon:
          resource.kind === "DOCKER_REGISTRY"
            ? ContainerIcon
            : resource.git_provider === "gitlab"
              ? GitlabIcon
              : GithubIcon,
        parents: [resource.project_slug, resource.environment]
      };
    case "compose_stack":
      return {
        title: resource.slug,
        href: href(
          "/workspace/project/:projectSlug/:envSlug/compose-stacks/:composeStackSlug",
          {
            projectSlug: resource.project_slug,
            envSlug: resource.environment,
            composeStackSlug: resource.slug
          }
        ),
        icon: BoxesIcon,
        parents: [resource.project_slug, resource.environment]
      };
  }
}

/**
 * Unique per resource, the id is included because two services in different
 * projects can share the same slug.
 */
export function getSearchItemValue(item: CommandBarSearchItem) {
  return `${item.parents.join(" ")} ${item.title} ${item.resource.type} ${item.resource.id}`.trim();
}

function getNavItemsFromSearchResources(
  resources: SearchResource[]
): CommandBarSearchItem[] {
  // the API already returns them sorted by relevance, keep that order
  return resources.map((resource) => ({
    ...getNavItemFromSearchResource(resource),
    resource
  }));
}

function groupSearchItemsByType(
  items: CommandBarSearchItem[]
): CommandBarSearchGroup[] {
  // the API already returns the resources ranked & grouped by type,
  // so the insertion order of the map is the order it sent them in
  const groups = new Map<SearchResource["type"], CommandBarSearchItem[]>();

  for (const item of items) {
    const group = groups.get(item.resource.type);
    if (group) {
      group.push(item);
    } else {
      groups.set(item.resource.type, [item]);
    }
  }

  return Array.from(groups, ([type, items]) => ({
    heading: SEARCH_GROUP_HEADINGS[type],
    items
  }));
}

export type UseCommandBarSearchOptions = {
  search: string;
  debouncedSearch: string;
  /** searching is pointless when the palette is closed... */
  isOpen: boolean;
  /** ...or when the list shows something else than resources */
  isPaused: boolean;
};

/**
 * Searches the workspace resources & groups them by type, ready to be rendered.
 */
export function useCommandBarSearch({
  search,
  debouncedSearch,
  isOpen,
  isPaused
}: UseCommandBarSearchOptions) {
  const workspaceId = useWorkspaceStore((s) => s.workspace?.id);

  const { data, isLoading, isFetching } = useQuery({
    ...resourceQueries.search(workspaceId ?? "", debouncedSearch),
    enabled: Boolean(
      workspaceId && isOpen && search.trim().length > 0 && !isPaused
    )
  });

  const searchGroups = React.useMemo(
    () =>
      groupSearchItemsByType(
        search.trim().length > 0
          ? getNavItemsFromSearchResources(data?.data ?? [])
          : []
      ),
    [data, search]
  );

  // `Tab` selects whatever is highlighted, so we need to map it back to its item
  const searchItemsByValue = React.useMemo(() => {
    const itemsByValue = new Map<string, CommandBarSearchItem>();

    for (const group of searchGroups) {
      for (const item of group.items) {
        itemsByValue.set(getSearchItemValue(item), item);
      }
    }

    return itemsByValue;
  }, [searchGroups]);

  return { searchGroups, searchItemsByValue, isLoading, isFetching };
}
