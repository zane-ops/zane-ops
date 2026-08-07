import { useQuery } from "@tanstack/react-query";
import { useSearchParams } from "react-router";
import type { WorkspaceWithOwner } from "~/api/types";
import { Pagination } from "~/components/pagination";
import { Separator } from "~/components/ui/separator";
import { Table } from "~/components/ui/table";
import {
  adminWorkspaceQueries,
  licenseQueries,
  paginationListFilters
} from "~/lib/queries";
import { getQueryClient } from "~/lib/query-client";
import type { Route } from "./+types/workspace-list";

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
  return <Table></Table>;
}
