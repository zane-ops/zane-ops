import { useQuery } from "@tanstack/react-query";
import { type StatusBadgeColor, StatusBadge } from "~/components/status-badge";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow
} from "~/components/ui/table";
import { swarmQueries } from "~/lib/queries";
import { capitalizeText } from "~/lib/utils";
import type { Route } from "./+types/swarm-node-services";

// Docker swarm task states, see `DockerSwarmTaskState` in the backend
type SwarmTaskState =
  | "new"
  | "pending"
  | "assigned"
  | "accepted"
  | "ready"
  | "preparing"
  | "starting"
  | "running"
  | "complete"
  | "failed"
  | "shutdown"
  | "rejected"
  | "orphaned"
  | "remove";

type SwarmNodeServices = Record<
  string,
  { status: SwarmTaskState; message: string | null }
>;

const TASK_STATE_COLOR_MAP = {
  new: "blue",
  pending: "blue",
  assigned: "blue",
  accepted: "blue",
  ready: "blue",
  preparing: "blue",
  starting: "blue",
  running: "green",
  complete: "gray",
  shutdown: "gray",
  remove: "gray",
  failed: "red",
  rejected: "red",
  orphaned: "yellow"
} as const satisfies Record<SwarmTaskState, StatusBadgeColor>;

export default function SwarmNodeServicesPage({
  params,
  matches: {
    "3": { loaderData }
  }
}: Route.ComponentProps) {
  const { data: node } = useQuery({
    ...swarmQueries.singleNode(params.serverId),
    initialData: loaderData.node
  });

  const services = Object.entries(
    (node.services ?? {}) as SwarmNodeServices
  ).sort(([a], [b]) => a.localeCompare(b));

  return (
    <section className="flex flex-col gap-4 py-4">
      <p className="text-grey">
        Status of the ZaneOps services running on this server, updated on each
        healthcheck.
      </p>
      <Table>
        <TableHeader>
          <TableRow>
            <TableHead className="sticky top-0 z-20">Service</TableHead>
            <TableHead className="sticky top-0 z-20">Status</TableHead>
            <TableHead className="sticky top-0 z-20">Message</TableHead>
          </TableRow>
        </TableHeader>
        <TableBody>
          {services.length === 0 ? (
            <TableRow>
              <TableCell colSpan={3} className="text-center text-grey py-4">
                No services reported for this server yet
              </TableCell>
            </TableRow>
          ) : (
            services.map(([name, service]) => {
              const color = TASK_STATE_COLOR_MAP[service.status] ?? "gray";
              return (
                <TableRow key={name}>
                  <TableCell className="font-mono">{name}</TableCell>
                  <TableCell>
                    <StatusBadge
                      color={color}
                      pingState={color === "green" ? "animated" : "static"}
                    >
                      {capitalizeText(service.status)}
                    </StatusBadge>
                  </TableCell>
                  <TableCell className="text-grey">
                    {service.message || "-"}
                  </TableCell>
                </TableRow>
              );
            })
          )}
        </TableBody>
      </Table>
    </section>
  );
}
