import { useInfiniteQuery, useQuery } from "@tanstack/react-query";
import { notUndefined, useVirtualizer } from "@tanstack/react-virtual";
import {
  ArrowDown01Icon,
  ArrowUp10Icon,
  ArrowUpIcon,
  ChevronsUpDownIcon,
  LoaderIcon,
  Maximize2Icon,
  Minimize2Icon,
  PlusIcon,
  XIcon
} from "lucide-react";
import * as React from "react";
import type { DateRange } from "react-day-picker";
import { flushSync } from "react-dom";
import { useParams, useSearchParams } from "react-router";
import { useDebouncedCallback } from "use-debounce";
import type { Writeable } from "zod";
import { DateRangeWithShortcuts } from "~/components/date-range-with-shortcuts";
import { HttpLogRequestDetails } from "~/components/http-log-request-details";
import { MultiSelect } from "~/components/multi-select";
import { Ping } from "~/components/ping";
import { Button } from "~/components/ui/button";
import { Input } from "~/components/ui/input";
import {
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
    request_method: search.request_method,
    request_host: search.request_host,
    request_ip: search.request_ip,
    request_path: search.request_path,
    request_query: search.request_query,
    request_user_agent: search.request_user_agent,
    status: search.status,
    sort_by: search.sort_by
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

type SortDirection = "ascending" | "descending" | "indeterminate";

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

  const { sort_by } = search;
  const filters = {
    time_after: search.time_after,
    time_before: search.time_before,
    request_method: search.request_method,
    request_host: search.request_host,
    request_ip: search.request_ip,
    request_path: search.request_path,
    request_query: search.request_query,
    request_user_agent: search.request_user_agent,
    status: search.status,
    sort_by
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

  const toggleSort = (field: "time" | "request_duration_ns") => {
    let nextDirection: SortDirection = "ascending";

    if (sort_by?.includes(field)) {
      nextDirection = "descending";
    } else if (sort_by?.includes(`-${field}`)) {
      nextDirection = "indeterminate";
    }

    let newSortBy = (sort_by ?? []).filter(
      (sort_field) => sort_field !== field && sort_field !== `-${field}`
    );
    switch (nextDirection) {
      case "ascending": {
        newSortBy.push(field);
        break;
      }
      case "descending": {
        newSortBy.push(`-${field}`);
        break;
      }
    }

    searchParams.delete("sort_by");
    newSortBy
      .toSorted((a, b) => {
        if (a.replace("-", "") === "time") return -1;
        if (b.replace("-", "") === "time") return 1;
        return 0;
      })
      .forEach((sort_by) => {
        searchParams.append(`sort_by`, sort_by.toString());
      });
    setSearchParams(searchParams, {
      replace: true
    });
    virtualizer.scrollToIndex(0, {
      behavior: "smooth"
    });
  };

  const getSortDirection = (field: "time" | "request_duration_ns") => {
    let direction: SortDirection = "indeterminate";
    if (sort_by?.includes(field)) {
      direction = "ascending";
    } else if (sort_by?.includes(`-${field}`)) {
      direction = "descending";
    }
    return direction;
  };
  const timeSortDirection = getSortDirection("time");
  const durationSortDirection = getSortDirection("request_duration_ns");

  const autoRefetchRef = (node: HTMLDivElement | null) => {
    if (!node) return;

    const observer = new IntersectionObserver(
      (entries) => {
        const entry = entries[0];
        if (entry.isIntersecting) {
          setIsAutoRefetchEnabled(true);
        } else {
          setIsAutoRefetchEnabled(false);
        }
      },
      {
        root: node.closest("#log-content"),
        rootMargin: "0px",
        threshold: 0.1
      }
    );

    observer.observe(node);
    return () => {
      observer.unobserve(node);
    };
  };

  const fetchNextPageRef = (node: HTMLDivElement | null) => {
    if (!node) return;
    const observer = new IntersectionObserver(
      (entries) => {
        const entry = entries[0];
        if (
          entry.isIntersecting &&
          !logsQuery.isFetching &&
          logsQuery.hasNextPage
        ) {
          logsQuery.fetchNextPage();
        }
      },
      {
        root: node.closest("#log-content"),
        rootMargin: "120%",
        threshold: 0.1 // how much of the item should be in view before firing this observer in percentage
      }
    );

    observer.observe(node);
    return () => {
      observer.unobserve(node);
    };
  };

  const fetchPreviousPageRef = (node: HTMLDivElement | null) => {
    if (!node) return;
    const observer = new IntersectionObserver(
      (entries) => {
        const entry = entries[0];
        if (
          entry.isIntersecting &&
          !logsQuery.isFetching &&
          logsQuery.hasPreviousPage
        ) {
          logsQuery.fetchPreviousPage();
        }
      },
      {
        root: node.closest("#log-content"),
        rootMargin: "20%",
        threshold: 0.1
      }
    );

    observer.observe(node);
    return () => {
      observer.unobserve(node);
    };
  };

  const containerRef = React.useRef<React.ComponentRef<"div">>(null);
  const virtualizer = useVirtualizer<HTMLDivElement, HTMLTableRowElement>({
    count: logs.length,
    getScrollElement: () => containerRef.current,
    estimateSize: () => 53,
    overscan: 10
  });

  const items = virtualizer.getVirtualItems();
  const [before, after] =
    items.length > 0
      ? [
          notUndefined(items[0]).start - virtualizer.options.scrollMargin,
          virtualizer.getTotalSize() - notUndefined(items[items.length - 1]).end
        ]
      : [0, 0];

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
          "flex flex-col gap-4 relative",
          search.isMaximized ? "container px-0 h-[82dvh]" : "h-[60dvh] mt-8"
        )}
        id="log-content"
      >
        <HeaderSection />

        {!isAutoRefetchEnabled && (
          <Button
            variant="secondary"
            className="absolute bottom-4 left-4  z-30"
            size="sm"
            onClick={() => {
              virtualizer.scrollToIndex(0, {
                behavior: "smooth"
              });
            }}
          >
            <span>Top</span> <ArrowUpIcon size={15} />
          </Button>
        )}
        <div
          className={cn(
            "overflow-auto",
            search.isMaximized ? "h-[95%]" : "h-[85%]"
          )}
          style={{
            overflowAnchor: "none"
          }}
          ref={containerRef}
        >
          <table className="w-full caption-bottom text-sm z-50">
            <TableHeader>
              <TableRow className="border-none">
                <TableHead className="sticky top-0 z-20 bg-toggle">
                  <button
                    onClick={() => toggleSort("time")}
                    className="flex cursor-pointer items-center gap-2"
                  >
                    Date
                    {timeSortDirection === "indeterminate" && (
                      <ChevronsUpDownIcon size={15} className="flex-none" />
                    )}
                    {timeSortDirection === "ascending" && (
                      <ArrowDown01Icon size={15} className="flex-none" />
                    )}
                    {timeSortDirection === "descending" && (
                      <ArrowUp10Icon size={15} className="flex-none" />
                    )}
                  </button>
                </TableHead>
                <TableHead className="sticky top-0 z-20 bg-toggle">
                  Method
                </TableHead>
                <TableHead className="sticky top-0 z-20 bg-toggle">
                  Status
                </TableHead>
                <TableHead className="sticky top-0 z-20 bg-toggle">
                  <button
                    onClick={() => toggleSort("request_duration_ns")}
                    className="flex cursor-pointer items-center gap-2"
                  >
                    Duration
                    {durationSortDirection === "indeterminate" && (
                      <ChevronsUpDownIcon size={15} className="flex-none" />
                    )}
                    {durationSortDirection === "ascending" && (
                      <ArrowDown01Icon size={15} className="flex-none" />
                    )}
                    {durationSortDirection === "descending" && (
                      <ArrowUp10Icon size={15} className="flex-none" />
                    )}
                  </button>
                </TableHead>
                <TableHead className="sticky top-0 z-20 bg-toggle">
                  Host
                </TableHead>
                <TableHead className="sticky top-0 z-20 bg-toggle">
                  Path
                </TableHead>
                <TableHead className="sticky top-0 z-20 bg-toggle">
                  Client IP
                </TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              <tr>
                <td
                  colSpan={7}
                  className="px-4 text-sm text-grey h-6 border-b border-border py-2"
                >
                  <div className="h-px" ref={fetchPreviousPageRef} />
                  <div
                    className="inline-flex items-center gap-2"
                    ref={autoRefetchRef}
                  >
                    <Ping />
                    <em className="text-green-500">LIVE</em> --
                    {logs.length === 0 && !logsQuery.isFetching && (
                      <span>No logs yet,</span>
                    )}
                    <span>New logs will appear here</span>
                  </div>
                </td>
              </tr>
              {before > 0 && (
                <tr>
                  <td colSpan={7} style={{ height: before }} />
                </tr>
              )}

              {items.map((virtualRow) => {
                const log = logs[virtualRow.index];
                return (
                  <TableRow
                    className="border-border cursor-pointer"
                    key={log.id}
                    onClick={() => {
                      if (log.request_id) {
                        searchParams.set("request_id", log.request_id);
                        setSearchParams(searchParams);
                      }
                    }}
                    ref={virtualizer.measureElement}
                  >
                    <LogTableRowContent log={log} key={log.id} />
                  </TableRow>
                );
              })}
              {after > 0 && (
                <tr>
                  <td colSpan={7} style={{ height: after }} />
                </tr>
              )}

              {logs.length > 0 && (
                <TableRow className="hover:bg-transparent text-gray-500 px-2">
                  <TableCell colSpan={7} className="relative">
                    {logsQuery.hasNextPage || logsQuery.isFetchingNextPage ? (
                      <div
                        ref={fetchNextPageRef}
                        className={cn(
                          "items-center flex gap-2",
                          "w-full sticky left-0"
                        )}
                      >
                        <LoaderIcon size={15} className="animate-spin" />
                        <p>Fetching previous logs...</p>
                      </div>
                    ) : (
                      <div className="inline-flex items-center sticky">
                        -- End of the list --
                      </div>
                    )}
                  </TableCell>
                </TableRow>
              )}
            </TableBody>
          </table>
        </div>
      </div>
    </div>
  );
}

