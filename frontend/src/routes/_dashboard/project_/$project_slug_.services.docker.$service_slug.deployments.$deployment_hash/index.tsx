import { useInfiniteQuery, useQueryClient } from "@tanstack/react-query";
import { createFileRoute, useNavigate } from "@tanstack/react-router";
import { useVirtualizer } from "@tanstack/react-virtual";
import { AnsiHtml } from "fancy-ansi/react";
import {
  ChevronRightIcon,
  LoaderIcon,
  Maximize2Icon,
  Minimize2Icon,
  SearchIcon,
  XIcon
} from "lucide-react";
import * as React from "react";
import type { DateRange } from "react-day-picker";
import { useDebouncedCallback } from "use-debounce";
import { DateRangeWithShortcuts } from "~/components/date-range-with-shortcuts";
import { withAuthRedirect } from "~/components/helper/auth-redirect";
import { MultiSelect } from "~/components/multi-select";

import { Button, buttonVariants } from "~/components/ui/button";

import { Input } from "~/components/ui/input";
import {
  Tooltip,
  TooltipContent,
  TooltipProvider,
  TooltipTrigger
} from "~/components/ui/tooltip";

import { MAX_VISIBLE_LOG_CHARS_LIMIT } from "~/lib/constants";
import {
  type DeploymentLog,
  type DeploymentLogFitlers,
  LOG_LEVELS,
  LOG_SOURCES,
  deploymentLogSearchSchema,
  deploymentQueries
} from "~/lib/queries";
import type { Writeable } from "~/lib/types";
import { cn } from "~/lib/utils";
import { excerpt } from "~/utils";

export const Route = createFileRoute(
  "/_dashboard/project/$project_slug/services/docker/$service_slug/deployments/$deployment_hash/"
)({
  validateSearch: (search) => deploymentLogSearchSchema.parse(search),
  component: withAuthRedirect(DeploymentLogsDetailPage)
});

function useRouteParams() {
  return Route.useParams({
    select(params) {
      return {
        deployment_hash: params.deployment_hash,
        project_slug: params.project_slug,
        service_slug: params.service_slug
      };
    }
  });
}

