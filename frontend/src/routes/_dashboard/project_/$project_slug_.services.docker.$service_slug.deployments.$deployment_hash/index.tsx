import { useInfiniteQuery } from "@tanstack/react-query";
import { createFileRoute, useNavigate } from "@tanstack/react-router";
import { LoaderIcon, SearchIcon, XIcon } from "lucide-react";
import * as React from "react";
import { type DateRange } from "react-day-picker";
import { useDebounce } from "use-debounce";
import { DateRangeWithShortcuts } from "~/components/date-range-with-shortcuts";
import { withAuthRedirect } from "~/components/helper/auth-redirect";
import { Loader } from "~/components/loader";
import { MultiSelect } from "~/components/multi-select";
import { Button } from "~/components/ui/button";

import { Input } from "~/components/ui/input";

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

import { isEmptyObject } from "~/utils";

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
    page: searchParams.page ?? 1,
    per_page: searchParams.per_page ?? 50,
    created_at_after: searchParams.created_at_after,
    created_at_before: searchParams.created_at_before,
    source:
      searchParams.source ?? (LOG_SOURCES as Writeable<typeof LOG_SOURCES>),
    level: searchParams.level ?? (LOG_LEVELS as Writeable<typeof LOG_LEVELS>),
    content: debouncedSearchQuery
  } satisfies DeploymentLogFitlers;

  const logsQuery = useInfiniteQuery(
    deploymentQueries.logs({
      deployment_hash,
      project_slug,
      service_slug,
      filters
    })
  );

  const logs = React.useMemo(() => {
    return (
      logsQuery.data?.pages
        .flat()
        .map((item) => item.results)
        .flat() ?? []
    );
  }, [logsQuery.data]);

  const clearFilters = React.useCallback(() => {
    navigate({
      to: "./",
      replace: true
    });

    if (inputRef.current) {
      inputRef.current.value = "";
    }
  }, [navigate]);

  if (logsQuery.isLoading) {
    return <Loader className="h-[50vh]" />;
  }

  const date: DateRange = {
    from: filters.created_at_after,
    to: filters.created_at_before
  };

  return (
    <div className="grid grid-cols-12 gap-4 mt-8">
      <div className="col-span-12 flex flex-col h-[65vh] gap-2">
        <form
          action={(formData) => {
            console.log({
              data: formData
            });
          }}
          className="rounded-t-sm w-full flex gap-2 flex-col md:flex-row flex-wrap lg:flex-nowrap"
        >
          <div className="flex items-center gap-2 order-first">
            <DateRangeWithShortcuts
              date={date}
              setDate={(newDateRange) =>
                navigate({
                  search: {
                    ...filters,
                    created_at_before: newDateRange?.to,
                    created_at_after: newDateRange?.from
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
                    source: newVal
                  },
                  replace: true
                });
              }}
              placeholder="log sources"
            />
          </div>
        </form>
        <hr className="border-border" />
        {!isEmptyObject(searchParams) && (
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
          className="text-xs whitespace-no-wrap font-mono pt-2 pb-10 relative h-full rounded-md w-full bg-muted/25 dark:bg-card overflow-y-auto"
        >
          {logs.length === 0 &&
            (logsQuery.isFetching ? (
              <div className="text-sm text-center items-center flex gap-2 text-gray-500 absolute left-1/2 top-1/2 -translate-x-1/2 -translate-y-1/2">
                <LoaderIcon size={15} className="animate-spin" />
                <p>Fetching logs...</p>
              </div>
            ) : isEmptyObject(searchParams) ? (
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
            ))}

          {logs.length > 0 &&
            logs.map((log) => (
              <Log
                key={log.id}
                created_at={log.created_at}
                level={log.level}
                content={log.content as string}
                searchValue={filters.content}
              />
            ))}
        </pre>
      </div>
    </div>
  );
}

type LogProps = Pick<DeploymentLog, "level" | "created_at"> & {
  content: string;
  searchValue?: string;
};

const Log = React.memo(function ({
  content,
  searchValue,
  level,
  created_at
}: LogProps) {
  const search = searchValue ?? "";
  return (
    <div
      className={cn("flex gap-2 px-2", level === "ERROR" && "bg-red-400/20")}
    >
      <span className="text-grey">{formatLogTime(created_at)}</span>
      <pre
        className="text-wrap break-all"
        dangerouslySetInnerHTML={{
          __html:
            search.length > 0
              ? colorLogs(getHighlightedText(content, search))
              : colorLogs(content)
        }}
      />
    </div>
  );
});

function formatLogTime(time: string) {
  const date = new Date(time);
  const now = new Date();
  const dateFormat = new Intl.DateTimeFormat(navigator.language, {
    month: "short",

    day: "numeric",
    year: date.getFullYear() === now.getFullYear() ? undefined : "numeric"
  }).format(date);

  const hourFormat = new Intl.DateTimeFormat(navigator.language, {
    hour: "numeric",
    minute: "numeric",
    second: "numeric"
  }).format(date);

  return `${dateFormat}, ${hourFormat}`;
}

function escapeRegExp(input: string): string {
  return input.replace(/[.*+?^${}()|[\]\\]/g, "\\$&"); // $& means the whole matched string
}

// New function to get highlighted text as HTML string
function getHighlightedText(text: string, highlight: string): string {
  // Split on highlight term and include term into parts, ignore case
  const parts = text.split(new RegExp(`(${escapeRegExp(highlight)})`, "gi"));
  return parts
    .map((part) => {
      if (part.toLowerCase() === highlight.toLowerCase()) {
        return `<span class="bg-yellow-200/40">${part}</span>`;
      } else {
        return part;
      }
    })
    .join("");
}

function colorLogs(text: string) {
  const ansiStyles: Record<string, string> = {
    // Standard foreground colors
    "\u001b[30m": "text-black",
    "\u001b[31m": "text-red-500",
    "\u001b[32m": "text-green-500",
    "\u001b[33m": "text-yellow-500",
    "\u001b[34m": "text-blue-500",
    "\u001b[35m": "text-purple-500",
    "\u001b[36m": "text-cyan-500",
    "\u001b[37m": "text-gray-500",

    // Bright foreground colors
    "\u001b[90m": "text-gray-700",
    "\u001b[91m": "text-red-600",
    "\u001b[92m": "text-green-600",
    "\u001b[93m": "text-yellow-600",
    "\u001b[94m": "text-blue-600",
    "\u001b[95m": "text-purple-600",
    "\u001b[96m": "text-cyan-600",
    "\u001b[97m": "text-white",

    // Reset
    "\u001b[0m": ""
  };

  // Matches ANSI escape sequences
  const ansiRegex = /\u001b\[([0-9]+)m/g;

  // Keeps track of open span tags to ensure they are closed properly
  let openSpans = 0;

  text = text.replace(ansiRegex, (match, code) => {
    const ansiCode = `\u001b[${code}m`;
    const tailwindClass = ansiStyles[ansiCode];

    if (tailwindClass) {
      openSpans++;
      return `</span><span class="${tailwindClass}">`;
    } else if (ansiCode === "\u001b[0m") {
      if (openSpans > 0) {
        openSpans--;
        return "</span>";
      } else {
        return "";
      }
    }
    return "";
  });

  // Close any unclosed spans
  while (openSpans > 0) {
    text += "</span>";
    openSpans--;
  }

  return `<span>${text}</span>`;
}
