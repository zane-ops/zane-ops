import { useInfiniteQuery } from "@tanstack/react-query";
import {
  CheckIcon,
  ChevronRightIcon,
  ChevronsUpDownIcon,
  Code,
  CopyIcon,
  FilterIcon,
  LoaderIcon
} from "lucide-react";
import * as React from "react";
import { useSearchParams } from "react-router";
import { type Writeable, z } from "zod";
import { CopyButton } from "~/components/copy-button";
import { StatusBadge, type StatusBadgeColor } from "~/components/status-badge";
import {
  Accordion,
  AccordionContent,
  AccordionItem,
  AccordionTrigger
} from "~/components/ui/accordion";
import { Button } from "~/components/ui/button";
import {
  Sheet,
  SheetContent,
  SheetHeader,
  SheetTitle
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
import { formattedTime, pluralize, wait } from "~/utils";
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

  const [httpLogs, httpLog] = await Promise.all([
    queryClient.ensureInfiniteQueryData(
      deploymentQueries.httpLogs({
        deployment_hash,
        project_slug,
        service_slug,
        filters,
        queryClient
      })
    ),
    search.request_id
      ? queryClient.ensureQueryData(
          deploymentQueries.singleHttpLog({
            deployment_hash,
            project_slug,
            request_uuid: search.request_id,
            service_slug
          })
        )
      : undefined
  ] as const);
  return { httpLogs, httpLog };
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
    <>
      <LogRequestDetails
        open={Boolean(loaderData.httpLog)}
        log={loaderData.httpLog}
        onClose={() => {
          searchParams.delete("request_id");
          setSearchParams(searchParams, { replace: true });
        }}
      />

      <div className="flex flex-col h-[60dvh]">
        <Table className="relative h-full overflow-y-auto z-50">
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
                    // navigate(`./${log.request_id}`);
                    searchParams.set("request_id", log.request_id);
                    setSearchParams(searchParams, { replace: true });
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
        <p className="whitespace-nowrap max-w-[150px] text-ellipsis overflow-x-hidden flex-shrink">
          {log.request_host}
        </p>
      </TableCell>
      <TableCell>
        <p className="whitespace-nowrap max-w-[300px] text-ellipsis overflow-x-hidden flex-shrink">
          {log.request_path}
          {log.request_query && (
            <span className="text-grey">?{log.request_query}</span>
          )}
        </p>
      </TableCell>

      <TableCell>
        <p className="text-grey whitespace-nowrap max-w-[150px] text-ellipsis overflow-x-hidden flex-shrink">
          {ip}
        </p>
      </TableCell>
    </TableRow>
  );
}

type LogRequestDetailsProps = {
  log?: HttpLog;
  open?: boolean;
  onClose?: () => void;
};

export function LogRequestDetails({
  log,
  onClose,
  open = false
}: LogRequestDetailsProps) {
  return (
    <Sheet
      open={open}
      onOpenChange={(open) => {
        if (!open) {
          onClose?.();
        }
      }}
    >
      <SheetContent
        side="right"
        className="z-99 border-border flex flex-col gap-4 overflow-y-auto"
      >
        {log && <LogRequestDetailsContent log={log} />}
      </SheetContent>
    </Sheet>
  );
}