export function DeploymentLogsDetailPage(): React.JSX.Element {
  const { deployment_hash, project_slug, service_slug } = useRouteParams();
  const searchParams = Route.useSearch();
  const navigate = useNavigate({
    from: "./"
  });
  // const inputRef = React.useRef<React.ComponentRef<"input">>(null);
  const [isAutoRefetchEnabled, setIsAutoRefetchEnabled] = React.useState(true);

  const filters = {
    time_after: searchParams.time_after,
    time_before: searchParams.time_before,
    source:
      searchParams.source ?? (LOG_SOURCES as Writeable<typeof LOG_SOURCES>),
    level: searchParams.level ?? (LOG_LEVELS as Writeable<typeof LOG_LEVELS>),
    query: searchParams.query ?? ""
  } satisfies DeploymentLogFitlers;

  const isEmptySearchParams =
    !searchParams.time_after &&
    !searchParams.time_before &&
    (searchParams.source?.length === 0 || !searchParams.source) &&
    (searchParams.level?.length === 0 || !searchParams.level) &&
    (searchParams.query ?? "").length === 0;

  const queryClient = useQueryClient();

  const logsQuery = useInfiniteQuery(
    deploymentQueries.logs({
      deployment_hash,
      project_slug,
      service_slug,
      filters,
      queryClient,
      autoRefetchEnabled: isAutoRefetchEnabled
    })
  );

  const logs =
    logsQuery.data?.pages.toReversed().flatMap((item) => item.results) ?? [];

  const logContentRef = React.useRef<React.ComponentRef<"section">>(null);

  const virtualizer = useVirtualizer({
    count: logs.length,
    getScrollElement: () => logContentRef.current,
    estimateSize: () => 16 * 2,
    paddingStart: 16,
    paddingEnd: 8,
    overscan: 1
  });
  const virtualItems = virtualizer.getVirtualItems();

  const [_, startTransition] = React.useTransition();

  const clearFilters = () => {
    startTransition(() =>
      navigate({
        to: "./",
        search: {
          isMaximized: searchParams.isMaximized
        },
        replace: true
      })
    );

    // if (inputRef.current) {
    //   inputRef.current.value = "";
    // }
  };

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
          logsQuery.fetchPreviousPage();
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

  const logContainerRef = (node: HTMLElement | null) => {
    if (!node) return;

    const invertedWheelScroll = (event: WheelEvent) => {
      node.scrollTop -= event.deltaY;
      event.preventDefault();
    };

    const abortCtrl = new AbortController();
    node.addEventListener("wheel", invertedWheelScroll, {
      passive: false,
      signal: abortCtrl.signal
    });

    logContentRef.current = node;
    return () => {
      abortCtrl.abort();
      logContentRef.current = null;
    };
  };

  return (
    <div
      className={cn(
        "grid grid-cols-12 gap-4 mt-8",
        searchParams.isMaximized &&
          "fixed inset-0 top-20 bg-background z-50 p-5 w-full"
      )}
    >
      <div
        className={cn(
          "col-span-12 flex flex-col gap-2",
          searchParams.isMaximized ? "container px-0 h-[82dvh]" : "h-[60dvh]"
        )}
      >
        <HeaderSection startTransition={startTransition} />

        <section
          id="log-content"
          ref={logContainerRef}
          className={cn(
            "-scale-y-100 justify-start min-h-0",
            "text-xs font-mono h-full rounded-md w-full",
            "bg-muted/25 dark:bg-neutral-950",
            "overflow-y-auto overflow-x-clip contain-strict",
            "whitespace-no-wrap"
          )}
        >
          {logs.length === 0 &&
            (logsQuery.isFetching ? (
              <div className="-scale-y-100 text-sm text-center items-center flex gap-2 text-gray-500 absolute left-1/2 top-1/2 -translate-x-1/2 -translate-y-1/2">
                <LoaderIcon size={15} className="animate-spin" />
                <p>Fetching logs...</p>
              </div>
            ) : isEmptySearchParams ? (
              <div className="-scale-y-100 text-sm text-center items-center flex flex-col text-gray-500 absolute left-1/2 top-1/2 -translate-x-1/2 -translate-y-1/2">
                <h3 className="text-base font-semibold">No logs yet</h3>
                <p className="inline-block max-w-lg text-balance ">
                  New log entries will appear here.
                </p>
              </div>
            ) : (
              <div className="-scale-y-100 text-sm px-2 gap-1.5 text-center items-center flex flex-col text-gray-500 absolute left-1/2 top-1/2 -translate-x-1/2 -translate-y-1/2">
                <h3 className="text-base font-semibold text-balance w-full">
                  No logs maching the selected filters
                </h3>
                <p className="inline-block max-w-lg text-balance">
                  New log entries that match your search parameters will appear
                  here.
                </p>
                <button className="text-sm underline" onClick={clearFilters}>
                  Clear filters
                </button>
              </div>
            ))}

          {logs.length > 0 && (
            <div
              style={{
                height: logs.length > 0 ? virtualizer.getTotalSize() : "auto"
              }}
              className={cn("relative justify-start")}
            >
              <div
                className="absolute top-0 left-0 w-full"
                style={{
                  transform: `translateY(${virtualItems[0]?.start ?? 0}px)`
                }}
              >
                {virtualItems.map((virtualRow) => {
                  const log = logs[virtualRow.index];
                  return (
                    <div
                      key={virtualRow.key}
                      className="w-full"
                      data-index={virtualRow.index}
                      ref={virtualizer.measureElement}
                    >
                      {logsQuery.hasNextPage && virtualRow.index === 0 && (
                        <div ref={fetchNextPageRef} className="w-fit h-px" />
                      )}
                      {virtualRow.index === 0 && (
                        <div
                          className="w-full pt-2 text-center -scale-y-100 text-grey italic"
                          ref={autoRefetchRef}
                        >
                          -- LIVE <Ping /> new log entries will appear here --
                        </div>
                      )}

                      <Log
                        id={log.id}
                        time={log.time}
                        level={log.level}
                        key={log.id}
                        content={(log.content as string) ?? ""}
                        content_text={log.content_text ?? ""}
                      />

                      {(logsQuery.hasPreviousPage ||
                        logsQuery.isFetchingPreviousPage) &&
                        virtualRow.index === logs.length - 1 && (
                          <div
                            ref={fetchPreviousPageRef}
                            className="text-center items-center justify-center flex gap-2 text-gray-500 px-2 mb-2 -scale-y-100"
                          >
                            <LoaderIcon size={15} className="animate-spin" />
                            <p>Fetching previous logs...</p>
                          </div>
                        )}
                    </div>
                  );
                })}
              </div>
            </div>
          )}
        </section>
      </div>
    </div>
  );
}

