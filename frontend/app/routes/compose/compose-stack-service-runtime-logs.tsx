import {
  useInfiniteQuery,
  useQuery,
  useQueryClient
} from "@tanstack/react-query";
import {
  ArrowDownIcon,
  ArrowLeftIcon,
  LoaderIcon,
  Maximize2Icon,
  Minimize2Icon,
  SearchIcon,
  XIcon
} from "lucide-react";
import React from "react";
import type { DateRange } from "react-day-picker";
import {
  Navigate,
  href,
  useMatches,
  useParams,
  useSearchParams
} from "react-router";
import { Virtuoso } from "react-virtuoso";
import { useDebouncedCallback } from "use-debounce";
import type { Writeable } from "zod";
import type { ComposeStackTask } from "~/api/types";
import { DateRangeWithShortcuts } from "~/components/date-range-with-shortcuts";
import { Log } from "~/components/log";
import { MultiSelect } from "~/components/multi-select";
import { Ping } from "~/components/ping";
import { Button } from "~/components/ui/button";
import { Input } from "~/components/ui/input";
import {
  Select,
  SelectContent,
  SelectGroup,
  SelectItem,
  SelectLabel,
  SelectTrigger,
  SelectValue
} from "~/components/ui/select";
import {
  Tooltip,
  TooltipContent,
  TooltipProvider,
  TooltipTrigger
} from "~/components/ui/tooltip";
import { REALLY_BIG_NUMBER_THAT_IS_LESS_THAN_MAX_SAFE_INTEGER } from "~/lib/constants";
import {
  type ComposeStackRuntimeLogFilters,
  LOG_LEVELS,
  composeStackQueries,
  stackRuntimeLogSearchSchema
} from "~/lib/queries";
import { cn, formatLogTime } from "~/lib/utils";
import { queryClient } from "~/root";
import { TASK_STATUS_COLOR_MAP } from "~/routes/compose/components/compose-stack-service-replica-card";
import { stringToColor } from "~/utils";
import type { Route } from "./+types/compose-stack-service-runtime-logs";

export async function clientLoader({
  params: {
    projectSlug: project_slug,
    serviceSlug: service_name,
    envSlug: env_slug,
    composeStackSlug: stack_slug
  },
  request
}: Route.ClientLoaderArgs) {
  const searchParams = new URL(request.url).searchParams;
  const search = stackRuntimeLogSearchSchema.parse(searchParams);
  const filters = {
    time_after: search.time_after,
    time_before: search.time_before,
    level: search.level ?? (LOG_LEVELS as Writeable<typeof LOG_LEVELS>),
    query: search.query ?? "",
    container_id: search.container_id
  } satisfies ComposeStackRuntimeLogFilters;

  queryClient.prefetchInfiniteQuery(
    composeStackQueries.runtimeLogs({
      stack_slug,
      project_slug,
      service_name,
      env_slug,
      filters,
      queryClient
    })
  );
  return;
}

