import { useInfiniteQuery, useQueryClient } from "@tanstack/react-query";
import {
  ArrowDownIcon,
  LoaderIcon,
  Maximize2Icon,
  Minimize2Icon
} from "lucide-react";
import * as React from "react";
import { useSearchParams } from "react-router";
import { Virtuoso } from "react-virtuoso";
import { Ping } from "~/components/ping";
import { Button } from "~/components/ui/button";
import {
  Tooltip,
  TooltipContent,
  TooltipProvider,
  TooltipTrigger
} from "~/components/ui/tooltip";
import { REALLY_BIG_NUMBER_THAT_IS_LESS_THAN_MAX_SAFE_INTEGER } from "~/lib/constants";
import { deploymentQueries } from "~/lib/queries";
import { cn } from "~/lib/utils";
import { queryClient } from "~/root";
import { Log } from "~/routes/deployments/deployment-logs";
import type { Route } from "./+types/deployment-build-logs";

export async function clientLoader({
  params: {
    projectSlug: project_slug,
    serviceSlug: service_slug,
    envSlug: env_slug,
    deploymentHash: deployment_hash
  },
  request
}: Route.ClientLoaderArgs) {
  queryClient.prefetchInfiniteQuery(
    deploymentQueries.buildLogs({
      deployment_hash,
      project_slug,
      service_slug,
      env_slug,
      queryClient
    })
  );
  return;
}

