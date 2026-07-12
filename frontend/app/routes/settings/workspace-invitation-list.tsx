import { useQuery } from "@tanstack/react-query";
import {
  ChevronDownIcon,
  CrownIcon,
  type LucideIcon,
  RefreshCcwIcon,
  ShieldIcon,
  Trash2Icon,
  UserIcon,
  UserSearchIcon,
  XIcon
} from "lucide-react";
import { Link, href, useSearchParams } from "react-router";
import type { WorkspaceInvitation } from "~/api/types";
import { Code } from "~/components/code";
import { CopyButton } from "~/components/copy-button";
import { Pagination } from "~/components/pagination";
import { StatusBadge } from "~/components/status-badge";
import { Button } from "~/components/ui/button";
import {
  Popover,
  PopoverContent,
  PopoverTrigger
} from "~/components/ui/popover";
import { Separator } from "~/components/ui/separator";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow
} from "~/components/ui/table";
import {
  Tooltip,
  TooltipContent,
  TooltipProvider,
  TooltipTrigger
} from "~/components/ui/tooltip";
import {
  ensureMinRole,
  paginationListFilters,
  workspaceQueries
} from "~/lib/queries";
import { getQueryClient } from "~/lib/query-client";
import {
  cn,
  formattedTime,
  hasMinRole,
  metaTitle,
  pluralize,
  stringToColor
} from "~/lib/utils";
import {
  getCurrentWorkspace,
  useCurrentWorkspace
} from "~/lib/workspace-store";
import type { Route } from "./+types/workspace-invitation-list";

export function meta() {
  return [
    metaTitle("Workspace Invitations")
  ] satisfies ReturnType<Route.MetaFunction>;
}

export async function clientLoader({ request }: Route.ClientLoaderArgs) {
  const queryClient = getQueryClient();
  await ensureMinRole(queryClient, "Admin");
  const workspace = await getCurrentWorkspace(queryClient);

  const searchParams = new URL(request.url).searchParams;
  const search = paginationListFilters.parse(searchParams);
  const filters = {
    page: search.page ?? 1,
    per_page: search.per_page ?? 10
  };

  const invitations = await queryClient.ensureQueryData(
    workspaceQueries.invitations(workspace.id, filters)
  );
  return {
    invitations
  };
}

export default function WorkspaceInvitationListPage({
  loaderData
}: Route.ComponentProps) {
  const [searchParams, setSearchParams] = useSearchParams();
  const search = paginationListFilters.parse(searchParams);

  const filters = {
    page: search.page ?? 1,
    per_page: search.per_page ?? 10
  };
  const workspaceId = useCurrentWorkspace().id;
  const { data } = useQuery({
    ...workspaceQueries.invitations(workspaceId, filters),
    initialData: loaderData.invitations
  });

  const invitations = data.results;

  const totalPages = Math.ceil(data.count / filters.per_page);
  const emptySearchParams =
    !searchParams.get("per_page") && !searchParams.get("page");

  return (
    <section className="flex flex-col gap-4">
      <div className="flex items-center gap-4">
        <h2 className="text-2xl">Pending invitations</h2>
      </div>
      <Separator />
      <div className="flex gap-2 items-center h-9">
        <h3 className="text-grey">Manage your workspace invitations</h3>
        {!emptySearchParams && (
          <Button
            variant="outline"
            className="inline-flex w-min gap-1"
            size="sm"
            asChild
          >
            <Link to="./" prefetch="intent" replace>
              <XIcon size={15} />
              <span>Reset filters</span>
            </Link>
          </Button>
        )}
      </div>

      <WorkspaceInvitationsTable invitations={invitations} />

      <div className="my-4 block">
        {invitations.length > 0 && data.count > 10 && (
          <Pagination
            totalPages={totalPages}
            currentPage={filters.page}
            perPage={filters.per_page}
            onChangePage={(newPage) => {
              searchParams.set("page", newPage.toString());
              setSearchParams(searchParams, {
                replace: true
              });
            }}
            onChangePerPage={(newPerPage) => {
              searchParams.set("page", "1");
              searchParams.set("per_page", newPerPage.toString());
              setSearchParams(searchParams, {
                replace: true
              });
            }}
          />
        )}
      </div>
    </section>
  );
}

type WorkspaceInvitationsTableProps = {
  invitations: WorkspaceInvitation[];
};

