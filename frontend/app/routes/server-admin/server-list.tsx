import { useQuery } from "@tanstack/react-query";
import { Link, href, useSearchParams } from "react-router";

import {
  CpuIcon,
  CrownIcon,
  GlobeIcon,
  HeartPulseIcon,
  HourglassIcon,
  LoaderIcon,
  type LucideIcon,
  MemoryStickIcon,
  NetworkIcon,
  PlusIcon,
  PowerOffIcon,
  ServerIcon,
  TerminalIcon,
  TextSearchIcon,
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
import type { Route } from "./+types/server-list";

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

      <ul>
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
  hostname,
  cpus,
  memory_bytes,
  docker_version,
  is_app_server,
  is_build_server,
  status,
  role,
  private_ip,
  is_initial_install_server
}: SwarmNode) {
  const memory =
    memory_bytes !== null ? formatStorageValue(memory_bytes) : null;
  return (
    <Card>
      <CardContent className="rounded-md bg-toggle p-0">
        <div className="flex items-center gap-4.5 p-4 ">
          <div className="flex flex-col items-center p-3 rounded-md gap-3">
            <ServerIcon className="size-8 text-grey flex-none" />
            <Badge variant="outline">server</Badge>
          </div>

          <div className="flex flex-col gap-1.5 items-start">
            <h3 className="font-medium text-lg">{hostname}</h3>

            <div className="flex items-center gap-1">
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
                    <span className="flex items-center gap-0.5 group cursor-help">
                      <GlobeIcon className="size-4 text-grey flex-none" />
                      <span className="sr-only">private IP:</span>
                      &nbsp;
                      <span className="group-hover:underline decoration-wavy decoration-1 ">
                        {private_ip}
                      </span>
                    </span>
                  </TooltipTrigger>
                  <TooltipContent className="max-w-64">
                    Private IP
                  </TooltipContent>
                </Tooltip>

                <span>&middot;</span>

                <Tooltip delayDuration={0}>
                  <TooltipTrigger asChild>
                    <span className="flex items-center gap-0.5 group cursor-help">
                      <NetworkIcon className="size-3.5 flex-none text-grey" />
                      <span className="sr-only">Swarm Role:</span>
                      &nbsp;
                      <span className="group-hover:underline decoration-wavy decoration-1">
                        {capitalizeText(role)}
                      </span>
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

          <div className="flex-grow"></div>

          <div className="self-start flex items-start gap-1 h-full pt-1">
            <TooltipProvider>
              <Tooltip delayDuration={0}>
                <TooltipTrigger asChild>
                  <Button size="sm" variant="ghost" asChild>
                    <Link
                      to={{
                        pathname: href("/admin/server-console")
                      }}
                    >
                      <TerminalIcon className="size-4" />
                      <span className="sr-only">
                        Access to the server's console
                      </span>
                    </Link>
                  </Button>
                </TooltipTrigger>
                <TooltipContent>Access to the server's console</TooltipContent>
              </Tooltip>
              <Tooltip delayDuration={0}>
                <TooltipTrigger asChild>
                  <Button size="sm" variant="ghost" asChild>
                    <Link
                      to={{
                        pathname: href("/admin/server-console")
                      }}
                    >
                      <TextSearchIcon className="size-4" />
                      <span className="sr-only">See deployment logs</span>
                    </Link>
                  </Button>
                </TooltipTrigger>
                <TooltipContent>See server provisionning logs</TooltipContent>
              </Tooltip>
            </TooltipProvider>
          </div>
        </div>

        <CardFooter className="border-border border-t flex items-center gap-2 text-sm py-2 px-4">
          <TooltipProvider>
            <Tooltip delayDuration={0}>
              <TooltipTrigger asChild>
                <span className="flex items-center gap-1">
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
                <span className="flex items-center gap-1">
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
                <span className="flex items-center gap-1">
                  <DockerHubLogo className="size-4 flex-none text-grey" />
                  <span className="sr-only">Docker version:</span>v
                  {docker_version}
                </span>
              </TooltipTrigger>
              <TooltipContent>Docker version</TooltipContent>
            </Tooltip>

            <span className="w-px bg-muted h-3" />

            <div className="flex items-center gap-1">
              {is_app_server && (
                <Tooltip delayDuration={0}>
                  <TooltipTrigger asChild>
                    <Code className="inline-flex items-center gap-1 cursor-help">
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
              {is_build_server && (
                <Tooltip delayDuration={0}>
                  <TooltipTrigger asChild>
                    <Code className="inline-flex items-center gap-1 cursor-help">
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
  DRAINED: "gray"
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
    DRAINED: TriangleAlertIcon
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
