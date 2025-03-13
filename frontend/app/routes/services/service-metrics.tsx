import { useQuery } from "@tanstack/react-query";

import {
  CpuIcon,
  DatabaseIcon,
  MicrochipIcon,
  NetworkIcon
} from "lucide-react";
import { Form, useSearchParams } from "react-router";
import { Area, AreaChart, CartesianGrid, XAxis, YAxis } from "recharts";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader
} from "~/components/ui/card";
import {
  ChartContainer,
  ChartLegend,
  ChartLegendContent,
  ChartTooltip,
  ChartTooltipContent
} from "~/components/ui/chart";
import { FieldSet, FieldSetSelect } from "~/components/ui/fieldset";
import {
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue
} from "~/components/ui/select";
import { metrisSearch, serviceQueries } from "~/lib/queries";
import { queryClient } from "~/root";
import {
  convertValueToBytes,
  formatStorageValue,
  timeAgoFormatter
} from "~/utils";
import type { Route } from "./+types/service-metrics";

export async function clientLoader({
  request,
  params: { projectSlug: project_slug, serviceSlug: service_slug }
}: Route.ClientLoaderArgs) {
  const searchParams = new URL(request.url).searchParams;
  const filters = metrisSearch.parse({
    time_range: searchParams.get("time_range")
  });

  const metrics = await queryClient.ensureQueryData(
    serviceQueries.metrics({
      project_slug,
      service_slug,
      filters
    })
  );

  return { metrics };
}

