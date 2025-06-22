import { useQuery } from "@tanstack/react-query";
import {
  ArrowUpIcon,
  ChartNoAxesColumn,
  ChevronDownIcon,
  ChevronRight,
  CircleXIcon,
  Container,
  ExternalLinkIcon,
  GithubIcon,
  GlobeIcon,
  KeyRoundIcon,
  LoaderIcon,
  PaintbrushIcon,
  RocketIcon,
  SettingsIcon
} from "lucide-react";
import {
  Link,
  Outlet,
  useFetcher,
  useLocation,
  useNavigate,
  useParams
} from "react-router";
import { NavLink } from "~/components/nav-link";
import { ServiceChangesModal } from "~/components/service-changes-modal";
import { StatusBadge } from "~/components/status-badge";
import {
  Breadcrumb,
  BreadcrumbItem,
  BreadcrumbLink,
  BreadcrumbList,
  BreadcrumbPage,
  BreadcrumbSeparator
} from "~/components/ui/breadcrumb";
import { Button, SubmitButton } from "~/components/ui/button";

import * as React from "react";

import { ServiceCleanupQueueConfirm } from "~/components/service-cleanup-queue-confirm-modal";
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
import type { clientAction as deployClientAction } from "~/routes/services/deploy-docker-service";
import { formatURL, metaTitle, pluralize } from "~/utils";
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

  let serviceImage =
    service.image ??
    (
      service.unapplied_changes.filter((change) => change.field === "source")[0]
        ?.new_value as Pick<Service, "image" | "credentials">
    )?.image;

  let serviceRepository =
    service.repository_url ??
    (
      service.unapplied_changes.filter(
        (change) => change.field === "git_source"
      )[0]?.new_value as Pick<Service, "repository_url">
    )?.repository_url;

  if (serviceImage && !serviceImage.includes(":")) {
    serviceImage += ":latest";
  }
  let extraServiceUrls: Service["urls"] = [];

  if (service && service.urls.length > 1) {
    let [_, ...rest] = service.urls;
    extraServiceUrls = rest;
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
                  <Container size={15} />
                  <span className="text-grey text-sm">{serviceImage}</span>
                </>
              ) : (
                <>
                  <GithubIcon size={15} />
                  <a
                    className="text-grey text-sm hover:underline inline-flex gap-1 items-center"
                    href={serviceRepository ?? "#"}
                    target="_blank"
                  >
                    <span>{serviceRepository}</span>
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
  const deployFetcher = useFetcher<typeof deployClientAction>();
  const params = useParams<Route.ComponentProps["params"]>();
  const navigate = useNavigate();

  React.useEffect(() => {
    if (deployFetcher.state === "idle" && deployFetcher.data) {
      if (!deployFetcher.data.errors) {
        navigate(
          `/project/${params.projectSlug}/${params.envSlug}/services/${params.serviceSlug}`
        );
      }
    }
  }, [
    deployFetcher.data,
    deployFetcher.state,
    params.projectSlug,
    params.serviceSlug,
    params.envSlug
  ]);

  return (
    <div
      className={cn(
        "flex flex-row sm:flex-col sm:justify-end md:items-center flex-wrap md:flex-row",
        className
      )}
    >
      <ServiceChangesModal
        service={service}
        project_slug={params.projectSlug!}
      />

      <Popover>
        <PopoverTrigger asChild>
          <Button
            type="button"
            variant="secondary"
            className="flex-1 md:flex-auto gap-1 rounded-md"
          >
            <span>Actions</span>
            <ChevronDownIcon size={15} />
          </Button>
        </PopoverTrigger>
        <PopoverContent
          side="bottom"
          align="end"
          sideOffset={5}
          className={cn(
            "w-min",
            "flex flex-col gap-0 p-2",
            "z-50 rounded-md border border-border bg-popover text-popover-foreground shadow-md outline-hidden",
            "data-[state=open]:animate-in data-[state=closed]:animate-out data-[state=closed]:fade-out-0 data-[state=open]:fade-in-0 data-[state=closed]:zoom-out-95 data-[state=open]:zoom-in-95",
            "data-[side=bottom]:slide-in-from-top-2 data-[side=left]:slide-in-from-right-2 data-[side=right]:slide-in-from-left-2 data-[side=top]:slide-in-from-bottom-2"
          )}
        >
          <deployFetcher.Form
            method="post"
            action={
              service.type === "DOCKER_REGISTRY"
                ? "./deploy-docker-service"
                : "./deploy-git-service"
            }
          >
            <SubmitButton
              isPending={deployFetcher.state !== "idle"}
              variant="ghost"
              size="sm"
              className="flex items-center gap-2 justify-start dark:text-card-foreground w-full"
            >
              {deployFetcher.state !== "idle" ? (
                <LoaderIcon className="animate-spin opacity-50" size={15} />
              ) : (
                <RocketIcon size={15} className="flex-none opacity-50" />
              )}
              <span>Deploy now</span>
            </SubmitButton>
          </deployFetcher.Form>
          <ServiceCleanupQueueConfirm />
        </PopoverContent>
      </Popover>
    </div>
  );
}
