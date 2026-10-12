import { useQuery } from "@tanstack/react-query";
import {
  ChevronRightIcon,
  ContainerIcon,
  HashIcon,
  LoaderIcon,
  MessageCircleMoreIcon
} from "lucide-react";
import * as React from "react";
import type { FullSwarmNode } from "~/api/types";
import type { StatusBadgeColor } from "~/components/status-badge";
import {
  Accordion,
  AccordionContent,
  AccordionItem,
  AccordionTrigger
} from "~/components/ui/accordion";
import { Card } from "~/components/ui/card";
import { swarmQueries } from "~/lib/queries";
import { cn, getDockerImageIconURL } from "~/lib/utils";
import type { Route } from "./+types/swarm-node-services";

type SwarmService = FullSwarmNode["services"][string];

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
} as const satisfies Record<SwarmService["status"], StatusBadgeColor>;

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

  const services = Object.entries(node.services ?? {}).sort(([a], [b]) =>
    a.localeCompare(b)
  );

  return (
    <section className="flex flex-col gap-4 py-4">
      <p className="text-grey">
        Status of the ZaneOps services running on this server, updated on each
        healthcheck.
      </p>
      <ul className="flex flex-col gap-4">
        {services.length === 0 ? (
          <></>
        ) : (
          services.map(([name, service]) => (
            <li key={name}>
              <SwarmNodeService name={name} service={service} />
            </li>
          ))
        )}
      </ul>
    </section>
  );
}

type SwarmNodeServiceProps = {
  service: SwarmService;
  name: string;
  className?: string;
};

function SwarmNodeService({ service, name, className }: SwarmNodeServiceProps) {
  const color = TASK_STATE_COLOR_MAP[service.status];

  const [iconNotFound, setIconNotFound] = React.useState(false);
  const [accordionValue, setAccordionValue] = React.useState("");
  let iconSrc: string | null = null;
  if (service.image) {
    iconSrc = getDockerImageIconURL(service.image);
  }

  const [imageVersion, imageSha] = service.image.split("@");

  const prefix = "zane_zane-";
  const serviceName = name.replace(prefix, "");
  const isLoading = color === "blue";

  return (
    <Card
      className={cn(
        "border border-border p-1 shadow-none group relative flex flex-col gap-1",
        "border-gray-600",
        className
      )}
    >
      <div
        className={cn(
          "rounded-md py-2 pl-4 pr-3 flex flex-col  items-start gap-0 font-normal",
          "md:flex-row md:items-center md:gap-6",
          "relative bg-muted"
        )}
      >
        {/* Status */}
        <div
          className={cn(
            "min-w-26 flex flex-row items-end justify-center h-full gap-2 pt-2 pb-6 md:pt-0 md:pb-0",
            "md:flex-col md:items-start"
          )}
        >
          <div
            className={cn(
              "relative top-0.5 rounded-md text-link px-2  inline-flex gap-1 items-center py-0.5",
              {
                "bg-emerald-400/30 dark:bg-emerald-600/20 text-green-600  dark:text-emerald-400":
                  color === "green",
                "bg-red-600/25 text-red-700 dark:text-red-400": color === "red",
                "bg-yellow-400/30 dark:bg-yellow-600/20 text-amber-700 dark:text-yellow-300":
                  color === "yellow",
                "bg-gray-600/20 dark:bg-gray-600/60 text-card-foreground":
                  color === "gray",
                "bg-blue-500/30 text-link": color === "blue"
              }
            )}
          >
            <code className="text-sm">
              {(service.status === "remove"
                ? "removed"
                : service.status
              ).toUpperCase()}
            </code>
            {isLoading && (
              <LoaderIcon className="animate-spin flex-none" size={15} />
            )}
          </div>
        </div>

        {/* Name & image */}
        <div className="flex flex-col gap-2 grow">
          <div className="flex gap-1 items-center">
            <HashIcon className="size-4 flex-none text-grey md:hidden" />
            <span className="inline text-sm text-start break-all">
              <span className="text-grey hidden md:inline">{prefix}</span>
              <span>{serviceName}</span>
            </span>
          </div>

          <div className="inline-flex items-start gap-1">
            {iconSrc && !iconNotFound ? (
              <img
                src={iconSrc}
                onError={() => setIconNotFound(true)}
                alt={`Logo for ${service.image}`}
                className="size-4 md:size-3 flex-none object-center object-contain rounded-sm relative top-1"
              />
            ) : (
              <ContainerIcon className="flex-none size-3 relative top-0.5" />
            )}
            <small className="break-all inline whitespace-normal text-start text-xs">
              {imageVersion}
              <span className="text-grey">@{imageSha}</span>
            </small>
          </div>
        </div>
      </div>

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
          value={`service-${name}`}
          className="w-full p-0 font-normal border-none"
        >
          <AccordionTrigger
            className={cn(
              "rounded-md py-1 px-4 flex items-center gap-6 font-normal cursor-pointer",
              "data-[state=open]:rounded-b-none [&[data-state=open]_svg]:rotate-90",
              "bg-muted"
            )}
          >
            <div className="flex w-full items-center">
              <span className="text-sm">details</span>
              <ChevronRightIcon className="size-4" />
            </div>
          </AccordionTrigger>

          <AccordionContent
            className={cn(
              "flex items-center gap-6 px-3 py-3",
              "w-full border-none rounded-b-md",
              "bg-muted"
            )}
          >
            <div className="flex flex-col w-full">
              {/* Task message */}
              <div className="text-sm inline-grid items-stretch gap-2 grid-cols-[auto_1fr]">
                <div className="w-4 hidden md:flex flex-col items-center gap-2 h-full self-stretch relative top-1">
                  <MessageCircleMoreIcon className="size-4 flex-none text-grey" />
                </div>

                <div className="flex flex-col gap-0 w-full">
                  <span>Message</span>
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
                        "bg-blue-500/30 text-link dark:text-blue-100":
                          color === "blue"
                      }
                    )}
                  >
                    {service.message}
                  </span>
                </div>
              </div>
            </div>
          </AccordionContent>
        </AccordionItem>
      </Accordion>
    </Card>
  );
}
