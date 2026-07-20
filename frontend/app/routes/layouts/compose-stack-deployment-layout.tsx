import { useQuery } from "@tanstack/react-query";
import {
  HistoryIcon,
  InfoIcon,
  LoaderIcon,
  RocketIcon,
  SquareChartGanttIcon
} from "lucide-react";
import { Link, Outlet, useFetcher } from "react-router";
import { DeploymentStatusBadge } from "~/components/deployment-status-badge";
import { NavLink } from "~/components/nav-link";
import { SubmitButton } from "~/components/ui/button";
import { getCurrentWorkspace, useCurrentWorkspace } from "~/lib/auth-store";
import { composeStackQueries, userQueries } from "~/lib/queries";
import { getQueryClient } from "~/lib/query-client";
import { cn, formattedTime, metaTitle, notFound } from "~/lib/utils";
import type { clientAction as cancelDeploymentAction } from "~/routes/compose/cancel-compose-deployment";
import type { Route } from "./+types/compose-stack-deployment-layout";

export async function clientLoader({ params }: Route.ClientLoaderArgs) {
  const queryClient = getQueryClient();
  const { id: workspaceId } = await getCurrentWorkspace(queryClient);
  const [stack, deployment] = await Promise.all([
    queryClient.ensureQueryData(
      composeStackQueries.single({
        workspaceId,
        project_slug: params.projectSlug,
        stack_slug: params.composeStackSlug,
        env_slug: params.envSlug
      })
    ),
    queryClient.ensureQueryData(
      composeStackQueries.singleDeployment({
        workspaceId,
        project_slug: params.projectSlug,
        stack_slug: params.composeStackSlug,
        env_slug: params.envSlug,
        deployment_hash: params.deploymentHash
      })
    )
  ]);

  if (!deployment || !stack) {
    throw notFound();
  }

  return { deployment, stack };
}

export default function ComposeStackDeploymentLayoutPage({
  loaderData,
  params
}: Route.ComponentProps) {
  const workspaceId = useCurrentWorkspace().id;
  const { data: deployment } = useQuery({
    ...composeStackQueries.singleDeployment({
      workspaceId,
      project_slug: params.projectSlug,
      stack_slug: params.composeStackSlug,
      env_slug: params.envSlug,
      deployment_hash: params.deploymentHash
    }),
    initialData: loaderData.deployment
  });

  const cancellableDeploymentsStatuses: Array<typeof deployment.status> = [
    "QUEUED",
    "DEPLOYING"
  ];

  const isCancellable =
    !deployment.finished_at &&
    cancellableDeploymentsStatuses.includes(deployment.status);

  const status_emoji_map = {
    FINISHED: "☑️",
    FAILED: "❌",
    QUEUED: "⏳",
    DEPLOYING: "🚀",
    CANCELLED: "🚫"
  } satisfies Record<(typeof deployment)["status"], string>;

  const meta = metaTitle(
    `${status_emoji_map[deployment.status]} ${params.composeStackSlug} / ${params.deploymentHash}`
  );

  return (
    <>
      <title>{meta.title}</title>

      <section
        id="header"
        className="flex flex-col md:flex-row md:items-center gap-4 justify-between"
      >
        <div className="flex flex-col gap-2 md:gap-0">
          <div className="inline-flex flex-wrap gap-1 items-center">
            <h1 className="text-xl md:text-2xl inline-flex gap-1 items-center">
              <RocketIcon className="size-6 flex-none" />
              <span className="text-grey sr-only md:not-sr-only flex-none">
                <Link to={`./../..`} className="hover:underline">
                  {params.composeStackSlug}
                </Link>
              </span>
              <span>/</span>
              <span>{deployment.hash}</span>
            </h1>

            <DeploymentStatusBadge
              status={deployment.status}
              className="py-1"
            />

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
          <li>
            <NavLink to="." prefetch="viewport">
              <span>Build logs</span>
              <SquareChartGanttIcon size={15} className="flex-none" />
            </NavLink>
          </li>

          <li>
            <NavLink to="./details">
              <span>Details</span>
              <InfoIcon size={15} className="flex-none" />
            </NavLink>
          </li>
        </ul>
      </nav>
      <section className="mt-2">
        <Outlet />
      </section>
    </>
  );
}

function DeploymentCancelForm() {
  const fetcher = useFetcher<typeof cancelDeploymentAction>();
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
