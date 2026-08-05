import type {
  InfiniteData,
  UseInfiniteQueryResult
} from "@tanstack/react-query";
import { notUndefined, useVirtualizer } from "@tanstack/react-virtual";
import {
  ArrowDown01Icon,
  ArrowUp10Icon,
  ArrowUpIcon,
  ChevronsUpDownIcon,
  LoaderIcon
} from "lucide-react";
import * as React from "react";
import { useSearchParams } from "react-router";
import type { HttpLog } from "~/api/types";
import { Code } from "~/components/code";
import { Ping } from "~/components/ping";
import { Button } from "~/components/ui/button";
import {
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow
} from "~/components/ui/table";
import { COUNTRY_CODE_LIST } from "~/lib/countryCodeList";
import { type HttpLogQueryData, httpLogSearchSchema } from "~/lib/queries";
import type { SortDirection } from "~/lib/types";
import { cn, formatDuration, formatLogTime } from "~/lib/utils";

type SortableField = "time" | "request_duration_ns";

export type HttpLogTableProps = {
  logsQuery: UseInfiniteQueryResult<InfiniteData<HttpLogQueryData>, Error>;
  /**
   * Auto refetching is paused whenever the user scrolls away from the top of the list.
   */
  onAutoRefetchEnabledChange: (enabled: boolean) => void;
  isAutoRefetchEnabled: boolean;
  /**
   * Show the compose stack service each request was routed to.
   */
  showStackServiceColumn?: boolean;
};

export function HttpLogTable({
  logsQuery,
  onAutoRefetchEnabledChange,
  isAutoRefetchEnabled,
  showStackServiceColumn = false
}: HttpLogTableProps) {
  const [searchParams, setSearchParams] = useSearchParams();
  const search = httpLogSearchSchema.parse(searchParams);
  const { sort_by } = search;

  const logs = (logsQuery.data?.pages ?? []).flatMap((item) => item.results);
  const columnCount = showStackServiceColumn ? 9 : 8;

  const containerRef = React.useRef<React.ComponentRef<"div">>(null);
  const virtualizer = useVirtualizer<HTMLDivElement, HTMLTableRowElement>({
    count: logs.length,
    getScrollElement: () => containerRef.current,
    estimateSize: () => 53,
    overscan: 10
  });

  const toggleSort = (field: SortableField) => {
    let nextDirection: SortDirection = "ascending";

    if (sort_by?.includes(field)) {
      nextDirection = "descending";
    } else if (sort_by?.includes(`-${field}`)) {
      nextDirection = "indeterminate";
    }

    const newSortBy = (sort_by ?? []).filter(
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

  const getSortDirection = (field: SortableField) => {
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
        onAutoRefetchEnabledChange(entry.isIntersecting);
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

  const items = virtualizer.getVirtualItems();
  const [virtualizerPaddingBefore, virtualizerPaddingAfter] =
    items.length > 0
      ? [
          notUndefined(items[0]).start - virtualizer.options.scrollMargin,
          virtualizer.getTotalSize() - notUndefined(items[items.length - 1]).end
        ]
      : [0, 0];

  return (
    <>
      {!isAutoRefetchEnabled && (
        <Button
          variant="secondary"
          className="absolute bottom-5 left-1/2 z-30 rounded-md"
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
                  <span>Duration</span>
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
              {showStackServiceColumn && (
                <TableHead className="sticky top-0 z-20 bg-toggle">
                  Service
                </TableHead>
              )}
              <TableHead className="sticky top-0 z-20 bg-toggle">
                Client IP
              </TableHead>
              <TableHead className="sticky top-0 z-20 bg-toggle">
                Country
              </TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            <tr>
              <td
                colSpan={columnCount}
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
            {virtualizerPaddingBefore > 0 && (
              <tr>
                <td
                  colSpan={columnCount}
                  style={{ height: virtualizerPaddingBefore }}
                />
              </tr>
            )}

            {items.map((virtualRow) => {
              const log = logs[virtualRow.index];
              return (
                <TableRow
                  className="border-border cursor-pointer"
                  key={log.id}
                  data-state={
                    log.request_uuid === search.request_id ? "selected" : null
                  }
                  onClick={() => {
                    if (log.request_uuid) {
                      searchParams.set("request_id", log.request_uuid);
                      setSearchParams(searchParams);
                    }
                  }}
                  data-index={virtualRow.index}
                  ref={virtualizer.measureElement}
                >
                  <LogTableRowContent
                    log={log}
                    showStackServiceColumn={showStackServiceColumn}
                  />
                </TableRow>
              );
            })}
            {virtualizerPaddingAfter > 0 && (
              <tr>
                <td
                  colSpan={columnCount}
                  style={{ height: virtualizerPaddingAfter }}
                />
              </tr>
            )}

            {logs.length > 0 && (
              <TableRow className="hover:bg-transparent text-gray-500 px-2">
                <TableCell colSpan={columnCount} className="relative">
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
    </>
  );
}

type LogTableRowProps = {
  log: HttpLog;
  showStackServiceColumn: boolean;
};

function LogTableRowContent({ log, showStackServiceColumn }: LogTableRowProps) {
  const logTime = formatLogTime(log.time);
  const { value: duration, unit } = formatDuration(
    log.request_duration_ns / 1_000_000 /*from ns to ms*/
  );

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

      {showStackServiceColumn && (
        <TableCell>
          <Code className="whitespace-nowrap max-w-[150px] text-ellipsis overflow-x-hidden flex-shrink">
            {log.stack_service_name}
          </Code>
        </TableCell>
      )}

      <TableCell>
        <p className="text-grey whitespace-nowrap max-w-[150px] text-ellipsis overflow-x-hidden flex-shrink">
          {log.request_ip}
        </p>
      </TableCell>

      <TableCell>
        <p className="text-grey whitespace-nowrap max-w-[150px] text-ellipsis overflow-x-hidden flex-shrink">
          {log.request_country_code ? (
            <span>
              {log.request_country_code}{" "}
              {COUNTRY_CODE_LIST[log.request_country_code]?.flag}
            </span>
          ) : (
            <span className="font-mono">N/A</span>
          )}
        </p>
      </TableCell>
    </>
  );
}
