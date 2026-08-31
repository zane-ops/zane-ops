import { useQuery } from "@tanstack/react-query";
import { Command as CommandPrimitive } from "cmdk";
import {
  ChevronRightIcon,
  LightbulbIcon,
  LoaderIcon,
  XIcon
} from "lucide-react";
import React from "react";
import { href, useFetcher, useNavigate } from "react-router";
import type { AuthedUserResponse } from "~/api/types";
import { useResourceActionGroups } from "~/components/commandbar/commandbar-resource-actions";
import {
  getNavItemFromSearchResource,
  getSearchItemKeywords
} from "~/components/commandbar/commandbar-search";
import { useCommandBarState } from "~/components/commandbar/commandbar-state";
import type {
  CommandBarActionGroup,
  CommandBarNavGroup
} from "~/components/commandbar/commandbar-types";
import { filterGroupsByRole } from "~/components/commandbar/commandbar-utils";
import { CommandBarWorkspaceList } from "~/components/commandbar/commandbar-workspace-list";
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
import { cn } from "~/lib/utils";

export type CommandBarProps = {
  navGroups?: CommandBarNavGroup[];
  actionGroups?: CommandBarActionGroup[];
  authedUser?: AuthedUserResponse | null;
};

const logger = createDevLogger(import.meta.url);

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
    view,
    exitView,
    highlightedValue,
    setHighlightedValue,
    inputRef,
    handleOpenChange,
    handleCmdInputKeyDown,
    handleCmdBarKeyDown,
    runCmd,
    searchGroups,
    isSearchingResources
  } = useCommandBarState();

  const navigationGroups = React.useMemo(
    () => filterGroupsByRole(navGroups, user),
    [navGroups, user]
  );

  const actionViewGroups = React.useMemo(
    () => filterGroupsByRole(actionGroups, user),
    [actionGroups, user]
  );

  const resourceActionGroups = useResourceActionGroups(
    view.type === "resource" ? view.resource : null,
    user
  );

  const selectedItem =
    view.type === "resource"
      ? getNavItemFromSearchResource(view.resource)
      : null;

  // the resource & the action views both render `CommandBarActionGroup`s
  const commandActionsGroups =
    view.type === "resource"
      ? resourceActionGroups
      : view.type === "action"
        ? actionViewGroups
        : [];

  const navigate = useNavigate();
  // this fetcher lives in `CommandBar` & not in the list, so the submission
  // isn't cancelled when the dialog closes right after selecting a workspace
  const { submit } = useFetcher();

  if (!user?.user) return null;

  const actionViewHint = (
    <div className="inline-flex items-center gap-1 text-muted-foreground">
      <LightbulbIcon className="size-3 flex-none" />
      <span>Type</span>
      <kbd className="rounded-sm px-1  font-mono bg-muted">{">"}</kbd>
      <span>To Open Action Mode</span>
    </div>
  );

  const resourceViewHint = (
    <div className="inline-flex items-center gap-1 whitespace-nowrap text-muted-foreground">
      <LightbulbIcon className="size-3 flex-none" />
      <span>Press</span>
      <kbd className="rounded-sm px-1  font-mono bg-muted">escape</kbd>
      <span>to deselect item</span>
    </div>
  );

  const workspaceViewHint = (
    <div className="inline-flex items-center gap-1 whitespace-nowrap text-muted-foreground">
      <LightbulbIcon className="size-3 flex-none" />
      <span>Press</span>
      <kbd className="rounded-sm px-1  font-mono bg-muted">escape</kbd>
      <span>to exit workspace switch</span>
    </div>
  );

  logger.scope("CommandBar").info({
    highlightedValue
  });

  const commandListRef =
    React.useRef<React.ComponentRef<typeof CommandPrimitive.List>>(null);

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
        filter(value, query, keywords) {
          let search = query;
          if (query.startsWith(">")) {
            search = query.substring(1);
          }
          search = search.trim().toLowerCase();
          if (!search) return 1;

          // `value` is the item's `id`, so match against its `keywords`
          // (title, group, parents...) instead
          const haystack = [value, ...(keywords ?? [])].join(" ").toLowerCase();
          return haystack.includes(search) ? 1 : 0;
        }
      }}
    >
      <div className="flex flex-col gap-1 pt-3 px-3 items-start">
        <Button
          type="button"
          size="xs"
          variant="outline"
          className={cn(
            "text-xs gap-1.5",
            (selectedItem || view.type === "workspace") && "pr-1"
          )}
          onClick={() => {
            if (view.type === "resource" || view.type === "workspace") {
              exitView();
              inputRef.current?.focus();
            }
          }}
        >
          {selectedItem ? (
            <>
              <span className="inline-flex items-center gap-1">
                <selectedItem.icon className="size-3 flex-none text-grey" />
                <div className="inline-flex items-center gap-0 5">
                  {selectedItem.parents.map((parent, idx) => (
                    <React.Fragment key={idx}>
                      <span>{parent}</span>
                      <ChevronRightIcon className="size-3 flex-none text-grey" />
                    </React.Fragment>
                  ))}
                  {selectedItem.title}
                </div>
              </span>
              <XIcon className="size-3 flex-none" />
            </>
          ) : view.type === "workspace" ? (
            <>
              <span>Switch workspace</span>
              <XIcon className="size-3 flex-none" />
            </>
          ) : view.type === "action" ? (
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
                : view.type === "workspace"
                  ? "Search workspaces..."
                  : "Search pages, resources, actions..."
            }
            className="text-base bg-inherit focus-visible:outline-hidden px-2 w-full grow"
            value={search}
            ref={inputRef}
            onValueChange={(value) => {
              setSearch(value);
              setTimeout(() => {
                commandListRef.current?.scrollTo({
                  top: 0,
                  behavior: "instant"
                });
              });
            }}
          />
        </div>
      </div>

      <CommandPrimitive.List
        ref={commandListRef}
        className={cn(
          "bg-popover rounded-md border border-border overflow-y-auto overflow-x-hidden",
          "max-h-124 min-h-0 h-[calc(var(--cmdk-list-height)+var(--spacing)*3)] ",
          "scroll-py-2",
          "transition-[height] duration-200 ease-in-out",
          "rounded-t-none border-x-0 border-b-0 px-0 py-1"
        )}
      >
        <CommandEmpty>
          {isSearchingResources ? (
            <div className="flex items-center gap-2 w-full justify-center">
              Searching...
              <LoaderIcon className="size-4 flex-none text-grey animate-spin" />
            </div>
          ) : (
            "No results"
          )}
        </CommandEmpty>

        {view.type === "home" && (
          <CommandGroup
            heading={actionViewHint}
            className="[&_[cmdk-group-heading]]:text-xs overflow-visible"
          />
        )}

        {view.type === "resource" && (
          <CommandGroup
            heading={resourceViewHint}
            className="[&_[cmdk-group-heading]]:text-xs overflow-visible"
          />
        )}

        {view.type === "workspace" && (
          <>
            <CommandGroup
              heading={workspaceViewHint}
              className="[&_[cmdk-group-heading]]:text-xs overflow-visible"
            />
            <CommandBarWorkspaceList
              onSelectWorkspace={(workspaceId) =>
                runCmd(() =>
                  submit(
                    { workspace_id: workspaceId },
                    { method: "post", action: href("/switch-workspace") }
                  )
                )
              }
            />
          </>
        )}

        {/* Actions for a selected item/Global actions */}
        {commandActionsGroups.map((group, groupIndex) => (
          <React.Fragment key={group.heading}>
            {groupIndex > 0 && <CommandSeparator />}
            <CommandGroup
              heading={group.heading}
              className={cn(
                "[&_[cmdk-group-heading]]:py-2 [&_[cmdk-group-heading]]:text-xs",
                "pb-3 !px-2",
                groupIndex > 0 && "[&_[cmdk-group-heading]]:pt-3"
              )}
            >
              {group.items.map((action) => (
                <CommandItem
                  key={action.id}
                  value={action.id}
                  keywords={[action.title, group.heading]}
                  onSelect={() =>
                    runCmd(
                      () => {
                        // both can be set: `onSelect` runs the action &
                        // `href` is where the user lands afterwards
                        action.onSelect?.();
                        if (action.href) {
                          navigate(action.href);
                        }
                      },
                      { keepOpen: action.keepOpen }
                    )
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
        {view.type === "home" &&
          navigationGroups.map((group, groupIndex) => (
            <React.Fragment key={group.heading}>
              {groupIndex > 0 && <CommandSeparator />}
              <CommandGroup
                heading={group.heading}
                className={cn(
                  "[&_[cmdk-group-heading]]:py-2 [&_[cmdk-group-heading]]:text-xs",
                  groupIndex !== 0 && "[&_[cmdk-group-heading]]:pt-3",
                  "pb-2 !px-2"
                )}
              >
                {group.items.map((item) => (
                  <CommandItem
                    key={item.id}
                    value={item.id}
                    keywords={[item.title, group.heading]}
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
        {view.type === "home" &&
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
                      key={item.id}
                      value={item.id}
                      keywords={getSearchItemKeywords(item)}
                      onSelect={() => runCmd(() => navigate(item.href))}
                      className={cn(
                        "h-9 flex items-center gap-2 px-0",
                        "aria-selected:*:data-[slot=kbd-shortcuts]:inline-block"
                      )}
                    >
                      <item.icon className="flex-none text-grey size-4" />
                      <div className="inline-flex gap-0.5 items-baseline w-full">
                        <div className="inline-flex gap-0.5 items-baseline max-w-50">
                          {item.parents.map((parent, index) => (
                            <React.Fragment key={`${parent}-${index}`}>
                              <p
                                className={cn(
                                  "text-grey whitespace-nowrap",
                                  index === item.parents.length - 1 &&
                                    "overflow-ellipsis overflow-x-hidden"
                                )}
                              >
                                {parent}
                              </p>
                              <ChevronRightIcon className="size-4 flex-none text-grey relative top-1" />
                            </React.Fragment>
                          ))}
                        </div>
                        <p className="text-card-foreground font-medium whitespace-nowrap">
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
      </CommandPrimitive.List>
    </CommandDialog>
  );
}
