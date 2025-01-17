import {
  Tooltip,
  TooltipContent,
  TooltipProvider,
  TooltipTrigger
} from "@radix-ui/react-tooltip";
import { useInfiniteQuery, useQueryClient } from "@tanstack/react-query";
import { AnsiHtml } from "fancy-ansi/react";
import {
  ArrowDownIcon,
  ChevronRightIcon,
  LoaderIcon,
  Maximize2Icon,
  Minimize2Icon,
  SearchIcon,
  XIcon
} from "lucide-react";
import * as React from "react";
import type { DateRange } from "react-day-picker";
import { useSearchParams } from "react-router";
import { Virtuoso } from "react-virtuoso";
import { useDebouncedCallback } from "use-debounce";
import type { Writeable } from "zod";
import { DateRangeWithShortcuts } from "~/components/date-range-with-shortcuts";
import { MultiSelect } from "~/components/multi-select";
import { Button, buttonVariants } from "~/components/ui/button";
import { Input } from "~/components/ui/input";
import {
  MAX_VISIBLE_LOG_CHARS_LIMIT,
  REALLY_BIG_NUMBER_THAT_IS_LESS_THAN_MAX_SAFE_INTEGER
} from "~/lib/constants";
import {
  type DeploymentLog,
  type DeploymentLogFitlers,
  LOG_LEVELS,
  LOG_SOURCES,
  deploymentLogSearchSchema,
  deploymentQueries
} from "~/lib/queries";
import { cn, formatLogTime } from "~/lib/utils";
import { queryClient } from "~/root";
import { excerpt } from "~/utils";
import { type Route } from "./+types/deployment-logs";