type LogTableRowProps = {
  log: HttpLog;
};

function LogTableRowContent({ log }: LogTableRowProps) {
  const logTime = formatLogTime(log.time);
  let duration = log.request_duration_ns / 1_000_000;
  let unit = "ms";

  if (duration > 1000) {
    duration = duration / 1_000;
    unit = "s";
  }

  return (
    <>
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
        {Intl.NumberFormat("en-US", {
          maximumFractionDigits: 3
        }).format(duration)}
        <span className="text-grey">{unit}</span>
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
    </>
  );
}

const FIELD_LABEL_MAP: Record<string, string> = {
  host: "request_host",
  path: "request_path",
  query: "request_query",
  "user agent": "request_user_agent",
  "client ip": "request_ip",
  status: "status"
};

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

  const [selectedFields, setSelectedFields] = React.useState(() => {
    return possible_fields.filter((field) => {
      if (field === "request_query") {
        return field in search;
      } else {
        return field in search && (search[field]?.length ?? 0) > 0;
      }
    });
  });

  const available_fields = possible_fields.filter(
    (field) => !selectedFields.includes(field)
  );

  const isEmptySearchParams =
    !search.time_after &&
    !search.time_before &&
    (search.sort_by ?? []).length === 0 &&
    (search.request_method ?? []).length === 0 &&
    possible_fields.every((field) => {
      if (field === "request_query") {
        return !(field in search);
      } else {
        return !(field in search) || (search[field]?.length ?? 0) === 0;
      }
    });

  const clearFilters = () => {
    startTransition(() => {
      const newSearchParams = new URLSearchParams();
      if (searchParams.get("isMaximized")) {
        newSearchParams.set("isMaximized", `${search.isMaximized}`);
      }
      setSearchParams(newSearchParams, {
        replace: true
      });
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

  React.useEffect(() => {
    setSelectedFields(
      possible_fields.filter((field) => {
        if (field === "request_query") {
          return field in search;
        } else {
          return field in search && (search[field]?.length ?? 0) > 0;
        }
      })
    );
  }, [searchParams]);

  return (
    <>
      <section
        className="rounded-t-sm w-full flex gap-2 items-start justify-between"
        ref={parentRef}
      >
        <div className="flex items-center gap-2 flex-wrap">
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
            className="min-w-[250px]"
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

          {selectedFields.includes("status") && (
            <div className="inline-flex items-center gap-1">
              <StatusFilter statuses={search.status ?? []} />
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

          {selectedFields.includes("request_host") && (
            <div className="inline-flex items-center gap-1">
              <HostFilter hosts={search.request_host ?? []} />
              <Button
                onClick={() => {
                  setSelectedFields((fields) =>
                    fields.filter((field) => field !== "request_host")
                  );
                  searchParams.delete("request_host");
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

          {selectedFields.includes("request_path") && (
            <div className="inline-flex items-center gap-1">
              <PathFilter paths={search.request_path ?? []} />
              <Button
                onClick={() => {
                  setSelectedFields((fields) =>
                    fields.filter((field) => field !== "request_path")
                  );
                  searchParams.delete("request_path");
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

          {selectedFields.includes("request_ip") && (
            <div className="inline-flex items-center gap-1">
              <ClientIpFilter clientIps={search.request_ip ?? []} />
              <Button
                onClick={() => {
                  setSelectedFields((fields) =>
                    fields.filter((field) => field !== "request_ip")
                  );
                  searchParams.delete("request_ip");
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

          {selectedFields.includes("request_user_agent") && (
            <div className="inline-flex items-center gap-1">
              <UserAgentFilter userAgents={search.request_user_agent ?? []} />
              <Button
                onClick={() => {
                  setSelectedFields((fields) =>
                    fields.filter((field) => field !== "request_user_agent")
                  );
                  searchParams.delete("request_user_agent");
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

          {available_fields.length > 0 && (
            <MultiSelect
              value={[]}
              align="start"
              className="w-auto"
              Icon={PlusIcon}
              options={Object.keys(FIELD_LABEL_MAP)}
              closeOnSelect
              onValueChange={([newField]) => {
                const field = FIELD_LABEL_MAP[
                  newField
                ] as (typeof possible_fields)[number];
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
          )}

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
      </section>
      <hr className="border-border" />
    </>
  );
}

type StatusFilterProps = {
  statuses: string[];
};
function StatusFilter({ statuses }: StatusFilterProps) {
  const [searchParams, setSearchParams] = useSearchParams();
  return (
    <MultiSelect
      value={statuses}
      className="w-auto"
      name="status"
      options={[...new Set(["200", "300", "400", "500", ...statuses])]}
      closeOnSelect
      onValueChange={(statuses) => {
        searchParams.delete("status");
        statuses.forEach((status) => searchParams.append("status", status));
        setSearchParams(searchParams, { replace: true });
      }}
      label="status"
      acceptArbitraryValues
    />
  );
}

type HostFilterProps = {
  hosts: string[];
};

function HostFilter({ hosts }: HostFilterProps) {
  const {
    deploymentHash: deployment_hash,
    projectSlug: project_slug,
    serviceSlug: service_slug
  } = useParams() as Required<Route.LoaderArgs["params"]>;
  const [searchParams, setSearchParams] = useSearchParams();
  const [inputValue, setInputValue] = React.useState("");

  const { data: hostList = [] } = useQuery(
    deploymentQueries.filterHttpLogFields({
      deployment_hash,
      project_slug,
      service_slug,
      field: "request_host",
      value: inputValue
    })
  );
  return (
    <MultiSelect
      value={hosts}
      className="w-auto"
      name="request_host"
      options={[...new Set([...hostList, ...hosts])]}
      closeOnSelect
      inputValue={inputValue}
      onInputValueChange={setInputValue}
      onValueChange={(statuses) => {
        searchParams.delete("request_host");
        statuses.forEach((status) =>
          searchParams.append("request_host", status)
        );
        setSearchParams(searchParams, { replace: true });
      }}
      label="host"
      acceptArbitraryValues
    />
  );
}

type PathFilterProps = {
  paths: string[];
};

function PathFilter({ paths }: PathFilterProps) {
  const {
    deploymentHash: deployment_hash,
    projectSlug: project_slug,
    serviceSlug: service_slug
  } = useParams() as Required<Route.LoaderArgs["params"]>;
  const [searchParams, setSearchParams] = useSearchParams();
  const [inputValue, setInputValue] = React.useState("");

  const { data: hostList = [] } = useQuery(
    deploymentQueries.filterHttpLogFields({
      deployment_hash,
      project_slug,
      service_slug,
      field: "request_path",
      value: inputValue
    })
  );
  return (
    <MultiSelect
      value={paths}
      className="w-auto"
      name="request_path"
      options={[...new Set([...hostList, ...paths])]}
      closeOnSelect
      inputValue={inputValue}
      onInputValueChange={setInputValue}
      onValueChange={(statuses) => {
        searchParams.delete("request_path");
        statuses.forEach((status) =>
          searchParams.append("request_path", status)
        );
        setSearchParams(searchParams, { replace: true });
      }}
      label="path"
      acceptArbitraryValues
    />
  );
}

type ClientIpFilterProps = {
  clientIps: string[];
};

function ClientIpFilter({ clientIps }: ClientIpFilterProps) {
  const {
    deploymentHash: deployment_hash,
    projectSlug: project_slug,
    serviceSlug: service_slug
  } = useParams() as Required<Route.LoaderArgs["params"]>;
  const [searchParams, setSearchParams] = useSearchParams();
  const [inputValue, setInputValue] = React.useState("");

  const { data: ipList = [] } = useQuery(
    deploymentQueries.filterHttpLogFields({
      deployment_hash,
      project_slug,
      service_slug,
      field: "request_ip",
      value: inputValue
    })
  );
  return (
    <MultiSelect
      value={clientIps}
      className="w-auto"
      name="request_ip"
      options={[...new Set([...ipList, ...clientIps])]}
      closeOnSelect
      inputValue={inputValue}
      onInputValueChange={setInputValue}
      onValueChange={(statuses) => {
        searchParams.delete("request_ip");
        statuses.forEach((status) => searchParams.append("request_ip", status));
        setSearchParams(searchParams, { replace: true });
      }}
      label="client ip"
      acceptArbitraryValues
    />
  );
}

type UserAgentFilterProps = {
  userAgents: string[];
};

function UserAgentFilter({ userAgents }: UserAgentFilterProps) {
  const {
    deploymentHash: deployment_hash,
    projectSlug: project_slug,
    serviceSlug: service_slug
  } = useParams() as Required<Route.LoaderArgs["params"]>;
  const [searchParams, setSearchParams] = useSearchParams();
  const [inputValue, setInputValue] = React.useState("");

  const { data: uaList = [] } = useQuery(
    deploymentQueries.filterHttpLogFields({
      deployment_hash,
      project_slug,
      service_slug,
      field: "request_user_agent",
      value: inputValue
    })
  );
  return (
    <MultiSelect
      value={userAgents}
      className="w-auto"
      name="request_user_agent"
      options={[...new Set([...uaList, ...userAgents])]}
      closeOnSelect
      inputValue={inputValue}
      onInputValueChange={setInputValue}
      onValueChange={(statuses) => {
        searchParams.delete("request_user_agent");
        statuses.forEach((status) =>
          searchParams.append("request_user_agent", status)
        );
        setSearchParams(searchParams, { replace: true });
      }}
      label="user agent"
      acceptArbitraryValues
    />
  );
}
