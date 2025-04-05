import { useQuery } from "@tanstack/react-query";
import {
  BanIcon,
  ChartNoAxesColumnIcon,
  ChevronRight,
  ClockArrowUpIcon,
  FastForwardIcon,
  GlobeIcon,
  HammerIcon,
  HeartPulseIcon,
  HistoryIcon,
  HourglassIcon,
  InfoIcon,
  LoaderIcon,
  PauseIcon,
  RefreshCwOffIcon,
  RocketIcon,
  RotateCcwIcon,
  SquareChartGanttIcon,
  TextSearchIcon,
  Trash2Icon,
  TriangleAlertIcon,
  XIcon
} from "lucide-react";
import { Link, Outlet, useFetcher, useParams } from "react-router";
import { NavLink } from "~/components/nav-link";
import { StatusBadge, type StatusBadgeColor } from "~/components/status-badge";
import {
  Breadcrumb,
  BreadcrumbItem,
  BreadcrumbLink,
  BreadcrumbList,
  BreadcrumbPage,
  BreadcrumbSeparator
} from "~/components/ui/breadcrumb";
import { Button, SubmitButton } from "~/components/ui/button";
import {
  Popover,
  PopoverContent,
  PopoverTrigger
} from "~/components/ui/popover";
import type { DEPLOYMENT_STATUSES } from "~/lib/constants";
import {
  deploymentQueries,
  serverQueries,
  serviceQueries
} from "~/lib/queries";
import { cn, isNotFoundError, notFound } from "~/lib/utils";
import { queryClient } from "~/root";
import type { clientAction as cancelClientAction } from "~/routes/deployments/cancel-deployment";
import {
  capitalizeText,
  formatURL,
  formattedTime,
  metaTitle,
  pluralize
} from "~/utils";
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
  let [service, limits, deployment] = await Promise.all([
    queryClient.ensureQueryData(
      serviceQueries.single({
        project_slug: params.projectSlug,
        service_slug: params.serviceSlug,
        env_slug: params.envSlug
      })
    ),
    queryClient.ensureQueryData(serverQueries.resourceLimits),
    queryClient.ensureQueryData(
      deploymentQueries.single({
        project_slug: params.projectSlug,
        service_slug: params.serviceSlug,
        env_slug: params.envSlug,
        deployment_hash: params.deploymentHash
      })
    )
  ]);

  if (!deployment || !service) {
    throw notFound();
  }

  return { deployment, limits, service };
}