export default function ComposeStackRuntimeLogsPage({
  params
}: Route.ComponentProps) {
  const [searchParams, setSearchParams] = useSearchParams();
  const search = stackRuntimeLogSearchSchema.parse(searchParams);
  const [isAutoRefetchEnabled, setIsAutoRefetchEnabled] = React.useState(true);
  const filters = {
    time_after: search.time_after,
    time_before: search.time_before,
    level: search.level ?? (LOG_LEVELS as Writeable<typeof LOG_LEVELS>),
    query: search.query ?? "",
    container_id: search.container_id
  } satisfies ComposeStackRuntimeLogFilters;

  const isEmptySearchParams =
    !search.time_after &&
    !search.time_before &&
    !search.container_id &&
    (search.level?.length === 0 || !search.level) &&
    (search.query ?? "").length === 0;

  const queryClient = useQueryClient();
  const logsQuery = useInfiniteQuery({
    ...composeStackQueries.runtimeLogs({
      service_name: params.serviceSlug,
      project_slug: params.projectSlug,
      stack_slug: params.composeStackSlug,
      env_slug: params.envSlug,
      filters,
      queryClient,
      autoRefetchEnabled: isAutoRefetchEnabled
    }),
    enabled: !search.context
  });

  const logsWithContextQuery = useQuery({
    ...composeStackQueries.logWithContext({
      service_name: params.serviceSlug,
      project_slug: params.projectSlug,
      stack_slug: params.composeStackSlug,
      env_slug: params.envSlug,
      time: search.context!,
      context_lines: search.context_lines ?? 20
    }),
    enabled: !!search.context
  });

  const logs = logsWithContextQuery.isEnabled
    ? (logsWithContextQuery.data?.results ?? [])
    : (logsQuery.data?.pages ?? []).flatMap((item) => item.results);
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
        search.isMaximized && "fixed inset-0 bg-background z-100 w-full mt-0"
      )}
    >
      <div
        className={cn(
          "col-span-12 flex flex-col gap-2 relative",
          search.isMaximized ? "container px-0 h-dvh" : "h-[60dvh]"
        )}
      >
        {!search.isMaximized && (
          <HeaderSection
            startTransition={startTransition}
            inputRef={inputRef}
          />
        )}

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

        {search.isMaximized && (
          <TooltipProvider>
            <Tooltip delayDuration={0}>
              <TooltipTrigger asChild>
                <Button
                  variant="outline"
                  className="absolute top-5 right-5 z-30"
                  onClick={() => {
                    searchParams.set(
                      "isMaximized",
                      (!search.isMaximized).toString()
                    );
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
        )}

        {logs.length === 0 ? (
          <section
            className={cn(
              "justify-start min-h-0",
              "text-xs font-mono h-full rounded-md w-full",
              "bg-muted/25 dark:bg-neutral-950",
              "overflow-y-auto overflow-x-clip contain-strict",
              "whitespace-no-wrap",
              search.isMaximized && "rounded-none"
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
              "whitespace-no-wrap [overflow-anchor:none]",
              search.isMaximized && "rounded-none"
            )}
            data={logs}
            components={{
              Header: () =>
                !search.context &&
                (logsQuery.hasPreviousPage ||
                  logsQuery.isFetchingPreviousPage) ? (
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
                  <div className="h-8"></div>
                ),
              Footer: () => (
                <>
                  {!search.context && (
                    <div ref={fetchNextPageRef} className="w-fit h-px" />
                  )}
                  <div
                    className={cn("w-full pb-2 text-center text-grey italic")}
                    ref={autoRefetchRef}
                  >
                    {search.context ? (
                      <>-- End of log context --</>
                    ) : (
                      <>
                        -- LIVE <Ping /> new log entries will appear here --
                      </>
                    )}
                  </div>
                </>
              )
            }}
            itemContent={(_, log) => (
              <Log
                id={log.id}
                time={log.time}
                timestamp={log.timestamp}
                level={log.level}
                key={log.id}
                content={(log.content as string) ?? ""}
                content_text={log.content_text ?? ""}
                container_id={log.container_id}
              />
            )}
          />
        )}
      </div>
    </div>
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
  const search = stackRuntimeLogSearchSchema.parse(searchParams);

  const params = useParams() as Route.ComponentProps["params"];
  const {
    2: { loaderData }
  } = useMatches() as Route.ComponentProps["matches"];

  const { data: stack } = useQuery({
    ...composeStackQueries.single({
      project_slug: params.projectSlug,
      stack_slug: params.composeStackSlug,
      env_slug: params.envSlug
    }),
    initialData: loaderData.stack
  });

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
    !search.container_id &&
    !search.context &&
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

  const clearContext = () => {
    startTransition(() => {
      searchParams.delete("context");
      searchParams.delete("context_lines");
      setSearchParams(searchParams, {
        replace: true
      });
    });
  };

  const searchLogsForContent = useDebouncedCallback((query: string) => {
    startTransition(() => {
      searchParams.set("query", query);
      setSearchParams(searchParams, { replace: true });
    });
  }, 300);

  // const contextAsDate = search.context
  const logContextTime = search.context
    ? formatLogTime(new Date(search.context / 1_000_000 /* ns to ms */))
    : null;

  const serviceFound = Object.entries(stack.services).find(
    ([name]) => name === params.serviceSlug
  );

  if (!serviceFound) {
    return (
      <Navigate
        to={href(
          "/project/:projectSlug/:envSlug/compose-stacks/:composeStackSlug",
          params
        )}
      />
    );
  }

  const [, service] = serviceFound;

  const tasks = service.tasks
    .filter((t) => t.container_id !== null)
    .toSorted((tA, tB) => tB.version - tA.version) as Array<
    Omit<ComposeStackTask, "container_id"> & { container_id: string }
  >;

  const running = tasks.filter(
    (task) =>
      task.desired_status === "running" || task.desired_status === "complete"
  );

  const old = tasks.filter(
    (task) =>
      task.desired_status !== "running" && task.desired_status !== "complete"
  );

  return (
    <>
      <section className="rounded-t-sm w-full flex gap-2 flex-col items-start">
        <div
          className="flex items-center gap-2 flex-wrap"
          hidden={!!search.context}
        >
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

          <Select
            value={search.container_id ?? "<all>"}
            onValueChange={(value) => {
              searchParams.delete("container_id");
              if (value !== "<all>") {
                searchParams.set("container_id", value);
              }
              setSearchParams(searchParams);
            }}
          >
            <SelectTrigger className="w-54 [&_[data-label]]:inline placeholder-shown:text-grey">
              <SelectValue
                placeholder="select container"
                className="text-grey"
              />
            </SelectTrigger>
            <SelectContent className="border border-border text-sm">
              <SelectItem value="<all>">(All replicas)</SelectItem>
              <SelectGroup>
                <SelectLabel>Current</SelectLabel>
                {running.map((task) => (
                  <ContainerSelectItem task={task} key={task.id} />
                ))}
              </SelectGroup>
              <SelectGroup>
                <SelectLabel>Previous</SelectLabel>

                {old.map((task) => (
                  <ContainerSelectItem task={task} key={task.id} />
                ))}
              </SelectGroup>
            </SelectContent>
          </Select>

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
          {logContextTime ? (
            <>
              <Button
                variant="outline"
                className="inline-flex w-min gap-1"
                onClick={clearContext}
              >
                <ArrowLeftIcon size={15} />
                <span>Back</span>
              </Button>
              <Select
                value={(search.context_lines ?? 20).toString()}
                onValueChange={(value) => {
                  searchParams.set("context_lines", value);
                  setSearchParams(searchParams);
                }}
              >
                <SelectTrigger className="w-36 [&_[data-label]]:inline">
                  <SelectValue />
                </SelectTrigger>
                <SelectContent className="border border-border">
                  {[10, 20, 30, 40, 50, 100, 500].map((pageSize) => (
                    <SelectItem key={pageSize} value={pageSize.toString()}>
                      <span data-label className="text-grey hidden">
                        Show
                      </span>
                      &nbsp;
                      {pageSize} lines
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
              <div className="px-11 relative flex-1  bg-muted/40 dark:bg-card/30 py-2 rounded-md">
                <SearchIcon
                  size={15}
                  className="absolute left-4 top-1/2 -translate-y-1/2 text-grey"
                />
                <span className="text-grey">Viewing surrounding logs</span>

                {search.query && (
                  <>
                    <span className="text-grey"> • from search: "</span>
                    {search.query}
                    <span className="text-grey">"</span>
                  </>
                )}
              </div>
            </>
          ) : (
            <>
              <SearchIcon size={15} className="absolute left-4 text-grey" />
              <Input
                className="px-14 w-full md:min-w-150 text-sm  bg-muted/40 dark:bg-card/30"
                placeholder="Search for log contents"
                name="query"
                defaultValue={search.query}
                ref={inputRef}
                hidden={!!search.context}
                onChange={(ev) => {
                  const newQuery = ev.currentTarget.value;
                  if (newQuery !== (search.query ?? "")) {
                    searchLogsForContent(newQuery);
                  }
                }}
              />
            </>
          )}

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

type TaskWithContainerId = Omit<ComposeStackTask, "container_id"> & {
  container_id: string;
};

type ContainerSelectItemProps = {
  task: TaskWithContainerId;
};

function ContainerSelectItem({ task }: ContainerSelectItemProps) {
  const color = TASK_STATUS_COLOR_MAP[task.status];
  const containerColor = stringToColor(task.container_id);
  return (
    <SelectItem key={task.id} value={task.container_id}>
      <div
        className="inline-flex items-center gap-1"
        style={
          {
            "--container-color-light": containerColor.light,
            "--container-color-dark": containerColor.dark
          } as React.CSSProperties
        }
      >
        <span
          data-label
          className="text-[var(--container-color-light)] dark:text-[var(--container-color-dark)]"
        >
          {task.container_id.substring(0, 12)}
        </span>
        <div
          className={cn(
            "rounded-md bg-link/20 text-link px-1  inline-flex gap-1 items-center py-0",
            {
              "bg-emerald-400/30 dark:bg-emerald-600/20 text-green-600  dark:text-emerald-400":
                color === "green",
              "bg-red-600/25 text-red-700 dark:text-red-400": color === "red",
              "bg-yellow-400/30 dark:bg-yellow-600/20 text-amber-700 dark:text-yellow-300":
                color === "yellow",
              "bg-gray-600/20 dark:bg-gray-600/60 text-card-foreground":
                color === "gray",
              "bg-link/30 text-link": color === "blue"
            }
          )}
        >
          <code className="text-sm">{task.status}</code>
        </div>
      </div>
    </SelectItem>
  );
}
