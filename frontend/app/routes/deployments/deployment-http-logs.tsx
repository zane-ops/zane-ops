import { useInfiniteQuery } from "@tanstack/react-query";
import { ArrowDown, Folder, Settings } from "lucide-react";
import * as React from "react";
import { Link, useSearchParams } from "react-router";
import type { Writeable } from "zod";
import type { StatusBadge } from "~/components/status-badge";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow
} from "~/components/ui/table";
import {
  Tooltip,
  TooltipContent,
  TooltipProvider,
  TooltipTrigger
} from "~/components/ui/tooltip";
import {
  type DeploymentHTTPLogFilters,
  REQUEST_METHODS,
  deploymentHttpLogSearchSchema,
  deploymentQueries
} from "~/lib/queries";
import { cn, formatLogTime } from "~/lib/utils";
import { queryClient } from "~/root";
import { type Route } from "./+types/deployment-http-logs";

export async function clientLoader({
  request,
  params: {
    deploymentHash: deployment_hash,
    projectSlug: project_slug,
    serviceSlug: service_slug
  }
}: Route.ClientLoaderArgs) {
  const searchParams = new URL(request.url).searchParams;
  const search = deploymentHttpLogSearchSchema.parse(searchParams);
  const filters = {
    time_after: search.time_after,
    time_before: search.time_before,
    request_method:
      search.request_method ??
      (REQUEST_METHODS as Writeable<typeof REQUEST_METHODS>),
    request_host: search.request_host,
    request_ip: search.request_ip,
    request_path: search.request_path,
    status: search.status
  } satisfies DeploymentHTTPLogFilters;

  const httpLogs = await queryClient.ensureInfiniteQueryData(
    deploymentQueries.httpLogs({
      deployment_hash,
      project_slug,
      service_slug,
      filters,
      queryClient
    })
  );
  return { httpLogs };
}

export default function DeploymentHttpLogsPage({
  loaderData,
  params: {
    deploymentHash: deployment_hash,
    projectSlug: project_slug,
    serviceSlug: service_slug
  }
}: Route.ComponentProps) {
  const [searchParams, setSearchParams] = useSearchParams();
  const search = deploymentHttpLogSearchSchema.parse(searchParams);
  const [isAutoRefetchEnabled, setIsAutoRefetchEnabled] = React.useState(true);

  const filters = {
    time_after: search.time_after,
    time_before: search.time_before,
    request_method:
      search.request_method ??
      (REQUEST_METHODS as Writeable<typeof REQUEST_METHODS>),
    request_host: search.request_host,
    request_ip: search.request_ip,
    request_path: search.request_path,
    status: search.status
  } satisfies DeploymentHTTPLogFilters;

  const logsQuery = useInfiniteQuery({
    ...deploymentQueries.httpLogs({
      deployment_hash,
      project_slug,
      service_slug,
      filters,
      queryClient,
      autoRefetchEnabled: isAutoRefetchEnabled
    }),
    initialData: loaderData.httpLogs
  });

  const logs = logsQuery.data.pages.flatMap((item) => item.results);

  return (
    <Table>
      <TableHeader className="bg-toggle">
        <TableRow className="border-none">
          <TableHead>
            <TooltipProvider>
              <Tooltip delayDuration={0}>
                <TooltipTrigger asChild>
                  <button
                    // onClick={() => handleSort("slug")}
                    className="flex cursor-pointer items-center gap-2"
                  >
                    Date
                    <ArrowDown size={15} className="flex-none" />
                  </button>
                </TooltipTrigger>
                <TooltipContent>
                  <div className="capitalize">Status</div>
                </TooltipContent>
              </Tooltip>
            </TooltipProvider>
          </TableHead>
          <TableHead>Method</TableHead>
          <TableHead>Status</TableHead>
          <TableHead>Duration</TableHead>
          <TableHead>Host</TableHead>
          <TableHead>Path</TableHead>
          <TableHead>IP</TableHead>
        </TableRow>
      </TableHeader>
      <TableBody>
        {logs.map((log) => {
          const logTime = formatLogTime(log.time);
          return (
            <TableRow className="border-border cursor-pointer" key={log.id}>
              <TableCell className="font-medium ">
                <time
                  className="text-grey"
                  dateTime={new Date(log.time).toISOString()}
                >
                  <span className="sr-only sm:not-sr-only">
                    {logTime.dateFormat},&nbsp;
                  </span>
                  <span>{logTime.hourFormat}</span>
                </time>
              </TableCell>
              <TableCell>{log.request_method}</TableCell>
              <TableCell
                className={cn("", {
                  "text-blue-600": log.status.toString().startsWith("1"),
                  "text-green-600": log.status.toString().startsWith("2"),
                  "text-grey": log.status.toString().startsWith("3"),
                  "text-yellow-600": log.status.toString().startsWith("4"),
                  "text-red-600": log.status.toString().startsWith("5")
                })}
              >
                {log.status}
              </TableCell>
              <TableCell>
                {Intl.NumberFormat("en-US").format(
                  log.request_duration_ns / 1_000_000
                )}
                <span className="text-grey">ms</span>
              </TableCell>
              <TableCell>{log.request_host}</TableCell>
              <TableCell>
                {log.request_path}
                {log.request_query && (
                  <span className="text-grey">?{log.request_query}</span>
                )}
              </TableCell>

              <TableCell>
                <span className="text-grey">{log.request_ip}</span>
              </TableCell>
            </TableRow>
          );
        })}
      </TableBody>
    </Table>
  );
}
