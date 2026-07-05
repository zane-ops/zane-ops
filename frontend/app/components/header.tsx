import { useQuery } from "@tanstack/react-query";
import {
  Building2Icon,
  CheckIcon,
  ChevronsUpDownIcon,
  CommandIcon,
  LogOutIcon,
  SearchIcon,
  ServerIcon,
  SettingsIcon
} from "lucide-react";
import type * as React from "react";
import { Link, href, useFetcher, useNavigate } from "react-router";
import type { AuthedUserResponse, WorkspaceMembership } from "~/api/types";
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
  user: AuthedUserResponse;
  memberships: WorkspaceMembership[];
};

export function Header({ user, memberships }: HeaderProps) {
  //   const [sheetOpen, setSheetOpen] = React.useState(false);

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

        {/* <div className="relative top-0.5 h-5 w-[2px] bg-grey/30 rounded-md rotate-15"></div>

        <span className="flex justify-center items-center gap-2 p-1 text-sm font-medium">
          <p className="whitespace-nowrap">Workspaces</p>
        </span> */}

        <div className="relative top-0.5 h-5 w-[2px] bg-grey/30 rounded-md rotate-15"></div>

        {user.membership && memberships && (
          <WorkspaceMembershipList
            current={user.membership}
            memberships={memberships}
          />
        )}

        <div className="flex grow  w-full items-center"></div>

        {/* <div className="flex items-center gap-2 "> */}
        <Button
          variant="outline"
          className="pl-3 pr-4 py-1 rounded-lg text-grey border-grey/20 gap-2"
        >
          <SearchIcon className="size-4 flex-none" />
          <span>Search for projects, services...</span>
          &nbsp;
          <span className="font-mono px-1.5 gap-0.5 inline-flex items-center bg-muted rounded-md py-0.5 text-foreground">
            <CommandIcon className="size-4 flex-none" /> K
          </span>
        </Button>

        <UserDropdown user={user} />
        {/* </div> */}

        {/** Mobile */}
        {/* <div className="md:hidden block">
          <Sheet open={sheetOpen} onOpenChange={setSheetOpen}>
            <SheetTrigger>
              <Menu />
            </SheetTrigger>
            <SheetContent className="border flex rounded-xl  flex-col gap-5 w-full h-[calc(100dvh-100px)] border-border">
              <SheetHeader>
                <div className="absolute w-full top-3.5">
                  <div className="flex justify-between w-[78%] items-center">
                    <Link to="/">
                      <ThemedLogo className="w-10 flex-none h-10 mr-8" />
                    </Link>
                  </div>
                </div>
              </SheetHeader>
              <div className="flex mt-14 flex-col gap-3">
                <CommandMenuSearchbar onSelect={() => setSheetOpen(false)} />

                <div className="flex items-center  w-full">
                  <SheetClose asChild>
                    <Button
                      asChild
                      className="flex w-full justify-between text-sm items-center gap-1"
                    >
                      <Link to="/create-project">Create Project</Link>
                    </Button>
                  </SheetClose>
                </div>
              </div>

              <div className="flex flex-col">
                <div className="flex justify-between px-2 py-3 items-center border-b border-border">
                  <p>{user.username}</p>
                  <CircleUser className="w-8 opacity-70" />
                </div>

                <SheetClose asChild>
                  <Link
                    to={href("/settings")}
                    className="flex items-center gap-1 p-2 hover:bg-muted transition rounded-md"
                  >
                    <SettingsIcon size={15} />
                    <span>Settings</span>
                  </Link>
                </SheetClose>
              </div>

              <SheetClose asChild>
                <Button
                  type="submit"
                  form="logout-form"
                  variant="outline"
                  className="p-2 border text-red-400 hover:text-red-500 hover:bg-muted"
                  disabled={fetcher.state !== "idle"}
                >
                  {fetcher.state !== "idle" ? (
                    "Logging out..."
                  ) : (
                    <div>Log Out</div>
                  )}
                </Button>
              </SheetClose>
            </SheetContent>
          </Sheet>
        </div> */}
      </header>
    </>
  );
}

export type WorkspaceMembershipListProps = {
  current: WorkspaceMembership;
  memberships: WorkspaceMembership[];
};

function WorkspaceMembershipList({
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
            {memberships.map((m) => (
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
                  onClick={(e) => {
                    e.currentTarget.form?.requestSubmit();
                  }}
                >
                  <div
                    className={cn(
                      "size-6 flex-none rounded-md flex items-center justify-center"
                    )}
                  >
                    <Building2Icon className="!size-4 flex-none" />
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
            ))}
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
                navigate("/settings");
              }}
            >
              <SettingsIcon />
              Settings
            </DropdownMenuItem>
            {user.is_superuser && (
              <DropdownMenuItem
                className="my-2"
                onClick={() => {
                  navigate("/admin");
                }}
              >
                <ServerIcon />
                Server Admin
              </DropdownMenuItem>
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