export default function DeploymentLayoutPage({
  loaderData,
  params: {
    projectSlug: project_slug,
    serviceSlug: service_slug,
    envSlug: env_slug,
    deploymentHash: deployment_hash
  }
}: Route.ComponentProps) {
  const { data: deployment } = useQuery({
    ...deploymentQueries.single({
      project_slug,
      service_slug,
      env_slug,
      deployment_hash
    }),
    initialData: loaderData.deployment
  });

  const [firstURL, ...extraDeploymentURLs] = deployment.urls;
  const cancellableDeploymentsStatuses: Array<typeof deployment.status> = [
    "QUEUED",
    "PREPARING",
    "BUILDING",
    "STARTING",
    "RESTARTING"
  ];
  const isCancellable = cancellableDeploymentsStatuses.includes(
    deployment.status
  );

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
              <Link
                to={`/project/${project_slug}/production`}
                prefetch="intent"
              >
                {project_slug}
              </Link>
            </BreadcrumbLink>
          </BreadcrumbItem>
          <BreadcrumbSeparator />
          <BreadcrumbItem>
            <BreadcrumbLink
              asChild
              className={cn(
                env_slug !== "production"
                  ? "text-link"
                  : "text-green-500 dark:text-primary"
              )}
            >
              <Link
                to={`/project/${project_slug}/${env_slug}`}
                prefetch="intent"
              >
                {env_slug}
              </Link>
            </BreadcrumbLink>
          </BreadcrumbItem>

          <BreadcrumbSeparator />
          <BreadcrumbItem>
            <Link
              to={`/project/${project_slug}/${env_slug}/services/${service_slug}`}
            >
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
              {isCancellable && <DeploymentCancelForm />}
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
            {firstURL && (
              <div className="flex gap-3 items-center flex-wrap">
                <a
                  href={formatURL({
                    domain: firstURL.domain
                  })}
                  target="_blank"
                  className="underline text-link text-sm break-all"
                >
                  {formatURL({
                    domain: firstURL.domain
                  })}
                </a>
              </div>
            )}

            {extraDeploymentURLs.length > 0 && (
              <Popover>
                <PopoverTrigger asChild>
                  <button>
                    <StatusBadge
                      className="relative top-0.5 text-xs pl-3 pr-2 inline-flex items-center gap-1"
                      color="gray"
                      pingState="hidden"
                    >
                      <span>
                        {`+${extraDeploymentURLs.length} ${pluralize("url", extraDeploymentURLs.length)}`}
                      </span>
                      <ChevronRight size={15} className="flex-none" />
                    </StatusBadge>
                  </button>
                </PopoverTrigger>
                <PopoverContent
                  align="start"
                  side="top"
                  className="px-4 pt-3 pb-2 max-w-[300px] md:max-w-[500px] lg:max-w-[600px] w-auto"
                >
                  <ul className="w-full">
                    {extraDeploymentURLs.map((url) => (
                      <li key={url.domain} className="w-full">
                        <a
                          href={formatURL(url)}
                          target="_blank"
                          className="underline text-link text-sm inline-block w-full"
                        >
                          <p className="whitespace-nowrap overflow-x-hidden text-ellipsis">
                            {formatURL(url)}
                          </p>
                        </a>
                      </li>
                    ))}
                  </ul>
                </PopoverContent>
              </Popover>
            )}
          </div>
        </section>

        <nav className="mt-5">
          <ul
            className={cn(
              "overflow-x-auto overflow-y-clip h-[2.55rem] w-full items-start justify-start rounded-none border-b border-border ",
              "inline-flex items-stretch p-0.5 text-muted-foreground"
            )}
          >
            <li>
              <NavLink to="./build-logs" prefetch="viewport">
                <span>Deployment logs</span>
                <SquareChartGanttIcon size={15} className="flex-none" />
              </NavLink>
            </li>
            <li>
              <NavLink to="." prefetch="viewport">
                <span>Runtime logs</span>
                <TextSearchIcon size={15} className="flex-none" />
              </NavLink>
            </li>

            <li>
              <NavLink to="./http-logs" prefetch="viewport">
                <span>HTTP logs</span>
                <GlobeIcon size={15} className="flex-none" />
              </NavLink>
            </li>

            <li>
              <NavLink to="./details">
                <span>Details</span>
                <InfoIcon size={15} className="flex-none" />
              </NavLink>
            </li>
            <li>
              <NavLink to="./metrics">
                <span>Metrics</span>
                <ChartNoAxesColumnIcon size={15} className="flex-none" />
              </NavLink>
            </li>
          </ul>
        </nav>
        <section className="mt-2">
          <Outlet />
        </section>
      </>
    </>
  );
}

const DEPLOYMENT_STATUS_COLOR_MAP = {
  STARTING: "blue",
  RESTARTING: "blue",
  BUILDING: "blue",
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
    BUILDING: HammerIcon,
    PREPARING: HourglassIcon,
    CANCELLING: RefreshCwOffIcon
  } as const satisfies Record<typeof status, React.ComponentType<any>>;

  const Icon = icons[status];

  const isLoading = [
    "STARTING",
    "PREPARING",
    "BUILDING",
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

function DeploymentCancelForm() {
  const fetcher = useFetcher<typeof cancelClientAction>();
  const isPending = fetcher.state !== "idle";

  return (
    <fetcher.Form
      method="POST"
      action={`./cancel`}
      className="self-end relative top-0.5"
    >
      <input type="hidden" name="do_not_redirect" value="true" />

      <SubmitButton
        isPending={isPending}
        size="sm"
        variant="destructive"
        className={cn(
          "inline-flex gap-1 items-center",
          isPending && "opacity-80"
        )}
      >
        {isPending ? (
          <>
            <LoaderIcon className="animate-spin" size={15} />
            Cancelling
          </>
        ) : (
          <span>Cancel</span>
        )}
      </SubmitButton>
    </fetcher.Form>
  );
}
