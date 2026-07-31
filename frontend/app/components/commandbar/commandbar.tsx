import { useQuery } from "@tanstack/react-query";
import { Command as CommandPrimitive } from "cmdk";
import {
  BoxesIcon,
  ChevronRightIcon,
  ContainerIcon,
  FolderIcon,
  GithubIcon,
  GitlabIcon,
  LightbulbIcon,
  LoaderIcon,
  type LucideIcon,
  NetworkIcon
} from "lucide-react";
import * as React from "react";
import { href, useNavigate } from "react-router";
import { useDebounce } from "use-debounce";
import type { AuthedUserResponse, SearchResource, UserRole } from "~/api/types";
import { useCommandBarStore } from "~/components/commandbar/commandbar-store";
import { Button } from "~/components/ui/button";
import {
  CommandDialog,
  CommandEmpty,
  CommandGroup,
  CommandItem,
  CommandList,
  CommandSeparator
} from "~/components/ui/command";
import { createDevLogger } from "~/lib/logger";
import { resourceQueries, userQueries } from "~/lib/queries";
import { cn, excerpt, hasMinRole, isEditableTarget } from "~/lib/utils";
import { useWorkspaceStore } from "~/lib/workspace-store";

const logger = createDevLogger(import.meta.url);

export type CommandBarNavGroup = {
  heading: string;
  items: CommandBarNavItem[];
  minRole?: UserRole;
};

export type CommandBarNavItem = {
  href: string;
  title: string;
  icon: LucideIcon;
  showInEE?: boolean;
  minRole?: UserRole;
};

export type CommandBarSearchItem = Omit<
  CommandBarNavItem,
  "showInEE" | "minRole"
> & {
  resource: SearchResource;
  /** ancestors of the resource, ex: `["my-project", "production"]` for a service */
  parents: string[];
};

export type CommandBarSearchGroup = {
  heading: string;
  items: CommandBarSearchItem[];
};

export type CommandBarAction = {
  id: string;
  title: string;
  icon: LucideIcon;
  href?: string;
  onSelect?: () => void;
  minRole?: UserRole;
};

export type CommandBarProps = {
  navGroups?: CommandBarNavGroup[];
  authedUser?: AuthedUserResponse | null;
};

const SEARCH_RESULTS_HINT_VALUE = "[search-results-hint]";
const SELECTED_ITEM_HINT_VALUE = "[selected-item-hint]";

/** values that the filter should always keep visible, whatever the query is */
const ALWAYS_VISIBLE_VALUES = new Set([
  SEARCH_RESULTS_HINT_VALUE,
  SELECTED_ITEM_HINT_VALUE
]);

