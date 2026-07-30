import { useQuery } from "@tanstack/react-query";
import {
  BoxIcon,
  BoxesIcon,
  ChartNoAxesColumn,
  GlobeIcon,
  HashIcon,
  RocketIcon,
  SettingsIcon
} from "lucide-react";
import { Outlet, useFetcher } from "react-router";
import type { ComposeStack } from "~/api/types";
import { getComposeStackStatus } from "~/components/compose-stack-cards";
import { CopyButton } from "~/components/copy-button";
import { DeploymentStatusBadge } from "~/components/deployment-status-badge";
import { type NavItem, NavLink } from "~/components/nav-link";
import {
  Tooltip,
  TooltipContent,
  TooltipProvider,
  TooltipTrigger
} from "~/components/ui/tooltip";
import { composeStackQueries, userQueries } from "~/lib/queries";
import { getQueryClient } from "~/lib/query-client";
import {
  cn,
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
import { ComposeStackActionsPopover } from "~/routes/compose/components/compose-stack-actions-popover";
import { ComposeStackChangesModal } from "~/routes/compose/components/compose-stack-changes-modal";
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
  const queryClient = getQueryClient();
  const { id: workspaceId } = await getCurrentWorkspace(queryClient);
  const stack = await queryClient.ensureQueryData(
    composeStackQueries.single({
      workspaceId,
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
  const membership = useCurrentWorkspaceMembership();
  const isMember = hasMinRole(membership, "Member");
  const workspaceId = useCurrentWorkspace().id;
  const { data: stack } = useQuery({
    ...composeStackQueries.single({
      workspaceId,
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

  const navItems: NavItem[] = [
    {
      title: "Services",
      href: ".",
      icon: BoxIcon
    },
    {
      title: "Settings",
      href: "./settings",
      icon: SettingsIcon
    },
    {
      title: "Deployments",
      href: "./deployments/",
      icon: RocketIcon
    }
  ];

  if (isMember) {
    navItems.push({
      title: "Http logs",
      href: "./http-logs",
      icon: GlobeIcon
    });
  }

  navItems.push({
    title: "Metrics",
    href: "./metrics",
    icon: ChartNoAxesColumn
  });

  return (
    <>
      <title>{title}</title>

      <section
        id="header"
        className="flex flex-col sm:flex-row md:items-center gap-4 justify-between"
      >
        <div className="flex flex-col gap-2">
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
            <span>ID: {stack.id}</span>
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

        {hasMinRole(membership, "Member") && (
          <DeployStackForm stack={stack} params={params} />
        )}
      </section>

      <nav className="mt-5">
        <ul
          className={cn(
            "overflow-x-auto overflow-y-clip h-[2.55rem] w-full items-start justify-start rounded-none border-b border-border ",
            "inline-flex items-stretch p-0.5 text-muted-foreground"
          )}
        >
          {navItems.map((item) => (
            <li key={item.href}>
              <NavLink to={item.href} prefetch="viewport">
                <span>{item.title}</span>
                <item.icon size={15} className="flex-none" />
              </NavLink>
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

type DeployStackFormProps = {
  className?: string;
  stack: ComposeStack;
  params: Route.ComponentProps["params"];
};

function DeployStackForm({ className, stack, params }: DeployStackFormProps) {
  return (
    <div
      className={cn(
        "flex flex-row flex-wrap",
        "sm:flex-col sm:justify-end",
        "md:flex-row md:items-center gap-2",
        className
      )}
    >
      <ComposeStackChangesModal
        stack={stack}
        projectSlug={params.projectSlug}
        envSlug={params.envSlug}
      />
      <ComposeStackActionsPopover
        stack={stack}
        projectSlug={params.projectSlug}
        envSlug={params.envSlug}
      />
    </div>
  );
}
