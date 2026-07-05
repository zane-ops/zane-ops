import { useQuery } from "@tanstack/react-query";
import {
  Building2Icon,
  CheckIcon,
  ChevronsUpDownIcon,
  CommandIcon,
  LogOutIcon,
  SearchIcon,
  ServerIcon,
  SettingsIcon,
  UserIcon
} from "lucide-react";
import type * as React from "react";
import { Link, href, useFetcher, useNavigate } from "react-router";
import type { AuthedUserResponse, WorkspaceMembership } from "~/api/types";
import { CommandBarTrigger } from "~/components/commandbar/commandbar-trigger";
import { ThemedLogo } from "~/components/logo";
import { StatusBadge } from "~/components/status-badge";
import { Button } from "~/components/ui/button";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuGroup,
  DropdownMenuItem,
  DropdownMenuLabel,
  DropdownMenuSeparator,
  DropdownMenuTrigger
} from "~/components/ui/dropdown-menu";
import { userQueries } from "~/lib/queries";

import { cn } from "~/lib/utils";
import type { clientAction } from "~/routes/switch-workspace";
import { stringToColor } from "~/utils";

type HeaderProps = {
  leftSlot?: React.ReactNode;
  rigthSlot?: React.ReactNode;
};

export function Header({ leftSlot, rigthSlot }: HeaderProps) {
  return (
    <>
      {!import.meta.env.PROD && (
        <div
          className={cn(
            "py-0.5 bg-red-500 text-white text-center fixed top-0 left-0 right-0  z-49",
            "w-full"
          )}
        >
          <p className="">⚠️ YOU ARE IN DEV ⚠️</p>
        </div>
      )}

      <header
        className={cn(
          "flex px-6 py-4 items-center gap-4",
          "border-b border-opacity-65 border-border bg-toggle justify-between sticky top-0 z-60",
          !import.meta.env.PROD && "top-7"
        )}
      >
        <Link to="/">
          <ThemedLogo className="flex-none size-10 mr-3" />
        </Link>

        {leftSlot && (
          <div className="relative top-0.5 h-5 w-[2px] bg-grey/30 rounded-md rotate-15" />
        )}

        {leftSlot}

        <div className="flex grow  w-full items-center"></div>

        {rigthSlot}
      </header>
    </>
  );
}

export type WorkspaceMembershipListProps = {
  current: WorkspaceMembership;
  memberships: WorkspaceMembership[];
};

export function WorkspaceMembershipList({
  current,
  ...props
}: WorkspaceMembershipListProps) {
  const workspaceColor = stringToColor(current.workspace.name);

  const { data } = useQuery({
    ...userQueries.memberships,
    initialData: props.memberships
  });
  const memberships = data ?? [];

  const fetcher = useFetcher<typeof clientAction>();

  return (
    <>
      <fetcher.Form
        method="post"
        action={href("/switch-workspace")}
        id="switch-workspace-form"
        className="hidden"
      />
      <DropdownMenu>
        <DropdownMenuTrigger className="flex justify-center items-center gap-2 p-1">
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
            {/* <Building2Icon className="size-4 flex-none" /> */}
            <span>{current.workspace.name.charAt(0).toUpperCase()}</span>
          </div>
          <p className="whitespace-nowrap text-foreground">
            {current.workspace.name}
          </p>
          <ChevronsUpDownIcon className="size-3.5 flex-none my-auto text-grey" />
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
                        <CheckIcon className="size-full text-teal-600" />
                      )}
                    </span>
                  </button>
                </DropdownMenuItem>
              );
            })}
          </DropdownMenuGroup>
        </DropdownMenuContent>
      </DropdownMenu>
    </>
  );
}

export type UserDropdownProps = {
  user: AuthedUserResponse;
};

function getUserDisplayName(user: AuthedUserResponse["user"]) {
  return user.first_name.trim() ? user.first_name : user.username;
}

export function UserDropdown(props: UserDropdownProps) {
  const fetcher = useFetcher();
  const navigate = useNavigate();

  const { data } = useQuery({
    ...userQueries.authedUser,
    initialData: props.user
  });

  if (!data?.user) return null;

  const user = data.user;

  return (
    <>
      <fetcher.Form
        method="post"
        action={href("/logout")}
        id="logout-form"
        className="hidden"
      />
      <DropdownMenu>
        <DropdownMenuTrigger className="flex justify-center items-center gap-2 p-0 rounded-full">
          <div
            className={cn(
              "size-10 flex-none rounded-full flex items-center justify-center",
              "text-card-foreground bg-grey/10 border border-grey/20"
            )}
          >
            <p>{getUserDisplayName(user).charAt(0).toUpperCase()}</p>
          </div>
        </DropdownMenuTrigger>
        <DropdownMenuContent
          className="border border-border min-w-42 rounded-lg"
          align="end"
          alignOffset={-5}
        >
          <DropdownMenuGroup className="px-0.5">
            <DropdownMenuLabel className="flex flex-col">
              <span className="text-sm text-foreground">
                {getUserDisplayName(user)}
              </span>
              <span>{user.username}</span>
            </DropdownMenuLabel>
          </DropdownMenuGroup>
          <DropdownMenuSeparator className="my-1.5" />
          <DropdownMenuGroup>
            <DropdownMenuItem
              className="my-2"
              onClick={() => {
                navigate("/account");
              }}
            >
              <UserIcon />
              Account
            </DropdownMenuItem>
            <DropdownMenuItem
              className="my-2"
              onClick={() => {
                navigate("/settings");
              }}
            >
              <SettingsIcon />
              Settings
            </DropdownMenuItem>
            {user.is_superuser && (
              <>
                <DropdownMenuSeparator className="my-1.5" />
                <DropdownMenuItem
                  className="my-2"
                  onClick={() => {
                    navigate("/admin");
                  }}
                >
                  <ServerIcon />
                  Server Admin
                </DropdownMenuItem>
              </>
            )}
            <DropdownMenuSeparator className="my-1.5" />
            <DropdownMenuItem
              variant="destructive"
              disabled={fetcher.state !== "idle"}
              className="whitespace-nowrap"
              onClick={() => fetcher.submit(new FormData())}
              asChild
            >
              <button
                form="logout-form"
                type="submit"
                className="w-full"
                onClick={(e) => {
                  e.currentTarget.form?.requestSubmit();
                }}
              >
                <LogOutIcon />
                Log out
              </button>
            </DropdownMenuItem>
          </DropdownMenuGroup>
        </DropdownMenuContent>
      </DropdownMenu>
    </>
  );
}
