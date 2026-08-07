import { useQuery } from "@tanstack/react-query";
import { useSearchParams } from "react-router";
import { Separator } from "~/components/ui/separator";
import { adminWorkspaceQueries, paginationListFilters } from "~/lib/queries";
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

  const workspaces = await queryClient.ensureQueryData(
    adminWorkspaceQueries.list(filters)
  );
  return { workspaces };
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

  const tokens = data.results;
  const totalPages = Math.ceil(data.count / filters.per_page);

  return (
    <section className="flex flex-col gap-4">
      <div className="flex items-center gap-4">
        <h2 className="text-2xl">Workspaces</h2>
      </div>
      <Separator />
      <h3 className="text-grey">Manage the workspaces in this instance</h3>
    </section>
  );
}