const HeaderSection = React.memo(function HeaderSection({
  startTransition
}: { startTransition: React.TransitionStartFunction }) {
  const searchParams = Route.useSearch({
    select(search) {
      return {
        time_after: search.time_after,
        time_before: search.time_before,
        source: search.source,
        level: search.level,
        query: search.query,
        isMaximized: search.isMaximized
      };
    }
  });

  const navigate = useNavigate();
  const inputRef = React.useRef<React.ComponentRef<"input">>(null);

  const date: DateRange = {
    from: searchParams.time_after,
    to: searchParams.time_before
  };

  const isEmptySearchParams =
    !searchParams.time_after &&
    !searchParams.time_before &&
    (searchParams.source ?? []).length === 0 &&
    (searchParams.level ?? []).length === 0 &&
    (searchParams.query ?? "").length === 0;

  const clearFilters = () => {
    startTransition(() =>
      navigate({
        to: "./",
        search: {
          isMaximized: searchParams.isMaximized
        },
        replace: true
      })
    );

    if (inputRef.current) {
      inputRef.current.value = "";
    }
  };

  const searchLogsForContent = useDebouncedCallback((query: string) => {
    startTransition(() =>
      navigate({
        search: {
          ...searchParams,
          isMaximized: searchParams.isMaximized,
          query
        },
        replace: true
      })
    );
  }, 300);

  return (
    <>
      <section className="rounded-t-sm w-full flex gap-2 flex-col items-start">
        <div className="flex items-center gap-2 flex-wrap">
          <DateRangeWithShortcuts
            date={date}
            setDate={(newDateRange) =>
              navigate({
                search: {
                  ...searchParams,
                  isMaximized: searchParams.isMaximized,
                  time_before: newDateRange?.to,
                  time_after: newDateRange?.from
                },
                replace: true
              })
            }
            className="w-[250px] grow"
          />

          <MultiSelect
            value={searchParams.level as string[]}
            className="w-auto"
            options={LOG_LEVELS as Writeable<typeof LOG_LEVELS>}
            onValueChange={(newVal) => {
              navigate({
                search: {
                  ...searchParams,
                  isMaximized: searchParams.isMaximized,
                  level: newVal
                },
                replace: true
              });
            }}
            label="levels"
          />

          <MultiSelect
            value={searchParams.source as string[]}
            className="w-auto"
            options={LOG_SOURCES as Writeable<typeof LOG_SOURCES>}
            onValueChange={(newVal) => {
              navigate({
                search: {
                  ...searchParams,
                  isMaximized: searchParams.isMaximized,
                  source: newVal
                },
                replace: true
              });
            }}
            label="sources"
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

        <div className="flex gap-2 w-full items-center relative">
          <SearchIcon size={15} className="absolute left-4 text-grey" />

          <Input
            className="px-14 w-full md:min-w-150 text-sm  bg-muted/40 dark:bg-card/30"
            placeholder="Search for log contents"
            name="query"
            defaultValue={searchParams.query}
            ref={inputRef}
            onChange={(ev) => {
              const newQuery = ev.currentTarget.value;
              if (newQuery !== (searchParams.query ?? "")) {
                searchLogsForContent(newQuery);
              }
            }}
          />

          <TooltipProvider>
            <Tooltip delayDuration={0}>
              <TooltipTrigger asChild>
                <Button
                  variant="outline"
                  onClick={() => {
                    navigate({
                      search: {
                        ...searchParams,
                        isMaximized: !searchParams.isMaximized
                      },
                      replace: true
                    });
                  }}
                >
                  <span className="sr-only">
                    {searchParams.isMaximized ? "Minimize" : "Maximize"}
                  </span>
                  {searchParams.isMaximized ? (
                    <Minimize2Icon size={15} />
                  ) : (
                    <Maximize2Icon size={15} />
                  )}
                </Button>
              </TooltipTrigger>
              <TooltipContent className="max-w-64 text-balance">
                {searchParams.isMaximized ? "Minimize" : "Maximize"}
              </TooltipContent>
            </Tooltip>
          </TooltipProvider>
        </div>
      </section>
      <hr className="border-border" />
    </>
  );
});

function Ping() {
  return (
    <span className="relative inline-flex h-2 w-2">
      <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-green-500 opacity-75"></span>
      <span className="relative inline-flex rounded-full h-2 w-2 bg-green-500"></span>
    </span>
  );
}

type LogProps = Pick<DeploymentLog, "id" | "level" | "time"> & {
  content: string;
  content_text: string;
};

