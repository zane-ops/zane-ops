import { useQuery } from "@tanstack/react-query";
import {
  ChartNoAxesColumnIcon,
  GlobeIcon,
  HistoryIcon,
  InfoIcon,
  LoaderIcon,
  RocketIcon,
  SquareChartGanttIcon,
  TerminalIcon,
  TextSearchIcon
} from "lucide-react";
import { Link, Outlet, href, useFetcher, useParams } from "react-router";
import {
  HorizontalNavLink,
  type NavItem
} from "~/components/horizontal-nav-link";
import { SubmitButton } from "~/components/ui/button";

import { DeploymentStatusBadge } from "~/components/deployment-status-badge";
import {
  deploymentQueries,
  serverQueries,
  serviceQueries,
  userQueries
} from "~/lib/queries";
import { getQueryClient } from "~/lib/query-client";
import {
  cn,
  formattedTime,
  hasMinRole,
  isNotFoundError,
  metaTitle,
  notFound
} from "~/lib/utils";
import {
  getCurrentWorkspace,
  useCurrentWorkspace,
  useCurrentWorkspaceMembership
} from "~/lib/workspace-store";
import type { clientAction as cancelClientAction } from "~/routes/deployments/cancel-deployment";
import type { Route } from "./+types/deployment-layout";

export function meta({ params, error }: Route.MetaArgs) {
  const title = !error
    ? `${params.serviceSlug} / ${params.deploymentHash}`
    : isNotFoundError(error)
      ? "Error 404 - Deployment does not exist"
      : "Oops";
  return [metaTitle(title)] satisfies ReturnType<Route.MetaFunction>;
}

export async function clientLoader({ params }: Route.ClientLoaderArgs) {
  const queryClient = getQueryClient();
  const { id: workspaceId } = await getCurrentWorkspace(queryClient);
  const [service, limits, deployment] = await Promise.all([
    queryClient.ensureQueryData(
      serviceQueries.single({
        workspaceId,
        project_slug: params.projectSlug,
        service_slug: params.serviceSlug,
        env_slug: params.envSlug
      })
    ),
    queryClient.ensureQueryData(serverQueries.resourceLimits),
    queryClient.ensureQueryData(
      deploymentQueries.single({
        workspaceId,
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
  params
}: Route.ComponentProps) {
  const {
    projectSlug: project_slug,
    serviceSlug: service_slug,
    envSlug: env_slug,
    deploymentHash: deployment_hash
  } = params;
  const workspaceId = useCurrentWorkspace().id;
  const membership = useCurrentWorkspaceMembership();

  const { data: deployment } = useQuery({
    ...deploymentQueries.single({
      workspaceId,
      project_slug,
      service_slug,
      env_slug,
      deployment_hash
    }),
    initialData: loaderData.deployment
  });

  const cancellableDeploymentsStatuses: Array<typeof deployment.status> = [
    "QUEUED",
    "PREPARING",
    "BUILDING",
    "STARTING",
    "RESTARTING"
  ];
  const isCancellable =
    hasMinRole(membership, "Member") &&
    !deployment.finished_at &&
    cancellableDeploymentsStatuses.includes(deployment.status);

  const status_emoji_map = {
    HEALTHY: "🟢",
    UNHEALTHY: "🔴",
    FAILED: "❌",
    SLEEPING: "🌙",
    QUEUED: "⏳",
    PREPARING: "⏳",
    BUILDING: "🔨",
    REMOVED: "🗑️",
    STARTING: "▶️",
    RESTARTING: "🔄",
    CANCELLING: "⏹️",
    CANCELLED: "🚫"
  } satisfies Record<(typeof deployment)["status"], string>;

  const navItems: NavItem[] = [];

  if (hasMinRole(membership, "Member")) {
    navItems.push(
      {
        href: "./build-logs",
        title: "Deployment logs",
        icon: SquareChartGanttIcon
      },
      {
        href: ".",
        title: "Runtime logs",
        icon: TextSearchIcon
      },
      {
        href: "./http-logs",
        title: "HTTP logs",
        icon: GlobeIcon
      },
      {
        href: "./terminal",
        title: "Terminal",
        icon: TerminalIcon
      }
    );
  }

  navItems.push(
    {
      href: "./metrics",
      title: "Metrics",
      icon: ChartNoAxesColumnIcon
    },
    {
      href: "./details",
      title: "Details",
      icon: InfoIcon
    }
  );

  return (
    <>
      <title>{`${status_emoji_map[deployment.status]} ${service_slug} / ${deployment_hash} | ZaneOps`}</title>

      <section
        id="header"
        className="flex flex-col md:flex-row md:items-center gap-4 justify-between"
      >
        <div className="flex flex-col gap-2 md:gap-0">
          <div className="inline-flex flex-wrap gap-1 items-center">
            <h1 className="text-xl md:text-2xl inline-flex gap-1.5">
              <span className="text-grey sr-only md:not-sr-only flex-none">
                <Link
                  to={href(
                    "/workspace/project/:projectSlug/:envSlug/services/:serviceSlug",
                    params
                  )}
                  className="hover:underline"
                >
                  {service_slug}
                </Link>
              </span>
              <span>/</span>
              <span>{deployment.hash}</span>
            </h1>

            <DeploymentStatusBadge
              status={deployment.status}
              className="py-1 top-0"
            />
            {deployment.is_current_production && (
              <div className="py-1 rounded-md bg-link/20 text-link px-2  inline-flex gap-1 items-center">
                <RocketIcon size={15} className="flex-none" />
                <p>current</p>
              </div>
            )}
            {isCancellable && <DeploymentCancelForm />}
          </div>

          <p className="flex gap-1 items-center">
            <HistoryIcon size={15} />
            <span className="sr-only">Deployed at :</span>
            <time dateTime={deployment.queued_at} className="text-grey text-sm">
              {formattedTime(deployment.queued_at)}
            </time>
          </p>
        </div>
      </section>

      <nav className="mt-5">
        <ul
          className={cn(
            "overflow-x-auto overflow-y-clip h-[2.55rem] w-full items-start justify-start rounded-none border-b border-border ",
            "inline-flex items-stretch p-0.5 text-muted-foreground"
          )}
        >
          {navItems.map((item) => (
            <li key={item.title}>
              <HorizontalNavLink to={item.href} prefetch="viewport">
                <span>{item.title}</span>
                <item.icon size={15} className="flex-none" />
              </HorizontalNavLink>
            </li>
          ))}
        </ul>
      </nav>
      <section className="mt-2">
        <Outlet />
      </section>
    </>
  );
}

function DeploymentCancelForm() {
  const fetcher = useFetcher<typeof cancelClientAction>();
  const isPending = fetcher.state !== "idle";
  const params = useParams() as Route.ComponentProps["params"];

  return (
    <fetcher.Form
      method="POST"
      action={href(
        "/workspace/project/:projectSlug/:envSlug/services/:serviceSlug/deployments/:deploymentHash/cancel",
        params
      )}
      className="self-end"
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
