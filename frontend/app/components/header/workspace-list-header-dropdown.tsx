import { useQuery } from "@tanstack/react-query";
import { CheckIcon, ChevronsUpDownIcon } from "lucide-react";
import type * as React from "react";
import { Link, href, useFetcher, useParams } from "react-router";
import type { WorkspaceMembership } from "~/api/types";
import { StatusBadge } from "~/components/status-badge";
import { Button } from "~/components/ui/button";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuGroup,
  DropdownMenuItem,
  DropdownMenuLabel,
  DropdownMenuTrigger
} from "~/components/ui/dropdown-menu";
import { userQueries } from "~/lib/queries";

import { cn } from "~/lib/utils";
import type { clientAction } from "~/routes/switch-workspace";
import { stringToColor } from "~/utils";

export type WorkspaceMembershipListProps = {
  memberships: WorkspaceMembership[];
};

export function WorkspaceMembershipListHeaderDropdown({
  ...props
}: WorkspaceMembershipListProps) {
  const params = useParams<{ workspaceId: string }>();

  const workspaceId = params.workspaceId;

  const current = props.memberships.find((m) => m.workspace.id === workspaceId);

  const { data } = useQuery({
    ...userQueries.memberships,
    initialData: props.memberships
  });

  const fetcher = useFetcher<typeof clientAction>();

  if (!workspaceId || !current) return null;

  const memberships = data ?? [];
  const workspaceColor = stringToColor(current.workspace.name);

  return (
    <div className="inline-flex items-center gap-1">
      <fetcher.Form
        method="post"
        action={href("/switch-workspace")}
        id="switch-workspace-form"
        className="hidden"
      />
      <Button
        variant="ghost"
        asChild
        className="inline-flex gap-1.5 py-1 px-2 rounded-sm text-sm h-8"
      >
        <Link to={href("/:workspaceId", { workspaceId })}>
          <div
            style={
              {
                "--color-light": workspaceColor.light,
                "--color-dark": workspaceColor.dark
              } as React.CSSProperties
            }
            className={cn(
              "size-6 flex-none rounded-md flex items-center justify-center",
              "text-[var(--color-light)] dark:text-[var(--color-dark)]",
              "bg-[var(--color-light)]/10 dark:bg-[var(--color-dark)]/10",
              "border  border-[var(--color-light)]/10 dark:border-[var(--color-dark)]/10"
            )}
          >
            <span>{current.workspace.name.charAt(0).toUpperCase()}</span>
          </div>
          <p className="whitespace-nowrap text-foreground hidden lg:block">
            {current.workspace.name}
          </p>
          <StatusBadge
            pingState="hidden"
            className="py-0.5 px-1.5 text-xs hidden lg:inline-flex"
          >
            {current.role_name}
          </StatusBadge>
        </Link>
      </Button>
      <DropdownMenu>
        <DropdownMenuTrigger asChild>
          <Button
            variant="ghost"
            className="inline-flex justify-center items-center gap-2 p-1 h-8 w-6"
          >
            <ChevronsUpDownIcon className="size-3.5 flex-none my-auto text-grey" />
          </Button>
        </DropdownMenuTrigger>

        <DropdownMenuContent
          align="start"
          alignOffset={0}
          className="border min-w-0 border-border rounded-lg"
        >
          <DropdownMenuGroup className="px-0.5">
            <DropdownMenuLabel>Workspaces</DropdownMenuLabel>
            {memberships.map((m) => {
              const color = stringToColor(m.workspace.name);
              return (
                <DropdownMenuItem
                  key={m.id}
                  className="flex items-start gap-2 py-2 pl-2.5 pr-3"
                  asChild
                  disabled={fetcher.state !== "idle"}
                >
                  <button
                    form="switch-workspace-form"
                    type="submit"
                    name="workspace_id"
                    value={m.workspace.id}
                    className="w-full"
                    style={
                      {
                        "--color-light": color.light,
                        "--color-dark": color.dark
                      } as React.CSSProperties
                    }
                  >
                    <div
                      className={cn(
                        "size-6 flex-none rounded-md flex items-center justify-center",
                        "text-[var(--color-light)] dark:text-[var(--color-dark)]",
                        "bg-[var(--color-light)]/10 dark:bg-[var(--color-dark)]/10",
                        "border border-[var(--color-light)]/10 dark:border-[var(--color-dark)]/10"
                      )}
                    >
                      <span>{m.workspace.name.charAt(0).toUpperCase()}</span>
                    </div>

                    <div className="flex items-start gap-8 justify-between w-full">
                      <div className="flex flex-col mr-2 items-start gap-0.5">
                        <span className="font-medium">{m.workspace.name}</span>
                        <StatusBadge
                          pingState="hidden"
                          className="py-0.5 px-1.5 text-xs"
                        >
                          {m.role_name}
                        </StatusBadge>
                      </div>

                      <span className="flex size-4 items-center justify-center ml-auto flex-none py-2.5">
                        {m.id === current.id && (
                          <CheckIcon className="size-full text-teal-600 dark:text-teal-400" />
                        )}
                      </span>
                    </div>
                  </button>
                </DropdownMenuItem>
              );
            })}
          </DropdownMenuGroup>
        </DropdownMenuContent>
      </DropdownMenu>
    </div>
  );
}