function WorkspaceInvitationsTable({
  invitations
}: WorkspaceInvitationsTableProps) {
  return (
    <Table>
      <TableHeader>
        <TableRow>
          <TableHead className="sticky top-0 z-20">Username</TableHead>
          <TableHead className="sticky top-0 z-20">Role</TableHead>
          <TableHead className="sticky top-0 z-20">
            Accessible projects
          </TableHead>
          <TableHead className="sticky top-0 z-20">Created at</TableHead>
          <TableHead className="sticky top-0 z-20">Expires at</TableHead>
          <TableHead className="sticky top-0 z-20 px-4">Actions</TableHead>
        </TableRow>
      </TableHeader>
      <TableBody>
        {invitations.length === 0 ? (
          <TableRow className="px-2">
            <TableCell colSpan={5} className="p-2 text-muted-foreground italic">
              -- No invitations found --
            </TableCell>
          </TableRow>
        ) : (
          invitations.map((invitation) => {
            console.log({
              invitation
            });
            const createdAt = formattedTime(invitation.created_at);
            const expiresAt = formattedTime(invitation.expires_at);
            const isMember = hasMinRole(
              {
                user: { is_superuser: false },
                membership: invitation
              },
              "Member"
            );

            let Icon: LucideIcon;
            switch (invitation.role_name) {
              case "Member":
                Icon = UserIcon;
                break;
              case "Admin":
                Icon = ShieldIcon;
                break;
              case "Owner":
                Icon = CrownIcon;
                break;
              default:
                Icon = UserSearchIcon;
                break;
            }

            return (
              <TableRow className="px-2" key={invitation.id}>
                <TableCell className="p-2">{invitation.username}</TableCell>
                <TableCell className="p-2">
                  <StatusBadge
                    color="gray"
                    pingState="hidden"
                    className="gap-1.5"
                  >
                    <span>{invitation.role_name}</span>
                    <Icon className="size-4 flex-none" />
                  </StatusBadge>
                </TableCell>

                <TableCell className="p-2">
                  {isMember ? (
                    <Code className="px-2 whitespace-nowrap">All projects</Code>
                  ) : (
                    <Popover>
                      <PopoverTrigger asChild>
                        <button>
                          <StatusBadge
                            className="relative top-0.5 text-xs pl-3 pr-2 inline-flex items-center gap-1"
                            color="gray"
                            pingState="hidden"
                          >
                            <span>
                              {invitation.accessible_projects.length}&nbsp;
                              {pluralize(
                                "project",
                                invitation.accessible_projects.length
                              )}
                            </span>

                            <ChevronDownIcon className="flex-none size-4" />
                          </StatusBadge>
                        </button>
                      </PopoverTrigger>
                      <PopoverContent
                        align="start"
                        side="bottom"
                        className="px-4 pt-0 pb-2 w-fit min-w-42"
                      >
                        <ul>
                          <li className="text-xs text-grey my-2">Projects</li>
                          {invitation.accessible_projects.map((project) => {
                            const projectColor = stringToColor(project.slug);
                            return (
                              <li
                                style={
                                  {
                                    "--color-light": projectColor.light,
                                    "--color-dark": projectColor.dark
                                  } as React.CSSProperties
                                }
                                key={project.id}
                                className="inline-flex gap-2 items-center text-sm"
                              >
                                <div
                                  className={cn(
                                    "size-6 flex-none rounded-md flex items-center justify-center",
                                    "text-[var(--color-light)] dark:text-[var(--color-dark)]",
                                    "bg-[var(--color-light)]/10 dark:bg-[var(--color-dark)]/10",
                                    "border  border-[var(--color-light)]/10 dark:border-[var(--color-dark)]/10"
                                  )}
                                >
                                  <span>
                                    {project.slug.charAt(0).toUpperCase()}
                                  </span>
                                </div>
                                <span>{project.slug}</span>
                              </li>
                            );
                          })}
                        </ul>
                      </PopoverContent>
                    </Popover>
                  )}
                </TableCell>
                <TableCell className="p-2">
                  <time
                    className="text-grey whitespace-nowrap"
                    dateTime={new Date(invitation.created_at).toISOString()}
                  >
                    <span>{createdAt}</span>
                  </time>
                </TableCell>
                <TableCell className="p-2">
                  <time
                    className="text-grey whitespace-nowrap"
                    dateTime={new Date(invitation.expires_at).toISOString()}
                  >
                    <span>{expiresAt}</span>
                  </time>
                </TableCell>
                <TableCell className="p-2">
                  <WorkspaceInvitationActions invitation={invitation} />
                </TableCell>
              </TableRow>
            );
          })
        )}
      </TableBody>
    </Table>
  );
}

export type WorkspaceInvitationActionsProps = {
  invitation: WorkspaceInvitation;
};

function getInvitationLink(invitation: WorkspaceInvitation) {
  const registerLink =
    window.location.origin +
    href("/register/:token", { token: invitation.token });
  return registerLink;
}

export function WorkspaceInvitationActions({
  invitation
}: WorkspaceInvitationActionsProps) {
  return (
    <div className="flex items-center gap-1">
      <TooltipProvider>
        <Tooltip delayDuration={0}>
          <TooltipTrigger asChild>
            <CopyButton
              variant="ghost"
              label="Copy invitation link"
              value={getInvitationLink(invitation)}
              className="!opacity-100 flex-none h-9 rounded-md px-3 text-sm"
            />
          </TooltipTrigger>
          <TooltipContent>Copy invitation link</TooltipContent>
        </Tooltip>

        <div className="h-2 relative top-0.5 w-px bg-grey rounded-md" />

        <Tooltip delayDuration={0}>
          <TooltipTrigger asChild>
            <Button size="sm" variant="ghost" className="gap-1">
              <span className="sr-only">Regenerate link</span>
              <RefreshCcwIcon className="flex-none size-4" />
            </Button>
          </TooltipTrigger>
          <TooltipContent>Regenerate invitation link</TooltipContent>
        </Tooltip>
        <div className="h-2 relative top-0.5 w-px bg-grey rounded-md" />
        <Tooltip delayDuration={0}>
          <TooltipTrigger asChild>
            <Button size="sm" variant="ghost" className="gap-1 text-red-400">
              <span className="sr-only">Delete invitation</span>
              <Trash2Icon className="flex-none size-4" />
            </Button>
          </TooltipTrigger>
          <TooltipContent>Delete invitation</TooltipContent>
        </Tooltip>
      </TooltipProvider>
    </div>
  );
}
