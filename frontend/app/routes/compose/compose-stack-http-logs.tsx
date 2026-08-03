import { useInfiniteQuery } from "@tanstack/react-query";
import * as React from "react";
import { useSearchParams } from "react-router";
import { HttpLogDetails } from "~/components/http-logs/http-log-details";
import { HttpLogFilterBar } from "~/components/http-logs/http-log-filter-bar";
import { HttpLogTable } from "~/components/http-logs/http-log-table";
import { HttpLogsLayout } from "~/components/http-logs/http-logs-layout";
import { MultiSelect } from "~/components/multi-select";
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
import type { Route } from "./+types/compose-stack-http-logs";

export async function clientLoader({
  request,
  params: {
    projectSlug: project_slug,
    composeStackSlug: stack_slug,
    envSlug: env_slug
  }
}: Route.ClientLoaderArgs) {
  const queryClient = getQueryClient();
  await ensureMinRole(queryClient, "Member");
  const { id: workspaceId } = await getCurrentWorkspace(queryClient);
  const stack = await queryClient.ensureQueryData(
    composeStackQueries.single({
      workspaceId,
      project_slug,
      stack_slug,
      env_slug
    })
  );

  if (!stack) {
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
      composeStackQueries.httpLogs({
        workspaceId,
        project_slug,
        stack_slug,
        env_slug,
        stack_id: stack.id,
        filters,
        queryClient,
        stack_service_name: searchParams.getAll("stack_service_name")
      })
    ),
    search.request_id
      ? queryClient.ensureQueryData(
          composeStackQueries.singleHttpLog({
            workspaceId,
            project_slug,
            request_uuid: search.request_id,
            stack_slug,
            env_slug
          })
        )
      : undefined
  ] as const);
  return { httpLogs, httpLog, stack };
}

export default function ComposeStackHttpLogsPage({
  loaderData,
  params: {
    projectSlug: project_slug,
    composeStackSlug: stack_slug,
    envSlug: env_slug
  }
}: Route.ComponentProps) {
  const workspaceId = useCurrentWorkspace().id;
  const queryClient = getQueryClient();
  const [searchParams, setSearchParams] = useSearchParams();
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

  const selectedServiceNames = searchParams.getAll("stack_service_name");

  const logsQuery = useInfiniteQuery({
    ...composeStackQueries.httpLogs({
      workspaceId,
      project_slug,
      stack_slug,
      env_slug,
      stack_id: loaderData.stack.id,
      filters,
      queryClient,
      autoRefetchEnabled: isAutoRefetchEnabled,
      stack_service_name: selectedServiceNames
    }),
    initialData: loaderData.httpLogs
  });

  return (
    <HttpLogsLayout>
      <HttpLogDetails log={loaderData.httpLog} />

      <HttpLogFilterBar
        extraFilterParamKeys={["stack_service_name"]}
        extraFilters={
          <MultiSelect
            label="services"
            options={Object.keys(loaderData.stack.services)}
            align="start"
            value={selectedServiceNames}
            onValueChange={(newServices) => {
              searchParams.delete("stack_service_name");

              for (const svc of newServices) {
                searchParams.append("stack_service_name", svc);
              }
              setSearchParams(searchParams, { replace: true });
            }}
            className="w-auto"
          />
        }
        fieldValuesQuery={({ field, value }) =>
          composeStackQueries.filterHttpLogFields({
            workspaceId,
            project_slug,
            stack_slug,
            env_slug,
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
        showStackServiceColumn
      />
    </HttpLogsLayout>
  );
}
