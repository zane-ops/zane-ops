import { useQuery } from "@tanstack/react-query";
import { ChevronRightIcon, LayersIcon } from "lucide-react";
import * as React from "react";
import { Navigate, href } from "react-router";
import {
  Accordion,
  AccordionContent,
  AccordionItem,
  AccordionTrigger
} from "~/components/ui/accordion";
import { composeStackQueries } from "~/lib/queries";
import { cn } from "~/lib/utils";
import { ComposeStackServiceReplicaCard } from "~/routes/compose/components/compose-stack-service-replica-card";
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

  const [, service] = serviceFound;

  const tasks = service.tasks.toSorted((tA, tB) => tB.version - tA.version);

  const running = tasks.filter(
    (task) =>
      task.desired_status === "running" || task.desired_status === "complete"
  );

  const old = tasks.filter(
    (task) =>
      task.desired_status !== "running" && task.desired_status !== "complete"
  );

  const [accordionValue, setAccordionValue] = React.useState(
    running.length === 0
      ? "old"
      : service.desired_replicas === running.length
        ? ""
        : "old"
  );

  return (
    <section className="mt-8">
      {tasks.length === 0 && (
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

      <div className="flex flex-col gap-4 mt-6">
        {running.length > 0 && (
          <section className="flex flex-col gap-2">
            <h2 className="text-grey text-sm">Current</h2>
            <ul className="flex flex-col gap-4">
              {running.map((task) => (
                <li key={task.id}>
                  <ComposeStackServiceReplicaCard task={task} />
                </li>
              ))}
            </ul>
          </section>
        )}
        {old.length > 0 && (
          <section className="flex flex-col gap-2">
            <Accordion
              type="single"
              collapsible
              value={accordionValue}
              onValueChange={(state) => {
                setAccordionValue(state);
              }}
              className="border-none"
            >
              <AccordionItem value="old" className="border-none">
                <AccordionTrigger className="data-[state=open]:rounded-b-none [&[data-state=open]_svg]:rotate-90 cursor-pointer">
                  <h2 className="text-grey text-sm flex items-center gap-1">
                    <ChevronRightIcon className="size-4 flex-none" />
                    Previous
                  </h2>
                </AccordionTrigger>
                <AccordionContent>
                  <ul className="flex flex-col gap-4">
                    {old.map((task) => (
                      <li key={task.id}>
                        <ComposeStackServiceReplicaCard
                          task={task}
                          isPrevious
                        />
                      </li>
                    ))}
                  </ul>
                </AccordionContent>
              </AccordionItem>
            </Accordion>
          </section>
        )}
      </div>
    </section>
  );
}
