import { useQuery } from "@tanstack/react-query";
import {
  BanIcon,
  ClockArrowUpIcon,
  FastForwardIcon,
  GlobeIcon,
  HeartPulseIcon,
  HistoryIcon,
  HourglassIcon,
  InfoIcon,
  LoaderIcon,
  LogsIcon,
  PauseIcon,
  RefreshCwOffIcon,
  RocketIcon,
  RotateCcwIcon,
  Trash2Icon,
  TriangleAlertIcon,
  XIcon
} from "lucide-react";
import { Link, Outlet, useLocation, useNavigate } from "react-router";
import type { StatusBadgeColor } from "~/components/status-badge";
import {
  Breadcrumb,
  BreadcrumbItem,
  BreadcrumbLink,
  BreadcrumbList,
  BreadcrumbPage,
  BreadcrumbSeparator
} from "~/components/ui/breadcrumb";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "~/components/ui/tabs";
import type { DEPLOYMENT_STATUSES } from "~/lib/constants";
import { deploymentQueries } from "~/lib/queries";
import type { ValueOf } from "~/lib/types";
import { cn, isNotFoundError, notFound } from "~/lib/utils";
import { queryClient } from "~/root";
import { capitalizeText, formatURL, formattedTime, metaTitle } from "~/utils";
import { type Route } from "./+types/deployment-layout";

export function meta({ params, error }: Route.MetaArgs) {
  const title = !error
    ? `${params.serviceSlug} / ${params.deploymentHash}`
    : isNotFoundError(error)
      ? "Error 404 - Deployment does not exist"
      : "Oops";
  return [metaTitle(title)] satisfies ReturnType<Route.MetaFunction>;
}

export async function clientLoader({ params }: Route.ClientLoaderArgs) {
  let deployment = await queryClient.ensureQueryData(
    deploymentQueries.single({
      project_slug: params.projectSlug,
      service_slug: params.serviceSlug,
      deployment_hash: params.deploymentHash
    })
  );

  if (!deployment) {
    throw notFound();
  }

  return { deployment };
}

const TABS = {
  LOGS: "logs",
  HTTP_LOGS: "http-logs",
  DETAILS: "details"
} as const;

export default function DeploymentLayoutPage({
  loaderData,
  params: {
    projectSlug: project_slug,
    serviceSlug: service_slug,
    deploymentHash: deployment_hash
  }
}: Route.ComponentProps) {
  const location = useLocation();
  const navigate = useNavigate();

  const { data: deployment } = useQuery({
    ...deploymentQueries.single({
      project_slug,
      service_slug,
      deployment_hash
    }),
    initialData: loaderData.deployment
  });

  let currentSelectedTab: ValueOf<typeof TABS> = TABS.LOGS;
  if (location.pathname.match(/http\-logs\/?$/)) {
    currentSelectedTab = TABS.HTTP_LOGS;
  } else if (location.pathname.match(/details\/?$/)) {
    currentSelectedTab = TABS.DETAILS;
  }

  return (
    <>
      <Breadcrumb>
        <BreadcrumbList className="text-sm">
          <BreadcrumbItem>
            <BreadcrumbLink asChild>
              <Link to="/">Projects</Link>
            </BreadcrumbLink>
          </BreadcrumbItem>
          <BreadcrumbSeparator />
          <BreadcrumbItem>
            <BreadcrumbLink asChild>
              <Link to={`/project/${project_slug}/`}>{project_slug}</Link>
            </BreadcrumbLink>
          </BreadcrumbItem>

          <BreadcrumbSeparator />
          <BreadcrumbItem>
            <Link to={`/project/${project_slug}/services/${service_slug}`}>
              {service_slug}
            </Link>
          </BreadcrumbItem>

          <BreadcrumbSeparator />
          <BreadcrumbItem>
            <BreadcrumbPage>{deployment_hash}</BreadcrumbPage>
          </BreadcrumbItem>
        </BreadcrumbList>
      </Breadcrumb>

      <>
        <section
          id="header"
          className="flex flex-col md:flex-row md:items-center gap-4 justify-between"
        >
          <div className="md:mt-10 mt-5 flex flex-col gap-2 md:gap-0">
            <div className="inline-flex flex-wrap gap-1">
              <h1 className="text-xl md:text-2xl inline-flex gap-1.5">
                <span className="text-grey sr-only md:not-sr-only flex-none">
                  {service_slug} /
                </span>
                <span>{deployment.hash}</span>
              </h1>

              <DeploymentStatusBadge status={deployment.status} />
              {deployment.is_current_production && (
                <div className="relative top-0.5 rounded-md bg-link/20 text-link px-2  inline-flex gap-1 items-center">
                  <RocketIcon size={15} className="flex-none" />
                  <p>current</p>
                </div>
              )}
            </div>

            <p className="flex gap-1 items-center">
              <HistoryIcon size={15} />
              <span className="sr-only">Deployed at :</span>
              <time
                dateTime={deployment.queued_at}
                className="text-grey text-sm"
              >
                {formattedTime(deployment.queued_at)}
              </time>
            </p>
            {deployment.url && (
              <div className="flex gap-3 items-center flex-wrap">
                <a
                  href={formatURL({
                    domain: deployment.url
                  })}
                  target="_blank"
                  className="underline text-link text-sm break-all"
                >
                  {formatURL({
                    domain: deployment.url
                  })}
                </a>
              </div>
            )}
          </div>
        </section>

        <Tabs
          value={currentSelectedTab}
          className="w-full mt-5"
          onValueChange={(value) => {
            switch (value) {
              case TABS.LOGS:
                navigate(".");
                break;
              case TABS.HTTP_LOGS:
                navigate("./http-logs");
                break;
              case TABS.DETAILS:
                navigate("./details");
                break;
              default:
                break;
            }
          }}
        >
          <TabsList className="overflow-x-auto overflow-y-clip h-[2.55rem] w-full items-start justify-start bg-background rounded-none border-b border-border">
            <TabsTrigger value={TABS.LOGS} className="flex gap-2 items-center">
              <span>Runtime logs</span>
              <LogsIcon size={15} className="flex-none" />
            </TabsTrigger>

            <TabsTrigger
              value={TABS.HTTP_LOGS}
              className="flex gap-2 items-center"
            >
              <span>HTTP logs</span>
              <GlobeIcon size={15} className="flex-none" />
            </TabsTrigger>

            <TabsTrigger
              value={TABS.DETAILS}
              className="flex gap-2 items-center"
            >
              <span>Details</span>
              <InfoIcon size={15} className="flex-none" />
            </TabsTrigger>
          </TabsList>

          <TabsContent value={TABS.LOGS}>
            <Outlet />
          </TabsContent>

          <TabsContent value={TABS.HTTP_LOGS}>
            <Outlet />
          </TabsContent>
          <TabsContent value={TABS.DETAILS}>
            <Outlet />
          </TabsContent>
        </Tabs>
      </>
    </>
  );
}

