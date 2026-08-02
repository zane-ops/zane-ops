import { useQuery } from "@tanstack/react-query";
import { Command as CommandPrimitive } from "cmdk";
import {
  ChevronRightIcon,
  LightbulbIcon,
  LoaderIcon,
  XIcon
} from "lucide-react";
import React from "react";
import { useNavigate } from "react-router";
import type { AuthedUserResponse } from "~/api/types";
import { useResourceActionGroups } from "~/components/commandbar/commandbar-resource-actions";
import {
  getNavItemFromSearchResource,
  getSearchItemValue
} from "~/components/commandbar/commandbar-search";
import { useCommandBarState } from "~/components/commandbar/commandbar-state";
import type {
  CommandBarActionGroup,
  CommandBarNavGroup
} from "~/components/commandbar/commandbar-types";
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
import { userQueries } from "~/lib/queries";
import { cn, excerpt } from "~/lib/utils";

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
  const { data: user } = useQuery({
    ...userQueries.authedUser,
    initialData: authedUser
  });

  const {
    open,
    search,
    setSearch,
    isActionMode,
    selectedResource,
    highlightedValue,
    setHighlightedValue,
    inputRef,
    clearSelectedResource,
    handleOpenChange,
    handleCmdInputKeyDown,
    handleCmdBarKeyDown,
    runCmd,
    searchGroups,
    isLoading,
    isFetching
  } = useCommandBarState();

  const navigationGroups = React.useMemo(
    () => filterGroupsByRole(navGroups, user),
    [navGroups, user]
  );

  const actionModeGroups = React.useMemo(
    () => filterGroupsByRole(actionGroups, user),
    [actionGroups, user]
  );

  const resourceActionGroups = useResourceActionGroups(selectedResource, user);

  const selectedItem = selectedResource
    ? getNavItemFromSearchResource(selectedResource)
    : null;

  // the resource context & the action mode both render `CommandBarActionGroup`s
  const commandActionsGroups = selectedResource
    ? resourceActionGroups
    : isActionMode
      ? actionModeGroups
      : [];

  const navigate = useNavigate();

  if (!user?.user) return null;

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
        onKeyDown: handleCmdBarKeyDown,
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
            onKeyDown={handleCmdInputKeyDown}
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
                    runCmd(() => {
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
                    onSelect={() => runCmd(() => navigate(item.href))}
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
                      onSelect={() => runCmd(() => navigate(item.href))}
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
