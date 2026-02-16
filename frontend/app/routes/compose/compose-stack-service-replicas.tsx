import { useQuery } from "@tanstack/react-query";
import {
  ChevronRightIcon,
  ContainerIcon,
  HashIcon,
  Layers2Icon,
  LayersIcon,
  LoaderIcon,
  LogOutIcon,
  MessageCircleMoreIcon
} from "lucide-react";
import * as React from "react";
import { Link, Navigate, href } from "react-router";
import type { ComposeStackTask } from "~/api/types";
import { Code } from "~/components/code";
import type { StatusBadgeColor } from "~/components/status-badge";
import {
  Accordion,
  AccordionContent,
  AccordionItem,
  AccordionTrigger
} from "~/components/ui/accordion";
import { Button } from "~/components/ui/button";
import { Card } from "~/components/ui/card";
import {
  Tooltip,
  TooltipContent,
  TooltipProvider,
  TooltipTrigger
} from "~/components/ui/tooltip";
import { composeStackQueries } from "~/lib/queries";
import { cn } from "~/lib/utils";
import { getDockerImageIconURL } from "~/utils";
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
                  <ServiceTaskCard task={task} />
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
                        <ServiceTaskCard task={task} isPrevious />
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

export type ServiceTaskCardProps = {
  task: ComposeStackTask;
  isPrevious?: boolean;
};

const TASK_STATUS_COLOR_MAP = {
  new: "gray",
  pending: "gray",
  assigned: "blue",
  accepted: "blue",
  ready: "blue",
  preparing: "blue",
  starting: "blue",
  running: "green",
  complete: "yellow",
  failed: "red",
  shutdown: "gray",
  rejected: "red",
  orphaned: "red",
  remove: "gray"
} as const satisfies Record<ComposeStackTask["status"], StatusBadgeColor>;

