import { useInfiniteQuery } from "@tanstack/react-query";
import * as React from "react";
import { useSearchParams } from "react-router";
import { HttpLogDetails } from "~/components/http-logs/http-log-details";
import { HttpLogFilterBar } from "~/components/http-logs/http-log-filter-bar";
import { HttpLogTable } from "~/components/http-logs/http-log-table";
import { HttpLogsLayout } from "~/components/http-logs/http-logs-layout";
import {
  type HTTPLogFilters,
  composeStackQueries,
  ensureMinRole,
  httpLogSearchSchema
} from "~/lib/queries";
import { getQueryClient } from "~/lib/query-client";
import { notFound } from "~/lib/utils";
import {
  getCurrentWorkspace,
  useCurrentWorkspace
} from "~/lib/workspace-store";
import type { Route } from "./+types/compose-stack-service-http-logs";

export async function clientLoader({
  params,
  request
}: Route.ClientLoaderArgs) {
  const queryClient = getQueryClient();
  await ensureMinRole(queryClient, "Member");
  const { id: workspaceId } = await getCurrentWorkspace(queryClient);
  const stack = await queryClient.ensureQueryData(
    composeStackQueries.single({
      workspaceId: workspaceId,
      project_slug: params.projectSlug,
      stack_slug: params.composeStackSlug,
      env_slug: params.envSlug
    })
  );

  if (!stack) {
    throw notFound();
  }

  const service = Object.keys(stack.services).find(
    (svc) => svc === params.serviceSlug
  );

  if (!service) {
    throw notFound(`Service '${params.serviceSlug}' not found in this stack`);
  }

  const searchParams = new URL(request.url).searchParams;
  const search = httpLogSearchSchema.parse(searchParams);
  const filters = {
    time_after: search.time_after,
    time_before: search.time_before,
    request_method: search.request_method,
    request_host: search.request_host,
    request_ip: search.request_ip,
    request_path: search.request_path,
    request_query: search.request_query,
    request_user_agent: search.request_user_agent,
    request_country_code: search.request_country_code,
    status: search.status,
    sort_by: search.sort_by
  } satisfies HTTPLogFilters;

  const [httpLogs, httpLog] = await Promise.all([
    queryClient.ensureInfiniteQueryData(
      composeStackQueries.httpLogs({
        workspaceId: workspaceId,
        project_slug: params.projectSlug,
        stack_slug: params.composeStackSlug,
        env_slug: params.envSlug,
        stack_id: stack.id,
        filters,
        queryClient,
        stack_service_name: [params.serviceSlug]
      })
    ),
    search.request_id
      ? queryClient.ensureQueryData(
          composeStackQueries.singleHttpLog({
            workspaceId: workspaceId,
            project_slug: params.projectSlug,
            stack_slug: params.composeStackSlug,
            env_slug: params.envSlug,
            request_uuid: search.request_id
          })
        )
      : undefined
  ] as const);
  return { httpLogs, httpLog, stack };
}

export default function ComposeStackServiceHttpLogsPage({
  loaderData,
  params
}: Route.ComponentProps) {
  const queryClient = getQueryClient();
  const workspaceId = useCurrentWorkspace().id;
  const [searchParams] = useSearchParams();
  const search = httpLogSearchSchema.parse(searchParams);
  const [isAutoRefetchEnabled, setIsAutoRefetchEnabled] = React.useState(true);

  const filters = {
    time_after: search.time_after,
    time_before: search.time_before,
    request_method: search.request_method,
    request_host: search.request_host,
    request_ip: search.request_ip,
    request_path: search.request_path,
    request_query: search.request_query,
    request_user_agent: search.request_user_agent,
    request_country_code: search.request_country_code,
    status: search.status,
    sort_by: search.sort_by
  } satisfies HTTPLogFilters;

  const logsQuery = useInfiniteQuery({
    ...composeStackQueries.httpLogs({
      workspaceId: workspaceId,
      project_slug: params.projectSlug,
      stack_slug: params.composeStackSlug,
      env_slug: params.envSlug,
      stack_id: loaderData.stack.id,
      filters,
      queryClient,
      autoRefetchEnabled: isAutoRefetchEnabled,
      stack_service_name: [params.serviceSlug]
    }),
    initialData: loaderData.httpLogs
  });

  return (
    <HttpLogsLayout>
      <HttpLogDetails log={loaderData.httpLog} />

      <HttpLogFilterBar
        fieldValuesQuery={({ field, value }) =>
          composeStackQueries.filterHttpLogFields({
            workspaceId,
            project_slug: params.projectSlug,
            stack_slug: params.composeStackSlug,
            env_slug: params.envSlug,
            stack_id: loaderData.stack.id,
            field,
            value
          })
        }
      />

      <HttpLogTable
        logsQuery={logsQuery}
        isAutoRefetchEnabled={isAutoRefetchEnabled}
        onAutoRefetchEnabledChange={setIsAutoRefetchEnabled}
      />
    </HttpLogsLayout>
  );
}
