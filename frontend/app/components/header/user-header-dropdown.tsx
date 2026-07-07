import { useQuery, useQueryClient } from "@tanstack/react-query";
import { LogOutIcon, ServerIcon, SettingsIcon, UserIcon } from "lucide-react";
import { href, useFetcher, useNavigate, useParams } from "react-router";
import type { AuthedUserResponse } from "~/api/types";
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
import { useDeviceSize } from "~/lib/use-device-size";

import { cn } from "~/lib/utils";
import { hasMinRole } from "~/utils";

export type UserDropdownProps = {
  user: AuthedUserResponse;
};

function getUserDisplayName(user: AuthedUserResponse["user"]) {
  return user.first_name.trim() ? user.first_name : user.username;
}

export function UserHeaderDropdown(props: UserDropdownProps) {
  const fetcher = useFetcher();
  const navigate = useNavigate();
  const { workspaceId } = useParams();
  const deviceSize = useDeviceSize();

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
              "size-8 flex-none rounded-full flex items-center justify-center",
              "text-card-foreground bg-grey/10 border border-grey/20"
            )}
          >
            <p>{getUserDisplayName(user).charAt(0).toUpperCase()}</p>
          </div>
        </DropdownMenuTrigger>
        <DropdownMenuContent
          className="border border-border min-w-48 rounded-lg"
          align="end"
          alignOffset={deviceSize === "phone" ? 0 : -5}
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
                navigate(href("/account"));
              }}
            >
              <UserIcon />
              Account Settings
            </DropdownMenuItem>

            {workspaceId && hasMinRole(props.user, "Member") && (
              <DropdownMenuItem
                className="my-2"
                onClick={() => {
                  navigate(
                    href("/:workspaceId/settings", {
                      workspaceId: workspaceId!
                    })
                  );
                }}
              >
                <SettingsIcon />
                Workspace Settings
              </DropdownMenuItem>
            )}

            {hasMinRole(props.user, "ServerAdmin") && (
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
              asChild
            >
              <button form="logout-form" type="submit" className="w-full">
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