function LogRequestDetailsContent({ log }: { log: HttpLog }) {
  const searchParams = new URLSearchParams(log.request_query ?? "");
  const ip = log.request_headers["X-Forwarded-For"]?.[0] ?? log.request_ip;

  const isIPv6 = z.string().ip({ version: "v6" }).safeParse(ip).success;

  return (
    <>
      <SheetHeader>
        <SheetTitle className="font-normal text-card-foreground mt-5 text-base">
          <span className="border border-gray-600 bg-gray-600/10 px-2 py-1 border-opacity-60 rounded-md ">
            {log.request_method}
          </span>
          &nbsp;
          <span className="font-medium">{log.request_path}</span>
        </SheetTitle>
      </SheetHeader>
      <hr className="border-border -mx-6" />
      <h3>Request metadata:</h3>

      <dl className="flex flex-col gap-x-4 gap-y-2 items-center auto-rows-max">
        <div className="grid grid-cols-2 items-center gap-x-4 w-full">
          <dt className="text-grey  inline-flex items-center">ID</dt>
          <dd className="text-sm">{log.request_id}</dd>
        </div>

        <div className="grid grid-cols-2 items-center gap-x-4 w-full">
          <dt className="text-grey  inline-flex items-center">Status code</dt>
          <dd
            className={cn("", {
              "text-blue-600": log.status.toString().startsWith("1"),
              "text-green-600": log.status.toString().startsWith("2"),
              "text-grey": log.status.toString().startsWith("3"),
              "text-yellow-600": log.status.toString().startsWith("4"),
              "text-red-600": log.status.toString().startsWith("5")
            })}
          >
            {log.status}
          </dd>
        </div>

        <div className="grid grid-cols-2 items-center gap-x-4 w-full">
          <dt className="text-grey  inline-flex items-center">Date</dt>
          <dd className="text-sm">
            <time
              className="text-grey whitespace-nowrap"
              dateTime={new Date(log.time).toISOString()}
            >
              {formattedTime(log.time)}
            </time>
          </dd>
        </div>

        <div className="grid grid-cols-2 items-center gap-x-4 w-full">
          <dt className="text-grey  inline-flex items-center">Duration</dt>
          <dd className="text-sm">
            {Intl.NumberFormat("en-US").format(
              log.request_duration_ns / 1_000_000
            )}
            <span className="text-grey">ms</span>
          </dd>
        </div>

        <div className="grid grid-cols-2 items-center gap-x-4 w-full">
          <dt className="text-grey  inline-flex items-center">Client IP</dt>
          <dd className="text-sm break-all text-grey">{ip}</dd>
        </div>

        <div className="grid grid-cols-2 items-center gap-x-4 w-full">
          <dt className="text-grey  inline-flex items-center">Protocol</dt>
          <dd className="text-sm">{log.request_protocol}</dd>
        </div>

        <div className="grid grid-cols-2 items-start gap-x-4 w-full group">
          <dt className="text-grey inline-flex items-center gap-1 group">
            <span>User Agent</span>
            <TooltipProvider>
              <Tooltip delayDuration={0}>
                <TooltipTrigger asChild>
                  <Button
                    variant="ghost"
                    className="px-2.5 py-0.5 md:opacity-0 focus-visible:opacity-100 group-hover:opacity-100"
                  >
                    <FilterIcon size={15} />
                    <span className="sr-only">Filter this host</span>
                  </Button>
                </TooltipTrigger>
                <TooltipContent>Filter this host</TooltipContent>
              </Tooltip>

              <Tooltip delayDuration={0}>
                <TooltipTrigger asChild>
                  <CopyButton
                    label="Copy value"
                    value={log.request_user_agent ?? ""}
                  />
                </TooltipTrigger>
                <TooltipContent>Copy value</TooltipContent>
              </Tooltip>
            </TooltipProvider>
          </dt>
          <dd className="text-sm text-grey">
            {log.request_user_agent ?? <span className="font-mono">N/A</span>}
          </dd>
        </div>
      </dl>

      <hr className="border-border -mx-6" />

      <h3>URL data:</h3>
      <dl className="flex flex-col gap-x-4 gap-y-2 items-center auto-rows-max">
        <div className="grid grid-cols-2 items-center gap-x-4 w-full group">
          <dt className="text-grey inline-flex items-center gap-1 group">
            <span>Host</span>
            <TooltipProvider>
              <Tooltip delayDuration={0}>
                <TooltipTrigger asChild>
                  <Button
                    variant="ghost"
                    className="px-2.5 py-0.5 md:opacity-0 focus-visible:opacity-100 group-hover:opacity-100"
                  >
                    <FilterIcon size={15} />
                    <span className="sr-only">Filter this host</span>
                  </Button>
                </TooltipTrigger>
                <TooltipContent>Filter this host</TooltipContent>
              </Tooltip>

              <Tooltip delayDuration={0}>
                <TooltipTrigger asChild>
                  <CopyButton label="Copy value" value={log.request_host} />
                </TooltipTrigger>
                <TooltipContent>Copy value</TooltipContent>
              </Tooltip>
            </TooltipProvider>
          </dt>
          <dd className="text-sm">{log.request_host}</dd>
        </div>

        <div className="grid grid-cols-2 items-center gap-x-4 w-full">
          <dt className="text-grey inline-flex items-center gap-1 group">
            <span>Pathname</span>
            <TooltipProvider>
              <Tooltip delayDuration={0}>
                <TooltipTrigger asChild>
                  <Button
                    variant="ghost"
                    className="px-2.5 py-0.5 md:opacity-0 focus-visible:opacity-100 group-hover:opacity-100"
                  >
                    <FilterIcon size={15} />
                    <span className="sr-only">Filter this pathname</span>
                  </Button>
                </TooltipTrigger>
                <TooltipContent>Filter this pathname</TooltipContent>
              </Tooltip>

              <Tooltip delayDuration={0}>
                <TooltipTrigger asChild>
                  <CopyButton label="Copy value" value={log.request_path} />
                </TooltipTrigger>
                <TooltipContent>Copy value</TooltipContent>
              </Tooltip>
            </TooltipProvider>
          </dt>
          <dd className="text-sm">{log.request_path}</dd>
        </div>

        {log.request_query && (
          <div className="grid grid-cols-2 items-center gap-x-4 w-full border-b-0 border-border pb-2">
            <dt className="text-grey inline-flex items-center gap-1 group">
              <span>Query</span>
              <TooltipProvider>
                <Tooltip delayDuration={0}>
                  <TooltipTrigger asChild>
                    <Button
                      variant="ghost"
                      className="px-2.5 py-0.5 md:opacity-0 focus-visible:opacity-100 group-hover:opacity-100"
                    >
                      <FilterIcon size={15} />
                      <span className="sr-only">Filter this query</span>
                    </Button>
                  </TooltipTrigger>
                  <TooltipContent>Filter this query</TooltipContent>
                </Tooltip>

                <Tooltip delayDuration={0}>
                  <TooltipTrigger asChild>
                    <CopyButton
                      label="Copy value"
                      value={`?${log.request_query}`}
                    />
                  </TooltipTrigger>
                  <TooltipContent>Copy value</TooltipContent>
                </Tooltip>
              </TooltipProvider>
            </dt>
            <dd className="text-sm">
              <span className="text-grey">{"?"}</span>
              {searchParams.entries().map(([key, value], index) => (
                <span key={`${key}-${index}`}>
                  <span className="text-link">{key}</span>
                  {value && (
                    <>
                      <span className="text-grey">{"="}</span>
                      <span className="text-card-foreground break-all">
                        {value}
                      </span>
                    </>
                  )}
                  {index < searchParams.size - 1 && (
                    <span className="text-grey">{"&"}</span>
                  )}
                </span>
              ))}
            </dd>
          </div>
        )}
      </dl>

      <hr className="border-border -mx-6" />
      <Accordion type="single" collapsible defaultValue="request">
        <AccordionItem value="request" className="border-0">
          <AccordionTrigger className="gap-2 py-0 data-[state=open]:pb-4">
            <ChevronRightIcon className="h-4 w-4 shrink-0 transition-transform duration-200" />
            <h3>Response headers:</h3>
          </AccordionTrigger>
          <AccordionContent className="flex flex-col pb-0">
            <dl className="flex flex-col gap-0.5 text-base">
              {transformHeadersObjectToArray(log.response_headers).map(
                ([key, value]) => (
                  <div className="inline gap-1 w-full" key={`${key}-${value}`}>
                    <dt className="text-link inline flex-none">{key}:</dt>
                    &nbsp;&nbsp;
                    <dd className="break-all inline text-grey">{value}</dd>
                  </div>
                )
              )}
            </dl>
          </AccordionContent>
        </AccordionItem>
      </Accordion>
      <hr className="border-border -mx-6" />
      <Accordion type="single" collapsible defaultValue="response">
        <AccordionItem value="response" className="border-0">
          <AccordionTrigger className="gap-2 py-0 data-[state=open]:pb-4">
            <ChevronRightIcon className="h-4 w-4 shrink-0 transition-transform duration-200" />
            <h3>Request headers:</h3>
          </AccordionTrigger>
          <AccordionContent className="flex flex-col pb-0">
            <dl className="flex flex-col gap-0.5 text-base">
              {transformHeadersObjectToArray(log.request_headers).map(
                ([key, value]) => (
                  <div className="inline gap-1 w-full" key={`${key}-${value}`}>
                    <dt className="text-link inline flex-none">{key}:</dt>
                    &nbsp;&nbsp;
                    <dd className="break-all inline text-grey">{value}</dd>
                  </div>
                )
              )}
            </dl>
          </AccordionContent>
        </AccordionItem>
      </Accordion>
      <hr className="border-border -mx-6" />
    </>
  );
}

function transformHeadersObjectToArray(current: {
  [key: string]: string[];
}): Array<[string, string]> {
  const target: Array<[string, string]> = [];

  for (const key in current) {
    if (current.hasOwnProperty(key)) {
      current[key].forEach((value) => {
        target.push([key, value]);
      });
    }
  }

  return target;
}

function HeaderSection() {
  return;
}
