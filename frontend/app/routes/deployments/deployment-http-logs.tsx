import { useInfiniteQuery } from "@tanstack/react-query";
import {
  ChevronsUpDownIcon,
  LoaderIcon,
  Maximize2Icon,
  Minimize2Icon,
  PlusIcon,
  XIcon
} from "lucide-react";
import * as React from "react";
import { useSearchParams } from "react-router";
import type { Writeable } from "zod";
import { HttpLogRequestDetails } from "~/components/http-log-request-details";
import { Button } from "~/components/ui/button";

import type { DateRange } from "react-day-picker";
import { flushSync } from "react-dom";
import { useDebouncedCallback } from "use-debounce";
import { DateRangeWithShortcuts } from "~/components/date-range-with-shortcuts";
import { MultiSelect } from "~/components/multi-select";
import { Ping } from "~/components/ping";
import { Input } from "~/components/ui/input";
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
import type { Route } from "./+types/deployment-http-logs";

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
    request_query: search.request_query,
    request_user_agent: search.request_user_agent,
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
    request_query: search.request_query,
    request_user_agent: search.request_user_agent,
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
    <div
      className={cn(
        search.isMaximized &&
          "fixed inset-0 top-28 bg-background z-50 p-5 w-full"
      )}
    >
      <HttpLogRequestDetails
        open={Boolean(loaderData.httpLog)}
        log={loaderData.httpLog}
        onClose={() => {
          searchParams.delete("request_id");
          setSearchParams(searchParams, { replace: true });
        }}
      />

      <div
        className={cn(
          "flex flex-col gap-4",
          search.isMaximized ? "container px-0 h-[82dvh]" : "h-[60dvh] mt-8"
        )}
      >
        <HeaderSection />
        <Table className="relative h-full overflow-y-auto z-50">
          <TableHeader className="bg-toggle sticky top-0 z-20">
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
            <tr className="">
              <td
                colSpan={7}
                className="px-4 text-sm text-grey h-6 border-b border-border py-2"
              >
                <div className="h-px" />
                <div className="inline-flex items-center gap-2">
                  <Ping />
                  <em className="text-green-500">LIVE</em> -- New requests will
                  appear here
                </div>
              </td>
            </tr>
            {logs.map((log) => (
              <LogTableRow
                log={log}
                key={log.id}
                onClick={() => {
                  if (log.request_id) {
                    searchParams.set("request_id", log.request_id);
                    setSearchParams(searchParams, { replace: true });
                  }
                }}
              />
            ))}
            <TableRow className="hover:bg-transparent">
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
    </div>
  );
}

type LogTableRowProps = {
  log: HttpLog;
  onClick?: () => void;
};

function LogTableRow({ log, onClick }: LogTableRowProps) {
  const logTime = formatLogTime(log.time);
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
          {log.request_ip}
        </p>
      </TableCell>
    </TableRow>
  );
}

