import { Link, Outlet, createFileRoute } from "@tanstack/react-router";
import {
  Container,
  KeyRound,
  LoaderIcon,
  Rocket,
  Settings,
  TriangleAlert
} from "lucide-react";
import { withAuthRedirect } from "~/components/helper/auth-redirect";
import { MetaTitle } from "~/components/meta-title";
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
  Tooltip,
  TooltipContent,
  TooltipProvider,
  TooltipTrigger
} from "~/components/ui/tooltip";

import { useMutation } from "@tanstack/react-query";
import { type RequestInput, apiClient } from "~/api/client";
import { Loader } from "~/components/loader";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "~/components/ui/tabs";
import { useDeployDockerServiceMutation } from "~/lib/hooks/use-deploy-service-mutation";
import { useDockerServiceSingleQuery } from "~/lib/hooks/use-docker-service-single-query";
import { formatURL, getCsrfTokenHeader, pluralize } from "~/utils";

export const Route = createFileRoute(
  "/_dashboard/project/$project_slug/services/docker/$service_slug"
)({
  component: withAuthRedirect(ServiceDetailsLayout)
});

function ServiceDetailsLayout() {
  const { project_slug, service_slug } = Route.useParams();
  const serviceSingleQuery = useDockerServiceSingleQuery(
    project_slug,
    service_slug
  );
  const { isPending: isDeploying, mutate: deploy } =
    useDeployDockerServiceMutation(project_slug, service_slug);

  const baseUrl = `/project/${project_slug}/services/docker/${service_slug}`;
  const service = serviceSingleQuery.data?.data;
  let serviceImage =
    service?.image ??
    (service?.unapplied_changes.filter((change) => change.field === "image")[0]
      ?.new_value as string);

  if (serviceImage && !serviceImage.includes(":")) {
    serviceImage += ":latest";
  }
  let extraServiceUrls: NonNullable<typeof service>["urls"] = [];
  let _;
  if (service && service.urls.length > 1) {
    [_, ...extraServiceUrls] = service.urls;
  }

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
              <Link to={`/project/${project_slug}/`}>{project_slug}</Link>
            </BreadcrumbLink>
          </BreadcrumbItem>

          <BreadcrumbSeparator />
          <BreadcrumbItem>
            <BreadcrumbPage>{service_slug}</BreadcrumbPage>
          </BreadcrumbItem>
        </BreadcrumbList>
      </Breadcrumb>
      {serviceSingleQuery.isLoading ? (
        <>
          <div className="col-span-full">
            <Loader className="h-[70vh]" />
          </div>
        </>
      ) : service === undefined ? (
        <>
          <section className="col-span-full ">
            <MetaTitle title="404 - Service does not exist" />
            <div className="flex flex-col gap-5 h-[70vh] items-center justify-center">
              <div className="flex-col flex gap-3 items-center">
                <h1 className="text-3xl font-bold">Error 404</h1>
                <p className="text-lg">This service does not exist</p>
              </div>
              <Link to="/">
                <Button>Go home</Button>
              </Link>
            </div>
          </section>
        </>
      ) : (
        <>
          <MetaTitle title={service.slug} />
          <div className="flex items-center justify-between">
            <div className="mt-10">
              <h1 className="text-2xl">{service.slug}</h1>
              <p className="flex gap-1 items-center">
                <Container size={15} />
                <span className="text-gray-500 dark:text-gray-400 text-sm">
                  {serviceImage}
                </span>
              </p>
              {service.urls.length > 0 && (
                <div className="flex gap-3 items-center">
                  <a
                    href={formatURL(service.urls[0])}
                    target="_blank"
                    className="underline text-link text-sm"
                  >
                    {formatURL(service.urls[0])}
                  </a>
                  {service.urls.length > 1 && (
                    <TooltipProvider>
                      <Tooltip delayDuration={0}>
                        <TooltipTrigger asChild>
                          <span>
                            <StatusBadge
                              className="relative top-0.5 text-xs"
                              color="gray"
                              isPing={false}
                            >
                              <span>
                                {`+${service.urls.length - 1} ${pluralize("url", service.urls.length - 1)}`}
                              </span>
                            </StatusBadge>
                          </span>
                        </TooltipTrigger>
                        <TooltipContent
                          align="end"
                          side="right"
                          className="px-4 py-3"
                        >
                          <ul>
                            {extraServiceUrls.map((url) => (
                              <li key={url.id}>
                                <a
                                  href={formatURL(url)}
                                  target="_blank"
                                  className="underline text-link text-sm"
                                >
                                  {formatURL(url)}
                                </a>
                              </li>
                            ))}
                          </ul>
                        </TooltipContent>
                      </Tooltip>
                    </TooltipProvider>
                  )}
                </div>
              )}
            </div>

            <div className="flex items-center gap-2">
              {service.unapplied_changes.length > 0 && (
                <Button variant="warning">
                  <TriangleAlert size={15} />
                  <span className="mx-1">
                    {service.unapplied_changes.length}{" "}
                    {pluralize(
                      "unapplied change",
                      service.unapplied_changes.length
                    )}
                  </span>
                </Button>
              )}

              <form action={() => deploy({})}>
                <SubmitButton
                  isPending={isDeploying}
                  variant="secondary"
                  className="inline-flex gap-1 items-center"
                >
                  {isDeploying ? (
                    <>
                      <span>Deploying</span>
                      <LoaderIcon className="animate-spin" size={15} />
                    </>
                  ) : (
                    "Deploy"
                  )}
                </SubmitButton>
              </form>
            </div>
          </div>
          <Tabs defaultValue="deployment" className="w-full mt-5">
            <TabsList className="w-full items-start justify-start bg-background rounded-none border-b border-border">
              <TabsTrigger value="deployment" asChild>
                <Link className="flex gap-2 items-center" to={baseUrl}>
                  Deployments <Rocket size={15} />
                </Link>
              </TabsTrigger>

              <TabsTrigger value="envVariable">
                <Link
                  className="flex gap-2 items-center"
                  to={`${baseUrl}/env-variables`}
                >
                  Env Variables <KeyRound size={15} />
                </Link>
              </TabsTrigger>

              <TabsTrigger value="settings">
                <Link
                  className="flex gap-2 items-center"
                  to={`${baseUrl}/settings`}
                >
                  Settings <Settings size={15} />
                </Link>
              </TabsTrigger>
            </TabsList>

            <TabsContent value="deployment">
              <Outlet />
            </TabsContent>

            <TabsContent value="envVariable">
              <Outlet />
            </TabsContent>
            <TabsContent value="settings">
              <Outlet />
            </TabsContent>
          </Tabs>
        </>
      )}
    </>
  );
}
