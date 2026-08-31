import { useQuery } from "@tanstack/react-query";
import { useDebounce } from "@uidotdev/usehooks";
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
): Omit<CommandBarSearchItem, "resource" | "id"> {
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
 * Unique per resource & stable across renders: the command bar uses it as the
 * `value` of the item so the highlighted entry can be resolved back to its
 * resource. The type is part of it because two resources of different kinds
 * can share the same id.
 */
export function getSearchItemId(resource: SearchResource) {
  return `search-${resource.type}-${resource.id}`;
}

/** the words the fuzzy filter matches the query against */
export function getSearchItemKeywords(item: CommandBarSearchItem) {
  return [...item.parents, item.title, item.resource.type];
}

function getNavItemsFromSearchResources(
  resources: SearchResource[]
): CommandBarSearchItem[] {
  // the API already returns them sorted by relevance, keep that order
  return resources.map((resource) => ({
    ...getNavItemFromSearchResource(resource),
    id: getSearchItemId(resource),
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
  shouldSearch: boolean;
};

/**
 * Searches the workspace resources & groups them by type, ready to be rendered.
 */
export function useCommandBarSearch({
  search,
  shouldSearch
}: UseCommandBarSearchOptions) {
  const workspaceId = useWorkspaceStore((s) => s.workspace?.id);

  const debouncedSearch = useDebounce(search, 150);

  const { data, isLoading, isFetching } = useQuery({
    ...resourceQueries.search(workspaceId ?? "", debouncedSearch),
    enabled: Boolean(workspaceId && shouldSearch && search.trim().length > 0)
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
  const searchItemsById = React.useMemo(() => {
    const itemsById = new Map<string, CommandBarSearchItem>();

    for (const group of searchGroups) {
      for (const item of group.items) {
        itemsById.set(item.id, item);
      }
    }

    return itemsById;
  }, [searchGroups]);

  return {
    searchGroups,
    searchItemsById,
    isSearchingResources: isLoading || isFetching
  };
}
