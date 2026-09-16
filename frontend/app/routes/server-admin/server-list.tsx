import { useQuery } from "@tanstack/react-query";
import { Link, useSearchParams } from "react-router";

import { PlusIcon } from "lucide-react";
import type { SwarmNode } from "~/api/types";
import { Pagination } from "~/components/pagination";
import { StatusBadge, type StatusBadgeColor } from "~/components/status-badge";
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
import { swarmNodeListFilters, swarmQueries } from "~/lib/queries";
import { getQueryClient } from "~/lib/query-client";
import { formatStorageValue, metaTitle } from "~/lib/utils";
import type { Route } from "./+types/server-list";

export function meta() {
  return [metaTitle("Servers")] satisfies ReturnType<Route.MetaFunction>;
}

export async function clientLoader({ request }: Route.ClientLoaderArgs) {
  const queryClient = getQueryClient();

  const searchParams = new URL(request.url).searchParams;
  const search = swarmNodeListFilters.parse(searchParams);
  const filters = {
    page: search.page ?? 1,
    per_page: search.per_page ?? 10,
    ...search
  };

  const nodes = await queryClient.ensureQueryData(
    swarmQueries.nodeList(filters)
  );
  return { nodes };
}

export default function ServerListPage({ loaderData }: Route.ComponentProps) {
  const [searchParams, setSearchParams] = useSearchParams();
  const search = swarmNodeListFilters.parse(searchParams);

  const filters = {
    page: search.page ?? 1,
    per_page: search.per_page ?? 10,
    ...search
  };

  const { data } = useQuery({
    ...swarmQueries.nodeList(filters),
    initialData: loaderData.nodes
  });

  const nodes = data.results;
  const totalPages = Math.ceil(data.count / filters.per_page);

  return (
    <section className="flex flex-col gap-4">
      <div className="flex items-center gap-4">
        <h2 className="text-2xl">Servers</h2>
        <Button asChild variant="secondary" className="flex gap-2">
          <Link to="new" prefetch="intent">
            Add server <PlusIcon size={18} />
          </Link>
        </Button>
      </div>
      <Separator />
      <h3 className="text-grey">
        Add and manage the servers that make up your ZaneOps cluster. Services
        can be deployed to any server in this list.
      </h3>

      {/* <ServerTable nodes={nodes} /> */}

      <div className="my-4 block">
        {nodes.length > 0 && data.count > 10 && (
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

const STATUS_COLORS = {
  READY: "green",
  PROVISIONING: "blue",
  DOWN: "red",
  FAILED: "red",
  DRAINED: "gray"
} satisfies Record<SwarmNode["status"], StatusBadgeColor>;

type ServerTableProps = {
  nodes: SwarmNode[];
};

function ServerTable({ nodes }: ServerTableProps) {
  return (
    <Table>
      <TableHeader>
        <TableRow>
          <TableHead className="sticky top-0 z-20">Hostname</TableHead>
          <TableHead className="sticky top-0 z-20">Role</TableHead>
          <TableHead className="sticky top-0 z-20">Status</TableHead>
          <TableHead className="sticky top-0 z-20 whitespace-nowrap">
            Private IP
          </TableHead>
          <TableHead className="sticky top-0 z-20">Resources</TableHead>
          <TableHead className="sticky top-0 z-20">Docker</TableHead>
        </TableRow>
      </TableHeader>
      <TableBody>
        {nodes.length === 0 ? (
          <TableRow className="px-2">
            <TableCell colSpan={6} className="p-2 text-muted-foreground italic">
              -- No server found --
            </TableCell>
          </TableRow>
        ) : (
          nodes.map((node) => {
            const memory =
              node.memory_bytes !== null
                ? formatStorageValue(node.memory_bytes)
                : null;

            return (
              <TableRow className="px-2" key={node.id}>
                <TableCell className="p-2">
                  <div className="flex items-center gap-2">
                    <span>{node.hostname}</span>
                    {node.is_initial_install_server && (
                      <StatusBadge
                        color="gray"
                        pingState="hidden"
                        className="text-xs py-0.5 px-1.5"
                      >
                        initial
                      </StatusBadge>
                    )}
                  </div>
                </TableCell>
                <TableCell className="p-2 capitalize">
                  {node.role.toLowerCase()}
                </TableCell>
                <TableCell className="p-2">
                  <StatusBadge
                    color={STATUS_COLORS[node.status]}
                    pingState={
                      node.status === "PROVISIONING" ? "animated" : "static"
                    }
                    className="text-xs py-0.5 px-1.5 capitalize"
                  >
                    {node.status.toLowerCase()}
                  </StatusBadge>
                </TableCell>
                <TableCell className="p-2">
                  <code className="text-sm">{node.private_ip}</code>
                </TableCell>
                <TableCell className="p-2 text-grey whitespace-nowrap">
                  {node.cpus !== null ? `${node.cpus} CPU` : "-"}
                  &nbsp;/&nbsp;
                  {memory ? `${memory.value} ${memory.unit}` : "-"}
                </TableCell>
                <TableCell className="p-2 text-grey">
                  {node.docker_version}
                </TableCell>
              </TableRow>
            );
          })
        )}
      </TableBody>
    </Table>
  );
}
