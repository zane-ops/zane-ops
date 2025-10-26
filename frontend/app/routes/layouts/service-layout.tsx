import { useQuery } from "@tanstack/react-query";
import {
  ArrowUpIcon,
  ChartNoAxesColumn,
  ChevronRight,
  ContainerIcon,
  ExternalLinkIcon,
  GithubIcon,
  GitlabIcon,
  GlobeIcon,
  KeyRoundIcon,
  RocketIcon,
  SettingsIcon
} from "lucide-react";
import { Link, Outlet, useLocation, useParams } from "react-router";
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
import { Button } from "~/components/ui/button";
import { ServiceChangesModal } from "~/routes/services/components/service-changes-modal";

import * as React from "react";
import {
  Popover,
  PopoverContent,
  PopoverTrigger
} from "~/components/ui/popover";
import { type Service, serverQueries, serviceQueries } from "~/lib/queries";
import type { ValueOf } from "~/lib/types";
import { isNotFoundError, notFound } from "~/lib/utils";
import { cn } from "~/lib/utils";
import { queryClient } from "~/root";
import { ServiceActionsPopover } from "~/routes/services/components/service-actions-popover";
import {
  formatURL,
  getDockerImageIconURL,
  metaTitle,
  pluralize
} from "~/utils";
import type { Route } from "./+types/service-layout";

export function meta({ params, error }: Route.MetaArgs) {
  const title = !error
    ? params.serviceSlug
    : isNotFoundError(error)
      ? "Error 404 - Service does not exist"
      : "Oops";
  return [metaTitle(title)] satisfies ReturnType<Route.MetaFunction>;
}

export async function clientLoader({ params }: Route.ClientLoaderArgs) {
  let [service, limits] = await Promise.all([
    queryClient.ensureQueryData(
      serviceQueries.single({
        project_slug: params.projectSlug,
        service_slug: params.serviceSlug,
        env_slug: params.envSlug
      })
    ),
    queryClient.ensureQueryData(serverQueries.resourceLimits)
  ]);

  if (!service) {
    throw notFound();
  }

  return { limits, service };
}

const TABS = {
  DEPLOYMENTS: "deployments",
  ENV_VARIABLES: "envVariables",
  SETTINGS: "settings",
  HTTP_LOGS: "http-logs"
} as const;

