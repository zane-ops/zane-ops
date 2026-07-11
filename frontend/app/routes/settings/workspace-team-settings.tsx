import { useQuery } from "@tanstack/react-query";
import {
  ChevronDownIcon,
  CrownIcon,
  EllipsisIcon,
  ExternalLinkIcon,
  LoaderIcon,
  MailPlusIcon,
  PencilLineIcon,
  PlusIcon,
  SearchIcon,
  Trash2Icon,
  UserKeyIcon,
  UserXIcon,
  XIcon
} from "lucide-react";
import * as React from "react";
import { Link, redirect, useSearchParams } from "react-router";
import { useFetcher } from "react-router";
import { Form } from "react-router";
import { useSpinDelay } from "spin-delay";
import { useDebouncedCallback } from "use-debounce";
import type { Writeable } from "zod";
import type { WorkspaceMember, WorkspaceMembership } from "~/api/types";
import { Code } from "~/components/code";
import { SimpleConfirmationDialog } from "~/components/delete-confirmation-dialog";
import { Pagination } from "~/components/pagination";
import { StatusBadge } from "~/components/status-badge";
import { Button } from "~/components/ui/button";
import { DialogTrigger } from "~/components/ui/dialog";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger
} from "~/components/ui/dropdown-menu";
import {
  FieldSet,
  FieldSetInput,
  FieldSetLabel,
  FieldSetSelect
} from "~/components/ui/fieldset";
import { Input } from "~/components/ui/input";
import {
  Select,
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
import {
  DEFAULT_REGISTRIES,
  type DEPLOYMENT_STATUSES,
  SPIN_DELAY_DEFAULT_OPTIONS,
  WORKSPACE_ROLE_MAPPING
} from "~/lib/constants";
import {
  ensureAuthedUser,
  projectQueries,
  serviceDeploymentListFilters,
  workspaceMemberListFilters,
  workspaceQueries
} from "~/lib/queries";
import { getQueryClient } from "~/lib/query-client";
import { formatLogTime, notFound } from "~/lib/utils";
import {
  getCurrentWorkspace,
  useCurrentWorkspace
} from "~/lib/workspace-store";
import { hasMinRole, metaTitle, pluralize } from "~/utils";
import type { Route } from "./+types/workspace-team-settings";

export function meta() {
  return [metaTitle("Workspace Team")] satisfies ReturnType<Route.MetaFunction>;
}

export async function clientLoader({ request }: Route.ClientLoaderArgs) {
  const queryClient = getQueryClient();
  const user = await ensureAuthedUser(queryClient);
  if (!hasMinRole(user, "Member")) {
    throw notFound();
  }

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
        <Button asChild variant="secondary" className="flex gap-2">
          <Link to="invite" prefetch="intent">
            Invite User <MailPlusIcon size={18} />
          </Link>
        </Button>
      </div>
      <Separator />
      <h3 className="text-grey">Manage your workspace team</h3>

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

      <WorkspaceMembersTable
        members={members}
        showActionsColumn={hasMinRole(user, "Admin")}
      />

      <div className="my-4 block">
        {members.length > 0 && data.count > filters.per_page && (
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
  showActionsColumn: boolean;
};

function WorkspaceMembersTable({
  members,
  showActionsColumn
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
          <TableHead className="sticky top-0 z-20">Invited at</TableHead>
          {showActionsColumn && (
            <TableHead className="sticky top-0 z-20 px-4"></TableHead>
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
            const invitedAt = formatLogTime(member.created_at);
            return (
              <TableRow className="px-2" key={member.id}>
                <TableCell className="p-2">{member.user.username}</TableCell>
                <TableCell className="p-2 whitespace-nowrap">
                  {member.user.first_name ?? (
                    <span className="text-grey font-mono">N/A</span>
                  )}
                </TableCell>
                <TableCell className="p-2">
                  <StatusBadge color="gray" pingState="hidden">
                    <span>{member.role_name}</span>
                    {member.role_name === "Owner" && (
                      <CrownIcon className="size-4 flex-none" />
                    )}
                  </StatusBadge>
                </TableCell>
                <TableCell className="p-2">
                  <Code className="px-2 whitespace-nowrap">
                    {member.role > WORKSPACE_ROLE_MAPPING["Guest"]
                      ? "All projects"
                      : `${member.accessible_projects.length} ${pluralize("project", member.accessible_projects.length)}`}
                  </Code>
                </TableCell>
                <TableCell className="p-2">
                  <time
                    className="text-grey whitespace-nowrap"
                    dateTime={new Date(member.created_at).toISOString()}
                  >
                    <span>
                      {invitedAt.dateFormat},&nbsp;
                      <span>{invitedAt.hourFormat}</span>
                    </span>
                  </time>
                </TableCell>
                {showActionsColumn && (
                  <TableCell className="p-2">
                    <WorkspaceMemberActions member={member} />
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
      <DropdownMenu>
        <DropdownMenuTrigger asChild>
          <Button
            variant="outline"
            size="sm"
            className="gap-1.5 border-dashed"
            disabled={member.role_name === "Owner"}
          >
            Actions
            <ChevronDownIcon className="size-4 flex-none" />
          </Button>
        </DropdownMenuTrigger>

        <DropdownMenuContent align="end">
          <DropdownMenuItem className="flex items-center gap-2">
            <UserKeyIcon className="flex-none size-4" />
            <span>Edit permissions</span>
          </DropdownMenuItem>
          <DropdownMenuItem
            className="flex items-center gap-2"
            variant="destructive"
          >
            <UserXIcon className="flex-none size-4" />
            <span>Remove member</span>
          </DropdownMenuItem>
        </DropdownMenuContent>
      </DropdownMenu>
    </div>
  );
}

function RemoveConfirmationFormDialog({ member }: WorkspaceMemberActionsProps) {
  const fetcher = useFetcher();

  return (
    <SimpleConfirmationDialog
      fetcher={fetcher}
      title="Delete these Credentials ?"
      message={
        <span>
          This action <strong>CANNOT</strong> be undone. You will loose access
          to this workspace
        </span>
      }
      form={
        <fetcher.Form method="post" action={`./${member.id}`}>
          <input type="hidden" name="intent" value="delete" />
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
                  <>
                    <span>Remove member</span>
                    <UserXIcon className="flex-none size-4" />
                  </>
                </Button>
              </DialogTrigger>
            </TooltipTrigger>
            <TooltipContent>Remove member</TooltipContent>
          </Tooltip>
        </TooltipProvider>
      }
      extraInfo={
        <dl className="py-2 border-y border-border mb-5 ">
          {/* <div className="flex items-center gap-1">
            <dt className="select-none">Username: </dt>
            <dd className="text-grey dark:text-foreground">
              {credentials.username ?? (
                <span className="text-grey font-mono">N/A</span>
              )}
            </dd>
          </div>
          <div className="flex items-center gap-1">
            <dt className="select-none">URL:</dt>
            <dd className="text-link">
              <a
                href={credentials.url}
                target="_blank"
                className="underline text-link inline-flex items-center gap-1"
              >
                <span>{credentials.url}</span>
                <ExternalLinkIcon size={16} className="flex-none" />
              </a>
            </dd>
          </div> */}
        </dl>
      }
    />
  );
}
