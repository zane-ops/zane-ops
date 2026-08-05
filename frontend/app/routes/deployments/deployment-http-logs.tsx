import { useInfiniteQuery, useQueryClient } from "@tanstack/react-query";
import * as React from "react";
import { useSearchParams } from "react-router";
import { HttpLogFilterBar } from "~/components/http-logs/http-log-filter-bar";
import { HttpLogRequestDetails } from "~/components/http-logs/http-log-request-details";
import { HttpLogTable } from "~/components/http-logs/http-log-table";
import { HttpLogsLayout } from "~/components/http-logs/http-logs-layout";
import {
  type HTTPLogFilters,
  deploymentQueries,
  ensureMinRole,
  httpLogSearchSchema
} from "~/lib/queries";
import { getQueryClient } from "~/lib/query-client";
import {
  getCurrentWorkspace,
  useCurrentWorkspace
} from "~/lib/workspace-store";
import type { Route } from "./+types/deployment-http-logs";

export async function clientLoader({
  request,
  params: {
    deploymentHash: deployment_hash,
    projectSlug: project_slug,
    serviceSlug: service_slug,
    envSlug: env_slug
  }
}: Route.ClientLoaderArgs) {
  const queryClient = getQueryClient();
  await ensureMinRole(queryClient, "Member");
  const { id: workspaceId } = await getCurrentWorkspace(queryClient);
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
      deploymentQueries.httpLogs({
        workspaceId,
        deployment_hash,
        project_slug,
        service_slug,
        env_slug,
        filters,
        queryClient
      })
    ),
    search.request_id
      ? queryClient.ensureQueryData(
          deploymentQueries.singleHttpLog({
            workspaceId,
            deployment_hash,
            project_slug,
            service_slug,
            env_slug,
            request_uuid: search.request_id
          })
        )
      : undefined
  ] as const);
  return { httpLogs, httpLog };
}

export default function DeploymentHttpLogsPage({
  loaderData,
  params: {
    deploymentHash: deployment_hash,
    projectSlug: project_slug,
    serviceSlug: service_slug,
    envSlug: env_slug
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
    ...deploymentQueries.httpLogs({
      workspaceId,
      deployment_hash,
      project_slug,
      service_slug,
      env_slug,
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
          deploymentQueries.filterHttpLogFields({
            workspaceId,
            deployment_hash,
            project_slug,
            service_slug,
            env_slug,
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
