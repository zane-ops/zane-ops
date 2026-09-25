import { useQuery } from "@tanstack/react-query";
import { Link, useSearchParams } from "react-router";

import {
  BrainIcon,
  ClockPlusIcon,
  CpuIcon,
  CrownIcon,
  HeartPulseIcon,
  HourglassIcon,
  LoaderIcon,
  type LucideIcon,
  MemoryStickIcon,
  PenLineIcon,
  PickaxeIcon,
  PlusIcon,
  PowerOffIcon,
  ServerIcon,
  TerminalIcon,
  TriangleAlertIcon,
  XIcon
} from "lucide-react";
import type { SwarmNode } from "~/api/types";
import { Code } from "~/components/code";
import { DockerHubLogo } from "~/components/docker-hub-logo";
import { Pagination } from "~/components/pagination";
import type { StatusBadgeColor } from "~/components/status-badge";
import { Badge } from "~/components/ui/badge";
import { Button } from "~/components/ui/button";
import { Card, CardContent, CardFooter } from "~/components/ui/card";
import { Separator } from "~/components/ui/separator";
import {
  Tooltip,
  TooltipContent,
  TooltipProvider,
  TooltipTrigger
} from "~/components/ui/tooltip";
import { swarmNodeListFilters, swarmQueries } from "~/lib/queries";
import { getQueryClient } from "~/lib/query-client";
import {
  capitalizeText,
  cn,
  formatStorageValue,
  metaTitle,
  pluralize
} from "~/lib/utils";
import type { Route } from "./+types/swarm-node-list";

