import { useQuery } from "@tanstack/react-query";
import {
  BoxIcon,
  BoxesIcon,
  ChartNoAxesColumn,
  ClockIcon,
  GlobeIcon,
  HashIcon,
  LoaderIcon,
  RocketIcon,
  SettingsIcon
} from "lucide-react";
import { Link, Outlet, href, useFetcher, useParams } from "react-router";
import type { ComposeStack } from "~/api/types";
import { getComposeStackStatus } from "~/components/compose-stack-cards";
import { CopyButton } from "~/components/copy-button";
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
import {
  Tooltip,
  TooltipContent,
  TooltipProvider,
  TooltipTrigger
} from "~/components/ui/tooltip";
import { composeStackQueries } from "~/lib/queries";
import { cn, isNotFoundError, notFound } from "~/lib/utils";
import { queryClient } from "~/root";
import {
  capitalizeText,
  formattedTime,
  metaTitle,
  timeAgoFormatter
} from "~/utils";
import type { Route } from "./+types/compose-stack-layout";

export function meta({ params, error }: Route.MetaArgs) {
  const title = !error
    ? params.composeStackSlug
    : isNotFoundError(error)
      ? "Error 404 - Compose Stack does not exist"
      : "Oops";
  return [metaTitle(title)] satisfies ReturnType<Route.MetaFunction>;
}

export async function clientLoader({ params }: Route.ClientLoaderArgs) {
  const stack = await queryClient.ensureQueryData(
    composeStackQueries.single({
      project_slug: params.projectSlug,
      stack_slug: params.composeStackSlug,
      env_slug: params.envSlug
    })
  );
  if (!stack) {
    throw notFound();
  }

  return { stack };
}

export default function ComposeStackLayoutPage({
  params,
  loaderData
}: Route.ComponentProps) {
  const { data: stack } = useQuery({
    ...composeStackQueries.single({
      project_slug: params.projectSlug,
      stack_slug: params.composeStackSlug,
      env_slug: params.envSlug
    }),
    initialData: loaderData.stack
  });
  const status_emoji_map = {
    HEALTHY: "🟢",
    UNHEALTHY: "🔴",
    SLEEPING: "🌙",
    NOT_DEPLOYED_YET: "🆕",
    STARTING: "▶️"
  } as const;

  const stackStatus = getComposeStackStatus(stack);

  const { title } = metaTitle(`${status_emoji_map[stackStatus]} ${stack.slug}`);

  return (
    <>
      <title>{title}</title>
      <Breadcrumb>
        <BreadcrumbList className="text-sm">
          <BreadcrumbItem>
            <BreadcrumbLink asChild>
              <Link to="/" prefetch="intent">
                Projects
              </Link>
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
            <BreadcrumbPage>{params.composeStackSlug}</BreadcrumbPage>
          </BreadcrumbItem>
        </BreadcrumbList>
      </Breadcrumb>

      <section
        id="header"
        className="flex flex-col sm:flex-row md:items-center gap-4 justify-between"
      >
        <div className="mt-10 flex flex-col gap-2">
          <div className="flex items-center gap-x-2 flex-wrap">
            <h1 className="text-2xl inline-flex gap-1 items-center">
              <BoxesIcon className="size-6 flex-none" />
              {stack.slug}
            </h1>
            <span className="inline-block rounded-full size-0.5 bg-foreground relative top-0.5" />
            <DeploymentStatusBadge status={stackStatus} />
          </div>

          <div className="inline-flex gap-1 items-center text-grey text-sm">
            <HashIcon className="size-4 flex-none" />
            <span>{stack.id}</span>
            <TooltipProvider>
              <Tooltip delayDuration={0}>
                <TooltipTrigger asChild>
                  <CopyButton
                    label="Copy compose stack ID"
                    value={stack.id}
                    className="size-4 !opacity-100"
                  />
                </TooltipTrigger>
                <TooltipContent>Copy compose stack ID</TooltipContent>
              </Tooltip>
            </TooltipProvider>
          </div>
        </div>

        <DeployStackForm stack={stack} params={params} />
      </section>

      <nav className="mt-5">
        <ul
          className={cn(
            "overflow-x-auto overflow-y-clip h-[2.55rem] w-full items-start justify-start rounded-none border-b border-border ",
            "inline-flex items-stretch p-0.5 text-muted-foreground"
          )}
        >
          <li>
            <NavLink to=".">
              <span>Services</span>
              <BoxIcon size={15} className="flex-none" />
            </NavLink>
          </li>
          <li>
            <NavLink to="./settings">
              <span>Settings</span>
              <SettingsIcon size={15} className="flex-none" />
            </NavLink>
          </li>

          <li>
            <NavLink to="./env-variables">
              <span>Deployments</span>
              <RocketIcon size={15} className="flex-none" />
            </NavLink>
          </li>

          <li>
            <NavLink to="./http-logs" prefetch="viewport">
              <span>Http logs</span>
              <GlobeIcon size={15} className="flex-none" />
            </NavLink>
          </li>

          <li>
            <NavLink to="./metrics">
              <span>Metrics</span>
              <ChartNoAxesColumn size={15} className="flex-none" />
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

type DeployStackFormProps = {
  className?: string;
  stack: ComposeStack;
  params: Route.ComponentProps["params"];
};

function DeployStackForm({ className, stack, params }: DeployStackFormProps) {
  const fetcher = useFetcher();
  const isDeploying = fetcher.state !== "idle";

  return (
    <div
      className={cn(
        "flex flex-row flex-wrap",
        "sm:flex-col sm:justify-end",
        "md:flex-row md:items-center gap-1",
        className
      )}
    >
      <fetcher.Form
        method="post"
        action={href(
          "/project/:projectSlug/:envSlug/compose-stacks/:composeStackSlug/deploy",
          params
        )}
      >
        <SubmitButton isPending={isDeploying} variant="secondary">
          {isDeploying ? (
            <>
              <LoaderIcon className="animate-spin" size={15} />
              <span>Deploying</span>
            </>
          ) : (
            <>
              <RocketIcon size={15} />
              <span>Deploy now</span>
            </>
          )}
        </SubmitButton>
      </fetcher.Form>
    </div>
  );
}