const Log = ({ content, level, time, id, content_text }: LogProps) => {
  const date = new Date(time);

  const search = Route.useSearch({
    select: (search) => search.query ?? ""
  });

  const logTime = formatLogTime(date);

  return (
    <div
      id={`log-item-${id}`}
      className={cn(
        "w-full flex gap-2 hover:bg-slate-400/20 relative -scale-y-100 group",
        "py-0 px-4 border-none border-0 ring-0",
        level === "ERROR" && "bg-red-400/20"
      )}
    >
      <span className="inline-flex items-start select-none min-w-fit flex-none">
        <time className="text-grey" dateTime={date.toISOString()}>
          <span className="sr-only sm:not-sr-only">
            {logTime.dateFormat},&nbsp;
          </span>
          <span>{logTime.hourFormat}</span>
        </time>
      </span>

      <div className="grid relative z-10 w-full">
        {content_text.length <= MAX_VISIBLE_LOG_CHARS_LIMIT ? (
          <>
            <AnsiHtml
              aria-hidden="true"
              className={cn(
                "text-start z-10 relative",
                "col-start-1 col-end-1 row-start-1 row-end-1",
                "break-all text-wrap whitespace-pre [text-wrap-mode:wrap]"
              )}
              text={content}
            />
            <pre
              className={cn(
                "text-start -z-1 text-transparent relative",
                "col-start-1 col-end-1 row-start-1 row-end-1",
                "break-all text-wrap whitespace-pre [text-wrap-mode:wrap]"
              )}
            >
              {search.length > 0 ? (
                <HighlightedText text={content_text} highlight={search} />
              ) : (
                content_text
              )}
            </pre>
          </>
        ) : (
          <LongLogContent content_text={content_text} search={search} />
        )}
      </div>
    </div>
  );
};

function LongLogContent({
  content_text,
  search
}: { content_text: string; search: string }) {
  const [isFullContentShown, setIsFullContentShown] = React.useState(
    content_text.length <= MAX_VISIBLE_LOG_CHARS_LIMIT
  );

  const visibleContent = isFullContentShown
    ? content_text
    : excerpt(content_text, MAX_VISIBLE_LOG_CHARS_LIMIT);

  return (
    <>
      <pre
        className={cn(
          "text-start z-10  relative",
          "col-start-1 col-end-1 row-start-1 row-end-1",
          "break-all text-wrap whitespace-pre [text-wrap-mode:wrap]"
        )}
      >
        {search.length > 0 ? (
          <HighlightedText text={visibleContent} highlight={search} />
        ) : (
          visibleContent
        )}

        <button
          onClick={() => setIsFullContentShown(!isFullContentShown)}
          className={cn(
            buttonVariants({
              variant: "link"
            }),
            "inline-flex p-0 mx-2 underline h-auto rounded items-center cursor-pointer gap-1",
            "dark:text-primary text-link"
          )}
        >
          <span>{isFullContentShown ? "see less" : "see more"}</span>
          <ChevronRightIcon
            className={cn(
              "flex-none relative top-0.25",
              isFullContentShown && "-rotate-90"
            )}
            size={12}
          />
        </button>
      </pre>
    </>
  );
}

function escapeRegExp(input: string): string {
  return input.replace(/[.*+?^${}()|[\]\\]/g, "\\$&"); // $& means the whole matched string
}

const HighlightedText = React.memo(function HighlightedText({
  text,
  highlight
}: { text: string; highlight: string }) {
  // Split on highlight term and include term into parts, ignore case
  const parts = text.split(new RegExp(`(${escapeRegExp(highlight)})`, "gi"));
  return parts.map((part, index) => {
    if (part.toLowerCase() === highlight.toLowerCase()) {
      return (
        <span key={index} className="bg-yellow-400/50">
          {part}
        </span>
      );
    } else {
      return <span key={index}>{part}</span>;
    }
  });
});

function formatLogTime(time: string | Date) {
  const date = new Date(time);
  const now = new Date();
  const userTimeZone = Intl.DateTimeFormat().resolvedOptions().timeZone;

  const dateFormat = new Intl.DateTimeFormat("en-GB", {
    month: "short",
    day: "numeric",
    timeZone: userTimeZone,
    year: date.getFullYear() === now.getFullYear() ? undefined : "numeric"
  })
    .format(date)
    .replaceAll(".", "");

  const hourFormat = new Intl.DateTimeFormat("en-GB", {
    hour: "numeric",
    minute: "numeric",
    second: "numeric",
    timeZone: userTimeZone
  }).format(date);

  return { dateFormat, hourFormat };
}