export function meta() {
  return [
    metaTitle("ZaneOps Cluster")
  ] satisfies ReturnType<Route.MetaFunction>;
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

export default function SwarmNodeListPage({
  loaderData
}: Route.ComponentProps) {
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
        <h2 className="text-2xl">ZaneOps Cluster</h2>
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

      <ul className="flex flex-col w-full items-stretch gap-4">
        {nodes.map((node) => (
          <ServerCard key={node.id} {...node} />
        ))}
      </ul>

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

export function ServerCard({
  id,
  hostname,
  cpus,
  memory_bytes,
  docker_version,
  cluster_roles,
  status,
  swarm_role: role,
  private_ip,
  is_initial_install_server
}: SwarmNode) {
  const memory =
    memory_bytes !== null ? formatStorageValue(memory_bytes) : null;
  return (
    <Card>
      <CardContent className="rounded-md bg-toggle p-0">
        <div className="flex items-center gap-4.5 p-4">
          <div className="flex flex-col items-center p-3 rounded-md gap-3">
            <ServerIcon className="size-8 text-grey flex-none" />
            <Badge variant="outline">server</Badge>
          </div>

          <div className="flex flex-col gap-1.5 items-start w-full">
            <div className="flex items-center gap-2 w-full justify-between">
              <h3 className="font-medium text-lg">
                {hostname ? (
                  <span>
                    {hostname}
                    <span className="text-grey">@{private_ip}</span>{" "}
                  </span>
                ) : (
                  private_ip
                )}
              </h3>

              <div className="flex items-center gap-2">
                <Button
                  size="icon"
                  variant="ghost"
                  asChild
                  className="text-xs py-1.5 px-2.5 w-auto h-auto gap-2"
                >
                  <Link to={`./${id}`}>
                    <PenLineIcon className="size-4 flex-none text-grey" />
                    <span className="">Details</span>
                  </Link>
                </Button>

                <span className="w-px bg-muted h-3 rounded-lg" />
                <Button
                  size="icon"
                  variant="ghost"
                  asChild
                  className="text-xs py-1.5 px-2.5 w-auto h-auto gap-1"
                >
                  <Link to={`./${id}/console`}>
                    <TerminalIcon className="size-4 flex-none text-grey" />
                    <span className="">Console</span>
                  </Link>
                </Button>
              </div>
            </div>

            <div className="flex items-center gap-1 mb-0.5">
              {is_initial_install_server && (
                <div className="py-1 text-sm rounded-md bg-link/20 text-link px-2  inline-flex gap-1 items-center">
                  <CrownIcon className="size-4 flex-none" />
                  <p>Main server</p>
                </div>
              )}
              <ServerStatusBadge status={status} className="text-sm" />
            </div>

            <div className="flex items-center gap-2.5 text-sm">
              <TooltipProvider>
                <Tooltip delayDuration={0}>
                  <TooltipTrigger asChild>
                    <span className=" group cursor-help">
                      <div
                        className={cn(
                          "py-1 text-sm rounded-md px-2 inline-flex gap-1 items-center",
                          role === "WORKER"
                            ? "bg-slate-400/20 dark:bg-slate-600/25 text-slate-600 dark:text-slate-400"
                            : "bg-purple-600/20 text-purple-600 dark:text-purple-400"
                        )}
                      >
                        {role === "MANAGER" ? (
                          <BrainIcon className="size-3.5 flex-none" />
                        ) : (
                          <PickaxeIcon className="size-3.5 flex-none" />
                        )}
                        <span className="sr-only">Swarm Role: </span>
                        <span className="group-hover:underline decoration-wavy decoration-1">
                          {role}
                        </span>
                      </div>
                    </span>
                  </TooltipTrigger>
                  <TooltipContent className="max-w-64">
                    <span className="text-grey dark:text-card-foreground">
                      Swarm Role:
                    </span>
                    &nbsp;
                    {role === "MANAGER"
                      ? "Manager · maintains the cluster state and schedules services onto the other servers."
                      : "Worker · only runs the services assigned to it by the managers."}
                  </TooltipContent>
                </Tooltip>
              </TooltipProvider>
            </div>
          </div>
        </div>

        <CardFooter className="border-border border-t flex items-center gap-2 text-sm py-2 px-4">
          <TooltipProvider>
            <Tooltip delayDuration={0}>
              <TooltipTrigger asChild>
                <span className="flex items-center gap-1 cursor-help hover:underline decoration-1 decoration-wavy">
                  <CpuIcon className="size-4 flex-none text-grey" />
                  <span className="sr-only">CPU count:</span>
                  {cpus !== null ? (
                    <span>
                      {cpus} {pluralize("CPU", cpus)}
                    </span>
                  ) : (
                    "-"
                  )}
                </span>
              </TooltipTrigger>
              <TooltipContent>CPU count</TooltipContent>
            </Tooltip>

            <span>&middot;</span>

            <Tooltip delayDuration={0}>
              <TooltipTrigger asChild>
                <span className="flex items-center gap-1 cursor-help hover:underline decoration-1 decoration-wavy">
                  <MemoryStickIcon className="size-4 flex-none text-grey" />
                  <span className="sr-only">Memory:</span>
                  {memory ? `${memory.value} ${memory.unit}` : "-"}
                </span>
              </TooltipTrigger>
              <TooltipContent>Memory</TooltipContent>
            </Tooltip>

            <span>&middot;</span>

            <Tooltip delayDuration={0}>
              <TooltipTrigger asChild>
                <span className="flex items-center gap-1 cursor-help hover:underline decoration-1 decoration-wavy">
                  <DockerHubLogo className="size-4 flex-none text-grey" />
                  <span className="sr-only">Docker version:</span>v
                  {docker_version ?? "[-]"}
                </span>
              </TooltipTrigger>
              <TooltipContent>Docker version</TooltipContent>
            </Tooltip>

            <span className="w-px bg-muted h-3" />

            <div className="flex items-center gap-1">
              {cluster_roles.includes("APP_SERVER") && (
                <Tooltip delayDuration={0}>
                  <TooltipTrigger asChild>
                    <Code className="inline-flex items-center gap-1 cursor-help decoration-1 decoration-wavy hover:underline">
                      app server
                    </Code>
                  </TooltipTrigger>
                  <TooltipContent className="max-w-64">
                    <span className="dark:text-card-foreground text-grey">
                      App server:
                    </span>{" "}
                    your services can be deployed and run on this server.
                  </TooltipContent>
                </Tooltip>
              )}
              {cluster_roles.includes("BUILD_SERVER") && (
                <Tooltip delayDuration={0}>
                  <TooltipTrigger asChild>
                    <Code className="inline-flex items-center gap-1 cursor-help decoration-1 decoration-wavy hover:underline">
                      build server
                    </Code>
                  </TooltipTrigger>
                  <TooltipContent className="max-w-64">
                    <span className="dark:text-card-foreground text-grey">
                      Build server:
                    </span>{" "}
                    docker images for git services are built on this server.
                  </TooltipContent>
                </Tooltip>
              )}
            </div>
          </TooltipProvider>
        </CardFooter>
      </CardContent>
    </Card>
  );
}

const SERVER_STATUS_COLOR_MAP = {
  READY: "green",
  PROVISIONING: "blue",
  DOWN: "red",
  FAILED: "red",
  DRAINED: "gray",
  CREATED: "gray"
} as const satisfies Record<SwarmNode["status"], StatusBadgeColor>;

type ServerStatusBadgeProps = {
  status: SwarmNode["status"];
  className?: string;
  variant?: "outline" | "ghost";
};

export function ServerStatusBadge({
  status,
  className,
  variant = "ghost"
}: ServerStatusBadgeProps) {
  const color = SERVER_STATUS_COLOR_MAP[status];

  const icons = {
    READY: HeartPulseIcon,
    PROVISIONING: HourglassIcon,
    DOWN: PowerOffIcon,
    FAILED: XIcon,
    DRAINED: TriangleAlertIcon,
    CREATED: ClockPlusIcon
  } as const satisfies Record<typeof status, LucideIcon>;

  const Icon = icons[status];

  const isLoading = status === "PROVISIONING";
  const isActive = status === "READY";

  return (
    <div
      className={cn(
        " rounded-md bg-link/20 text-link px-2 py-1  inline-flex gap-1 items-center",
        {
          "bg-emerald-400/20 dark:bg-emerald-600/20 text-green-600  dark:text-emerald-400":
            color === "green",
          "bg-red-600/10 text-red-600 dark:text-red-400": color === "red",
          "bg-gray-600/20 dark:bg-gray-600/60 text-gray": color === "gray",
          "bg-link/20 text-link": color === "blue"
        },
        variant === "outline" && "!bg-transparent",
        className
      )}
    >
      <div className="relative">
        {isActive && (
          <Icon
            size={15}
            className="flex-none animate-ping absolute h-full w-full"
          />
        )}
        <Icon size={15} className="flex-none" />
      </div>
      <p>{capitalizeText(status.replaceAll("_", " "))}</p>
      {isLoading && <LoaderIcon className="animate-spin flex-none" size={15} />}
    </div>
  );
}
