import { useInfiniteQuery, useQuery } from "@tanstack/react-query";
import { createFileRoute, useNavigate } from "@tanstack/react-router";
import * as React from "react";
import type { DateRange } from "react-day-picker";
import { DateRangeWithShortcuts } from "~/components/date-range-with-shortcuts";
import { withAuthRedirect } from "~/components/helper/auth-redirect";
import { Loader } from "~/components/loader";
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
    <div className="grid grid-cols-12 gap-4">
      <aside className="flex mt-8 gap-2 flex-col col-span-3 h-full">
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
      </aside>
      <div className="col-span-9"></div>
    </div>
  );
}
