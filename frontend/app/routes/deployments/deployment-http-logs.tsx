import { useInfiniteQuery } from "@tanstack/react-query";
import { ChevronsUpDownIcon, LoaderIcon } from "lucide-react";
import * as React from "react";
import { useSearchParams } from "react-router";
import type { Writeable } from "zod";
import { Code } from "~/components/code";
import { Button } from "~/components/ui/button";
import { Input } from "~/components/ui/input";
import {
  Sheet,
  SheetClose,
  SheetContent,
  SheetDescription,
  SheetFooter,
  SheetHeader,
  SheetTitle,
  SheetTrigger
} from "~/components/ui/sheet";
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
  type HttpLog,
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

  const selectedRequest = logs.find(
    (log) => log.request_id === search.request_id
  );

  return (
    <>
      {selectedRequest && (
        <LogRequestDetails
          log={selectedRequest}
          onClose={() => {
            searchParams.delete("request_id");
            setSearchParams(searchParams);
          }}
        />
      )}
      <div className="flex flex-col h-[60dvh]">
        <Table className="relative h-full overflow-y-auto z-99">
          <TableHeader className="bg-toggle sticky top-0">
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
                        <ChevronsUpDownIcon size={15} className="flex-none" />
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
              <TableHead>
                <TooltipProvider>
                  <Tooltip delayDuration={0}>
                    <TooltipTrigger asChild>
                      <button
                        // onClick={() => handleSort("slug")}
                        className="flex cursor-pointer items-center gap-2"
                      >
                        Duration
                        <ChevronsUpDownIcon size={15} className="flex-none" />
                      </button>
                    </TooltipTrigger>
                    <TooltipContent>
                      <div className="capitalize">Status</div>
                    </TooltipContent>
                  </Tooltip>
                </TooltipProvider>
              </TableHead>
              <TableHead>Host</TableHead>
              <TableHead>Path</TableHead>
              <TableHead>IP</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            <tr className="h-px" />
            {logs.map((log) => (
              <LogTableRow
                log={log}
                key={log.id}
                onClick={() => {
                  if (log.request_id) {
                    searchParams.set("request_id", log.request_id);
                    setSearchParams(searchParams);
                  }
                }}
              />
            ))}
            <TableRow>
              <TableCell colSpan={7} className="relative">
                <div
                  className={cn(
                    "items-center flex gap-2 text-gray-500 px-2",
                    "w-full sticky left-0"
                  )}
                >
                  <LoaderIcon size={15} className="animate-spin" />
                  <p>Fetching previous logs...</p>
                </div>
              </TableCell>
            </TableRow>
          </TableBody>
        </Table>
      </div>
    </>
  );
}

type LogTableRowProps = {
  log: HttpLog;
  onClick?: () => void;
};

function LogTableRow({ log, onClick }: LogTableRowProps) {
  const logTime = formatLogTime(log.time);
  const ip = log.request_headers["X-Forwarded-For"] ?? log.request_ip;

  return (
    <TableRow
      className="border-border cursor-pointer"
      key={log.id}
      onClick={onClick}
    >
      <TableCell>
        <time
          className="text-grey whitespace-nowrap"
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
        {Intl.NumberFormat("en-US").format(log.request_duration_ns / 1_000_000)}
        <span className="text-grey">ms</span>
      </TableCell>
      <TableCell>
        <span className="whitespace-nowrap">{log.request_host}</span>
      </TableCell>
      <TableCell>
        <span className="whitespace-nowrap">
          {log.request_path}
          {log.request_query && (
            <span className="text-grey">?{log.request_query}</span>
          )}
        </span>
      </TableCell>

      <TableCell>
        <span className="text-grey">{ip}</span>
      </TableCell>
    </TableRow>
  );
}

type LogRequestDetailsProps = {
  log: HttpLog;
  onClose?: () => void;
};

export function LogRequestDetails({ log, onClose }: LogRequestDetailsProps) {
  return (
    <Sheet
      open
      onOpenChange={(open) => {
        if (!open) {
          onClose?.();
        }
      }}
    >
      <SheetContent side="right" className="z-99 border-border">
        <SheetHeader>
          <SheetTitle className="font-normal text-card-foreground">
            <Code>{log.request_method}</Code> {log.request_path}
          </SheetTitle>
        </SheetHeader>
        <dl className="flex flex-col gap-4 py-4">{/* ... */}</dl>
      </SheetContent>
    </Sheet>
  );
}

function HeaderSection() {
  return;
}
