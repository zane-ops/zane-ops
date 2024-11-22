import { useInfiniteQuery, useQueryClient } from "@tanstack/react-query";
import { createFileRoute, useNavigate } from "@tanstack/react-router";
import { useVirtualizer } from "@tanstack/react-virtual";
import { AnsiHtml } from "fancy-ansi/react";
import {
  LoaderIcon,
  Maximize2Icon,
  Minimize2Icon,
  SearchIcon,
  XIcon
} from "lucide-react";
import * as React from "react";
import type { DateRange } from "react-day-picker";
import { useDebounce } from "use-debounce";
import { DateRangeWithShortcuts } from "~/components/date-range-with-shortcuts";
import { withAuthRedirect } from "~/components/helper/auth-redirect";
import { MultiSelect } from "~/components/multi-select";

import { Button } from "~/components/ui/button";

import { Input } from "~/components/ui/input";
import {
  Tooltip,
  TooltipContent,
  TooltipProvider,
  TooltipTrigger
} from "~/components/ui/tooltip";

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

export function DeploymentLogsDetailPage(): React.JSX.Element {
  const { deployment_hash, project_slug, service_slug } = Route.useParams();
  const searchParams = Route.useSearch();
  const navigate = useNavigate();
  const [debouncedSearchQuery] = useDebounce(searchParams.content ?? "", 300);
  const inputRef = React.useRef<React.ElementRef<"input">>(null);
  const [isAutoRefetchEnabled, setIsAutoRefetchEnabled] = React.useState(true);

  const filters = {
    time_after: searchParams.time_after,
    time_before: searchParams.time_before,
    source:
      searchParams.source ?? (LOG_SOURCES as Writeable<typeof LOG_SOURCES>),
    level: searchParams.level ?? (LOG_LEVELS as Writeable<typeof LOG_LEVELS>),
    content: debouncedSearchQuery
  } satisfies DeploymentLogFitlers;

  const isEmptySearchParams = React.useMemo(() => {
    return (
      !searchParams.time_after &&
      !searchParams.time_before &&
      (LOG_SOURCES.every((source) => searchParams.source?.includes(source)) ||
        searchParams.source?.length === 0 ||
        !searchParams.source) &&
      (LOG_LEVELS.every((source) => searchParams.level?.includes(source)) ||
        searchParams.level?.length === 0 ||
        !searchParams.level) &&
      (searchParams.content ?? "").length === 0
    );
  }, [searchParams]);

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

  const logs = React.useMemo(() => {
    return (
      logsQuery.data?.pages.toReversed().flatMap((item) => item.results) ?? []
    );
  }, [logsQuery.data]);

  const clearFilters = React.useCallback(() => {
    navigate({
      to: "./",
      search: {
        isMaximized: searchParams.isMaximized
      },
      replace: true
    });

    if (inputRef.current) {
      inputRef.current.value = "";
    }
  }, [navigate, searchParams.isMaximized]);

  const loadNextPageRef = React.useRef<React.ElementRef<"div">>(null);
  const refetchRef = React.useRef<React.ElementRef<"div">>(null);
  const loadPreviousPageRef = React.useRef<React.ElementRef<"div">>(null);
  const logContentRef = React.useRef<React.ElementRef<"pre">>(null);

  let count = logs.length;
  if (logsQuery.hasNextPage) {
    count++;
  }
  if (logsQuery.hasPreviousPage) {
    count++;
  }

  // const virtualizer = useVirtualizer({
  //   count: logs.length,
  //   getScrollElement: () => logContentRef.current,
  //   estimateSize: () => 16 * 2,
  //   paddingStart: 16,
  //   paddingEnd: 8,
  //   overscan: 3
  // });
  // const virtualItems = virtualizer.getVirtualItems();

  React.useEffect(
    () => {
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
          root: logContentRef.current,
          rootMargin: "0px",
          threshold: 0.1
        }
      );

      const autoRefetchTrigger = refetchRef.current;
      if (autoRefetchTrigger) {
        observer.observe(autoRefetchTrigger);
        return () => {
          observer.unobserve(autoRefetchTrigger);
        };
      }
    },
    [
      // virtualItems
    ]
  );

  React.useEffect(() => {
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

    const loadPreviousPage = loadPreviousPageRef.current;
    if (loadPreviousPage) {
      observer.observe(loadPreviousPage);
      return () => {
        observer.unobserve(loadPreviousPage);
      };
    }
  }, [
    // virtualItems,
    logsQuery.fetchPreviousPage,
    logsQuery.isFetching,
    logsQuery.hasPreviousPage
  ]);

  React.useEffect(() => {
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
        root: logContentRef.current,
        rootMargin: "20%",
        threshold: 0.1
      }
    );

    const loadNextPage = loadNextPageRef.current;
    if (loadNextPage) {
      observer.observe(loadNextPage);
      return () => {
        observer.unobserve(loadNextPage);
      };
    }
  }, [
    // virtualItems,
    logsQuery.fetchNextPage,
    logsQuery.isFetching,
    logsQuery.hasNextPage,
    logsQuery.isFetchingNextPage
  ]);

  React.useEffect(() => {
    return;
    if (logContentRef.current) {
      if (!supportsCSSCustomHighlightsAPI()) {
        return;
      }

      CSS.highlights.clear();
      if (filters.content.length === 0) return;

      const parents = logContentRef.current.querySelectorAll(
        'pre[data-highlight="true"]'
      );
      // we know that these elements (`pre[data-highlight="true"]`) only have simple text nodes inside of them
      const allTextNodes = [...parents].map((parent) => parent.childNodes[0]);

      // Code originally copied from here :
      // https://microsoftedge.github.io/Demos/custom-highlight-api/
      const ranges = allTextNodes
        .map((el) => {
          return {
            el,
            text: (el?.textContent ?? "").toLowerCase()
          };
        })
        .filter(
          ({ text }) =>
            Boolean(text) && text.includes(filters.content.toLowerCase())
        )
        .map(({ text, el }) => {
          const indices = [];
          let startPos = 0;
          while (startPos < text.length) {
            const index = text.indexOf(filters.content.toLowerCase(), startPos);
            if (index === -1) break;
            indices.push(index);
            startPos = index + filters.content.length;
          }

          return indices.map((index) => {
            const range = new Range();
            range.setStart(el, index);
            range.setEnd(el, index + filters.content.length);
            return range;
          });
        });

      const highlight = new Highlight(...ranges.flat());
      CSS.highlights.set("search-results-highlight", highlight);
    }
  }, [
    filters.content,
    logs
    //  virtualItems
  ]);

  React.useEffect(() => {
    const parentElement = logContentRef.current;
    if (!parentElement) return;

    const invertedWheelScroll = (event: WheelEvent) => {
      parentElement.scrollTop -= event.deltaY;
      event.preventDefault();
    };

    const abortCtrl = new AbortController();
    parentElement.addEventListener("wheel", invertedWheelScroll, {
      passive: false,
      signal: abortCtrl.signal
    });

    return () => abortCtrl.abort();
  }, []);

  const date: DateRange = {
    from: filters.time_after,
    to: filters.time_before
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
          searchParams.isMaximized ? "container px-0 h-[82dvh]" : "h-[65dvh]"
        )}
      >
        <HeaderSection isFetchingLogs={logsQuery.isFetching} />

        <pre
          id="logContent"
          ref={logContentRef}
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
              // style={{
              //   height: logs.length > 0 ? virtualizer.getTotalSize() : "auto"
              // }}
              className={cn(
                "relative justify-start mb-auto",
                "[&_::highlight(search-results-highlight)]:bg-yellow-400/50"
              )}
            >
              <div
                className="absolute top-0 left-0 w-full"
                // style={{
                //   transform: `translateY(${virtualItems[0]?.start ?? 0}px)`
                // }}
              >
                {logs.map((virtualRow, index) => {
                  const log = logs[index];
                  return (
                    <div
                      // key={virtualRow.key}
                      key={log.id}
                      className="w-full"
                      // data-index={virtualRow.index}
                      // ref={virtualizer.measureElement}
                    >
                      {logsQuery.hasNextPage && index === 0 && (
                        <div ref={loadNextPageRef} className="w-full h-px" />
                      )}
                      {index === 0 && (
                        <div
                          className="w-full py-2 text-center -scale-y-100 text-grey italic"
                          ref={refetchRef}
                        >
                          -- LIVE <Ping /> new log entries will appear here --
                        </div>
                      )}

                      <Log
                        id={log.id}
                        time={log.time}
                        level={log.level}
                        content={(log.content as string) ?? ""}
                        content_text={log.content_text ?? ""}
                        searchValue={
                          !supportsCSSCustomHighlightsAPI()
                            ? ""
                            : filters.content
                        }
                      />

                      {(logsQuery.hasPreviousPage ||
                        logsQuery.isFetchingPreviousPage) &&
                        index === logs.length - 1 && (
                          <div
                            ref={loadPreviousPageRef}
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
        </pre>
      </div>
    </div>
  );
}

type HeaderSectionProps = {
  isFetchingLogs?: boolean;
};

const HeaderSection = React.memo(function HeaderSection({
  isFetchingLogs
}: HeaderSectionProps) {
  const searchParams = Route.useSearch();
  const navigate = useNavigate();
  const [debouncedSearchQuery] = useDebounce(searchParams.content ?? "", 300);
  const inputRef = React.useRef<React.ElementRef<"input">>(null);

  const filters = {
    time_after: searchParams.time_after,
    time_before: searchParams.time_before,
    source:
      searchParams.source ?? (LOG_SOURCES as Writeable<typeof LOG_SOURCES>),
    level: searchParams.level ?? (LOG_LEVELS as Writeable<typeof LOG_LEVELS>),
    content: debouncedSearchQuery
  } satisfies DeploymentLogFitlers;

  const date: DateRange = {
    from: filters.time_after,
    to: filters.time_before
  };

  const isEmptySearchParams = React.useMemo(() => {
    return (
      !searchParams.time_after &&
      !searchParams.time_before &&
      (LOG_SOURCES.every((source) => searchParams.source?.includes(source)) ||
        searchParams.source?.length === 0 ||
        !searchParams.source) &&
      (LOG_LEVELS.every((source) => searchParams.level?.includes(source)) ||
        searchParams.level?.length === 0 ||
        !searchParams.level) &&
      (filters.content ?? "").length === 0
    );
  }, [
    searchParams.time_after,
    searchParams.time_before,
    searchParams.source,
    searchParams.level,
    filters.content
  ]);

  const clearFilters = React.useCallback(() => {
    navigate({
      to: "./",
      search: {
        isMaximized: searchParams.isMaximized
      },
      replace: true
    });

    if (inputRef.current) {
      inputRef.current.value = "";
    }
  }, [navigate, searchParams.isMaximized]);

  return (
    <>
      <section className="rounded-t-sm w-full flex gap-2 flex-col md:flex-row flex-wrap lg:flex-nowrap">
        <div className="flex items-center gap-2 order-first">
          <DateRangeWithShortcuts
            date={date}
            setDate={(newDateRange) =>
              navigate({
                search: {
                  ...filters,
                  isMaximized: searchParams.isMaximized,
                  time_before: newDateRange?.to,
                  time_after: newDateRange?.from
                },
                replace: true
              })
            }
            className="min-w-[250px] w-full"
          />
        </div>

        <div className="flex w-full items-center relative flex-grow order-2">
          {isFetchingLogs ? (
            <LoaderIcon
              size={15}
              className="animate-spin absolute left-4 text-grey"
            />
          ) : (
            <SearchIcon size={15} className="absolute left-4 text-grey" />
          )}
          <Input
            className="px-14 w-full text-sm  bg-muted/40 dark:bg-card/30"
            placeholder="Search for log contents"
            name="content"
            defaultValue={searchParams.content}
            ref={inputRef}
            onKeyUp={(e) => {
              e.preventDefault();
              e.stopPropagation();
              const newQuery = e.currentTarget.value;
              if (newQuery !== (searchParams.content ?? "")) {
                navigate({
                  search: {
                    ...filters,
                    isMaximized: searchParams.isMaximized,
                    content: e.currentTarget.value
                  },
                  replace: true
                });
              }
            }}
          />
        </div>

        <div className="flex-shrink-0 flex items-center gap-1.5 order-1 lg:order-last">
          <MultiSelect
            value={filters.level}
            options={LOG_LEVELS as Writeable<typeof LOG_LEVELS>}
            onValueChange={(newVal) => {
              navigate({
                search: {
                  ...filters,
                  isMaximized: searchParams.isMaximized,
                  level: newVal
                },
                replace: true
              });
            }}
            placeholder="log levels"
          />

          <MultiSelect
            value={filters.source}
            options={LOG_SOURCES as Writeable<typeof LOG_SOURCES>}
            onValueChange={(newVal) => {
              navigate({
                search: {
                  ...filters,
                  isMaximized: searchParams.isMaximized,
                  source: newVal
                },
                replace: true
              });
            }}
            placeholder="log sources"
          />

          <TooltipProvider>
            <Tooltip delayDuration={0}>
              <TooltipTrigger asChild>
                <Button
                  variant="outline"
                  onClick={() => {
                    navigate({
                      search: {
                        ...filters,
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
    </>
  );
});

function LogHeaderSection() {
  return <></>;
}

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
  searchValue?: string;
};

const Log = React.memo(
  ({ content, searchValue, level, time, id, content_text }: LogProps) => {
    const search = searchValue ?? "";
    const date = new Date(time);

    const logTime = formatLogTime(date);
    // if (content_text.length > 1000) {
    //   const logExcerpt = excerpt(content_text, 1000);
    // }

    return (
      <pre className="w-full -scale-y-100 group">
        <pre
          id={`log-item-${id}`}
          className={cn(
            "flex gap-2 hover:bg-slate-400/20 relative",
            "py-0 px-4 border-none border-0 ring-0",
            level === "ERROR" && "bg-red-400/20",
            "group-open:bg-yellow-700/20"
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

          <div className="grid relative z-10">
            {/* {content_text.length > 1_000 ? ( */}
            <pre className="text-wrap text-start relative z-[-1] text-card-foreground break-all col-start-1 col-end-1 row-start-1 row-end-1">
              {content_text}
            </pre>
            {/* // ) : 
               <AnsiHtml
            //     aria-hidden="true"
            //     className="text-wrap text-start break-all z-10 mix-blend-color dark:mix-blend-color-dodge whitespace-pre relative col-start-1 col-end-1 row-start-1 row-end-1"
            //     text={content}
            //   />
            // )}
            {/* {supportsCSSCustomHighlightsAPI() ? (
              <pre
                data-highlight="true"
                className="text-wrap text-start relative z-[-1] text-transparent break-all col-start-1 col-end-1 row-start-1 row-end-1"
              >
                {content_text}
              </pre>
            ) : ( */}
            {/* <pre className="text-wrap text-start z-[-1] relative text-transparent break-all whitespace-pre col-start-1 col-end-1 row-start-1 row-end-1">
              {search.length > 0
                ? getHighlightedText(content_text, search)
                : content_text}
            </pre> */}
            {/* )} */}
          </div>
        </pre>
      </pre>
    );
  }
);

function escapeRegExp(input: string): string {
  return input.replace(/[.*+?^${}()|[\]\\]/g, "\\$&"); // $& means the whole matched string
}

function supportsCSSCustomHighlightsAPI() {
  return "highlights" in window.CSS;
}

function getHighlightedText(text: string, highlight: string) {
  // Split on highlight term and include term into parts, ignore case
  const parts = text.split(new RegExp(`(${escapeRegExp(highlight)})`, "gi"));
  return parts.map((part) => {
    if (part.toLowerCase() === highlight.toLowerCase()) {
      return <span className="bg-yellow-400/50">{part}</span>;
    } else {
      return <span>{part}</span>;
    }
  });
}

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
