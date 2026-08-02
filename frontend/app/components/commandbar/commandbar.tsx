import { useQuery } from "@tanstack/react-query";
import { Command as CommandPrimitive } from "cmdk";
import {
  ChevronRightIcon,
  LightbulbIcon,
  LoaderIcon,
  type LucideIcon,
  XIcon
} from "lucide-react";
import React from "react";
import { useNavigate } from "react-router";
import { useDebounce } from "use-debounce";
import type { AuthedUserResponse, SearchResource, UserRole } from "~/api/types";
import { useResourceActionGroups } from "~/components/commandbar/commandbar-resource-actions";
import {
  getNavItemFromSearchResource,
  getSearchItemValue,
  useCommandBarSearch
} from "~/components/commandbar/commandbar-search";
import { useCommandBarStore } from "~/components/commandbar/commandbar-store";
import { filterGroupsByRole } from "~/components/commandbar/commandbar-utils";
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
import { userQueries } from "~/lib/queries";
import { cn, excerpt, isEditableTarget } from "~/lib/utils";

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
  /** where to navigate to, runs after `onSelect` when both are set */
  href?: string;
  onSelect?: () => void;
  minRole?: UserRole;
};

export type CommandBarActionGroup = {
  heading: string;
  items: CommandBarAction[];
  minRole?: UserRole;
};

export type CommandBarProps = {
  navGroups?: CommandBarNavGroup[];
  actionGroups?: CommandBarActionGroup[];
  authedUser?: AuthedUserResponse | null;
};

