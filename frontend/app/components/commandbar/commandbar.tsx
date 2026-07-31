import { useQuery } from "@tanstack/react-query";
import { Command as CommandPrimitive } from "cmdk";
import {
  BoxesIcon,
  ChevronRightIcon,
  ContainerIcon,
  FolderIcon,
  GithubIcon,
  GitlabIcon,
  LoaderIcon,
  type LucideIcon,
  NetworkIcon
} from "lucide-react";
import * as React from "react";
import { href, useNavigate } from "react-router";
import { useDebounce } from "use-debounce";
import type {
  AuthedUserResponse,
  SearchResource,
  WorkspaceRoleName
} from "~/api/types";
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
import {
  capitalizeText,
  cn,
  excerpt,
  hasMinRole,
  isEditableTarget
} from "~/lib/utils";
import { useWorkspaceStore } from "~/lib/workspace-store";

const logger = createDevLogger(import.meta.url);

export type CommandBarNavGroup = {
  heading: string;
  items: CommandBarNavItem[];
  minRole?: WorkspaceRoleName | "ServerAdmin";
};

export type CommandBarNavItem = {
  href: string;
  title: string;
  icon: LucideIcon;
  showInEE?: boolean;
  minRole?: WorkspaceRoleName | "ServerAdmin";
};

export type CommandBarSearchItem = Omit<
  CommandBarNavItem,
  "showInEE" | "minRole"
> & {
  resource: SearchResource;
  /** ancestors of the resource, ex: `["my-project", "production"]` for a service */
  parents: string[];
};

export type CommandBarAction = {
  id: string;
  title: string;
  icon: LucideIcon;
  href?: string;
  onSelect?: () => void;
  minRole?: WorkspaceRoleName | "ServerAdmin";
};

export type CommandBarProps = {
  navGroups?: CommandBarNavGroup[];
  authedUser?: AuthedUserResponse | null;
};

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

  const searchItems = React.useMemo(
    () =>
      search.trim().length > 0
        ? getNavItemsFromSearchResources(resourceListData?.data ?? [])
        : [],
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

  const hint = (
    <div className="inline-flex items-center gap-1">
      <strong className="font-semibold">Tip:</strong>
      <span>Type</span>
      <kbd className="rounded-sm px-1  font-mono bg-muted">{">"}</kbd>
      <span>To Open Action Mode</span>
    </div>
  ); // Or press [escape] to quit context

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

          if (value.toLowerCase().includes(search.trim().toLowerCase())) {
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

        <CommandGroup
          heading={hint}
          className="[&_[cmdk-group-heading]]:text-xs overflow-visible"
        />

        {navigationGroups.map((group, groupIndex) => (
          <React.Fragment key={group.heading}>
            {groupIndex > 0 && <CommandSeparator />}
            <CommandGroup
              heading={group.heading}
              className={cn(
                "[&_[cmdk-group-heading]]:py-2 [&_[cmdk-group-heading]]:text-xs",
                groupIndex > 0 && "[&_[cmdk-group-heading]]:pt-3",
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
                  <item.icon className="flex-none text-grey" />
                  <span className="text-card-foreground">{item.title}</span>
                </CommandItem>
              ))}
            </CommandGroup>
          </React.Fragment>
        ))}

        {searchItems.length > 0 && (
          <>
            {navigationGroups.length > 0 && <CommandSeparator />}
            <CommandGroup
              heading="Search results"
              className={cn(
                "[&_[cmdk-group-heading]]:py-2 [&_[cmdk-group-heading]]:text-xs",
                navigationGroups.length > 0 && "[&_[cmdk-group-heading]]:pt-3",
                "pb-2 !px-2"
              )}
            >
              {searchItems.map((item) => (
                <CommandItem
                  key={item.resource.id}
                  value={`${item.parents.join(" ")} ${item.title} ${item.resource.type} ${item.resource.id}`}
                  onSelect={() => runCommand(() => navigate(item.href))}
                  className="h-9 flex items-center gap-2 px-0"
                >
                  <item.icon className="flex-none text-grey" />
                  <div className="inline-flex gap-0.5 items-baseline">
                    {item.parents.map((parent, index) => (
                      <React.Fragment key={`${parent}-${index}`}>
                        <span className="text-grey">{excerpt(parent, 40)}</span>
                        <ChevronRightIcon className="size-4 flex-none text-grey relative top-1" />
                      </React.Fragment>
                    ))}
                    <span className="text-card-foreground font-medium">
                      {item.title}
                    </span>
                  </div>
                </CommandItem>
              ))}
            </CommandGroup>
          </>
        )}
      </CommandList>
    </CommandDialog>
  );
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
        parents: ["Projects"]
      };
    case "environment":
      return {
        title: resource.name,
        href: href("/workspace/project/:projectSlug/:envSlug", {
          projectSlug: resource.project_slug,
          envSlug: resource.name
        }),
        icon: NetworkIcon,
        parents: ["Projects", resource.project_slug]
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
        parents: ["Projects", resource.project_slug, resource.environment]
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
        parents: ["Projects", resource.project_slug, resource.environment]
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
