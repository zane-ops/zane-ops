import { useQuery } from "@tanstack/react-query";
import {
  ArrowUpIcon,
  ChartNoAxesColumn,
  ChevronRight,
  Container,
  GlobeIcon,
  KeyRoundIcon,
  LoaderIcon,
  RocketIcon,
  SettingsIcon
} from "lucide-react";
import { Link, Outlet, useFetcher, useLocation } from "react-router";
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

import {
  Popover,
  PopoverContent,
  PopoverTrigger
} from "~/components/ui/popover";
import {
  type DockerService,
  serverQueries,
  serviceQueries
} from "~/lib/queries";
import type { ValueOf } from "~/lib/types";
import { isNotFoundError, notFound } from "~/lib/utils";
import { cn } from "~/lib/utils";
import { queryClient } from "~/root";
import { formatURL, metaTitle, pluralize } from "~/utils";
import { type Route } from "./+types/service-layout";

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
        service_slug: params.serviceSlug
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
  params: { projectSlug: project_slug, serviceSlug: service_slug }
}: Route.ComponentProps) {
  const location = useLocation();

  const { data: service } = useQuery({
    ...serviceQueries.single({
      project_slug,
      service_slug
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
        ?.new_value as Pick<DockerService, "image" | "credentials">
    )?.image;

  if (serviceImage && !serviceImage.includes(":")) {
    serviceImage += ":latest";
  }
  let extraServiceUrls: DockerService["urls"] = [];

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
              <Link to={`/project/${project_slug}/`} prefetch="intent">
                {project_slug}
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
          className="flex flex-col md:flex-row md:items-center gap-4 justify-between"
        >
          <div className="mt-10">
            <h1 className="text-2xl">{service.slug}</h1>
            <p className="flex gap-1 items-center">
              <Container size={15} />
              <span className="text-grey text-sm">{serviceImage}</span>
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
              <NavLink to="./http-logs">
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
  service: DockerService;
};

function DeployServiceForm({ className, service }: DeployServiceFormProps) {
  const fetcher = useFetcher();
  const isDeploying = fetcher.state !== "idle";

  return (
    <div className={cn("flex items-center gap-2 flex-wrap", className)}>
      <ServiceChangesModal service={service} />
      <fetcher.Form
        method="post"
        action="./deploy-service"
        className="flex flex-1 md:flex-auto"
      >
        <SubmitButton
          isPending={isDeploying}
          variant="secondary"
          className="w-full"
        >
          {isDeploying ? (
            <>
              <span>Deploying</span>
              <LoaderIcon className="animate-spin" size={15} />
            </>
          ) : (
            "Deploy now"
          )}
        </SubmitButton>
      </fetcher.Form>
    </div>
  );
}