export function ServiceTaskCard({
  task,
  isPrevious = false
}: ServiceTaskCardProps) {
  const color = TASK_STATUS_COLOR_MAP[task.status];

  const isLoading = color === "blue";

  const [iconNotFound, setIconNotFound] = React.useState(false);

  const image = task.image;

  let iconSrc: string | null = null;
  if (image) {
    iconSrc = getDockerImageIconURL(image);
  }

  const [imageVersion, imageSha] = task.image.split("@");

  const [accordionValue, setAccordionValue] = React.useState(
    color === "red" && !isPrevious ? `task-${task.id}` : ""
  );

  return (
    <Card
      className={cn("border border-border p-1 shadow-none group relative", {
        "border-emerald-500": color === "green",
        "border-red-600": color === "red",
        "border-amber-500": color === "yellow",
        "border-gray-600": color === "gray",
        "border-link": color === "blue",
        "border-dashed": isPrevious
      })}
    >
      {/* View logs button */}
      <Button
        asChild
        variant="ghost"
        size="sm"
        className={cn(
          "border hover:bg-inherit hidden md:inline-flex",
          "absolute top-4 right-4",
          {
            "border-emerald-500": color === "green",
            "border-gray-600": color === "gray",
            "border-amber-500": color === "yellow",
            "border-link": color === "blue",
            "border-red-600": color === "red"
          }
        )}
      >
        <Link to={"#"}>View logs</Link>
      </Button>

      <Accordion
        type="single"
        collapsible
        value={accordionValue}
        onValueChange={(state) => {
          setAccordionValue(state);
        }}
        className="w-full p-0 border-none"
      >
        <AccordionItem
          value={`task-${task.id}`}
          className="w-full p-0 font-normal border-none"
        >
          <AccordionTrigger
            className={cn(
              "rounded-md py-2 px-4 flex items-center gap-6 font-normal cursor-pointer data-[state=open]:rounded-b-none",
              {
                "bg-emerald-400/10 dark:bg-emerald-600/20 hover:bg-emerald-300/20":
                  color === "green",
                "bg-red-600/10 hover:bg-red-600/20": color === "red",
                "bg-yellow-400/10 dark:bg-yellow-600/10 ": color === "yellow",
                "bg-gray-600/10 hover:bg-gray-600/20": color === "gray",
                "bg-link/10 hover:bg-link/20": color === "blue"
              }
            )}
          >
            {/* Status */}
            <div className="min-w-26">
              <div
                className={cn(
                  "relative top-0.5 rounded-md bg-link/20 text-link px-2  inline-flex gap-1 items-center py-0.5",
                  {
                    "bg-emerald-400/30 dark:bg-emerald-600/20 text-green-600  dark:text-emerald-400":
                      color === "green",
                    "bg-red-600/25 text-red-700 dark:text-red-400":
                      color === "red",
                    "bg-yellow-400/30 dark:bg-yellow-600/20 text-amber-700 dark:text-yellow-300":
                      color === "yellow",
                    "bg-gray-600/20 dark:bg-gray-600/60 text-gray":
                      color === "gray",
                    "bg-link/30 text-link": color === "blue"
                  }
                )}
              >
                <code className="text-sm">{task.status.toUpperCase()}</code>
                {isLoading && (
                  <LoaderIcon className="animate-spin flex-none" size={15} />
                )}
              </div>
            </div>

            {/* ID & image */}
            <div className="flex flex-col gap-2 grow">
              <div className="flex gap-2">
                <TooltipProvider>
                  <Tooltip delayDuration={0}>
                    <TooltipTrigger asChild>
                      <span
                        tabIndex={0}
                        className="inline-flex items-center gap-1"
                      >
                        <HashIcon className="size-4 flex-none text-grey" />
                        <span>{task.id}</span>
                      </span>
                    </TooltipTrigger>
                    <TooltipContent>Replica ID</TooltipContent>
                  </Tooltip>

                  <Tooltip delayDuration={0}>
                    <TooltipTrigger asChild>
                      <span
                        tabIndex={0}
                        className="inline-flex items-center gap-1"
                      >
                        <Layers2Icon className="size-4 flex-none text-grey" />
                        <span>{task.slot}</span>
                      </span>
                    </TooltipTrigger>
                    <TooltipContent>Replica Number</TooltipContent>
                  </Tooltip>
                </TooltipProvider>
              </div>

              <div className="inline-flex items-start gap-1">
                {iconSrc && !iconNotFound ? (
                  <img
                    src={iconSrc}
                    onError={() => setIconNotFound(true)}
                    alt={`Logo for ${image}`}
                    className="size-3 flex-none object-center object-contain rounded-sm relative top-1"
                  />
                ) : (
                  <ContainerIcon className="flex-none size-3 relative top-1" />
                )}
                <small className="break-all inline whitespace-normal text-start">
                  {imageVersion}
                  <span className="text-grey">:{imageSha}</span>
                </small>
              </div>
            </div>
          </AccordionTrigger>

          <AccordionContent
            className={cn(
              "flex items-center gap-6 px-3 py-3 mt-1",
              "w-full border-none rounded-b-md ",
              {
                "bg-emerald-400/10 dark:bg-emerald-600/20 ": color === "green",
                "bg-red-600/10 ": color === "red",
                "bg-yellow-400/10 dark:bg-yellow-600/10 ": color === "yellow",
                "bg-gray-600/10": color === "gray",
                "bg-link/10": color === "blue"
              }
            )}
          >
            <div className="flex flex-col w-full">
              {/* Task message */}
              <div className="text-sm inline-grid items-stretch gap-2 grid-cols-[auto_1fr]">
                <div className="w-4 hidden md:flex flex-col items-center gap-2 h-full self-stretch relative top-1">
                  <MessageCircleMoreIcon className="size-4 flex-none text-grey" />
                  <div className="h-full  bg-grey/50 w-px min-h-5 grow flex-1 mb-1"></div>
                </div>

                <div className="flex flex-col gap-0 w-full">
                  <span>message</span>
                  <span
                    className={cn(
                      "w-full py-2 my-1 break-all rounded-md px-2",
                      {
                        "bg-emerald-400/30 dark:bg-emerald-600/20 text-green-700  dark:text-emerald-400":
                          color === "green",
                        "bg-red-600/25 text-red-700 dark:text-red-400":
                          color === "red",
                        "bg-yellow-400/30 dark:bg-yellow-600/20 text-amber-700 dark:text-yellow-300":
                          color === "yellow",
                        "bg-gray-600/20 dark:bg-gray-600/60 text-gray":
                          color === "gray",
                        "bg-link/30 text-link": color === "blue"
                      }
                    )}
                  >
                    {task.message}
                  </span>
                </div>
              </div>

              {/* container ID */}
              <div className="text-sm inline-grid items-start gap-2 grid-cols-[auto_1fr]">
                <div className="w-4 hidden md:flex flex-col items-center gap-2 relative top-1 h-full self-stretch">
                  <HashIcon className="size-4 flex-none text-grey" />
                  <div className="min-h-3 h-full bg-grey/50 w-px mb-2"></div>
                </div>

                <div className="flex flex-col">
                  <span>container ID</span>
                  <p className="text-grey my-1">
                    {task.container_id === null ? (
                      <pre className="font-mono">{`<empty>`}</pre>
                    ) : (
                      task.container_id
                    )}
                  </p>
                </div>
              </div>

              {/* Exit code */}
              <div className="text-sm inline-grid items-center gap-2 grid-cols-[auto_1fr]">
                <LogOutIcon className="size-4 flex-none text-grey" />

                <div className="flex gap-2 items-center">
                  <span>Exit Code:</span>
                  <Code className={cn(task.exit_code === null && "text-grey")}>
                    {task.exit_code === null ? "<empty>" : task.exit_code}
                  </Code>
                </div>
              </div>
            </div>
          </AccordionContent>
        </AccordionItem>
      </Accordion>
    </Card>
  );
}
