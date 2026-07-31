import { useQuery } from "@tanstack/react-query";
import { Command as CommandPrimitive } from "cmdk";
import { LoaderIcon, type LucideIcon } from "lucide-react";
import * as React from "react";
import { useNavigate } from "react-router";
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
import { cn, hasMinRole, isEditableTarget } from "~/lib/utils";
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

export type CommandBarAction = {
  id: string;
  title: string;
  icon: LucideIcon;
  href?: string;
  onSelect?: () => void;
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

  const [debouncedValue] = useDebounce(search, 300);

  const {
    data: resourceListData,
    isLoading,
    isFetching
  } = useQuery(resourceQueries.search(workspaceId ?? "", debouncedValue));

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

  const resourceList = resourceListData?.data ?? [];
  //   const isActionMode = search.startsWith(">");
  const hint = 'Type ">" To Open Action Mode'; // Or press [escape] to quit context

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
                  className="h-9 flex items-center gap-2 px-0"
                >
                  <item.icon className="flex-none text-gray-400" />
                  <span className="text-card-foreground">{item.title}</span>
                </CommandItem>
              ))}
            </CommandGroup>
          </React.Fragment>
        ))}
      </CommandList>
    </CommandDialog>
  );
}

function getNavGroupsFromSearchResources(resources: SearchResource[]) {
  // ...
}
