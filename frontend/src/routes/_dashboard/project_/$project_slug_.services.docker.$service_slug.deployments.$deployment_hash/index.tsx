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
import { Loader } from "~/components/loader";
import { MultiSelect } from "~/components/multi-select";
import {
  Accordion,
  AccordionContent,
  AccordionItem,
  AccordionTrigger
} from "~/components/ui/accordion";
import { Button } from "~/components/ui/button";

import { Input } from "~/components/ui/input";
import {
  Tooltip,
  TooltipArrow,
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

import { formatDateForTimeZone } from "~/utils";

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
      queryClient
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
  const loadPreviousPageRef = React.useRef<React.ElementRef<"div">>(null);
  const logContentRef = React.useRef<React.ElementRef<"pre">>(null);

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
    logsQuery.fetchNextPage,
    logsQuery.isFetching,
    logsQuery.hasNextPage,
    logsQuery.isFetchingNextPage
  ]);

  let count = logs.length;
  if (logsQuery.hasNextPage) {
    count++;
  }
  if (logsQuery.hasPreviousPage) {
    count++;
  }

  const virtualizer = useVirtualizer({
    count: logs.length,
    getScrollElement: () => logContentRef.current,
    estimateSize: () => 16,
    overscan: 50

    // scrollPaddingStart: 8,
    // scrollPaddingEnd: 16
    // paddingStart: 8,
    // paddingEnd: 16
  });
  const virtualItems = virtualizer.getVirtualItems();

  console.log({
    totalCount: logs.length
  });

  React.useEffect(() => {
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
  }, [filters.content, logs, virtualItems]);

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

  /**
   * Two outstanding bugs :
   * - when there are fewer items than the visible viewport, they get pushed at the end (bcos of `scaleY(-1)`)
   * - Tooltips seem to be painted in a weird order where the next element is always on top :
   *    -> https://renatello.com/css-position-fixed-not-working/
   *    -> now, they are inverted in position, the tooltip is far from where it should be
   */

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
          searchParams.isMaximized ? "container px-0 h-[82svh]" : "h-[65svh]"
        )}
      >
        <div className="rounded-t-sm w-full flex gap-2 flex-col md:flex-row flex-wrap lg:flex-nowrap">
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
            {logsQuery.isFetching ? (
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
        </div>
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

        <pre
          id="logContent"
          ref={logContentRef}
          className={cn(
            "-scale-y-100 justify-start min-h-0",
            "text-xs font-mono h-full rounded-md w-full",
            "bg-muted/25 dark:bg-neutral-950",
            "overflow-y-auto contain-strict",
            "pt-2 pb-4 whitespace-no-wrap"
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
              className={cn(
                "relative justify-start mb-auto",
                "[&_::highlight(search-results-highlight)]:bg-yellow-400/50",
                "[&_::highlight(search-results-highlight)]:text-card-foreground"
              )}
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
                        <div ref={loadNextPageRef} className="w-full h-px" />
                      )}

                      <Log
                        id={log.id}
                        time={log.time}
                        level={log.level}
                        index={virtualRow.index}
                        content={(log.content as string) ?? ""}
                        content_text={log.content_text ?? ""}
                        searchValue={
                          supportsCSSCustomHighlightsAPI()
                            ? ""
                            : filters.content
                        }
                      />
                      {(logsQuery.hasPreviousPage ||
                        logsQuery.isFetchingPreviousPage) &&
                        virtualRow.index === logs.length - 1 && (
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

type LogProps = Pick<DeploymentLog, "id" | "level" | "time"> & {
  content: string;
  content_text: string;
  searchValue?: string;
  index: number;
};

const Log = React.memo(
  ({
    content,
    searchValue,
    level,
    time,
    id,
    content_text,
    index
  }: LogProps) => {
    const search = searchValue ?? "";
    const date = new Date(time);
    const userTimeZone = Intl.DateTimeFormat().resolvedOptions().timeZone;
    const [isOpen, setIsOpen] = React.useState(false);

    return (
      <Accordion
        value={isOpen ? `log-item-${id}` : ""}
        onValueChange={(newVal) => setIsOpen(!!newVal.trim())}
        type="single"
        collapsible
        className="p-0 w-full"
      >
        <AccordionItem
          value={`log-item-${id}`}
          className={cn(
            "p-0 border-none border-0 ring-0 bg-transparent w-full ",
            isOpen ? "bg-yellow-500/20" : "bg-transparent"
          )}
        >
          <AccordionContent className="-scale-y-100  w-full px-4 py-2 max-w-[400px] data-[state=open]:animate-accordion-up data-[state=closed]:animate-accordion-down">
            <dl className="flex flex-col gap-0 ">
              <h4 className="font-semibold underline">Event time :</h4>
              <div className="grid grid-cols-3 gap-1">
                <dt className="col-span-1 text-foreground">{userTimeZone}:</dt>
                <dd className="col-span-2 text-card-foreground">
                  {formatDateForTimeZone(date, userTimeZone)}
                </dd>
              </div>
              <div className="grid grid-cols-3 gap-1">
                <dt className="col-span-1 text-foreground">UTC:</dt>
                <dd className="col-span-2 text-card-foreground">
                  {formatDateForTimeZone(date, "UTC")}
                </dd>
              </div>
              <div className="grid grid-cols-3 gap-1">
                <dt className="col-span-1 text-foreground">Timestamp:</dt>
                <dd className="col-span-2 text-card-foreground">
                  {date.getTime()}
                </dd>
              </div>
            </dl>
          </AccordionContent>
          <AccordionTrigger
            id={`log-item-${id}`}
            className={cn(
              "flex gap-2 px-2 hover:bg-slate-400/20 -scale-y-100 relative select-auto",
              "p-0 border-none border-0 ring-0",
              level === "ERROR" && "bg-red-400/20",
              isOpen ? "bg-yellow-700/20" : "bg-transparent"
            )}
          >
            <button className="inline-flex items-center">
              <time className="text-grey" dateTime={date.toISOString()}>
                {formatLogTime(date)}
              </time>
            </button>

            <div className="grid relative z-10">
              <AnsiHtml
                aria-hidden="true"
                className="text-wrap break-all select-none whitespace-pre relative col-start-1 col-end-1 row-start-1 row-end-1"
                text={content}
              />
              {supportsCSSCustomHighlightsAPI() ? (
                <pre
                  data-highlight="true"
                  className="text-wrap relative text-transparent z-10 break-all col-start-1 col-end-1 row-start-1 row-end-1"
                >
                  {content_text}
                </pre>
              ) : (
                <pre className="text-wrap relative text-transparent z-10 break-all col-start-1 col-end-1 row-start-1 row-end-1">
                  {search.length > 0
                    ? getHighlightedText(content_text, search)
                    : content_text}
                </pre>
              )}
            </div>
          </AccordionTrigger>
        </AccordionItem>
      </Accordion>
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
      return (
        <span className="bg-yellow-400/50 text-card-foreground">{part}</span>
      );
    } else {
      return <span>{part}</span>;
    }
  });
}

function formatLogTime(time: string | Date) {
  const date = new Date(time);
  const now = new Date();
  const dateFormat = new Intl.DateTimeFormat("en-GB", {
    month: "short",
    day: "numeric",
    year: date.getFullYear() === now.getFullYear() ? undefined : "numeric"
  })
    .format(date)
    .replaceAll(".", "");

  const hourFormat = new Intl.DateTimeFormat("en-GB", {
    hour: "numeric",
    minute: "numeric",
    second: "numeric"
  }).format(date);

  return `${dateFormat}, ${hourFormat}`;
}
