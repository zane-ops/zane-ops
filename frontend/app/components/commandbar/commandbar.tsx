import { Command as CommandPrimitive } from "cmdk";
import * as React from "react";
import type { WorkspaceRoleName } from "~/api/types";
import { useCommandBarStore } from "~/components/commandbar/commandbar-store";
import {
  CommandDialog,
  CommandEmpty,
  CommandList
} from "~/components/ui/command";
import { createDevLogger } from "~/lib/logger";
import { isEditableTarget } from "~/lib/utils";

const logger = createDevLogger(import.meta.url);

export type CommandBarNavGroup = {
  heading: string;
  items: CommandBarNavItem[];
};

export type CommandBarNavItem = {
  href?: string;
  title: string;
  icon?: React.ReactNode;
  showInEE?: boolean;
  minRole?: WorkspaceRoleName | "ServerAdmin";
};

export type CommandBarAction = {
  id: string;
  title: string;
  icon: React.ReactNode;
  href?: string;
  onSelect?: () => void;
};

export type CommandBarProps = {
  navItems: CommandBarNavGroup[];
};

export function CommandBar({ navItems = [] }: CommandBarProps) {
  const { open, setOpen, toggle } = useCommandBarStore();

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

  const [search, setSearch] = React.useState("");

  const isActionMode = search.startsWith(">");

  const handleOpenChange = React.useCallback(
    (nextOpen: boolean) => {
      setOpen(nextOpen);
      if (!nextOpen) {
        setSearch("");
      }
    },
    [setOpen]
  );

  const runCommand = React.useCallback(
    (command: () => void) => {
      setOpen(false);
      setSearch("");
      command();
    },
    [setOpen]
  );

  return (
    <CommandDialog
      open={open}
      onOpenChange={handleOpenChange}
      className="max-w-2xl **:data-[slot=command-input-wrapper]:h-15"
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
      <CommandPrimitive.Input
        placeholder="Search resources"
        value={search}
        onValueChange={setSearch}
      />

      <CommandList className="max-h-118 min-h-0  h-(--cmdk-list-height) scroll-pb-4 scroll-pt-2 transition-[height] duration-250 ease-in-out">
        <CommandEmpty>No results</CommandEmpty>
      </CommandList>
    </CommandDialog>
  );
}