export default function ServiceMetricsPage({
  loaderData,
  matches: {
    "2": {
      data: { limits, service }
    }
  },
  params: { projectSlug: project_slug, serviceSlug: service_slug }
}: Route.ComponentProps) {
  const [searchParams, setSearchParams] = useSearchParams();
  const filters = metrisSearch.parse({
    time_range: searchParams.get("time_range")
  });
  const { data: metrics } = useQuery({
    ...serviceQueries.metrics({
      project_slug,
      service_slug,
      filters
    }),
    initialData: loaderData.metrics
  });

  return (
    <div className="flex flex-col gap-4 py-4">
      <Form className="inline-flex">
        <FieldSet name="type">
          <label htmlFor="healthcheck_type" className="sr-only">
            Time range
          </label>
          <FieldSetSelect
            name="time_range"
            defaultValue={filters.time_range}
            onValueChange={(value) => {
              searchParams.set("time_range", value);
              setSearchParams(searchParams);
            }}
          >
            <SelectTrigger id="healthcheck_type" className="w-40">
              <SelectValue placeholder="Select a time range" />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="LAST_HOUR">Last hour</SelectItem>
              <SelectItem value="LAST_6HOURS">Previous 6 hours</SelectItem>
              <SelectItem value="LAST_DAY">Previous 24 hours</SelectItem>
              <SelectItem value="LAST_WEEK">Previous 7 days</SelectItem>
              <SelectItem value="LAST_MONTH">Previous 30 days</SelectItem>
            </SelectContent>
          </FieldSetSelect>
        </FieldSet>
      </Form>

      <div className="grid lg:grid-cols-2 gap-12">
        <Card className="flex flex-col">
          <CardHeader className="border-b border-border py-3">
            <CardDescription className="text-card-foreground flex items-center gap-2">
              <CpuIcon size={15} />
              <span>cpu usage</span>
            </CardDescription>
          </CardHeader>
          <CardContent className="p-4 flex-1 min-h-40 md:min-h-80">
            {metrics.length === 0 ? (
              <div className="flex h-full w-full items-center justify-center text-grey">
                No data
              </div>
            ) : (
              <ChartContainer
                config={{
                  avg_cpu: {
                    label: "Average usage",
                    color: "var(--chart-1)"
                  }
                }}
              >
                <AreaChart
                  accessibilityLayer
                  data={metrics}
                  margin={{
                    left: 12,
                    right: 12
                  }}
                >
                  <CartesianGrid vertical={false} />
                  <YAxis
                    tickLine={false}
                    axisLine={false}
                    domain={[0, 100]}
                    allowDataOverflow
                    type="number"
                  />
                  <XAxis
                    dataKey="bucket_epoch"
                    tickLine={false}
                    axisLine={false}
                    tickFormatter={(value) =>
                      timeAgoFormatter(value, true).replace("ago", "")
                    }
                    type="category"
                    allowDuplicatedCategory={false}
                  />

                  <ChartTooltip
                    cursor={false}
                    content={
                      <ChartTooltipContent
                        hideLabel
                        className="min-w-fit"
                        formatter={(value, name, { payload }) => {
                          const formattedDate = new Intl.DateTimeFormat(
                            "en-GB",
                            {
                              month: "short",
                              day: "numeric",
                              hour: "2-digit",
                              minute: "2-digit",
                              second: "2-digit"
                            }
                          ).format(new Date(payload.bucket_epoch));

                          return (
                            <div className="flex items-start text-sm text-muted-foreground flex-col">
                              <span>{formattedDate}</span>
                              <div className="ml-auto flex items-baseline gap-0.5 font-mono font-medium tabular-nums text-card-foreground text-sm">
                                {Number(value).toFixed(2)}
                                <span className="font-normal text-grey">%</span>
                              </div>
                            </div>
                          );
                        }}
                      />
                    }
                  />

                  <Area
                    dataKey={"avg_cpu"}
                    type="step"
                    fill={`var(--color-avg_cpu)`}
                    fillOpacity={0.4}
                    isAnimationActive={false}
                    stroke={`var(--color-avg_cpu)`}
                  />
                </AreaChart>
              </ChartContainer>
            )}
          </CardContent>
        </Card>

        <Card className="flex flex-col">
          <CardHeader className="border-b border-border py-3">
            <CardDescription className="text-card-foreground flex items-center gap-2">
              <MicrochipIcon size={15} />
              <span>memory usage</span>
            </CardDescription>
          </CardHeader>
          <CardContent className="p-4 flex-1 min-h-40 md:min-h-80">
            {metrics.length === 0 ? (
              <div className="flex h-full w-full items-center justify-center text-grey">
                No data
              </div>
            ) : (
              <ChartContainer
                config={{
                  avg_memory: {
                    label: "Average usage",
                    color: "var(--chart-2)"
                  }
                }}
              >
                <AreaChart
                  accessibilityLayer
                  data={metrics}
                  margin={{
                    left: 12,
                    right: 12
                  }}
                >
                  <CartesianGrid vertical={false} />
                  <YAxis
                    tickLine={false}
                    axisLine={false}
                    domain={[
                      0,
                      convertValueToBytes(
                        service.resource_limits?.memory?.value ??
                          limits.max_memory_in_bytes,
                        service.resource_limits?.memory?.unit
                      )
                    ]}
                    tickFormatter={(value) => {
                      const { value: value_str, unit } = formatStorageValue(
                        Number(value)
                      );
                      // `\u00A0` is a `non breaking space` aka `&nbsp;` TIL !
                      return value_str === "0"
                        ? "0"
                        : `${value_str}\u00A0${unit}`;
                    }}
                    type="number"
                    allowDataOverflow
                  />
                  <XAxis
                    dataKey="bucket_epoch"
                    tickLine={false}
                    axisLine={false}
                    tickCount={10}
                    tickFormatter={(value) =>
                      timeAgoFormatter(value, true).replace("ago", "")
                    }
                  />

                  <ChartTooltip
                    cursor={false}
                    content={
                      <ChartTooltipContent
                        hideLabel
                        className="min-w-fit"
                        formatter={(value, name, { payload }) => {
                          const formattedDate = new Intl.DateTimeFormat(
                            "en-GB",
                            {
                              month: "short",
                              day: "numeric",
                              hour: "2-digit",
                              minute: "2-digit",
                              second: "2-digit"
                            }
                          ).format(new Date(payload.bucket_epoch));
                          const { value: value_str, unit } = formatStorageValue(
                            Number(value)
                          );

                          return (
                            <div className="flex items-start text-sm text-muted-foreground flex-col">
                              <span>{formattedDate}</span>
                              <div className="ml-auto flex items-baseline gap-0.5 font-mono font-medium tabular-nums text-card-foreground text-sm">
                                {value_str}
                                <span className="font-normal text-grey">
                                  {unit}
                                </span>
                              </div>
                            </div>
                          );
                        }}
                      />
                    }
                  />

                  <Area
                    dataKey={"avg_memory"}
                    type="step"
                    fill={`var(--color-avg_memory)`}
                    fillOpacity={0.4}
                    isAnimationActive={false}
                    stroke={`var(--color-avg_memory)`}
                  />
                </AreaChart>
              </ChartContainer>
            )}
          </CardContent>
        </Card>

        <Card className="flex flex-col">
          <CardHeader className="border-b border-border py-3">
            <CardDescription className="text-card-foreground flex items-center gap-2">
              <NetworkIcon size={15} />
              <span>network I/O</span>
            </CardDescription>
          </CardHeader>
          <CardContent className="p-4 flex-1 min-h-40 md:min-h-80">
            {metrics.length === 0 ? (
              <div className="flex h-full w-full items-center justify-center text-grey">
                No data
              </div>
            ) : (
              <ChartContainer
                config={{
                  total_net_rx: {
                    label: "Inbound",
                    color: "var(--chart-4)"
                  },
                  total_net_tx: {
                    label: "Outbound",
                    color: "var(--chart-3)"
                  }
                }}
              >
                <AreaChart
                  accessibilityLayer
                  data={metrics}
                  margin={{
                    left: 12,
                    right: 12
                  }}
                >
                  <CartesianGrid vertical={false} />
                  <YAxis
                    tickLine={false}
                    axisLine={false}
                    domain={[
                      0,
                      Math.max(
                        ...metrics
                          .map((m) => [m.total_net_rx, m.total_net_tx])
                          .flat()
                      ) + convertValueToBytes(10, "MEGABYTES")
                    ]}
                    tickFormatter={(value) => {
                      const { value: value_str, unit } = formatStorageValue(
                        Number(value)
                      );
                      // `\u00A0` is a `non breaking space` aka `&nbsp;` TIL !
                      return value_str === "0"
                        ? "0"
                        : `${value_str}\u00A0${unit}`;
                    }}
                    type="number"
                    allowDataOverflow
                  />
                  <XAxis
                    dataKey="bucket_epoch"
                    tickLine={false}
                    axisLine={false}
                    tickCount={10}
                    tickFormatter={(value) =>
                      timeAgoFormatter(value, true).replace("ago", "")
                    }
                  />

                  <ChartTooltip
                    cursor={false}
                    content={
                      <ChartTooltipContent
                        hideLabel
                        className="min-w-fit"
                        formatter={(value, name, item, index) => {
                          const formattedDate = new Intl.DateTimeFormat(
                            "en-GB",
                            {
                              month: "short",
                              day: "numeric",
                              hour: "2-digit",
                              minute: "2-digit",
                              second: "2-digit"
                            }
                          ).format(new Date(item.payload.bucket_epoch));
                          const { value: value_str, unit } = formatStorageValue(
                            Number(value)
                          );

                          return (
                            <div className="flex items-start text-sm text-muted-foreground flex-col w-full">
                              {index === 0 && <span>{formattedDate}</span>}

                              <div className="ml-auto flex items-baseline justify-end gap-1 self-stretch w-full font-mono font-medium tabular-nums text-card-foreground text-sm">
                                <div className="flex gap-0.5">
                                  <span>{value_str}</span>
                                  <span className="font-normal text-grey">
                                    {unit}
                                  </span>
                                </div>
                                <div
                                  className="h-2.5 w-2.5 flex-none rounded-[2px] bg-[var(--color-bg)]"
                                  style={
                                    {
                                      "--color-bg": `var(--color-${name})`
                                    } as React.CSSProperties
                                  }
                                />
                              </div>
                            </div>
                          );
                        }}
                      />
                    }
                  />
                  <ChartLegend content={<ChartLegendContent />} />

                  <Area
                    dataKey={"total_net_tx"}
                    type="step"
                    fill={`var(--color-total_net_tx)`}
                    fillOpacity={0.4}
                    isAnimationActive={false}
                    stroke={`var(--color-total_net_tx)`}
                  />
                  <Area
                    dataKey={"total_net_rx"}
                    type="step"
                    fill={`var(--color-total_net_rx)`}
                    fillOpacity={0.4}
                    isAnimationActive={false}
                    stroke={`var(--color-total_net_rx)`}
                  />
                </AreaChart>
              </ChartContainer>
            )}
          </CardContent>
        </Card>

        <Card className="flex flex-col">
          <CardHeader className="border-b border-border py-3">
            <CardDescription className="text-card-foreground flex items-center gap-2">
              <DatabaseIcon size={15} />
              <span>disk I/O</span>
            </CardDescription>
          </CardHeader>
          <CardContent className="p-4 flex-1 min-h-40 md:min-h-80">
            {metrics.length === 0 ? (
              <div className="flex h-full w-full items-center justify-center text-grey">
                No data
              </div>
            ) : (
              <ChartContainer
                config={{
                  total_disk_read: {
                    label: "Reads",
                    color: "var(--chart-1)"
                  },
                  total_disk_write: {
                    label: "Writes",
                    color: "var(--chart-5)"
                  }
                }}
              >
                <AreaChart
                  accessibilityLayer
                  data={metrics}
                  margin={{
                    left: 12,
                    right: 12
                  }}
                >
                  <CartesianGrid vertical={false} />
                  <YAxis
                    tickLine={false}
                    axisLine={false}
                    domain={[
                      0,
                      Math.max(
                        ...metrics
                          .map((m) => [m.total_disk_write, m.total_disk_read])
                          .flat()
                      ) + convertValueToBytes(10, "MEGABYTES")
                    ]}
                    tickFormatter={(value) => {
                      const { value: value_str, unit } = formatStorageValue(
                        Number(value)
                      );
                      // `\u00A0` is a `non breaking space` aka `&nbsp;` TIL !
                      return value_str === "0"
                        ? "0"
                        : `${value_str}\u00A0${unit}`;
                    }}
                    type="number"
                    allowDataOverflow
                  />
                  <XAxis
                    dataKey="bucket_epoch"
                    tickLine={false}
                    axisLine={false}
                    tickCount={10}
                    tickFormatter={(value) =>
                      timeAgoFormatter(value, true).replace("ago", "")
                    }
                  />

                  <ChartTooltip
                    cursor={false}
                    content={
                      <ChartTooltipContent
                        hideLabel
                        className="min-w-fit"
                        formatter={(value, name, item, index) => {
                          const formattedDate = new Intl.DateTimeFormat(
                            "en-GB",
                            {
                              month: "short",
                              day: "numeric",
                              hour: "2-digit",
                              minute: "2-digit",
                              second: "2-digit"
                            }
                          ).format(new Date(item.payload.bucket_epoch));
                          const { value: value_str, unit } = formatStorageValue(
                            Number(value)
                          );

                          return (
                            <div className="flex items-start text-sm text-muted-foreground flex-col w-full">
                              {index === 0 && <span>{formattedDate}</span>}

                              <div className="ml-auto flex items-baseline justify-end gap-1 self-stretch w-full font-mono font-medium tabular-nums text-card-foreground text-sm">
                                <div className="flex gap-0.5">
                                  <span>{value_str}</span>
                                  <span className="font-normal text-grey">
                                    {unit}
                                  </span>
                                </div>
                                <div
                                  className="h-2.5 w-2.5 flex-none rounded-[2px] bg-[var(--color-bg)]"
                                  style={
                                    {
                                      "--color-bg": `var(--color-${name})`
                                    } as React.CSSProperties
                                  }
                                />
                              </div>
                            </div>
                          );
                        }}
                      />
                    }
                  />
                  <ChartLegend content={<ChartLegendContent />} />

                  <Area
                    dataKey={"total_disk_read"}
                    type="step"
                    fill={`var(--color-total_disk_read)`}
                    fillOpacity={0.4}
                    isAnimationActive={false}
                    stroke={`var(--color-total_disk_read)`}
                  />
                  <Area
                    dataKey={"total_disk_write"}
                    type="step"
                    fill={`var(--color-total_disk_write)`}
                    fillOpacity={0.4}
                    isAnimationActive={false}
                    stroke={`var(--color-total_disk_write)`}
                  />
                </AreaChart>
              </ChartContainer>
            )}
          </CardContent>
        </Card>
      </div>
    </div>
  );
}
