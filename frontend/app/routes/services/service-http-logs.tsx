import { useInfiniteQuery, useQueryClient } from "@tanstack/react-query";
import * as React from "react";
import { useSearchParams } from "react-router";
import { HttpLogFilterBar } from "~/components/http-logs/http-log-filter-bar";
import { HttpLogRequestDetails } from "~/components/http-logs/http-log-request-details";
import { HttpLogTable } from "~/components/http-logs/http-log-table";
import { HttpLogsLayout } from "~/components/http-logs/http-logs-layout";
import {
  type HTTPLogFilters,
  ensureMinRole,
  httpLogSearchSchema,
  serviceQueries
} from "~/lib/queries";
import { getQueryClient } from "~/lib/query-client";
import { notFound } from "~/lib/utils";
import {
  getCurrentWorkspace,
  useCurrentWorkspace
} from "~/lib/workspace-store";
import type { Route } from "./+types/service-http-logs";

export async function clientLoader({
  request,
  params: {
    projectSlug: project_slug,
    serviceSlug: service_slug,
    envSlug: env_slug
  }
}: Route.ClientLoaderArgs) {
  const queryClient = getQueryClient();
  await ensureMinRole(queryClient, "Member");
  const { id: workspaceId } = await getCurrentWorkspace(queryClient);
  const service = await queryClient.ensureQueryData(
    serviceQueries.single({
      workspaceId,
      project_slug,
      service_slug,
      env_slug
    })
  );

  if (!service) {
    throw notFound();
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
      serviceQueries.httpLogs({
        workspaceId,
        project_slug,
        service_slug,
        env_slug,
        service_id: service.id,
        filters,
        queryClient
      })
    ),
    search.request_id
      ? queryClient.ensureQueryData(
          serviceQueries.singleHttpLog({
            workspaceId,
            project_slug,
            request_uuid: search.request_id,
            service_slug,
            env_slug,
            service_id: service.id
          })
        )
      : undefined
  ] as const);
  return { httpLogs, httpLog, service };
}

export default function ServiceHttpLogsPage({
  loaderData,
  params: {
    projectSlug: project_slug,
    serviceSlug: service_slug,
    envSlug: env_slug
  },
  matches: {
    3: {
      loaderData: { service }
    }
  }
}: Route.ComponentProps) {
  const workspaceId = useCurrentWorkspace().id;
  const queryClient = useQueryClient();
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
    ...serviceQueries.httpLogs({
      workspaceId,
      project_slug,
      service_slug,
      env_slug,
      service_id: service.id,
      filters,
      queryClient,
      autoRefetchEnabled: isAutoRefetchEnabled
    }),
    initialData: loaderData.httpLogs
  });

  return (
    <HttpLogsLayout>
      <HttpLogRequestDetails log={loaderData.httpLog} />

      <HttpLogFilterBar
        fieldValuesQuery={({ field, value }) =>
          serviceQueries.filterHttpLogFields({
            workspaceId,
            project_slug,
            service_slug,
            env_slug,
            service_id: service.id,
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