export default function ServiceDetailsLayout({
  loaderData,
  params: {
    projectSlug: project_slug,
    serviceSlug: service_slug,
    envSlug: env_slug
  }
}: Route.ComponentProps) {
  const location = useLocation();

  const { data: service } = useQuery({
    ...serviceQueries.single({
      project_slug,
      service_slug,
      env_slug
    }),
    initialData: loaderData.service
  });

  let currentSelectedTab: ValueOf<typeof TABS> = TABS.DEPLOYMENTS;
  if (location.pathname.match(/env\-variables\/?$/)) {
    currentSelectedTab = TABS.ENV_VARIABLES;
  } else if (location.pathname.match(/settings\/?$/)) {
    currentSelectedTab = TABS.SETTINGS;
  } else if (location.pathname.match(/http\-logs\/?$/)) {
    currentSelectedTab = TABS.HTTP_LOGS;
  }

  const serviceGitSourceChange = service.unapplied_changes.find(
    (change) => change.field === "git_source"
  ) as
    | {
        new_value: Pick<
          Service,
          "repository_url" | "branch_name" | "commit_sha" | "git_app"
        >;
        id: string;
      }
    | undefined;

  let serviceImage =
    service.image ??
    (
      service.unapplied_changes.filter((change) => change.field === "source")[0]
        ?.new_value as Pick<Service, "image" | "credentials">
    )?.image;

  const serviceGitApp =
    service.git_app ?? serviceGitSourceChange?.new_value.git_app;
  const isGitlab =
    service.repository_url?.startsWith("https://gitlab.com") ||
    Boolean(serviceGitApp?.gitlab);

  const gitUrl =
    service?.environment?.preview_metadata?.pr_number && service?.repository_url
      ? `${service.repository_url?.replace(/.git$/, "")}${
          isGitlab ? "/-/merge_requests/" : "/pull/"
        }${service.environment.preview_metadata.pr_number}`
      : (service.repository_url ??
        serviceGitSourceChange?.new_value?.repository_url);

  if (serviceImage && !serviceImage.includes(":")) {
    serviceImage += ":latest";
  }
  let extraServiceUrls: Service["urls"] = [];

  if (service && service.urls.length > 1) {
    let [_, ...rest] = service.urls;
    extraServiceUrls = rest;
  }

  const [iconNotFound, setIconNotFound] = React.useState(false);

  let iconSrc: string | null = null;
  if (serviceImage) {
    iconSrc = getDockerImageIconURL(serviceImage);
  }

  return (
    <>
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
                env_slug === "production"
                  ? "text-green-500 dark:text-primary"
                  : env_slug.startsWith("preview")
                    ? "text-link"
                    : ""
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
            <BreadcrumbPage>{service_slug}</BreadcrumbPage>
          </BreadcrumbItem>
        </BreadcrumbList>
      </Breadcrumb>

      <>
        <section
          id="header"
          className="flex flex-col sm:flex-row md:items-center gap-4 justify-between"
        >
          <div className="mt-10">
            <h1 className="text-2xl">{service.slug}</h1>
            <p className="flex gap-1 items-center">
              {service.type === "DOCKER_REGISTRY" ? (
                <>
                  {iconSrc && !iconNotFound ? (
                    <img
                      src={iconSrc}
                      onError={() => setIconNotFound(true)}
                      alt={`Logo for ${serviceImage}`}
                      className="size-4 flex-none object-center object-contain"
                    />
                  ) : (
                    <ContainerIcon className="flex-none" size={16} />
                  )}
                  <span className="text-grey text-sm">{serviceImage}</span>
                </>
              ) : (
                <>
                  {isGitlab ? (
                    <GitlabIcon size={16} className="flex-none" />
                  ) : (
                    <GithubIcon size={16} className="flex-none" />
                  )}
                  <a
                    className="text-grey text-sm hover:underline inline-flex gap-1 items-center"
                    href={gitUrl ?? "#"}
                    target="_blank"
                    rel="noreferrer"
                  >
                    <span>{gitUrl}</span>
                    <ExternalLinkIcon size={15} />
                  </a>
                </>
              )}
            </p>
            {service.urls.length > 0 && (
              <div className="flex gap-3 items-center flex-wrap">
                <a
                  href={formatURL(service.urls[0])}
                  target="_blank"
                  className="underline text-link text-sm break-all"
                >
                  {formatURL(service.urls[0])}
                </a>
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
                            {`+${service.urls.length - 1} ${pluralize("url", service.urls.length - 1)}`}
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
                          <li key={url.id} className="w-full">
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

          <DeployServiceForm service={service} />
        </section>

        {currentSelectedTab === TABS.SETTINGS && (
          <Button
            variant="outline"
            className={cn(
              "inline-flex gap-2 fixed bottom-10 right-5 md:right-10 z-30",
              "bg-grey text-white dark:text-black"
            )}
            onClick={() => {
              const main = document.querySelector("main");
              main?.scrollIntoView({
                behavior: "smooth",
                block: "start"
              });
            }}
          >
            <span>Back to top</span> <ArrowUpIcon size={15} />
          </Button>
        )}

        <nav className="mt-5">
          <ul
            className={cn(
              "overflow-x-auto overflow-y-clip h-[2.55rem] w-full items-start justify-start rounded-none border-b border-border ",
              "inline-flex items-stretch p-0.5 text-muted-foreground"
            )}
          >
            <li>
              <NavLink to=".">
                <span>Deployments</span>
                <RocketIcon size={15} className="flex-none" />
              </NavLink>
            </li>

            <li>
              <NavLink to="./env-variables">
                <span>Env Variables</span>
                <KeyRoundIcon size={15} className="flex-none" />
              </NavLink>
            </li>

            <li>
              <NavLink to="./settings">
                <span>Settings</span>
                <SettingsIcon size={15} className="flex-none" />
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
    </>
  );
}

type DeployServiceFormProps = {
  className?: string;
  service: Service;
};

function DeployServiceForm({ className, service }: DeployServiceFormProps) {
  const params = useParams<Route.ComponentProps["params"]>();

  return (
    <div
      className={cn(
        "flex flex-row flex-wrap",
        "sm:flex-col sm:justify-end",
        "md:flex-row md:items-center gap-1",
        className
      )}
    >
      <ServiceChangesModal
        service={service}
        project_slug={params.projectSlug!}
      />

      <ServiceActionsPopover
        projectSlug={params.projectSlug!}
        envSlug={params.envSlug!}
        service={service}
      />
    </div>
  );
}
