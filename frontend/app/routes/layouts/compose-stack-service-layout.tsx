import { useQuery } from "@tanstack/react-query";
import {
  BoxIcon,
  ChartNoAxesColumn,
  ChevronRight,
  ContainerIcon,
  GlobeIcon,
  InfoIcon,
  LayersIcon,
  PickaxeIcon,
  RotateCcwIcon,
  ScrollTextIcon,
  TerminalIcon
} from "lucide-react";
import * as React from "react";
import { Link, Navigate, Outlet, href, useFetcher } from "react-router";
import type { ComposeStackService } from "~/api/types";
import { CopyButton } from "~/components/copy-button";
import { DeploymentStatusBadge } from "~/components/deployment-status-badge";
import { NavLink } from "~/components/nav-link";
import { StatusBadge } from "~/components/status-badge";
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
  Popover,
  PopoverContent,
  PopoverTrigger
} from "~/components/ui/popover";
import {
  Tooltip,
  TooltipContent,
  TooltipProvider,
  TooltipTrigger
} from "~/components/ui/tooltip";
import { composeStackQueries } from "~/lib/queries";
import { cn, notFound } from "~/lib/utils";
import { queryClient } from "~/root";
import {
  formatURL,
  getDockerImageIconURL,
  metaTitle,
  pluralize
} from "~/utils";
import type { Route } from "./+types/compose-stack-service-layout";

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

  const service = Object.keys(stack.services).find(
    (svc) => svc === params.serviceSlug
  );

  if (!service) {
    throw notFound(`Service '${params.serviceSlug}' not found in this stack`);
  }

  return { stack };
}

export default function ComposeStackServiceLayoutPage({
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

  const serviceFound = Object.entries(stack.services).find(
    ([name]) => name === params.serviceSlug
  );

  if (!serviceFound) {
    return (
      <Navigate
        to={href(
          "/project/:projectSlug/:envSlug/compose-stacks/:composeStackSlug",
          params
        )}
      />
    );
  }

  const [name, service] = serviceFound;

  const serviceUrls = stack.urls[name] ?? [];

  const status_emoji_map = {
    HEALTHY: "🟢",
    UNHEALTHY: "🔴",
    SLEEPING: "🌙",
    STARTING: "▶️",
    COMPLETE: "✅"
  } satisfies Record<(typeof service)["status"], string>;

  const { title } = metaTitle(
    `${status_emoji_map[service.status]} ${stack.slug} / ${params.serviceSlug}`
  );

  let serviceImage = service.image;

  if (serviceImage && !serviceImage.includes(":")) {
    serviceImage += ":latest";
  }

  let extraServiceUrls: typeof serviceUrls = [];

  if (service && serviceUrls.length > 1) {
    const [_, ...rest] = serviceUrls;
    extraServiceUrls = rest;
  }

  const [iconNotFound, setIconNotFound] = React.useState(false);

  let iconSrc: string | null = null;
  if (serviceImage) {
    iconSrc = getDockerImageIconURL(serviceImage);
  }

  return (
    <>
      <title>{title}</title>
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
            <BreadcrumbPage>{params.serviceSlug}</BreadcrumbPage>
          </BreadcrumbItem>
        </BreadcrumbList>
      </Breadcrumb>

      <section
        id="header"
        className="flex flex-col sm:flex-row md:items-center gap-4 justify-between"
      >
        <div className="mt-10 flex flex-col gap-2">
          <div className="flex items-center gap-x-2">
            <h1 className="text-xl md:text-2xl inline-flex gap-1 items-center">
              {service.mode.includes("job") ? (
                <PickaxeIcon className="size-6 flex-none" />
              ) : (
                <BoxIcon className="size-6 flex-none" />
              )}
              <span className="text-grey sr-only md:not-sr-only flex-none">
                <Link to={`./../..`} className="hover:underline">
                  {params.composeStackSlug}
                </Link>{" "}
                /
              </span>
              <span>{params.serviceSlug}</span>
            </h1>
            <span className="inline-block rounded-full size-0.5 bg-foreground relative top-0.5" />
            <DeploymentStatusBadge status={service.status} />
          </div>

          <div className="flex gap-1 items-center">
            {iconSrc && !iconNotFound ? (
              <img
                src={iconSrc}
                onError={() => setIconNotFound(true)}
                alt={`Logo for ${serviceImage}`}
                className="size-4 flex-none object-center object-contain rounded-sm"
              />
            ) : (
              <ContainerIcon className="flex-none" size={16} />
            )}
            <span className="text-grey text-sm">{serviceImage}</span>
          </div>

          <div>
            {serviceUrls.length > 0 && (
              <div className="flex gap-3 items-center flex-wrap">
                <div className="flex gap-0.5 items-center">
                  <TooltipProvider>
                    <Tooltip delayDuration={0}>
                      <TooltipTrigger asChild>
                        <CopyButton
                          value={
                            serviceUrls[0].domain + serviceUrls[0].base_path
                          }
                          label="Copy url"
                          size="icon"
                          className="hover:bg-transparent !opacity-100 size-4"
                        />
                      </TooltipTrigger>
                      <TooltipContent>Copy URL (without scheme)</TooltipContent>
                    </Tooltip>
                  </TooltipProvider>
                  <a
                    href={formatURL(serviceUrls[0])}
                    target="_blank"
                    className="underline text-link text-sm break-all inline-flex items-center gap-1"
                  >
                    {formatURL(serviceUrls[0])}
                  </a>
                </div>

                {extraServiceUrls.length > 0 && (
                  <Popover>
                    <PopoverTrigger asChild>
                      <button>
                        <StatusBadge
                          className="relative top-0.5 text-xs pl-3 pr-2 inline-flex items-center gap-1"
                          color="gray"
                          pingState="hidden"
                        >
                          <span>
                            {`+${serviceUrls.length - 1} ${pluralize("url", serviceUrls.length - 1)}`}
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
                        {extraServiceUrls.map((url) => (
                          <li
                            key={url.domain + url.base_path}
                            className="w-full flex items-center gap-0.5"
                          >
                            <CopyButton
                              value={url.domain + url.base_path}
                              label="Copy url"
                              size="icon"
                              className="hover:bg-transparent !opacity-100 size-4"
                            />
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
            )}
          </div>
        </div>

        <div>
          <RestartServiceForm params={params} />
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
            <NavLink to=".">
              <span>Replicas</span>
              <LayersIcon size={15} className="flex-none" />
            </NavLink>
          </li>

          <li>
            <NavLink to="./runtime-logs">
              <span>Runtime Logs</span>
              <ScrollTextIcon size={15} className="flex-none" />
            </NavLink>
          </li>
          <li>
            <NavLink to="./terminal">
              <span>Terminal</span>
              <TerminalIcon size={15} className="flex-none" />
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

type RestartServiceFormProps = {
  params: Route.ComponentProps["params"];
};

function RestartServiceForm({ params }: RestartServiceFormProps) {
  const fetcher = useFetcher();
  const isPending = fetcher.state !== "idle";
  return (
    <fetcher.Form method="post">
      <SubmitButton isPending={isPending} variant="secondary">
        <RotateCcwIcon className="size-4 flex-none" />
        <span>Restart service</span>
      </SubmitButton>
    </fetcher.Form>
  );
}
