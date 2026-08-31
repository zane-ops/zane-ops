import { useQuery } from "@tanstack/react-query";
import { BanIcon, ChevronDownIcon, CrownIcon } from "lucide-react";
import type * as React from "react";
import type { AdminWorkspaceMember } from "~/api/types";
import { Code } from "~/components/code";
import { StatusBadge } from "~/components/status-badge";
import {
  Popover,
  PopoverContent,
  PopoverTrigger
} from "~/components/ui/popover";
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
import { WorkspaceRoleBadge } from "~/components/workspace-role-badge";
import { WORKSPACE_ROLE_MAPPING } from "~/lib/constants";
import { adminWorkspaceQueries } from "~/lib/queries";
import {
  cn,
  formatLogTime,
  hasMinRole,
  metaTitle,
  pluralize,
  stringToColor
} from "~/lib/utils";
import type { Route } from "./+types/workspace-members";

export function meta() {
  return [
    metaTitle("Workspace Members")
  ] satisfies ReturnType<Route.MetaFunction>;
}

export async function clientLoader({}: Route.ClientLoaderArgs) {
  return;
}

export default function WorkspaceMembersPage({
  matches: {
    "1": {
      loaderData: {
        user: { user: currentUser }
      }
    },
    "3": { loaderData }
  },
  params
}: Route.ComponentProps) {
  const { data: workspace } = useQuery({
    ...adminWorkspaceQueries.single(params.workspaceId),
    initialData: loaderData.workspace
  });

  return (
    <section className="flex flex-col gap-4">
      <h3 className="text-grey">All the members of this workspace</h3>

      <WorkspaceMembersTable
        members={workspace.members}
        currentUsername={currentUser?.username}
      />
    </section>
  );
}

type WorkspaceMembersTableProps = {
  members: readonly AdminWorkspaceMember[];
  currentUsername?: string;
};

function WorkspaceMembersTable({
  members,
  currentUsername
}: WorkspaceMembersTableProps) {
  return (
    <Table>
      <TableHeader>
        <TableRow>
          <TableHead className="sticky top-0 z-20">Username</TableHead>
          <TableHead className="sticky top-0 z-20 whitespace-nowrap">
            Display Name
          </TableHead>
          <TableHead className="sticky top-0 z-20">Role</TableHead>
          <TableHead className="sticky top-0 z-20">
            Accessible projects
          </TableHead>
          <TableHead className="sticky top-0 z-20">Joined at</TableHead>
        </TableRow>
      </TableHeader>
      <TableBody>
        {members.length === 0 ? (
          <TableRow className="px-2">
            <TableCell colSpan={5} className="p-2 text-muted-foreground italic">
              -- No members found --
            </TableCell>
          </TableRow>
        ) : (
          members.map((member) => {
            const joinedAt = formatLogTime(member.created_at);
            const isMember = hasMinRole(member, "Member");
            const isSelf = member.user.username === currentUsername;

            return (
              <TableRow className="px-2" key={member.id}>
                <TableCell className="p-2">
                  <div className="flex items-center gap-1">
                    <span>
                      {member.user.username}
                      {isSelf && (
                        <>
                          &nbsp;
                          <span>&middot;</span>&nbsp;
                          <span className="text-link text-sm">you</span>
                        </>
                      )}
                    </span>

                    {!member.user.is_active && (
                      <StatusBadge
                        color="red"
                        pingState="hidden"
                        className="text-xs py-0.5 px-1.5 gap-1 mx-1 dark:text-red-100"
                      >
                        <span>Blocked</span>
                        <BanIcon className="size-3 flex-none" />
                      </StatusBadge>
                    )}
                  </div>
                </TableCell>
                <TableCell className="p-2 whitespace-nowrap">
                  {member.user.first_name || (
                    <span className="text-grey font-mono">N/A</span>
                  )}
                </TableCell>
                <TableCell className="p-2">
                  <TooltipProvider>
                    <Tooltip delayDuration={0}>
                      <TooltipTrigger asChild>
                        <span className="inline-flex cursor-help">
                          <WorkspaceRoleBadge role={member.role_name} />
                        </span>
                      </TooltipTrigger>
                      <TooltipContent
                        side="top"
                        className="max-w-60 text-pretty"
                      >
                        {WORKSPACE_ROLE_MAPPING[member.role_name].description}
                      </TooltipContent>
                    </Tooltip>
                  </TooltipProvider>
                </TableCell>
                <TableCell className="p-2">
                  {isMember ? (
                    <Code className="px-2 whitespace-nowrap">All projects</Code>
                  ) : (
                    <Popover>
                      <PopoverTrigger asChild>
                        <button className="cursor-pointer">
                          <StatusBadge
                            className="relative top-0.5 text-xs pl-3 pr-2 inline-flex items-center gap-1"
                            color="gray"
                            pingState="hidden"
                          >
                            <span>
                              {member.accessible_projects.length}&nbsp;
                              {pluralize(
                                "project",
                                member.accessible_projects.length
                              )}
                            </span>

                            <ChevronDownIcon className="flex-none size-4" />
                          </StatusBadge>
                        </button>
                      </PopoverTrigger>
                      <PopoverContent
                        align="start"
                        side="bottom"
                        className="px-4 pt-0 pb-2 w-fit min-w-42 max-h-[300px] overflow-y-auto overflow-x-clip"
                      >
                        <ul className="flex flex-col items-start gap-3 pb-2">
                          <li className="text-xs text-grey my-2">Projects</li>
                          {member.accessible_projects.map((project) => {
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
                                    "text-(--color-light) dark:text-(--color-dark)",
                                    "bg-(--color-light)/10 dark:bg-(--color-dark)/10",
                                    "border  border-(--color-light)/10 dark:border-(--color-dark)/10"
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
                    dateTime={new Date(member.created_at).toISOString()}
                  >
                    <span>
                      {joinedAt.dateFormat},&nbsp;
                      <span>{joinedAt.hourFormat}</span>
                    </span>
                  </time>
                </TableCell>
              </TableRow>
            );
          })
        )}
      </TableBody>
    </Table>
  );
}