export async function clientLoader({
  params: {
    projectSlug: project_slug,
    serviceSlug: service_slug,
    deploymentHash: deployment_hash
  },
  request
}: Route.ClientLoaderArgs) {
  const searchParams = new URL(request.url).searchParams;
  const search = deploymentLogSearchSchema.parse(searchParams);
  const filters = {
    time_after: search.time_after,
    time_before: search.time_before,
    source: search.source ?? (LOG_SOURCES as Writeable<typeof LOG_SOURCES>),
    level: search.level ?? (LOG_LEVELS as Writeable<typeof LOG_LEVELS>),
    query: search.query ?? ""
  } satisfies DeploymentLogFitlers;

  const logs = await queryClient.ensureInfiniteQueryData(
    deploymentQueries.logs({
      deployment_hash,
      project_slug,
      service_slug,
      filters,
      queryClient
    })
  );
  return { logs };
}
export default function DeploymentLogsPage({
  loaderData,
  params: {
    projectSlug: project_slug,
    serviceSlug: service_slug,
    deploymentHash: deployment_hash
  }
}: Route.ComponentProps) {
  const [searchParams, setSearchParams] = useSearchParams();
  const search = deploymentLogSearchSchema.parse(searchParams);
  const [isAutoRefetchEnabled, setIsAutoRefetchEnabled] = React.useState(true);
  const filters = {
    time_after: search.time_after,
    time_before: search.time_before,
    source: search.source ?? (LOG_SOURCES as Writeable<typeof LOG_SOURCES>),
    level: search.level ?? (LOG_LEVELS as Writeable<typeof LOG_LEVELS>),
    query: search.query ?? ""
  } satisfies DeploymentLogFitlers;

  const isEmptySearchParams =
    !search.time_after &&
    !search.time_before &&
    (search.source?.length === 0 || !search.source) &&
    (search.level?.length === 0 || !search.level) &&
    (search.query ?? "").length === 0;

  const queryClient = useQueryClient();
  const logsQuery = useInfiniteQuery({
    ...deploymentQueries.logs({
      deployment_hash,
      project_slug,
      service_slug,
      filters,
      queryClient,
      autoRefetchEnabled: isAutoRefetchEnabled
    }),
    initialData: loaderData.logs
  });

  const logs = (logsQuery.data?.pages ?? [])
    .toReversed()
    .flatMap((item) => item.results)
    .reverse();
  const logContentRef = React.useRef<React.ComponentRef<"section">>(null);
  const [, startTransition] = React.useTransition();
  const [isAtBottom, setIsAtBottom] = React.useState(true);
  const virtuoso = React.useRef<React.ComponentRef<typeof Virtuoso>>(null);

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

  const [firstItemIndex, setFirstItemIndex] = React.useState(
    REALLY_BIG_NUMBER_THAT_IS_LESS_THAN_MAX_SAFE_INTEGER
  );
  const inputRef = React.useRef<{ reset: () => void }>(null);

  const clearFilters = () => {
    startTransition(() => {
      setSearchParams(
        new URLSearchParams([["isMaximized", `${search.isMaximized}`]]),
        {
          replace: true
        }
      );
    });
    if (inputRef.current) {
      inputRef.current?.reset();
    }
  };

  return (
    <div
      className={cn(
        "grid grid-cols-12 gap-4 mt-8",
        search.isMaximized &&
          "fixed inset-0 top-20 bg-background z-50 p-5 w-full"
      )}
    >
      <div
        className={cn(
          "col-span-12 flex flex-col gap-2 relative",
          search.isMaximized ? "container px-0 h-[82dvh]" : "h-[60dvh]"
        )}
      >
        <HeaderSection startTransition={startTransition} inputRef={inputRef} />
        {!isAtBottom && (
          <Button
            variant="secondary"
            className="absolute top-28 right-4  z-30"
            size="sm"
            onClick={() => {
              virtuoso.current?.scrollToIndex({
                index: "LAST",
                behavior: "smooth",
                align: "end"
              });
            }}
          >
            <span>End</span> <ArrowDownIcon size={15} />
          </Button>
        )}

        {logs.length === 0 ? (
          <section
            className={cn(
              "justify-start min-h-0",
              "text-xs font-mono h-full rounded-md w-full",
              "bg-muted/25 dark:bg-neutral-950",
              "overflow-y-auto overflow-x-clip contain-strict",
              "whitespace-no-wrap"
            )}
          >
            {logsQuery.isFetching ? (
              <div className="text-sm text-center items-center flex gap-2 text-gray-500 absolute left-1/2 top-1/2 -translate-x-1/2 -translate-y-1/2">
                <LoaderIcon size={15} className="animate-spin" />
                <p>Fetching logs...</p>
              </div>
            ) : isEmptySearchParams ? (
              <div className="text-sm text-center items-center flex flex-col text-gray-500 absolute left-1/2 top-1/2 -translate-x-1/2 -translate-y-1/2">
                <h3 className="text-base font-semibold">No logs yet</h3>
                <p className="inline-block max-w-lg text-balance ">
                  New log entries will appear here.
                </p>
              </div>
            ) : (
              <div className="text-sm px-2 gap-1.5 text-center items-center flex flex-col text-gray-500 absolute left-1/2 top-1/2 -translate-x-1/2 -translate-y-1/2">
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
              "whitespace-no-wrap [overflow-anchor:none]"
            )}
            data={logs}
            components={{
              Header: () =>
                (logsQuery.hasPreviousPage ||
                  logsQuery.isFetchingPreviousPage) && (
                  <div
                    ref={fetchPreviousPageRef}
                    className={cn(
                      "text-center items-center justify-center flex gap-2 text-gray-500 px-2 my-2"
                    )}
                  >
                    <LoaderIcon size={15} className="animate-spin" />
                    <p>Fetching previous logs...</p>
                  </div>
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

function Ping() {
  return (
    <span className="relative inline-flex h-2 w-2">
      <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-green-500 opacity-75"></span>
      <span className="relative inline-flex rounded-full h-2 w-2 bg-green-500"></span>
    </span>
  );
}

const HeaderSection = React.memo(function HeaderSection({
  startTransition,
  inputRef: _inputRef
}: {
  startTransition: React.TransitionStartFunction;
  inputRef?: React.Ref<{ reset: () => void }>;
}) {
  const [searchParams, setSearchParams] = useSearchParams();
  const search = deploymentLogSearchSchema.parse(searchParams);

  React.useImperativeHandle(
    _inputRef,
    () => {
      return {
        reset() {
          if (inputRef.current) {
            inputRef.current.value = "";
          }
        }
      };
    },
    []
  );

  const inputRef = React.useRef<React.ComponentRef<"input">>(null);

  const date: DateRange = {
    from: search.time_after,
    to: search.time_before
  };

  const isEmptySearchParams =
    !search.time_after &&
    !search.time_before &&
    (search.source ?? []).length === 0 &&
    (search.level ?? []).length === 0 &&
    (search.query ?? "").length === 0;

  const clearFilters = () => {
    startTransition(() => {
      setSearchParams(
        new URLSearchParams([["isMaximized", `${search.isMaximized}`]]),
        {
          replace: true
        }
      );
    });

    if (inputRef.current) {
      inputRef.current.value = "";
    }
  };

  const searchLogsForContent = useDebouncedCallback((query: string) => {
    startTransition(() => {
      searchParams.set("query", query);
      setSearchParams(searchParams, { replace: true });
    });
  }, 300);

  return (
    <>
      <section className="rounded-t-sm w-full flex gap-2 flex-col items-start">
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
            value={search.level as string[]}
            className="w-auto"
            options={LOG_LEVELS as Writeable<typeof LOG_LEVELS>}
            onValueChange={(newVal) => {
              searchParams.delete("level");
              for (const value of newVal) {
                searchParams.append("level", value);
              }
              setSearchParams(searchParams, { replace: true });
            }}
            label="levels"
          />

          <MultiSelect
            value={search.source as string[]}
            className="w-auto"
            options={LOG_SOURCES as Writeable<typeof LOG_SOURCES>}
            onValueChange={(newVal) => {
              searchParams.delete("source");
              for (const value of newVal) {
                searchParams.append("source", value);
              }
              setSearchParams(searchParams, { replace: true });
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
            defaultValue={search.query}
            ref={inputRef}
            onChange={(ev) => {
              const newQuery = ev.currentTarget.value;
              if (newQuery !== (search.query ?? "")) {
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
        </div>
      </section>
      <hr className="border-border" />
    </>
  );
});

type LogProps = Pick<DeploymentLog, "id" | "level" | "time"> & {
  content: string;
  content_text: string;
};

function Log({ content, level, time, id, content_text }: LogProps) {
  const date = new Date(time);

  const [searchParams] = useSearchParams();
  const search = searchParams.get("query") ?? "";

  const logTime = formatLogTime(date);

  return (
    <div
      id={`log-item-${id}`}
      className={cn(
        "w-full flex gap-2 hover:bg-slate-400/20 relative  group",
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
                "break-all text-wrap whitespace-pre [text-wrap-mode:wrap] select-none"
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
}

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
