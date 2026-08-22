import { useInfiniteQuery, useQueryClient } from "@tanstack/react-query";
import * as React from "react";
import { useSearchParams } from "react-router";
import { HttpLogFilterBar } from "~/components/http-logs/http-log-filter-bar";
import { HttpLogRequestDetails } from "~/components/http-logs/http-log-request-details";
import { HttpLogTable } from "~/components/http-logs/http-log-table";
import { HttpLogsLayout } from "~/components/http-logs/http-logs-layout";
import { MultiSelect, type MultiSelectOption } from "~/components/multi-select";
import { Separator } from "~/components/ui/separator";
import {
  type HTTPLogFilters,
  HTTP_LOG_SOURCES,
  HTTP_LOG_SOURCE_LABELS,
  httpLogSearchSchema,
  proxyHttpLogQueries
} from "~/lib/queries";
import { getQueryClient } from "~/lib/query-client";
import { metaTitle } from "~/lib/utils";
import type { Route } from "./+types/global-http-logs";

export function meta() {
  return [
    metaTitle("Global HTTP Logs")
  ] satisfies ReturnType<Route.MetaFunction>;
}

const SOURCE_OPTIONS: MultiSelectOption[] = HTTP_LOG_SOURCES.map((source) => ({
  value: source,
  label: HTTP_LOG_SOURCE_LABELS[source]
}));

function getFiltersFromSearch(
  search: ReturnType<typeof httpLogSearchSchema.parse>
) {
  return {
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
}

export async function clientLoader({ request }: Route.ClientLoaderArgs) {
  const queryClient = getQueryClient();

  const searchParams = new URL(request.url).searchParams;
  const search = httpLogSearchSchema.parse(searchParams);
  const filters = getFiltersFromSearch(search);
  const source = searchParams.getAll("source");

  const [httpLogs, httpLog] = await Promise.all([
    queryClient.ensureInfiniteQueryData(
      proxyHttpLogQueries.list({
        filters,
        source,
        queryClient
      })
    ),
    search.request_id
      ? queryClient.ensureQueryData(
          proxyHttpLogQueries.single(search.request_id)
        )
      : undefined
  ] as const);
  return { httpLogs, httpLog };
}

export default function GlobalHttpLogsPage({
  loaderData
}: Route.ComponentProps) {
  const queryClient = useQueryClient();
  const [searchParams, setSearchParams] = useSearchParams();
  const search = httpLogSearchSchema.parse(searchParams);
  const [isAutoRefetchEnabled, setIsAutoRefetchEnabled] = React.useState(true);

  const filters = getFiltersFromSearch(search);
  const selectedSources = searchParams.getAll("source");

  const logsQuery = useInfiniteQuery({
    ...proxyHttpLogQueries.list({
      filters,
      source: selectedSources,
      queryClient,
      autoRefetchEnabled: isAutoRefetchEnabled
    }),
    initialData: loaderData.httpLogs
  });

  return (
    <section className="flex flex-col gap-4">
      <h2 className="text-2xl">Global HTTP logs</h2>
      <Separator />
      <h3 className="text-grey">See all http requests made to this server</h3>

      <HttpLogsLayout className="[&>#log-content]:mt-0">
        <HttpLogRequestDetails log={loaderData.httpLog} />

        <HttpLogFilterBar
          extraFilterParamKeys={["source"]}
          extraFilters={
            <MultiSelect
              label="source"
              options={SOURCE_OPTIONS}
              align="start"
              keepValuesCase
              value={selectedSources}
              onValueChange={(newSources) => {
                searchParams.delete("source");
                for (const source of newSources) {
                  searchParams.append("source", source);
                }
                setSearchParams(searchParams, { replace: true });
              }}
              className="w-auto"
            />
          }
          fieldValuesQuery={({ field, value }) =>
            proxyHttpLogQueries.filterHttpLogFields({ field, value })
          }
        />

        <HttpLogTable
          logsQuery={logsQuery}
          isAutoRefetchEnabled={isAutoRefetchEnabled}
          onAutoRefetchEnabledChange={setIsAutoRefetchEnabled}
          showSourceColumn
        />
      </HttpLogsLayout>
    </section>
  );
}