export function CommandBar({ navGroups = [], authedUser }: CommandBarProps) {
  const { open, setOpen, toggle } = useCommandBarStore();
  const [search, setSearch] = React.useState("");

  const workspaceId = useWorkspaceStore((s) => s.workspace?.id);

  const { data } = useQuery({
    ...userQueries.authedUser,
    initialData: authedUser
  });

  const handleOpenChange = React.useCallback(
    (nextOpen: boolean) => {
      setOpen(nextOpen);
      if (!nextOpen) {
        setSearch("");
      }
    },
    [setOpen]
  );

  const navigate = useNavigate();

  const runCommand = React.useCallback(
    (command: () => void) => {
      setOpen(false);
      command();
      setSearch("");
    },
    [setOpen]
  );

  const [debouncedValue] = useDebounce(search, 150);
  const isActionMode = search.startsWith(">");

  const {
    data: resourceListData,
    isLoading,
    isFetching
  } = useQuery({
    ...resourceQueries.search(workspaceId ?? "", debouncedValue),
    enabled: Boolean(workspaceId && search.trim().length > 0 && !isActionMode)
  });

  const navigationGroups = React.useMemo(() => {
    if (!data) return [];

    return navGroups
      .filter((group) => !group.minRole || hasMinRole(data, group.minRole))
      .map((group) => ({
        ...group,
        items: group.items.filter(
          (item) => !item.minRole || hasMinRole(data, item.minRole)
        )
      }))
      .filter((group) => group.items.length > 0);
  }, [navGroups, data]);

  const searchGroups = React.useMemo(
    () =>
      groupSearchItemsByType(
        search.trim().length > 0
          ? getNavItemsFromSearchResources(resourceListData?.data ?? [])
          : []
      ),
    [resourceListData, search]
  );

  React.useEffect(() => {
    function onKeyDown(event: KeyboardEvent) {
      if (
        event.key.toLowerCase() !== "k" ||
        !(event.metaKey || event.ctrlKey)
      ) {
        return;
      }

      if (!open && isEditableTarget(event.target)) {
        return;
      }

      event.preventDefault();
      toggle();
    }

    document.addEventListener("keydown", onKeyDown);
    return () => document.removeEventListener("keydown", onKeyDown);
  }, [open, toggle]);

  if (!data?.user) return null;

  const actionModeHint = (
    <div className="inline-flex items-center gap-1 text-muted-foreground">
      <LightbulbIcon className="size-3 flex-none" />
      <span>Type</span>
      <kbd className="rounded-sm px-1  font-mono bg-muted">{">"}</kbd>
      <span>To Open Action Mode</span>
    </div>
  );

  const searchItemHint = (
    <div className="inline-flex items-center gap-1 whitespace-nowrap text-muted-foreground font-medium">
      <LightbulbIcon className="size-3 flex-none" />

      <span>Type</span>
      <kbd className="rounded-sm px-1  font-mono bg-muted">Enter</kbd>
      <span>to jump to item</span>

      <span className="text-grey">&middot;</span>

      <span>Type</span>
      <kbd className="rounded-sm px-1  font-mono bg-muted">Tab</kbd>
      <span>to select item</span>
    </div>
  );

  const selectedItemContextHint = (
    <div className="inline-flex items-center gap-1 whitespace-nowrap">
      <LightbulbIcon className="size-3 flex-none" />
      <strong className="font-semibold"></strong>

      <span>Press</span>
      <kbd className="rounded-sm px-1  font-mono bg-muted">escape</kbd>
      <span>to deselect item</span>
    </div>
  );

  return (
    <CommandDialog
      open={open}
      onOpenChange={handleOpenChange}
      className={cn(
        "max-w-2xl **:data-[slot=command-input-wrapper]:h-15",
        "[&_[data-slot='command-list-wrapper']>*]:static",
        "md:top-[clamp(1.5rem,12vh,200px)] md:max-h-[calc(100dvh-clamp(1.5rem,12vh,200px)-1.5rem)] md:translate-y-0"
      )}
      commandProps={{
        loop: true,
        filter(value, query) {
          let search = query;
          if (query.startsWith(">")) {
            search = query.substring(1);

            logger.scope("CommandDialog", "commandProps", "filter").info({
              search,
              value
            });
            // TODO
          }

          logger.scope("CommandDialog", "commandProps", "filter").info({
            search,
            value
          });

          if (
            ALWAYS_VISIBLE_VALUES.has(value) ||
            value.toLowerCase().includes(search.trim().toLowerCase())
          ) {
            return 1;
          }
          return 0;
        }
      }}
    >
      <div className="flex flex-col gap-1 pt-3 px-3 items-start">
        <Button type="button" size="xs" variant="outline" className="text-xs">
          Home
        </Button>
        <div className="flex items-center gap-1 w-full px-0">
          <CommandPrimitive.Input
            autoFocus
            placeholder="Search pages, resources, actions..."
            className="text-base bg-inherit focus-visible:outline-hidden px-2 w-full grow"
            value={search}
            onValueChange={setSearch}
          />
        </div>
      </div>

      <CommandList
        className={cn(
          "max-h-124 min-h-0 h-[calc(var(--cmdk-list-height)+var(--spacing)*3)] scroll-pb-4 scroll-pt-2",
          "transition-[height] duration-200 ease-in-out",
          "rounded-t-none border-x-0 border-b-0 px-0"
        )}
      >
        <CommandEmpty>
          {isLoading || isFetching ? (
            <div className="flex items-center gap-2 w-full justify-center">
              Searching...
              <LoaderIcon className="size-4 flex-none text-grey animate-spin" />
            </div>
          ) : (
            "No results"
          )}
        </CommandEmpty>

        {searchGroups.length === 0 && (
          <CommandGroup
            heading={actionModeHint}
            className="[&_[cmdk-group-heading]]:text-xs overflow-visible"
          />
        )}
        {searchGroups.length > 0 && (
          <CommandGroup className="overflow-visible !px-2 py-0 [&_[cmdk-item]]:py-2.5!">
            {/* `disabled` keeps it out of the keyboard navigation, while still
                counting as a visible item so that cmdk doesn't hide the group */}
            <CommandItem
              disabled
              value={SEARCH_RESULTS_HINT_VALUE}
              className="px-0 py-0 text-xs text-muted-foreground data-[disabled='true']:opacity-100 font-medium [&[cmdk-item]_svg]:size-3"
            >
              {searchItemHint}
            </CommandItem>
          </CommandGroup>
        )}

        {navigationGroups.map((group, groupIndex) => (
          <React.Fragment key={group.heading}>
            {groupIndex > 0 && <CommandSeparator />}
            <CommandGroup
              heading={group.heading}
              className={cn(
                "[&_[cmdk-group-heading]]:py-2 [&_[cmdk-group-heading]]:text-xs",
                groupIndex === 0
                  ? "scroll-pt-10"
                  : "[&_[cmdk-group-heading]]:pt-3",
                "pb-2 !px-2"
              )}
            >
              {group.items.map((item) => (
                <CommandItem
                  key={item.href}
                  value={`${item.title} ${group.heading}`}
                  onSelect={() => runCommand(() => navigate(item.href))}
                  className="h-9 flex items-center gap-2 px-0 font-medium"
                >
                  <item.icon className="flex-none text-grey size-4" />
                  <span className="text-card-foreground">{item.title}</span>
                </CommandItem>
              ))}
            </CommandGroup>
          </React.Fragment>
        ))}

        {searchGroups.map((group, groupIndex) => {
          const hasContentAbove = navigationGroups.length > 0 || groupIndex > 0;

          return (
            <React.Fragment key={group.heading}>
              {hasContentAbove && <CommandSeparator />}
              <CommandGroup
                heading={group.heading}
                className={cn(
                  "[&_[cmdk-group-heading]]:py-2 [&_[cmdk-group-heading]]:text-xs",
                  hasContentAbove && "[&_[cmdk-group-heading]]:pt-3",
                  "pb-2 !px-2"
                )}
              >
                {group.items.map((item) => (
                  <CommandItem
                    key={item.resource.id}
                    value={`${item.parents.join(" ")} ${item.title} ${item.resource.type} ${item.resource.id}`}
                    onSelect={() => runCommand(() => navigate(item.href))}
                    className="h-9 flex items-center gap-2 px-0"
                  >
                    <item.icon className="flex-none text-grey size-4" />
                    <div className="inline-flex gap-0.5 items-baseline w-full">
                      {item.parents.map((parent, index) => (
                        <React.Fragment key={`${parent}-${index}`}>
                          <span className="text-grey">
                            {excerpt(parent, 40)}
                          </span>
                          <ChevronRightIcon className="size-4 flex-none text-grey relative top-1" />
                        </React.Fragment>
                      ))}
                      <p className="text-card-foreground font-medium">
                        {item.title}
                      </p>
                    </div>
                  </CommandItem>
                ))}
              </CommandGroup>
            </React.Fragment>
          );
        })}
      </CommandList>
    </CommandDialog>
  );
}

const SEARCH_GROUP_HEADINGS: Record<SearchResource["type"], string> = {
  service: "Services",
  compose_stack: "Compose Stacks",
  project: "Projects",
  environment: "Environments"
};

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

function getNavItemFromSearchResource(
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

function getNavItemsFromSearchResources(
  resources: SearchResource[]
): CommandBarSearchItem[] {
  // the API already returns them sorted by relevance, keep that order
  return resources.map((resource) => ({
    ...getNavItemFromSearchResource(resource),
    resource
  }));
}
