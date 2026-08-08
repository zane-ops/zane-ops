import { useQuery } from "@tanstack/react-query";
import { ChevronRightIcon } from "lucide-react";
import { env } from "process";
import { Link, href, useMatches, useSearchParams } from "react-router";
import type { WorkspaceWithOwner } from "~/api/types";
import { Pagination } from "~/components/pagination";
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
  adminWorkspaceQueries,
  licenseQueries,
  paginationListFilters
} from "~/lib/queries";
import { getQueryClient } from "~/lib/query-client";
import {
  cn,
  formatLogTime,
  getUserDisplayName,
  metaTitle,
  stringToColor
} from "~/lib/utils";
import type { Route } from "./+types/workspace-list";

export function meta() {
  return [metaTitle("Workspace List")] satisfies ReturnType<Route.MetaFunction>;
}

export async function clientLoader({ request }: Route.ClientLoaderArgs) {
  const queryClient = getQueryClient();

  const searchParams = new URL(request.url).searchParams;
  const search = paginationListFilters.parse(searchParams);
  const filters = {
    page: search.page ?? 1,
    per_page: search.per_page ?? 10
  };

  const [workspaces, license] = await Promise.all([
    queryClient.ensureQueryData(adminWorkspaceQueries.list(filters)),
    queryClient.ensureQueryData(licenseQueries.get)
  ]);
  return { workspaces, license };
}

export default function WorkspaceListPage({
  loaderData
}: Route.ComponentProps) {
  const [searchParams, setSearchParams] = useSearchParams();
  const search = paginationListFilters.parse(searchParams);

  const filters = {
    page: search.page ?? 1,
    per_page: search.per_page ?? 10
  };

  const { data } = useQuery({
    ...adminWorkspaceQueries.list(filters),
    initialData: loaderData.workspaces
  });

  const workspaces = data.results;
  const totalPages = Math.ceil(data.count / filters.per_page);

  return (
    <section className="flex flex-col gap-4">
      <div className="flex items-center gap-4">
        <h2 className="text-2xl">Workspaces</h2>
      </div>
      <Separator />
      <h3 className="text-grey">Manage the workspaces in this instance</h3>
      <WorkspaceListTable workspaces={workspaces} />

      <div className="my-4 block">
        {workspaces.length > 0 && data.count > 10 && (
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

type WorkspaceListTableProps = {
  workspaces: WorkspaceWithOwner[];
};

function WorkspaceListTable({ workspaces }: WorkspaceListTableProps) {
  const {
    "1": {
      loaderData: {
        user: { user: currentUser }
      }
    }
  } = useMatches() as Route.ComponentProps["matches"];

  return (
    <Table>
      <TableHeader>
        <TableRow>
          <TableHead className="sticky top-0 z-20">Name</TableHead>
          <TableHead className="sticky top-0 z-20 whitespace-nowrap">
            Owner
          </TableHead>
          <TableHead className="sticky top-0 z-20">Created At</TableHead>
        </TableRow>
      </TableHeader>
      <TableBody>
        {workspaces.length === 0 ? (
          <TableRow className="px-2">
            <TableCell colSpan={3} className="p-2 text-muted-foreground italic">
              -- No workspaces found --
            </TableCell>
          </TableRow>
        ) : (
          workspaces.map((workspace) => {
            const createdAt = formatLogTime(workspace.created_at);
            const color = stringToColor(workspace.name);
            const isSelf =
              workspace.owner?.user.username === currentUser.username;
            return (
              <TableRow className="px-2" key={workspace.id}>
                <TableCell
                  className="p-2"
                  style={
                    {
                      "--color-light": color.light,
                      "--color-dark": color.dark
                    } as React.CSSProperties
                  }
                >
                  <Link
                    to={href("/admin/workspaces/:workspaceId", {
                      workspaceId: workspace.id
                    })}
                    className="flex items-center gap-2 group"
                  >
                    <div
                      className={cn(
                        "size-6 flex-none rounded-md flex items-center justify-center",
                        "text-(--color-light) dark:text-(--color-dark)",
                        "bg-(--color-light)/10 dark:bg-(--color-dark)/10",
                        "border border-(--color-light)/10 dark:border-(--color-dark)/10"
                      )}
                    >
                      <span>{workspace.name.charAt(0).toUpperCase()}</span>
                    </div>

                    <div className="inline-flex gap-0.5 items-center group-hover:underline">
                      {workspace.name}
                      <ChevronRightIcon className="text-grey size-3.5" />
                    </div>
                  </Link>
                </TableCell>
                <TableCell className="p-2">
                  <span>{getUserDisplayName(workspace.owner.user)}</span>
                  {isSelf && (
                    <>
                      &nbsp;
                      <span>&middot;</span>&nbsp;
                      <span className="text-link text-sm">you</span>
                    </>
                  )}
                </TableCell>
                <TableCell className="p-2">
                  <time
                    className="text-grey whitespace-nowrap"
                    dateTime={new Date(workspace.created_at).toISOString()}
                  >
                    <span>
                      {createdAt.dateFormat},&nbsp;
                      <span>{createdAt.hourFormat}</span>
                    </span>
                  </time>
                </TableCell>
                <TableCell className="p-2 h-14"></TableCell>
              </TableRow>
            );
          })
        )}
      </TableBody>
    </Table>
  );
}
