import { Link, Outlet, createFileRoute } from "@tanstack/react-router";
import {
  ChevronRight,
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

import { Loader } from "~/components/loader";
import {
  Popover,
  PopoverContent,
  PopoverTrigger
} from "~/components/ui/popover";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "~/components/ui/tabs";
import { useDeployDockerServiceMutation } from "~/lib/hooks/use-deploy-docker-service-mutation";
import { useDockerServiceSingleQuery } from "~/lib/hooks/use-docker-service-single-query";
import { formatURL, pluralize } from "~/utils";

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
          <div className="flex flex-col md:flex-row md:items-center gap-4 justify-between">
            <div className="mt-10">
              <h1 className="text-2xl">{service.slug}</h1>
              <p className="flex gap-1 items-center">
                <Container size={15} />
                <span className="text-gray-500 dark:text-gray-400 text-sm">
                  {serviceImage}
                </span>
              </p>
              {service.urls.length > 0 && (
                <div className="flex gap-3 items-center flex-wrap">
                  <a
                    href={formatURL(service.urls[0])}
                    target="_blank"
                    className="underline text-link text-sm"
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
                            isPing={false}
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

            <div className="flex items-center gap-2 flex-wrap">
              {service.unapplied_changes.length > 0 && (
                <Button variant="warning" className="flex-1 md:flex-auto">
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

              <form
                action={() => deploy({})}
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
