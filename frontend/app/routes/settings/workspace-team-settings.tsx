import { useQuery } from "@tanstack/react-query";
import {
  ChevronDownIcon,
  LoaderIcon,
  MailPlusIcon,
  SearchIcon,
  UserKeyIcon,
  UserXIcon,
  XIcon
} from "lucide-react";
import * as React from "react";
import { Form, Link, href, useFetcher, useSearchParams } from "react-router";
import { useSpinDelay } from "spin-delay";
import { useDebouncedCallback } from "use-debounce";
import type { AuthedUserResponse, WorkspaceMember } from "~/api/types";
import { Code } from "~/components/code";
import { SimpleConfirmationDialog } from "~/components/delete-confirmation-dialog";
import { Pagination } from "~/components/pagination";
import { StatusBadge } from "~/components/status-badge";
import { Button } from "~/components/ui/button";
import { DialogTrigger } from "~/components/ui/dialog";
import {
  FieldSet,
  FieldSetInput,
  FieldSetLabel,
  FieldSetSelect
} from "~/components/ui/fieldset";
import {
  Popover,
  PopoverContent,
  PopoverTrigger
} from "~/components/ui/popover";
import {
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue
} from "~/components/ui/select";
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
import { WorkspaceRoleBadge } from "~/components/workspace-role-badge";
import {
  SPIN_DELAY_DEFAULT_OPTIONS,
  WORKSPACE_ROLE_MAPPING
} from "~/lib/constants";
import {
  ensureMinRole,
  workspaceMemberListFilters,
  workspaceQueries
} from "~/lib/queries";
import { getQueryClient } from "~/lib/query-client";
import {
  cn,
  formatLogTime,
  getUserDisplayName,
  hasMinRole,
  metaTitle,
  pluralize,
  stringToColor
} from "~/lib/utils";
import {
  getCurrentWorkspace,
  useCurrentWorkspace
} from "~/lib/workspace-store";
import type { Route } from "./+types/workspace-team-settings";

export function meta() {
  return [metaTitle("Workspace Team")] satisfies ReturnType<Route.MetaFunction>;
}

export async function clientLoader({ request }: Route.ClientLoaderArgs) {
  const queryClient = getQueryClient();
  await ensureMinRole(queryClient, "Member");

  const searchParams = new URL(request.url).searchParams;
  const search = workspaceMemberListFilters.parse(searchParams);
  const filters = {
    page: search.page ?? 1,
    per_page: search.per_page ?? 10,
    ...search
  };

  const { id: workspaceId } = await getCurrentWorkspace(queryClient);
  const members = await queryClient.ensureQueryData(
    workspaceQueries.members(workspaceId, filters)
  );

  return {
    members
  };
}

