import { useQuery } from "@tanstack/react-query";
import {
  ChartNoAxesColumnIcon,
  GlobeIcon,
  HistoryIcon,
  InfoIcon,
  LoaderIcon,
  SquareChartGanttIcon,
  TerminalIcon,
  TextSearchIcon
} from "lucide-react";
import { Link, Outlet, href, useFetcher } from "react-router";
import { DeploymentStatusBadge } from "~/components/deployment-status-badge";
import { NavLink } from "~/components/nav-link";
import {
  Breadcrumb,
  BreadcrumbItem,
  BreadcrumbLink,
  BreadcrumbList,
  BreadcrumbPage,
  BreadcrumbSeparator
} from "~/components/ui/breadcrumb";
import { SubmitButton } from "~/components/ui/button";
import { composeStackQueries } from "~/lib/queries";
import { cn, notFound } from "~/lib/utils";
import { queryClient } from "~/root";
import { formattedTime, metaTitle } from "~/utils";
import type { Route } from "./+types/compose-stack-deployment-layout";

export async function clientLoader({ params }: Route.ClientLoaderArgs) {
  const [stack, deployment] = await Promise.all([
    queryClient.ensureQueryData(
      composeStackQueries.single({
        project_slug: params.projectSlug,
        stack_slug: params.composeStackSlug,
        env_slug: params.envSlug
      })
    ),
    queryClient.ensureQueryData(
      composeStackQueries.singleDeployment({
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
  const { data: deployment } = useQuery({
    ...composeStackQueries.singleDeployment({
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
                to={href("/project/:projectSlug/:envSlug", {
                  ...params,
                  envSlug: "production"
                })}
                prefetch="intent"
              >
                {params.projectSlug}
              </Link>
            </BreadcrumbLink>
          </BreadcrumbItem>
          <BreadcrumbSeparator />
          <BreadcrumbItem>
            <BreadcrumbLink
              asChild
              className={cn(
                params.envSlug === "production"
                  ? "text-green-500 dark:text-primary"
                  : params.envSlug.startsWith("preview")
                    ? "text-link"
                    : ""
              )}
            >
              <Link
                to={href("/project/:projectSlug/:envSlug", params)}
                prefetch="intent"
              >
                {params.envSlug}
              </Link>
            </BreadcrumbLink>
          </BreadcrumbItem>

          <BreadcrumbSeparator />
          <BreadcrumbItem>
            <Link
              to={href(
                "/project/:projectSlug/:envSlug/compose-stacks/:composeStackSlug",
                params
              )}
            >
              {params.composeStackSlug}
            </Link>
          </BreadcrumbItem>

          <BreadcrumbSeparator />
          <BreadcrumbItem>
            <Link
              to={
                href(
                  "/project/:projectSlug/:envSlug/compose-stacks/:composeStackSlug/deployments",
                  params
                ) + "/"
              }
            >
              deployments
            </Link>
          </BreadcrumbItem>

          <BreadcrumbSeparator />
          <BreadcrumbItem>
            <BreadcrumbPage>{params.deploymentHash}</BreadcrumbPage>
          </BreadcrumbItem>
        </BreadcrumbList>
      </Breadcrumb>

      <section
        id="header"
        className="flex flex-col md:flex-row md:items-center gap-4 justify-between"
      >
        <div className="md:mt-10 mt-5 flex flex-col gap-2 md:gap-0">
          <div className="inline-flex flex-wrap gap-1">
            <h1 className="text-xl md:text-2xl inline-flex gap-1.5">
              <span className="text-grey sr-only md:not-sr-only flex-none">
                <Link to={`./../..`} className="hover:underline">
                  {params.composeStackSlug}
                </Link>{" "}
                /
              </span>
              <span>{deployment.hash}</span>
            </h1>

            <DeploymentStatusBadge status={deployment.status} />

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
  const fetcher = /* <typeof cancelClientAction> */ useFetcher();
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
