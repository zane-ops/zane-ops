import { useQuery } from "@tanstack/react-query";
import { ShieldIcon, XIcon } from "lucide-react";
import { Link, useSearchParams } from "react-router";
import type { WorkspaceInvitation } from "~/api/types";
import { Code } from "~/components/code";
import { Pagination } from "~/components/pagination";
import { StatusBadge } from "~/components/status-badge";
import { Button } from "~/components/ui/button";
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
  ensureMinRole,
  paginationListFilters,
  workspaceQueries
} from "~/lib/queries";
import { getQueryClient } from "~/lib/query-client";
import { formattedTime, hasMinRole, metaTitle, pluralize } from "~/lib/utils";
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
          <TableHead className="sticky top-0 z-20 px-4"></TableHead>
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

            return (
              <TableRow className="px-2" key={invitation.id}>
                <TableCell className="p-2">{invitation.username}</TableCell>
                <TableCell className="p-2">
                  <StatusBadge
                    color="gray"
                    pingState="hidden"
                    className="gap-1"
                  >
                    <span>{invitation.role_name}</span>
                    {invitation.role_name === "Admin" && (
                      <ShieldIcon className="size-4 flex-none" />
                    )}
                  </StatusBadge>
                </TableCell>

                <TableCell className="p-2">
                  <Code className="px-2 whitespace-nowrap">
                    {isMember
                      ? "All projects"
                      : `${invitation.accessible_projects.length} ${pluralize("project", invitation.accessible_projects.length)}`}
                  </Code>
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
                  {/* <WorkspaceMemberActions member={invitation} /> */}
                </TableCell>
              </TableRow>
            );
          })
        )}
      </TableBody>
    </Table>
  );
}