export default function WorkspaceTeamSettingsPage({
  loaderData,
  matches: {
    "1": {
      loaderData: { user }
    }
  }
}: Route.ComponentProps) {
  const [searchParams, setSearchParams] = useSearchParams();
  const search = workspaceMemberListFilters.parse(searchParams);

  const inputRef = React.useRef<React.ComponentRef<"input">>(null);

  const filters = {
    page: search.page ?? 1,
    per_page: search.per_page ?? 10,
    ...search
  };
  const workspaceId = useCurrentWorkspace().id;
  const { data, isFetching } = useQuery({
    ...workspaceQueries.members(workspaceId, filters),
    initialData: loaderData.members
  });

  const isFetchingMembers = useSpinDelay(
    isFetching,
    SPIN_DELAY_DEFAULT_OPTIONS
  );

  const searchMembers = useDebouncedCallback((query: string) => {
    searchParams.set("query", query);
    setSearchParams(searchParams, { replace: true });
  }, 300);

  React.useEffect(() => {
    if (inputRef.current && inputRef.current.value !== filters.query) {
      inputRef.current.value = filters.query ?? "";
    }
  }, [filters.query]);

  const members = data.results;

  const totalPages = Math.ceil(data.count / filters.per_page);
  const emptySearchParams =
    !(searchParams.get("query")?.trim() ?? "") &&
    !searchParams.get("role") &&
    !searchParams.get("per_page") &&
    !searchParams.get("page");

  return (
    <section className="flex flex-col gap-4">
      <div className="flex items-center gap-4">
        <h2 className="text-2xl">Team Settings</h2>
        {hasMinRole(user, "Admin") && (
          <Button asChild variant="secondary" className="flex gap-2">
            <Link to="invite" prefetch="intent">
              Invite User <MailPlusIcon size={18} />
            </Link>
          </Button>
        )}
      </div>
      <Separator />
      <h3 className="text-grey">Manage your workspace members</h3>

      <Form className="flex flex-wrap items-center md:gap-3 gap-1">
        <FieldSet name="query" className="flex md:w-[30%] w-full items-center">
          <FieldSetLabel className="sr-only">Search query</FieldSetLabel>

          {isFetchingMembers ? (
            <LoaderIcon size={20} className="animate-spin relative left-4" />
          ) : (
            <SearchIcon size={20} className="relative left-4" />
          )}

          <FieldSetInput
            onChange={(e) => {
              searchMembers(e.currentTarget.value);
            }}
            ref={inputRef}
            defaultValue={filters.query}
            className="px-14 -mx-5 w-full my-1 text-sm focus-visible:right-0"
            placeholder="Search query"
          />
        </FieldSet>

        <FieldSet name="role">
          <FieldSetLabel className="sr-only">Role</FieldSetLabel>

          <FieldSetSelect
            value={filters.role ?? "ALL"}
            onValueChange={(value) => {
              searchParams.delete("role");

              if (value !== "ALL") {
                searchParams.set("role", value);
              }
              setSearchParams(searchParams, { replace: true });
            }}
          >
            <SelectTrigger
              id="role"
              className="w-min gap-2 border-dashed data-placeholder:text-grey whitespace-nowrap"
            >
              <SelectValue placeholder="Role" />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="ALL">All roles</SelectItem>
              {Object.keys(WORKSPACE_ROLE_MAPPING).map((role) => (
                <SelectItem value={role} key={role}>
                  {role}
                </SelectItem>
              ))}
            </SelectContent>
          </FieldSetSelect>
        </FieldSet>

        {!emptySearchParams && (
          <Button variant="outline" className="inline-flex w-min gap-1" asChild>
            <Link to="./" prefetch="intent" replace>
              <XIcon size={15} />
              <span>Reset filters</span>
            </Link>
          </Button>
        )}
      </Form>

      <WorkspaceMembersTable members={members} currentUser={user} />

      <div className="my-4 block">
        {members.length > 0 && data.count > 10 && (
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

type WorkspaceMembersTableProps = {
  members: WorkspaceMember[];
  currentUser: AuthedUserResponse;
};

function WorkspaceMembersTable({
  members,
  currentUser
}: WorkspaceMembersTableProps) {
  const showActionsColumn = hasMinRole(currentUser, "Admin");

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
          <TableHead className="sticky top-0 z-20">Joinet at</TableHead>
          {showActionsColumn && (
            <TableHead className="sticky top-0 z-20 px-4">Actions</TableHead>
          )}
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

            const isSelf = currentUser.membership?.id === member.id;
            // owners can manage everyone, admins only people below them
            const canManageMember =
              hasMinRole(currentUser, "Owner") ||
              (hasMinRole(currentUser, "Admin") &&
                !hasMinRole(member, "Admin"));

            const showActions = !isSelf && canManageMember;

            return (
              <TableRow className="px-2" key={member.id}>
                <TableCell className="p-2">{member.user.username}</TableCell>
                <TableCell className="p-2 whitespace-nowrap">
                  {member.user.first_name ?? (
                    <span className="text-grey font-mono">N/A</span>
                  )}
                </TableCell>
                <TableCell className="p-2">
                  <WorkspaceRoleBadge role={member.role_name} />
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
                    dateTime={new Date(member.created_at).toISOString()}
                  >
                    <span>
                      {joinedAt.dateFormat},&nbsp;
                      <span>{joinedAt.hourFormat}</span>
                    </span>
                  </time>
                </TableCell>
                {showActionsColumn && (
                  <TableCell className="p-2">
                    {showActions && <WorkspaceMemberActions member={member} />}
                  </TableCell>
                )}
              </TableRow>
            );
          })
        )}
      </TableBody>
    </Table>
  );
}

export type WorkspaceMemberActionsProps = {
  member: WorkspaceMember;
};

export function WorkspaceMemberActions({
  member
}: WorkspaceMemberActionsProps) {
  return (
    <div className="flex items-center gap-1">
      <TooltipProvider>
        <Tooltip delayDuration={0}>
          <TooltipTrigger asChild>
            <Button
              variant="ghost"
              size="icon"
              asChild
              disabled={hasMinRole(member, "Owner")}
            >
              <Link
                to={href("/workspace/settings/team/:id/permissions", {
                  id: member.id.toString()
                })}
              >
                <UserKeyIcon className="flex-none size-4" />
                <span className="sr-only">Edit permissions</span>
              </Link>
            </Button>
          </TooltipTrigger>
          <TooltipContent>Edit member permissions</TooltipContent>
        </Tooltip>
      </TooltipProvider>

      <div className="h-2 relative top-0.5 w-px bg-grey rounded-md" />

      <RemoveConfirmationFormDialog member={member} />
    </div>
  );
}

function RemoveConfirmationFormDialog({ member }: WorkspaceMemberActionsProps) {
  const fetcher = useFetcher();

  return (
    <SimpleConfirmationDialog
      fetcher={fetcher}
      title={
        <>
          Remove&nbsp;
          <span className="text-grey ">
            &ldquo;{member.user.username}&rdquo;
          </span>
          &nbsp;from this workspace?
        </>
      }
      message={
        <span>
          They will immediately lose access to this workspace and all of its
          projects. You can invite them again later, but their permissions will
          need to be set up from scratch.
        </span>
      }
      form={
        <fetcher.Form
          method="post"
          action={href("/workspace/settings/team/:id/remove", {
            id: member.id.toString()
          })}
        >
          <input type="hidden" name="intent" value="remove" />
        </fetcher.Form>
      }
      trigger={
        <TooltipProvider>
          <Tooltip delayDuration={0}>
            <TooltipTrigger asChild>
              <DialogTrigger asChild>
                <Button
                  size="sm"
                  variant="ghost"
                  className="gap-1 text-red-400"
                >
                  <span className="sr-only">Remove member from workspace</span>
                  <UserXIcon className="flex-none size-4" />
                </Button>
              </DialogTrigger>
            </TooltipTrigger>
            <TooltipContent>Remove member from workspace</TooltipContent>
          </Tooltip>
        </TooltipProvider>
      }
    />
  );
}
