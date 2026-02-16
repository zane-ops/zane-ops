import { useQuery } from "@tanstack/react-query";
import { LayersIcon } from "lucide-react";
import { Navigate, href } from "react-router";
import type { ComposeStackTask } from "~/api/types";
import { Card } from "~/components/ui/card";
import { composeStackQueries } from "~/lib/queries";
import { cn } from "~/lib/utils";
import type { Route } from "./+types/compose-stack-service-replicas";

export default function ComposeStackServiceReplicasPage({
  params,
  matches: {
    2: { loaderData }
  }
}: Route.ComponentProps) {
  const { data: stack } = useQuery({
    ...composeStackQueries.single({
      project_slug: params.projectSlug,
      stack_slug: params.composeStackSlug,
      env_slug: params.envSlug
    }),
    initialData: loaderData.stack
  });

  const serviceFound = Object.entries(stack.services).find(
    ([name]) => name === params.serviceSlug
  );

  if (!serviceFound) {
    return (
      <Navigate
        to={href(
          "/project/:projectSlug/:envSlug/compose-stacks/:composeStackSlug",
          params
        )}
      />
    );
  }

  const [name, service] = serviceFound;

  const desired_replicas = service.desired_replicas;

  const all_statuses: Array<ComposeStackTask["status"]> = [
    "pending",
    "new",
    "assigned",
    "accepted",
    "ready",
    "preparing",
    "starting",
    "running",
    "complete",
    "failed",
    "shutdown",
    "rejected",
    "orphaned",
    "remove"
  ];

  const current_statuses: Array<ComposeStackTask["status"]> = [
    "pending",
    "new",
    "assigned",
    "accepted",
    "ready",
    "preparing",
    "starting",
    "running",
    "complete"
  ];

  const old_statuses: Array<ComposeStackTask["status"]> = [
    "failed",
    "shutdown",
    "rejected",
    "orphaned",
    "remove"
  ];

  const running = service.tasks.filter((task) =>
    current_statuses.includes(task.status)
  );

  const old = service.tasks.filter((task) =>
    old_statuses.includes(task.status)
  );

  return (
    <section className="mt-8">
      {service.tasks.length === 0 && (
        <div
          className={cn(
            "flex flex-col gap-2 items-center py-24 bg-muted/20",
            "border-border border-dashed rounded-md border-1"
          )}
        >
          <h2 className="text-lg font-medium inline-flex gap-2 items-center">
            <LayersIcon className="size-4.5 flex-none text-grey" />
            <span>No running replicas</span>
          </h2>
          <h3 className="text-base text-grey">This service is offline</h3>
        </div>
      )}
    </section>
  );
}

export type ServiceReplicaCardProps = {};

export function ServiceReplicaCard({}: ServiceReplicaCardProps) {
  return <Card></Card>;
}