const DEPLOYMENT_STATUS_COLOR_MAP = {
  STARTING: "blue",
  RESTARTING: "blue",
  PREPARING: "blue",
  CANCELLING: "blue",
  HEALTHY: "green",
  UNHEALTHY: "red",
  FAILED: "red",
  REMOVED: "gray",
  CANCELLED: "gray",
  QUEUED: "gray",
  SLEEPING: "yellow"
} as const satisfies Record<
  (typeof DEPLOYMENT_STATUSES)[number],
  StatusBadgeColor
>;

type DeploymentStatusBadgeProps = {
  status: keyof typeof DEPLOYMENT_STATUS_COLOR_MAP;
  className?: string;
};

function DeploymentStatusBadge({
  status,
  className
}: DeploymentStatusBadgeProps) {
  const color = DEPLOYMENT_STATUS_COLOR_MAP[status];

  const icons = {
    HEALTHY: HeartPulseIcon,
    RESTARTING: RotateCcwIcon,
    FAILED: XIcon,
    UNHEALTHY: TriangleAlertIcon,
    CANCELLED: BanIcon,
    QUEUED: ClockArrowUpIcon,
    REMOVED: Trash2Icon,
    SLEEPING: PauseIcon,
    STARTING: FastForwardIcon,
    PREPARING: HourglassIcon,
    CANCELLING: RefreshCwOffIcon
  } as const satisfies Record<typeof status, React.ComponentType<any>>;

  const Icon = icons[status];

  const isLoading = [
    "STARTING",
    "PREPARING",
    "CANCELLING",
    "RESTARTING"
  ].includes(status);

  const isActive = ["HEALTHY", "UNHEALTHY"].includes(status);
  return (
    <div
      className={cn(
        "relative top-0.5 rounded-md bg-link/20 text-link px-2  inline-flex gap-1 items-center",
        {
          "bg-emerald-400/20 dark:bg-emerald-600/20 text-green-600  dark:text-emerald-400":
            color === "green",
          "bg-red-600/10 text-red-600 dark:text-red-400": color === "red",
          "bg-yellow-400/20 dark:bg-yellow-600/20 text-yellow-600 dark:text-yellow-400":
            color === "yellow",
          "bg-gray-600/20 dark:bg-gray-600/60 text-gray": color === "gray",
          "bg-link/20 text-link": color === "blue"
        },
        className
      )}
    >
      <div className="relative ">
        {isActive && (
          <Icon
            size={15}
            className="flex-none animate-ping absolute h-full w-full"
          />
        )}
        <Icon size={15} className="flex-none" />
      </div>
      <p>{capitalizeText(status)}</p>
      {isLoading && <LoaderIcon className="animate-spin flex-none" size={15} />}
    </div>
  );
}
