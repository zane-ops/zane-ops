import { Separator } from "@radix-ui/react-separator";
import { useQuery } from "@tanstack/react-query";
import {
  ExternalLinkIcon,
  PencilLineIcon,
  PlusIcon,
  Trash2Icon
} from "lucide-react";
import { Link, useSearchParams } from "react-router";
import { Pagination } from "~/components/pagination";
import { StatusBadge } from "~/components/status-badge";
import { Button } from "~/components/ui/button";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow
} from "~/components/ui/table";
import { buildRegistryListFilters, buildRegistryQueries } from "~/lib/queries";
import { queryClient } from "~/root";
import { formatURL, metaTitle } from "~/utils";
import type { Route } from "./+types/build-registries-list";

export function meta() {
  return [
    metaTitle("Build Registries")
  ] satisfies ReturnType<Route.MetaFunction>;
}

export async function clientLoader({ request }: Route.ClientLoaderArgs) {
  const searchParams = new URL(request.url).searchParams;
  const search = buildRegistryListFilters.parse(searchParams);

  const filters = {
    page: search.page ?? 1,
    per_page: search.per_page ?? 10
  };

  const registryList = await queryClient.ensureQueryData(
    buildRegistryQueries.list(filters)
  );
  return {
    registryList
  };
}

export default function BuildRegistryListPage({
  loaderData
}: Route.ComponentProps) {
  const [searchParams, setSearchParams] = useSearchParams();
  const search = buildRegistryListFilters.parse(searchParams);

  const filters = {
    page: search.page ?? 1,
    per_page: search.per_page ?? 10
  };

  const {
    data: { results: registries, count: totalDeployments }
  } = useQuery({
    ...buildRegistryQueries.list(filters),
    initialData: loaderData.registryList
  });

  const totalPages = Math.ceil(totalDeployments / filters.per_page);

  return (
    <section className="flex flex-col gap-4">
      <div className="flex items-center gap-4">
        <h2 className="text-2xl">Build Registries</h2>
        <Button asChild variant="secondary" className="flex gap-2">
          <Link to="new" prefetch="intent">
            New <PlusIcon size={18} />
          </Link>
        </Button>
      </div>
      <Separator />
      <h3>
        Manage registries used by ZaneOps to store your built applications.
      </h3>

      <Table>
        <TableHeader>
          <TableRow>
            <TableHead className="sticky top-0 z-20">Name</TableHead>
            <TableHead className="sticky top-0 z-20">Username</TableHead>
            <TableHead className="sticky top-0 z-20">Domain</TableHead>
            <TableHead className="sticky top-0 z-20 px-4">Actions</TableHead>
          </TableRow>
        </TableHeader>
        <TableBody>
          {registries.length === 0 && (
            <TableRow className="px-2">
              <TableCell
                className="p-2 text-muted-foreground italic"
                colSpan={4}
              >
                -- No registries found --
              </TableCell>
            </TableRow>
          )}

          {registries.map((registry) => (
            <TableRow key={registry.id}>
              <TableCell className="p-2">
                <div className="flex gap-2 items-center">
                  {registry.name}
                  {registry.is_global && (
                    <StatusBadge color="blue" pingState="hidden">
                      Global
                    </StatusBadge>
                  )}
                </div>
              </TableCell>
              <TableCell className="p-2">
                {registry.registry_username}
              </TableCell>
              <TableCell className="p-2">
                <a
                  href={`//${registry.registry_domain}`}
                  target="_blank"
                  className="underline text-link inline-flex items-center gap-1"
                  rel="noreferrer"
                >
                  <span>{formatURL({ domain: registry.registry_domain })}</span>
                  <ExternalLinkIcon size={16} className="flex-none" />
                </a>
              </TableCell>

              <TableCell className="p-2">
                <div className="flex items-center gap-2">
                  <Button variant="ghost" asChild size="sm">
                    <Link
                      to={`./${registry.id}`}
                      className="inline-flex gap-2 items-center"
                    >
                      <PencilLineIcon className="size-4 flex-none" />
                      <span>Edit</span>
                    </Link>
                  </Button>

                  <Separator className="h-2 relative top-0.5 w-px bg-grey rounded-md" />

                  <Button
                    variant="ghost"
                    className="text-red-400 inline-flex gap-2 items-center"
                    size="sm"
                  >
                    <Trash2Icon className="size-4 flex-none" />
                    <span>Delete</span>
                  </Button>
                </div>
              </TableCell>
            </TableRow>
          ))}
        </TableBody>
      </Table>
      <div className="my-4 block">
        {registries.length > 0 && totalDeployments > 10 && (
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