function HeaderSection() {
  const [, startTransition] = React.useTransition();
  const [searchParams, setSearchParams] = useSearchParams();
  const search = deploymentHttpLogSearchSchema.parse(searchParams);

  const inputRef = React.useRef<React.ComponentRef<"input">>(null);

  const date: DateRange = {
    from: search.time_after,
    to: search.time_before
  };

  const possible_fields = [
    "request_host",
    "request_path",
    "request_query",
    "request_user_agent",
    "request_ip",
    "status"
  ] satisfies Array<keyof DeploymentHTTPLogFilters>;

  const [selectedFields, setSelectedFields] = React.useState(
    possible_fields.filter((field) => field in search)
  );

  const available_fields = possible_fields.filter(
    (field) => !selectedFields.includes(field)
  );

  const isEmptySearchParams =
    !search.time_after &&
    !search.time_before &&
    (search.request_method ?? []).length === 0 &&
    possible_fields.every((field) => !(field in search));

  const clearFilters = () => {
    startTransition(() => {
      setSearchParams(
        new URLSearchParams([["isMaximized", `${search.isMaximized}`]]),
        {
          replace: true
        }
      );
      setSelectedFields([]);
    });

    if (inputRef.current) {
      inputRef.current.value = "";
    }
  };

  const searchForQuery = useDebouncedCallback((query: string) => {
    startTransition(() => {
      searchParams.set("request_query", query);
      setSearchParams(searchParams, { replace: true });
    });
  }, 300);

  const parentRef = React.useRef<React.ComponentRef<"section">>(null);

  return (
    <>
      <section
        className="rounded-t-sm w-full flex gap-2 items-start justify-between"
        ref={parentRef}
      >
        <div className="flex items-center gap-2 flex-wrap">
          <DateRangeWithShortcuts
            date={date}
            setDate={(newDateRange) => {
              searchParams.delete("time_before");
              searchParams.delete("time_after");
              if (newDateRange?.to) {
                searchParams.set("time_before", newDateRange?.to.toISOString());
              }
              if (newDateRange?.from) {
                searchParams.set(
                  "time_after",
                  newDateRange?.from.toISOString()
                );
              }
              setSearchParams(searchParams, { replace: true });
            }}
            className="w-[250px] grow"
          />

          <MultiSelect
            value={search.request_method as string[]}
            className="w-auto"
            options={REQUEST_METHODS as Writeable<typeof REQUEST_METHODS>}
            onValueChange={(newVal) => {
              searchParams.delete("request_method");
              for (const value of newVal) {
                searchParams.append("request_method", value);
              }
              setSearchParams(searchParams, { replace: true });
            }}
            label="method"
          />

          {selectedFields.includes("request_query") && (
            <div className="inline-flex items-center gap-1">
              <Input
                placeholder="query"
                name="request_query"
                className="max-w-40"
                defaultValue={search.request_query}
                onChange={(ev) => {
                  const newQuery = ev.currentTarget.value;
                  if (newQuery !== (search.request_query ?? "")) {
                    searchForQuery(
                      newQuery.startsWith("?")
                        ? newQuery.substring(1)
                        : newQuery
                    );
                  }
                }}
              />
              <Button
                onClick={() => {
                  setSelectedFields((fields) =>
                    fields.filter((field) => field !== "request_query")
                  );
                  searchParams.delete("request_query");
                  setSearchParams(searchParams, { replace: true });
                }}
                variant="outline"
                className="bg-inherit"
                type="button"
              >
                <XIcon size={15} className="flex-none" />
                <span className="sr-only">Remove field</span>
              </Button>
            </div>
          )}

          {selectedFields.includes("status") && (
            <div className="inline-flex items-center gap-1">
              <MultiSelect
                value={search.status ? [search.status.toString()] : []}
                className="w-auto"
                name="status"
                options={
                  search.status
                    ? [
                        ...new Set([
                          "200",
                          "300",
                          "400",
                          "500",
                          search.status.toString()
                        ])
                      ]
                    : ["200", "300", "400", "500"]
                }
                closeOnSelect
                onValueChange={(statuses) => {
                  const lastStatus = statuses.at(-1);
                  searchParams.delete("status");
                  if (lastStatus) {
                    searchParams.set("status", lastStatus);
                  }
                  setSearchParams(searchParams, { replace: true });
                }}
                label="status"
                acceptArbitraryValues
              />
              <Button
                onClick={() => {
                  setSelectedFields((fields) =>
                    fields.filter((field) => field !== "status")
                  );
                  searchParams.delete("status");
                  setSearchParams(searchParams, { replace: true });
                }}
                variant="outline"
                className="bg-inherit"
                type="button"
              >
                <XIcon size={15} className="flex-none" />
                <span className="sr-only">Remove field</span>
              </Button>
            </div>
          )}

          <MultiSelect
            value={[]}
            align="start"
            className="w-auto"
            Icon={PlusIcon}
            options={available_fields}
            closeOnSelect
            onValueChange={([newField]) => {
              const field = newField as (typeof possible_fields)[number];
              if (!selectedFields.includes(field)) {
                flushSync(() => {
                  setSelectedFields([...selectedFields, field]);
                });

                const element = parentRef.current?.querySelector(
                  `[name=${field}]`
                ) as HTMLElement | null;
                element?.focus();
              }
            }}
            label="Add Filter"
          />

          {!isEmptySearchParams && (
            <Button
              variant="outline"
              className="inline-flex w-min gap-1"
              onClick={clearFilters}
            >
              <XIcon size={15} />
              <span>Reset filters</span>
            </Button>
          )}
        </div>
        <TooltipProvider>
          <Tooltip delayDuration={0}>
            <TooltipTrigger asChild>
              <Button
                variant="outline"
                onClick={() => {
                  searchParams.set("isMaximized", `${!search.isMaximized}`);
                  setSearchParams(searchParams, { replace: true });
                }}
              >
                <span className="sr-only">
                  {search.isMaximized ? "Minimize" : "Maximize"}
                </span>
                {search.isMaximized ? (
                  <Minimize2Icon size={15} />
                ) : (
                  <Maximize2Icon size={15} />
                )}
              </Button>
            </TooltipTrigger>
            <TooltipContent className="max-w-64 text-balance">
              {search.isMaximized ? "Minimize" : "Maximize"}
            </TooltipContent>
          </Tooltip>
        </TooltipProvider>
      </section>
      <hr className="border-border" />
    </>
  );
}

function HostFilter() {
  return;
}
