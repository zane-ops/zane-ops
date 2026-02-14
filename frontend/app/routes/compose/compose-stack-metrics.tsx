import { useQuery } from "@tanstack/react-query";
import {
  CpuIcon,
  DatabaseIcon,
  MicrochipIcon,
  NetworkIcon
} from "lucide-react";
import { Form, useSearchParams } from "react-router";
import { Area, AreaChart, CartesianGrid, XAxis, YAxis } from "recharts";
import { MultiSelect } from "~/components/multi-select";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader
} from "~/components/ui/card";
import {
  type ChartConfig,
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
import {
  composeStackQueries,
  serverQueries,
  stackMetrisSearch
} from "~/lib/queries";
import { queryClient } from "~/root";
import {
  formatStorageValue,
  getMaxDomainForStorageValue,
  timeAgoFormatter
} from "~/utils";
import type { Route } from "./+types/compose-stack-metrics";

export async function clientLoader({
  request,
  params
}: Route.ClientLoaderArgs) {
  const searchParams = new URL(request.url).searchParams;
  const filters = stackMetrisSearch.parse({
    time_range: searchParams.get("time_range"),
    service_names: searchParams.getAll("service_names")
  });

  const [metrics, limits] = await Promise.all([
    queryClient.ensureQueryData(
      composeStackQueries.metrics({
        project_slug: params.projectSlug,
        stack_slug: params.composeStackSlug,
        env_slug: params.envSlug,
        filters
      })
    ),
    queryClient.ensureQueryData(serverQueries.resourceLimits)
  ]);

  return { metrics, limits };
}

export default function ComposeStackMetricsPage({
  loaderData,
  params,
  matches: {
    "2": {
      loaderData: { stack }
    }
  }
}: Route.ComponentProps) {
  const [searchParams, setSearchParams] = useSearchParams();
  const filters = stackMetrisSearch.parse({
    time_range: searchParams.get("time_range"),
    service_names: searchParams.getAll("service_names")
  });
  const { data } = useQuery({
    ...composeStackQueries.metrics({
      project_slug: params.projectSlug,
      stack_slug: params.composeStackSlug,
      env_slug: params.envSlug,
      filters
    }),
    initialData: loaderData.metrics
  });

  const allServiceNames = Object.keys(stack.services);

  /**
   * Metrics is flattened as an array of object with
   * each object being: { bucket: '...', service_1: value, service_2: value, ... }
   */
  const metrics: Record<
    Exclude<keyof (typeof data)[number], "bucket_epoch" | "service_name">,
    Array<Record<string, string | number>>
  > = {
    avg_cpu: [],
    avg_memory: [],
    total_disk_read: [],
    total_disk_write: [],
    total_net_rx: [],
    total_net_tx: []
  };
  const selectedServices =
    filters.service_names.length === 0
      ? allServiceNames
      : filters.service_names;

  const unique_values_by_bucket_epoch: Record<
    string,
    Record<keyof typeof metrics, Record<string, number>>
  > = {};

  let maxCPU = 0;
  let maxMemory = 0;
  let maxNetRx = 0;
  let maxNetTx = 0;
  let maxDiskRead = 0;
  let maxDiskWrite = 0;

  for (const datum of data) {
    if (!unique_values_by_bucket_epoch[datum.bucket_epoch]) {
      unique_values_by_bucket_epoch[datum.bucket_epoch] = {
        avg_cpu: {},
        avg_memory: {},
        total_disk_read: {},
        total_disk_write: {},
        total_net_rx: {},
        total_net_tx: {}
      };

      // all the values for all the buckets should be filled for all services otherwise, the chart won't render
      // that's why we fill the values with 0 by default, this will be overriden by the actual values
      // if they are available
      for (const svc of selectedServices) {
        unique_values_by_bucket_epoch[datum.bucket_epoch]["avg_cpu"][svc] = 0;
        unique_values_by_bucket_epoch[datum.bucket_epoch]["avg_memory"][svc] =
          0;
        unique_values_by_bucket_epoch[datum.bucket_epoch]["total_disk_read"][
          svc
        ] = 0;
        unique_values_by_bucket_epoch[datum.bucket_epoch]["total_disk_write"][
          svc
        ] = 0;
        unique_values_by_bucket_epoch[datum.bucket_epoch]["total_net_rx"][svc] =
          0;
        unique_values_by_bucket_epoch[datum.bucket_epoch]["total_net_tx"][svc] =
          0;
      }
    }

    /******************
     *      CPU       *
     ******************/
    // avg_cpu is the average CPU in percent accross all cpus
    // we need to calculate how much CPUs it makes compared to the total number of CPUS:
    // 100% => limit
    // avg_cpu (in percent %) => x
    // x = (limit * avg) / 100
    // Here is the formula to get back the percent based on the value of number of CPUs:
    // this is used in the <ChartToolip /> below
    // 100/avg = limit/x
    // avg/100 = x/limit
    // avg = (x*100)/limit
    const avg_cpu = (loaderData.limits.no_of_cpus * datum.avg_cpu) / 100;
    unique_values_by_bucket_epoch[datum.bucket_epoch]["avg_cpu"][
      datum.service_name
    ] = avg_cpu;

    /******************
     *     Memory     *
     ******************/

    unique_values_by_bucket_epoch[datum.bucket_epoch]["avg_memory"][
      datum.service_name
    ] = datum.avg_memory;

    /******************
     *    Network     *
     ******************/
    unique_values_by_bucket_epoch[datum.bucket_epoch]["total_net_rx"][
      datum.service_name
    ] = datum.total_net_rx;
    unique_values_by_bucket_epoch[datum.bucket_epoch]["total_net_tx"][
      datum.service_name
    ] = datum.total_net_tx;

    /******************
     *    Storage     *
     ******************/
    unique_values_by_bucket_epoch[datum.bucket_epoch]["total_disk_read"][
      datum.service_name
    ] = datum.total_disk_read;
    unique_values_by_bucket_epoch[datum.bucket_epoch]["total_disk_write"][
      datum.service_name
    ] = datum.total_disk_write;

    /******************
     *   Max values   *
     ******************/
    maxCPU = Math.max(avg_cpu, maxCPU);
    maxMemory = Math.max(datum.avg_memory, maxMemory);
    maxNetRx = Math.max(datum.total_net_rx, maxNetRx);
    maxNetTx = Math.max(datum.total_net_tx, maxNetTx);
    maxDiskRead = Math.max(datum.total_disk_read, maxDiskRead);
    maxDiskWrite = Math.max(datum.total_disk_write, maxDiskWrite);
  }

  const chartConfig: ChartConfig = {};

  const colors = [
    `--chart-1`,
    `--chart-2`,
    `--chart-3`,
    `--chart-4`,
    `--chart-5`,
    `--chart-6`,
    `--chart-7`,
    `--chart-8`
  ];
  for (let i = 0; i < allServiceNames.length; i++) {
    const service = allServiceNames[i];
    chartConfig[service] = {
      color: `var(${colors[i % 8]})`,
      label: service
    };
  }

  for (const bucket_epoch in unique_values_by_bucket_epoch) {
    metrics["avg_cpu"].push({
      bucket_epoch: bucket_epoch,
      ...unique_values_by_bucket_epoch[bucket_epoch]["avg_cpu"]
    });
    metrics["avg_memory"].push({
      bucket_epoch: bucket_epoch,
      ...unique_values_by_bucket_epoch[bucket_epoch]["avg_memory"]
    });
    metrics["total_net_rx"].push({
      bucket_epoch: bucket_epoch,
      ...unique_values_by_bucket_epoch[bucket_epoch]["total_net_rx"]
    });
    metrics["total_net_tx"].push({
      bucket_epoch: bucket_epoch,
      ...unique_values_by_bucket_epoch[bucket_epoch]["total_net_tx"]
    });
    metrics["total_disk_read"].push({
      bucket_epoch: bucket_epoch,
      ...unique_values_by_bucket_epoch[bucket_epoch]["total_disk_read"]
    });
    metrics["total_disk_write"].push({
      bucket_epoch: bucket_epoch,
      ...unique_values_by_bucket_epoch[bucket_epoch]["total_disk_write"]
    });
  }

  return (
    <div className="flex flex-col gap-4 py-4">
      <Form className="flex items-center gap-4">
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
        <MultiSelect
          label="services"
          className="inline-flex w-auto border-border border-solid"
          options={allServiceNames}
          align="start"
          value={filters.service_names}
          onValueChange={(newServices) => {
            searchParams.delete("service_names");

            for (const svc of newServices) {
              searchParams.append("service_names", svc);
            }
            setSearchParams(searchParams);
          }}
        />
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
            {metrics["avg_cpu"].length === 0 ? (
              <div className="flex h-full w-full items-center justify-center text-grey">
                No data
              </div>
            ) : (
              <ChartContainer config={chartConfig}>
                <AreaChart
                  accessibilityLayer
                  data={metrics["avg_cpu"]}
                  margin={{
                    left: 12,
                    right: 12
                  }}
                >
                  <CartesianGrid vertical={false} />
                  <YAxis
                    tickLine={false}
                    axisLine={false}
                    domain={[0, loaderData.limits.no_of_cpus]}
                    allowDataOverflow
                    type="number"
                    tickFormatter={(value) => {
                      const fmt = Intl.NumberFormat("en-GB", {
                        maximumFractionDigits: 2
                      });
                      return fmt.format(value as number);
                    }}
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

                  <ChartLegend content={<ChartLegendContent />} />
                  <ChartTooltip
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

                          const value_str = Intl.NumberFormat("en-GB", {
                            maximumFractionDigits: 4
                          }).format(Number(value));

                          // formula used here
                          const percent =
                            (Number(value) * 100) /
                            loaderData.limits.no_of_cpus;
                          const value_percent = Intl.NumberFormat("en-GB", {
                            maximumFractionDigits: 2
                          }).format(percent);

                          return (
                            <div className="flex items-start text-sm text-muted-foreground flex-col w-full">
                              {index === 0 && <span>{formattedDate}</span>}

                              <div className="ml-auto flex items-baseline justify-between gap-4 self-stretch w-full font-mono font-medium tabular-nums text-card-foreground text-sm">
                                <div className="flex items-center gap-1">
                                  <div
                                    className="h-2.5 w-2.5 flex-none rounded-[2px] bg-[var(--color-bg)]"
                                    style={
                                      {
                                        "--color-bg": `var(--color-${name})`
                                      } as React.CSSProperties
                                    }
                                  />
                                  <span className="text-grey">{name}</span>
                                </div>
                                <div className="flex gap-0.5">
                                  <span>{value_str}</span>
                                  <span className="text-foreground">CPUs</span>
                                  <span className="font-normal text-grey">
                                    ({value_percent}%)
                                  </span>
                                </div>
                              </div>
                            </div>
                          );
                        }}
                      />
                    }
                  />

                  {selectedServices.map((svc) => (
                    <Area
                      dataKey={svc}
                      key={svc}
                      type="step"
                      fill={`var(--color-${svc})`}
                      fillOpacity={0.4}
                      isAnimationActive={false}
                      stroke={`var(--color-${svc})`}
                    />
                  ))}
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
            {metrics["avg_memory"].length === 0 ? (
              <div className="flex h-full w-full items-center justify-center text-grey">
                No data
              </div>
            ) : (
              <ChartContainer config={chartConfig}>
                <AreaChart
                  accessibilityLayer
                  data={metrics["avg_memory"]}
                  margin={{
                    left: 12,
                    right: 12
                  }}
                >
                  <CartesianGrid vertical={false} />
                  <YAxis
                    tickLine={false}
                    axisLine={false}
                    domain={[0, loaderData.limits.max_memory_in_bytes]}
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

                  <ChartLegend content={<ChartLegendContent />} />
                  <ChartTooltip
                    cursor={false}
                    content={
                      <ChartTooltipContent
                        hideLabel
                        className="min-w-fit"
                        formatter={(value, name, { payload }, index) => {
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
                            <div className="flex items-start w-full text-sm text-muted-foreground flex-col">
                              {index === 0 && <span>{formattedDate}</span>}
                              <div className="ml-auto flex justify-between self-stretch w-full items-baseline gap-4 font-mono font-medium tabular-nums text-card-foreground text-sm">
                                <div className="flex items-center gap-1">
                                  <div
                                    className="h-2.5 w-2.5 flex-none rounded-[2px] bg-[var(--color-bg)]"
                                    style={
                                      {
                                        "--color-bg": `var(--color-${name})`
                                      } as React.CSSProperties
                                    }
                                  />
                                  <span className="text-grey">{name}</span>
                                </div>
                                <div className="flex gap-0.5 items-baseline">
                                  <span>{value_str}</span>
                                  <span className="font-normal text-grey">
                                    {unit}
                                  </span>
                                </div>
                              </div>
                            </div>
                          );
                        }}
                      />
                    }
                  />

                  {selectedServices.map((svc) => (
                    <Area
                      dataKey={svc}
                      type="step"
                      fill={`var(--color-${svc})`}
                      fillOpacity={0.4}
                      isAnimationActive={false}
                      stroke={`var(--color-${svc})`}
                    />
                  ))}
                </AreaChart>
              </ChartContainer>
            )}
          </CardContent>
        </Card>

        <Card className="flex flex-col">
          <CardHeader className="border-b border-border py-3">
            <CardDescription className="text-card-foreground flex items-center gap-2">
              <NetworkIcon size={15} />
              <span>network Inbound</span>
            </CardDescription>
          </CardHeader>
          <CardContent className="p-4 flex-1 min-h-40 md:min-h-80">
            {metrics["total_net_rx"].length === 0 ? (
              <div className="flex h-full w-full items-center justify-center text-grey">
                No data
              </div>
            ) : (
              <ChartContainer config={chartConfig}>
                <AreaChart
                  accessibilityLayer
                  data={metrics["total_net_rx"]}
                  margin={{
                    left: 12,
                    right: 12
                  }}
                >
                  <CartesianGrid vertical={false} />
                  <YAxis
                    tickLine={false}
                    axisLine={false}
                    domain={[0, getMaxDomainForStorageValue(maxNetRx)]}
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

                  <ChartLegend content={<ChartLegendContent />} />
                  <ChartTooltip
                    cursor={false}
                    content={
                      <ChartTooltipContent
                        hideLabel
                        className="min-w-fit"
                        formatter={(value, name, { payload }, index) => {
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
                            <div className="flex items-start w-full text-sm text-muted-foreground flex-col">
                              {index === 0 && <span>{formattedDate}</span>}
                              <div className="ml-auto flex justify-between self-stretch w-full items-baseline gap-4 font-mono font-medium tabular-nums text-card-foreground text-sm">
                                <div className="flex items-center gap-1">
                                  <div
                                    className="h-2.5 w-2.5 flex-none rounded-[2px] bg-[var(--color-bg)]"
                                    style={
                                      {
                                        "--color-bg": `var(--color-${name})`
                                      } as React.CSSProperties
                                    }
                                  />
                                  <span className="text-grey">{name}</span>
                                </div>
                                <div className="flex gap-0.5 items-baseline">
                                  <span>{value_str}</span>
                                  <span className="font-normal text-grey">
                                    {unit}
                                  </span>
                                </div>
                              </div>
                            </div>
                          );
                        }}
                      />
                    }
                  />

                  {selectedServices.map((svc) => (
                    <Area
                      dataKey={svc}
                      type="step"
                      fill={`var(--color-${svc})`}
                      fillOpacity={0.4}
                      isAnimationActive={false}
                      stroke={`var(--color-${svc})`}
                    />
                  ))}
                </AreaChart>
              </ChartContainer>
            )}
          </CardContent>
        </Card>

        <Card className="flex flex-col">
          <CardHeader className="border-b border-border py-3">
            <CardDescription className="text-card-foreground flex items-center gap-2">
              <NetworkIcon size={15} />
              <span>network Outbound</span>
            </CardDescription>
          </CardHeader>
          <CardContent className="p-4 flex-1 min-h-40 md:min-h-80">
            {metrics["total_net_tx"].length === 0 ? (
              <div className="flex h-full w-full items-center justify-center text-grey">
                No data
              </div>
            ) : (
              <ChartContainer config={chartConfig}>
                <AreaChart
                  accessibilityLayer
                  data={metrics["total_net_tx"]}
                  margin={{
                    left: 12,
                    right: 12
                  }}
                >
                  <CartesianGrid vertical={false} />
                  <YAxis
                    tickLine={false}
                    axisLine={false}
                    domain={[0, getMaxDomainForStorageValue(maxNetTx)]}
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

                  <ChartLegend content={<ChartLegendContent />} />
                  <ChartTooltip
                    cursor={false}
                    content={
                      <ChartTooltipContent
                        hideLabel
                        className="min-w-fit"
                        formatter={(value, name, { payload }, index) => {
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
                            <div className="flex items-start w-full text-sm text-muted-foreground flex-col">
                              {index === 0 && <span>{formattedDate}</span>}
                              <div className="ml-auto flex justify-between self-stretch w-full items-baseline gap-4 font-mono font-medium tabular-nums text-card-foreground text-sm">
                                <div className="flex items-center gap-1">
                                  <div
                                    className="h-2.5 w-2.5 flex-none rounded-[2px] bg-[var(--color-bg)]"
                                    style={
                                      {
                                        "--color-bg": `var(--color-${name})`
                                      } as React.CSSProperties
                                    }
                                  />
                                  <span className="text-grey">{name}</span>
                                </div>
                                <div className="flex gap-0.5 items-baseline">
                                  <span>{value_str}</span>
                                  <span className="font-normal text-grey">
                                    {unit}
                                  </span>
                                </div>
                              </div>
                            </div>
                          );
                        }}
                      />
                    }
                  />

                  {selectedServices.map((svc) => (
                    <Area
                      dataKey={svc}
                      type="step"
                      fill={`var(--color-${svc})`}
                      fillOpacity={0.4}
                      isAnimationActive={false}
                      stroke={`var(--color-${svc})`}
                    />
                  ))}
                </AreaChart>
              </ChartContainer>
            )}
          </CardContent>
        </Card>

        <Card className="flex flex-col">
          <CardHeader className="border-b border-border py-3">
            <CardDescription className="text-card-foreground flex items-center gap-2">
              <DatabaseIcon size={15} />
              <span>Disk Read</span>
            </CardDescription>
          </CardHeader>
          <CardContent className="p-4 flex-1 min-h-40 md:min-h-80">
            {metrics["total_disk_read"].length === 0 ? (
              <div className="flex h-full w-full items-center justify-center text-grey">
                No data
              </div>
            ) : (
              <ChartContainer config={chartConfig}>
                <AreaChart
                  accessibilityLayer
                  data={metrics["total_disk_read"]}
                  margin={{
                    left: 12,
                    right: 12
                  }}
                >
                  <CartesianGrid vertical={false} />
                  <YAxis
                    tickLine={false}
                    axisLine={false}
                    domain={[0, getMaxDomainForStorageValue(maxDiskRead)]}
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

                  <ChartLegend content={<ChartLegendContent />} />
                  <ChartTooltip
                    cursor={false}
                    content={
                      <ChartTooltipContent
                        hideLabel
                        className="min-w-fit"
                        formatter={(value, name, { payload }, index) => {
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
                            <div className="flex items-start w-full text-sm text-muted-foreground flex-col">
                              {index === 0 && <span>{formattedDate}</span>}
                              <div className="ml-auto flex justify-between self-stretch w-full items-baseline gap-4 font-mono font-medium tabular-nums text-card-foreground text-sm">
                                <div className="flex items-center gap-1">
                                  <div
                                    className="h-2.5 w-2.5 flex-none rounded-[2px] bg-[var(--color-bg)]"
                                    style={
                                      {
                                        "--color-bg": `var(--color-${name})`
                                      } as React.CSSProperties
                                    }
                                  />
                                  <span className="text-grey">{name}</span>
                                </div>
                                <div className="flex gap-0.5 items-baseline">
                                  <span>{value_str}</span>
                                  <span className="font-normal text-grey">
                                    {unit}
                                  </span>
                                </div>
                              </div>
                            </div>
                          );
                        }}
                      />
                    }
                  />

                  {selectedServices.map((svc) => (
                    <Area
                      dataKey={svc}
                      type="step"
                      fill={`var(--color-${svc})`}
                      fillOpacity={0.4}
                      isAnimationActive={false}
                      stroke={`var(--color-${svc})`}
                    />
                  ))}
                </AreaChart>
              </ChartContainer>
            )}
          </CardContent>
        </Card>

        <Card className="flex flex-col">
          <CardHeader className="border-b border-border py-3">
            <CardDescription className="text-card-foreground flex items-center gap-2">
              <DatabaseIcon size={15} />
              <span>Disk Writes</span>
            </CardDescription>
          </CardHeader>
          <CardContent className="p-4 flex-1 min-h-40 md:min-h-80">
            {metrics["total_disk_write"].length === 0 ? (
              <div className="flex h-full w-full items-center justify-center text-grey">
                No data
              </div>
            ) : (
              <ChartContainer config={chartConfig}>
                <AreaChart
                  accessibilityLayer
                  data={metrics["total_disk_write"]}
                  margin={{
                    left: 12,
                    right: 12
                  }}
                >
                  <CartesianGrid vertical={false} />
                  <YAxis
                    tickLine={false}
                    axisLine={false}
                    domain={[0, getMaxDomainForStorageValue(maxDiskWrite)]}
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

                  <ChartLegend content={<ChartLegendContent />} />
                  <ChartTooltip
                    cursor={false}
                    content={
                      <ChartTooltipContent
                        hideLabel
                        className="min-w-fit"
                        formatter={(value, name, { payload }, index) => {
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
                            <div className="flex items-start w-full text-sm text-muted-foreground flex-col">
                              {index === 0 && <span>{formattedDate}</span>}
                              <div className="ml-auto flex justify-between self-stretch w-full items-baseline gap-4 font-mono font-medium tabular-nums text-card-foreground text-sm">
                                <div className="flex items-center gap-1">
                                  <div
                                    className="h-2.5 w-2.5 flex-none rounded-[2px] bg-[var(--color-bg)]"
                                    style={
                                      {
                                        "--color-bg": `var(--color-${name})`
                                      } as React.CSSProperties
                                    }
                                  />
                                  <span className="text-grey">{name}</span>
                                </div>
                                <div className="flex gap-0.5 items-baseline">
                                  <span>{value_str}</span>
                                  <span className="font-normal text-grey">
                                    {unit}
                                  </span>
                                </div>
                              </div>
                            </div>
                          );
                        }}
                      />
                    }
                  />

                  {selectedServices.map((svc) => (
                    <Area
                      dataKey={svc}
                      type="step"
                      fill={`var(--color-${svc})`}
                      fillOpacity={0.4}
                      isAnimationActive={false}
                      stroke={`var(--color-${svc})`}
                    />
                  ))}
                </AreaChart>
              </ChartContainer>
            )}
          </CardContent>
        </Card>
      </div>
    </div>
  );
}
