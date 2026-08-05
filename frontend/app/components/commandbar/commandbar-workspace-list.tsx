import { useQuery } from "@tanstack/react-query";
import type * as React from "react";
import { CommandGroup, CommandItem } from "~/components/ui/command";
import { WorkspaceRoleBadge } from "~/components/workspace-role-badge";
import { userQueries } from "~/lib/queries";
import { cn, stringToColor } from "~/lib/utils";
import { useWorkspaceMembershipStore } from "~/lib/workspace-store";

export type CommandBarWorkspaceListProps = {
  onSelectWorkspace: (workspaceId: string) => void;
};

/**
 * The list shown in `workspace-switch` mode, the workspace the user is
 * already in is left out since selecting it would be a no-op.
 */
export function CommandBarWorkspaceList({
  onSelectWorkspace
}: CommandBarWorkspaceListProps) {
  const currentMembership = useWorkspaceMembershipStore((s) => s.membership);
  const { data } = useQuery(userQueries.memberships);

  const memberships = (data ?? []).filter(
    (membership) => membership.id !== currentMembership?.id
  );

  return (
    <CommandGroup
      heading="Switch to"
      className={cn(
        "[&_[cmdk-group-heading]]:py-2 [&_[cmdk-group-heading]]:text-xs",
        "pb-2 !px-2"
      )}
    >
      {memberships.map((membership) => {
        const color = stringToColor(membership.workspace.name);
        return (
          <CommandItem
            key={membership.id}
            value={membership.workspace.name}
            onSelect={() => onSelectWorkspace(membership.workspace.id)}
            className="flex items-center gap-2 px-0 py-2 h-9"
            style={
              {
                "--color-light": color.light,
                "--color-dark": color.dark
              } as React.CSSProperties
            }
          >
            <div
              className={cn(
                "size-5 flex-none rounded-md flex items-center justify-center",
                "text-(--color-light) dark:text-(--color-dark)",
                "bg-(--color-light)/10 dark:bg-(--color-dark)/10",
                "border border-(--color-light)/10 dark:border-(--color-dark)/10"
              )}
            >
              <span className="text-xs">
                {membership.workspace.name.charAt(0).toUpperCase()}
              </span>
            </div>

            <div className="flex items-center gap-1 min-w-0">
              <span className="font-medium text-card-foreground truncate">
                {membership.workspace.name}
              </span>
              <WorkspaceRoleBadge size="sm" role={membership.role_name} />
            </div>
          </CommandItem>
        );
      })}
    </CommandGroup>
  );
}
