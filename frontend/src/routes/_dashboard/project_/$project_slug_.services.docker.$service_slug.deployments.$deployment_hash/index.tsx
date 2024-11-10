import * as Form from "@radix-ui/react-form";
import { useInfiniteQuery, useQuery } from "@tanstack/react-query";
import { createFileRoute, useNavigate } from "@tanstack/react-router";
import { SearchIcon, XIcon } from "lucide-react";
import * as React from "react";
import type { DateRange } from "react-day-picker";
import { DateRangeWithShortcuts } from "~/components/date-range-with-shortcuts";
import { withAuthRedirect } from "~/components/helper/auth-redirect";
import { Loader } from "~/components/loader";
import { Button } from "~/components/ui/button";
import { Checkbox } from "~/components/ui/checkbox";
import { Input } from "~/components/ui/input";
import { Label } from "~/components/ui/label";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue
} from "~/components/ui/select";
import {
  Tooltip,
  TooltipContent,
  TooltipProvider,
  TooltipTrigger
} from "~/components/ui/tooltip";
import {
  type DeploymentLogFitlers,
  LOG_LEVELS,
  LOG_SOURCES,
  deploymentLogSearchSchema,
  deploymentQueries
} from "~/lib/queries";
import type { Writeable } from "~/lib/types";
import { cn } from "~/lib/utils";

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

  const filters = {
    page: searchParams.page ?? 1,
    per_page: searchParams.per_page ?? 10,
    time_after: searchParams.time_after,
    time_before: searchParams.time_before,
    cursor: searchParams.cursor,
    source:
      searchParams.source ?? (LOG_SOURCES as Writeable<typeof LOG_SOURCES>),
    level: searchParams.level ?? (LOG_LEVELS as Writeable<typeof LOG_LEVELS>)
  } satisfies DeploymentLogFitlers;

  const logsQuery = useInfiniteQuery(
    deploymentQueries.logs({
      deployment_hash,
      project_slug,
      service_slug,
      filters
    })
  );

  if (logsQuery.isLoading) {
    return <Loader className="h-[50vh]" />;
  }

  const date: DateRange = {
    from: filters.time_after,
    to: filters.time_before
  };

  return (
    <div className="grid grid-cols-12 gap-4 mt-8">
      <aside className="col-span-3 h-full hidden">
        <Form.Root
          action=""
          onChange={(e) => {
            console.log({
              data: new FormData(e.currentTarget)
            });
          }}
          className="flex gap-3 flex-col sticky top-0"
        >
          <div className="flex w-full items-center gap-2">
            <DateRangeWithShortcuts
              date={date}
              setDate={(newDateRange) =>
                navigate({
                  search: {
                    ...filters,
                    time_before: newDateRange?.to,
                    time_after: newDateRange?.from
                  },
                  replace: true
                })
              }
              className={cn("w-full")}
            />
            <Button
              variant="outline"
              onClick={() =>
                navigate({
                  search: {
                    ...filters,
                    time_before: undefined,
                    time_after: undefined
                  },
                  replace: true
                })
              }
              className="py-2.5 h-auto"
            >
              <XIcon size={15} className="flex-none" />
            </Button>
          </div>

          {/* <div className="flex flex-col gap-1.5">
            <Label htmlFor="logLevel">Log level</Label>
            <Select
              name="level"
              // value={changedVolumeMode}
              // onValueChange={(mode) => setChangedVolumeMode(mode as VolumeMode)}
            >
              <SelectTrigger id="logLevel">
                <SelectValue placeholder="Select a log level" />
              </SelectTrigger>
              <SelectContent>
                {LOG_LEVELS.map((level) => (
                  <SelectItem value={level} key={level} className="capitalize">
                    {level}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div> */}

          <fieldset className="flex flex-col gap-1.5">
            <legend>Levels</legend>
            {LOG_LEVELS.map((level) => (
              <Form.Field
                name="source"
                key={level}
                className="inline-flex gap-2 items-center"
              >
                <Form.Control asChild>
                  <Checkbox value={level} />
                </Form.Control>

                <Form.Label className="text-gray-400 inline-flex gap-1 items-center capitalize">
                  {level}
                </Form.Label>
              </Form.Field>
            ))}
          </fieldset>

          <fieldset className="flex flex-col gap-1.5">
            <legend>Sources</legend>
            {LOG_SOURCES.map((source) => (
              <Form.Field
                name="source"
                key={source}
                className="inline-flex gap-2 items-center"
              >
                <Form.Control asChild>
                  <Checkbox value={source} />
                </Form.Control>

                <Form.Label className="text-gray-400 inline-flex gap-1 items-center capitalize">
                  {source}
                </Form.Label>
              </Form.Field>
            ))}
          </fieldset>
        </Form.Root>
      </aside>

      <div className="col-span-12 flex flex-col h-[65vh] gap-2">
        <form
          action={() => {}}
          onChange={(e) => {
            console.log({
              change: new FormData(e.currentTarget)
            });
          }}
          className="rounded-t-sm w-full flex gap-2"
        >
          <div className="flex items-center gap-2">
            <DateRangeWithShortcuts
              date={date}
              setDate={(newDateRange) =>
                navigate({
                  search: {
                    ...filters,
                    time_before: newDateRange?.to,
                    time_after: newDateRange?.from
                  },
                  replace: true
                })
              }
              className={cn("w-[235px]")}
            />
            {date.from !== undefined && date.to !== undefined && (
              <TooltipProvider>
                <Tooltip delayDuration={0}>
                  <TooltipTrigger>
                    <Button
                      variant="outline"
                      onClick={() =>
                        navigate({
                          search: {
                            ...filters,
                            time_before: undefined,
                            time_after: undefined
                          },
                          replace: true
                        })
                      }
                      className="py-2.5 h-auto px-2"
                    >
                      <span className="sr-only">Clear date</span>
                      <XIcon size={15} className="flex-none" />
                    </Button>
                  </TooltipTrigger>
                  <TooltipContent>Clear date</TooltipContent>
                </Tooltip>
              </TooltipProvider>
            )}
          </div>

          <div className="flex w-full items-center relative">
            <SearchIcon className="absolute left-4 text-grey" />
            <Input
              className="px-14 w-full text-sm  bg-muted/40 dark:bg-card/30"
              placeholder="Search for log contents"
              name="query"
              onKeyUp={(e) => {
                e.preventDefault();
                e.stopPropagation();
                console.log({
                  v: e.currentTarget.value
                });
              }}
            />
          </div>
        </form>
        <hr className="border-border" />
        <div className="rounded-md px-4 pb-2  overflow-y-auto bg-muted/25 dark:bg-card h-full w-full">
          <pre
            id="logContent"
            className="text-base whitespace-no-wrap overflow-x-scroll font-mono pt-2 "
          >
            <span className="italic text-gray-500">
              {/* {!!searchValue ? ( */}
              {/* <>No logs matching filter `{searchValue}`</> */}
              {/* ) : ( */}
              <>No logs yets</>
              {/* )} */}
            </span>
          </pre>
        </div>
      </div>
    </div>
  );
}