export function CommandBar({
  navGroups = [],
  actionGroups = [],
  authedUser
}: CommandBarProps) {
  const { open, setOpen, toggle } = useCommandBarStore();
  const [search, setSearch] = React.useState("");

  const { data } = useQuery({
    ...userQueries.authedUser,
    initialData: authedUser
  });

  const [debouncedValue] = useDebounce(search, 150);
  const isActionMode = search.startsWith(">");

  const [selectedResource, setSelectedResource] =
    React.useState<SearchResource | null>(null);

  const { searchGroups, searchItemsByValue, isLoading, isFetching } =
    useCommandBarSearch({
      search,
      debouncedSearch: debouncedValue,
      isOpen: open,
      isPaused: isActionMode || selectedResource !== null
    });

  const navigationGroups = React.useMemo(
    () => filterGroupsByRole(navGroups, data),
    [navGroups, data]
  );

  const actionModeGroups = React.useMemo(
    () => filterGroupsByRole(actionGroups, data),
    [actionGroups, data]
  );

  const selectedItem = selectedResource
    ? getNavItemFromSearchResource(selectedResource)
    : null;

  const resourceActionGroups = useResourceActionGroups(selectedResource, data);

  // the resource context & the action mode both render `CommandBarActionGroup`s
  const commandActionsGroups = selectedResource
    ? resourceActionGroups
    : isActionMode
      ? actionModeGroups
      : [];

  /** the value of the item currently highlighted in the list */
  const [highlightedValue, setHighlightedValue] = React.useState("");

  const clearSelectedResource = React.useCallback(() => {
    setSearch("");
    setSelectedResource(null);
  }, []);

  const handleOpenChange = React.useCallback(
    (nextOpen: boolean) => {
      logger
        .scope("CommandBar", "handleOpenChange")
        .info({ selectedResource, nextOpen });

      if (!nextOpen && selectedResource) return;

      if (!nextOpen) clearSelectedResource();

      setOpen(nextOpen);
    },
    [setOpen, selectedResource]
  );

  const handleInputKeyDown = React.useCallback(
    (ev: React.KeyboardEvent<HTMLDivElement>) => {
      // `Tab` selects whatever is highlighted if found
      if (ev.key === "Tab") {
        const item = searchItemsByValue.get(highlightedValue);

        logger
          .scope("handleInputKeyDown")
          .info({ highlightedValue, item, searchItemsByValue });

        ev.preventDefault();
        ev.stopPropagation();

        if (!item) return;

        setSearch("");
        setSelectedResource(item.resource);
      }
    },
    [searchItemsByValue, highlightedValue]
  );

  const handleCommandBarKeyDown = React.useCallback(
    (event: React.KeyboardEvent<HTMLDivElement>) => {
      // `escape` clears the context first, it only closes the dialog
      // once there is nothing left to clear
      logger
        .scope("CommandBar", "handleCommandBarKeyDown")
        .info({ selectedResource, "event.key": event.key });

      if (event.key === "Escape" && selectedResource) {
        event.preventDefault();
        event.stopPropagation();

        clearSelectedResource();
      }
    },
    [selectedResource]
  );

  const navigate = useNavigate();

  const runCommand = React.useCallback(
    (command: () => void) => {
      command();
      setOpen(false);
      clearSelectedResource();
    },
    [setOpen, clearSelectedResource]
  );

  const inputRef = React.useRef<React.ComponentRef<"input">>(null);

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

  const selectedItemContextHint = (
    <div className="inline-flex items-center gap-1 whitespace-nowrap text-muted-foreground">
      <LightbulbIcon className="size-3 flex-none" />
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
        value: highlightedValue,
        onValueChange: setHighlightedValue,
        onKeyDown: handleCommandBarKeyDown,
        filter(value, query) {
          let search = query;
          if (query.startsWith(">")) {
            search = query.substring(1);
          }

          if (value.toLowerCase().includes(search.trim().toLowerCase())) {
            return 1;
          }
          return 0;
        }
      }}
    >
      <div className="flex flex-col gap-1 pt-3 px-3 items-start">
        <Button
          type="button"
          size="xs"
          variant="outline"
          className={cn("text-xs gap-1.5", selectedItem && "pr-1")}
          onClick={() => {
            if (selectedItem) {
              clearSelectedResource();
              inputRef.current?.focus();
            }
          }}
        >
          {selectedItem ? (
            <>
              <span className="inline-flex items-center gap-1">
                <selectedItem.icon className="size-3 flex-none text-grey" />
                <div className="inline-flex items-center gap-0 5">
                  <span className="capitalize">
                    {selectedResource?.type.replace("_", " ") + "s"}
                  </span>
                  <ChevronRightIcon className="size-3 flex-none text-grey" />
                  {selectedItem.title}
                </div>
              </span>
              <XIcon className="size-3 flex-none" />
            </>
          ) : isActionMode ? (
            "Action mode"
          ) : (
            "Home"
          )}
        </Button>
        <div className="flex items-center gap-1 w-full px-0">
          <CommandPrimitive.Input
            autoFocus
            onKeyDown={handleInputKeyDown}
            placeholder={
              selectedItem
                ? `Search actions for ${selectedItem.title}...`
                : "Search pages, resources, actions..."
            }
            className="text-base bg-inherit focus-visible:outline-hidden px-2 w-full grow"
            value={search}
            ref={inputRef}
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

        {!isActionMode && !selectedResource && (
          <CommandGroup
            heading={actionModeHint}
            className="[&_[cmdk-group-heading]]:text-xs overflow-visible"
          />
        )}

        {selectedResource && (
          <CommandGroup
            heading={selectedItemContextHint}
            className="[&_[cmdk-group-heading]]:text-xs overflow-visible"
          />
        )}

        {/* Actions for a selected item/Global actions */}
        {commandActionsGroups.map((group, groupIndex) => (
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
              {group.items.map((action) => (
                <CommandItem
                  key={action.id}
                  value={`${action.title} ${group.heading}`}
                  onSelect={() =>
                    runCommand(() => {
                      // both can be set: `onSelect` runs the action &
                      // `href` is where the user lands afterwards
                      action.onSelect?.();
                      if (action.href) {
                        navigate(action.href);
                      }
                    })
                  }
                  className="h-9 flex items-center gap-2 px-0 font-medium"
                >
                  <action.icon className="flex-none text-grey size-4" />
                  <span className="text-card-foreground">{action.title}</span>
                </CommandItem>
              ))}
            </CommandGroup>
          </React.Fragment>
        ))}

        {/* Navigation items */}
        {!isActionMode &&
          !selectedResource &&
          navigationGroups.map((group, groupIndex) => (
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

        {/* Search results */}
        {!isActionMode &&
          !selectedResource &&
          searchGroups.map((group, groupIndex) => {
            const hasContentAbove =
              navigationGroups.length > 0 || groupIndex > 0;

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
                      value={getSearchItemValue(item)}
                      onSelect={() => runCommand(() => navigate(item.href))}
                      className={cn(
                        "h-9 flex items-center gap-2 px-0",
                        "aria-selected:*:data-[slot=kbd-shortcuts]:inline-block"
                      )}
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
                        <p className="text-card-foreground font-medium whitespace-nowrap overflow-ellipsis">
                          {item.title}
                        </p>
                      </div>
                      <div
                        className="whitespace-nowrap hidden text-xs"
                        data-slot="kbd-shortcuts"
                      >
                        <kbd className="rounded-sm px-1  font-mono bg-muted">
                          Enter
                        </kbd>{" "}
                        <span>to jump to</span>
                        <span>&nbsp;&nbsp;</span>
                        <kbd className="rounded-sm px-1  font-mono bg-muted">
                          Tab
                        </kbd>{" "}
                        <span>to select</span>
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