export default function DeploymentBuildLogsPage({
  params: {
    projectSlug: project_slug,
    serviceSlug: service_slug,
    envSlug: env_slug,
    deploymentHash: deployment_hash
  }
}: Route.ComponentProps) {
  const [searchParams, setSearchParams] = useSearchParams();
  const [isAutoRefetchEnabled, setIsAutoRefetchEnabled] = React.useState(true);

  const queryClient = useQueryClient();
  const logsQuery = useInfiniteQuery({
    ...deploymentQueries.buildLogs({
      deployment_hash,
      project_slug,
      service_slug,
      env_slug,
      queryClient,
      autoRefetchEnabled: isAutoRefetchEnabled
    })
  });
  const logs = (logsQuery.data?.pages ?? []).flatMap((item) => item.results);

  const logContentRef = React.useRef<React.ComponentRef<"section">>(null);
  const [isAtBottom, setIsAtBottom] = React.useState(true);
  const virtuoso = React.useRef<React.ComponentRef<typeof Virtuoso>>(null);
  const [firstItemIndex, setFirstItemIndex] = React.useState(
    REALLY_BIG_NUMBER_THAT_IS_LESS_THAN_MAX_SAFE_INTEGER
  );

  const fetchNextPageRef = (node: HTMLDivElement | null) => {
    if (!node) return;
    const observer = new IntersectionObserver(
      (entries) => {
        const entry = entries[0];
        if (
          entry.isIntersecting &&
          !logsQuery.isFetching &&
          !logsQuery.isFetchingNextPage &&
          logsQuery.hasNextPage
        ) {
          logsQuery.fetchNextPage();
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
          logsQuery.fetchPreviousPage().then((query) => {
            const pages = query.data?.pages;
            if (pages) {
              const lastPageCount = pages[pages.length - 1];
              setFirstItemIndex(
                (index) => index - lastPageCount.results.length
              );
            }
          });
        }
      },
      {
        root: logContentRef.current,
        rootMargin: "120%",
        threshold: 0.1 // how much of the item should be in view before firing this observer in percentage
      }
    );

    observer.observe(node);
    return () => {
      observer.unobserve(node);
    };
  };

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

  const isMaximized = searchParams.get("isMaximized") === "true";

  return (
    <div
      className={cn(
        "grid grid-cols-12 gap-4 mt-8",
        isMaximized && "fixed inset-0 bg-background z-100 w-full mt-0"
      )}
    >
      <div
        className={cn(
          "col-span-12 flex flex-col gap-2 relative",
          isMaximized ? "container px-0 h-dvh" : "h-[60dvh]"
        )}
      >
        {!isAtBottom && (
          <Button
            variant="secondary"
            className="absolute bottom-5 left-1/2 z-30 rounded-full"
            size="sm"
            onClick={() => {
              virtuoso.current?.scrollToIndex({
                index: "LAST",
                behavior: "smooth",
                align: "end"
              });
            }}
          >
            <ArrowDownIcon size={15} />
          </Button>
        )}

        <TooltipProvider>
          <Tooltip delayDuration={0}>
            <TooltipTrigger asChild>
              <Button
                variant="outline"
                className="absolute top-5 right-5 z-30"
                onClick={() => {
                  searchParams.set("isMaximized", (!isMaximized).toString());
                  setSearchParams(searchParams, { replace: true });
                }}
              >
                <span className="sr-only">
                  {isMaximized ? "Minimize" : "Maximize"}
                </span>
                {isMaximized ? (
                  <Minimize2Icon size={15} />
                ) : (
                  <Maximize2Icon size={15} />
                )}
              </Button>
            </TooltipTrigger>
            <TooltipContent className="max-w-64 text-balance">
              {isMaximized ? "Minimize" : "Maximize"}
            </TooltipContent>
          </Tooltip>
        </TooltipProvider>

        {logs.length === 0 ? (
          <section
            className={cn(
              "justify-start min-h-0",
              "text-xs font-mono h-full rounded-md w-full",
              "bg-muted/25 dark:bg-neutral-950",
              "overflow-y-auto overflow-x-clip contain-strict",
              "whitespace-no-wrap",
              isMaximized && "rounded-none"
            )}
          >
            {logsQuery.isFetching ? (
              <div className="text-sm text-center items-center flex gap-2 text-gray-500 absolute left-1/2 top-1/2 -translate-x-1/2 -translate-y-1/2">
                <LoaderIcon size={15} className="animate-spin" />
                <p>Fetching logs...</p>
              </div>
            ) : (
              <div className="text-sm text-center items-center flex flex-col text-gray-500 absolute left-1/2 top-1/2 -translate-x-1/2 -translate-y-1/2">
                <h3 className="text-base font-semibold">No logs yet</h3>
                <p className="inline-block max-w-lg text-balance ">
                  New log entries will appear here.
                </p>
              </div>
            )}
          </section>
        ) : (
          <Virtuoso
            id="log-content"
            firstItemIndex={firstItemIndex}
            initialTopMostItemIndex={logs.length - 1}
            followOutput="smooth"
            alignToBottom
            ref={virtuoso}
            atBottomStateChange={(isAtBottom) => {
              setIsAtBottom(isAtBottom);
            }}
            className={cn(
              "text-xs font-mono h-full rounded-md w-full",
              "bg-muted/25 dark:bg-neutral-950",
              "overflow-y-auto overflow-x-clip contain-strict",
              "whitespace-no-wrap [overflow-anchor:none]",
              isMaximized && "rounded-none"
            )}
            data={logs}
            components={{
              Header: () =>
                logsQuery.hasPreviousPage ||
                logsQuery.isFetchingPreviousPage ? (
                  <div
                    ref={fetchPreviousPageRef}
                    className={cn(
                      "text-center items-center justify-center flex gap-2 text-gray-500 px-2 my-2"
                    )}
                  >
                    <LoaderIcon size={15} className="animate-spin" />
                    <p>Fetching previous logs...</p>
                  </div>
                ) : (
                  <div className="my-2" />
                ),
              Footer: () => (
                <>
                  <div ref={fetchNextPageRef} className="w-fit h-px" />
                  <div
                    className={cn("w-full pb-2 text-center text-grey italic")}
                    ref={autoRefetchRef}
                  >
                    -- LIVE <Ping /> new log entries will appear here --
                  </div>
                </>
              )
            }}
            itemContent={(_, log) => (
              <Log
                id={log.id}
                time={log.time}
                level={log.level}
                timestamp={log.timestamp}
                key={log.id}
                content={(log.content as string) ?? ""}
                content_text={log.content_text ?? ""}
              />
            )}
          />
        )}
      </div>
    </div>
  );
}
