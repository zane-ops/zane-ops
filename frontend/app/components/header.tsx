import { useQuery } from "@tanstack/react-query";
import {
  Building2Icon,
  CheckIcon,
  ChevronsUpDownIcon,
  CommandIcon,
  LoaderIcon,
  LogOutIcon,
  SearchIcon,
  SettingsIcon,
  UserIcon
} from "lucide-react";
import type * as React from "react";
import { Link, useFetcher, useNavigate } from "react-router";
import type { AuthedUser, WorkspaceMembership } from "~/api/types";
import { ThemedLogo } from "~/components/logo";
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
import { stringToColor } from "~/utils";

type HeaderProps = {
  user: AuthedUser;
  memberships: WorkspaceMembership[];
};

export function Header(props: HeaderProps) {
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
          "flex px-6 py-2 items-center gap-4",
          "border-b border-opacity-65 border-border bg-toggle justify-between sticky top-0 z-60",
          !import.meta.env.PROD && "top-7"
        )}
      >
        <Link to="/">
          <ThemedLogo className="flex-none size-10 mr-3" />
        </Link>

        <div className="relative top-0.5 h-5 w-[2px] bg-grey/30 rounded-md rotate-0"></div>

        {props.user.membership && props.memberships && (
          <>
            <WorkspaceMembershipList
              current={props.user.membership}
              memberships={props.memberships}
            />

            {/* <div className="relative top-0.5 h-5 w-[2px] bg-grey/30 rounded-md rotate-15"></div> */}
          </>
        )}

        <div className="flex grow  w-full items-center">
          {/* <Button asChild>
            <Link to="/create-project" prefetch="intent">
              Create project
            </Link>
          </Button> */}

          {/* <div className="flex mx-2 w-full justify-center items-center">
            <CommandMenuSearchbar />
          </div> */}
        </div>

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
        <UserDropdown user={props.user} />

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

export type UserDropdownProps = {
  user: AuthedUser;
};

export function UserDropdown(props: UserDropdownProps) {
  const fetcher = useFetcher();
  const navigate = useNavigate();

  const { data } = useQuery({
    ...userQueries.authedUser,
    initialData: props.user
  });

  if (!data?.user) return null;

  const userColor = stringToColor(data.user.username);

  return (
    <>
      <fetcher.Form
        method="post"
        action="/logout"
        id="logout-form"
        className="hidden"
      />
      <DropdownMenu>
        <DropdownMenuTrigger className="flex justify-center items-center gap-2 p-0 rounded-full">
          <div
            style={
              {
                "--color-light": userColor.light,
                "--color-dark": userColor.dark
              } as React.CSSProperties
            }
            className={cn(
              "size-10 flex-none rounded-full flex items-center justify-center",
              //   "text-[var(--color-light)] dark:text-[var(--color-dark)]",
              //   "bg-[var(--color-light)]/10 dark:bg-[var(--container-color-dark)]/10",
              "text-card-foreground bg-grey/10 border border-grey/20"
            )}
          >
            <p>{data.user.username.charAt(0).toUpperCase()}</p>
            {/* <UserIcon className="size-4 flex-none" /> */}
          </div>
          {/* <p>{data.user.username}</p> */}
          {/* <ChevronsUpDownIcon className="size-3.5 flex-none my-auto text-grey" /> */}
        </DropdownMenuTrigger>
        <DropdownMenuContent
          className="border min-w-0  border-border w-34 rounded-lg"
          align="end"
          alignOffset={-5}
        >
          {/* <MenubarContentItem
              icon={SettingsIcon}
              text="Settings"
              onClick={() => {
                navigate("/settings");
              }}
            /> */}

          {/* <MenubarSeparator /> */}
          {/* <button
              className="w-full"
              onClick={(e) => {
                e.currentTarget.form?.requestSubmit();
              }}
              form="logout-form"
              disabled={fetcher.state !== "idle"}
            >
              {fetcher.state !== "idle" ? (
                "Logging out..."
              ) : (
                <MenubarContentItem
                  icon={LogOut}
                  text="Logout"
                  className="text-red-400"
                />
              )}
            </button> */}

          <DropdownMenuItem
            onClick={() => {
              navigate("/settings");
            }}
          >
            <SettingsIcon />
            Settings
          </DropdownMenuItem>
          <DropdownMenuSeparator />
          <DropdownMenuItem
            variant="destructive"
            disabled={fetcher.state !== "idle"}
            className="whitespace-nowrap"
          >
            {fetcher.state !== "idle" ? (
              <LoaderIcon className="animate-spin" />
            ) : (
              <LogOutIcon />
            )}
            {fetcher.state !== "idle" ? "Logging out..." : "Log out"}
          </DropdownMenuItem>
        </DropdownMenuContent>
      </DropdownMenu>
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

  const { data: memberships = [] } = useQuery({
    ...userQueries.memberships,
    initialData: props.memberships
  });

  return (
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
            "bg-[var(--color-light)]/10 dark:bg-[var(--color-dark)]/10"
          )}
        >
          <Building2Icon className="size-4 flex-none" />
        </div>
        <p className="whitespace-nowrap">{current.workspace.name}</p>
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
              >
                <div
                  style={
                    {
                      "--color-light": color.light,
                      "--color-dark": color.dark
                    } as React.CSSProperties
                  }
                  className={cn(
                    "size-6 flex-none rounded-md flex items-center justify-center",
                    "text-[var(--color-light)] dark:text-[var(--color-dark)]",
                    "bg-[var(--color-light)]/10 dark:bg-[var(--color-dark)]/10"
                  )}
                >
                  <Building2Icon className="!size-4 flex-none" />
                </div>

                <div className="flex flex-col mr-2">
                  <span className="font-medium">{m.workspace.name}</span>
                  <span className="text-grey">{m.workspace.id}</span>
                </div>

                <span className="flex size-4 items-center justify-center ml-auto flex-none py-2.5">
                  {m.id === current.id && (
                    <CheckIcon className="size-full text-grey" />
                  )}
                </span>
              </DropdownMenuItem>
            );
          })}
        </DropdownMenuGroup>
      </DropdownMenuContent>
    </DropdownMenu>
  );
}
