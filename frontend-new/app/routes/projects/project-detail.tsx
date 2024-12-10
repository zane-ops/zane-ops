import { useQuery } from "@tanstack/react-query";
import { LoaderIcon, PlusIcon, Search } from "lucide-react";
import * as React from "react";
import {
  Link,
  isRouteErrorResponse,
  useRouteError,
  useSearchParams
} from "react-router";
import { useSpinDelay } from "spin-delay";
import { useDebouncedCallback } from "use-debounce";
import { DockerServiceCard, GitServiceCard } from "~/components/service-cards";
import {
  Breadcrumb,
  BreadcrumbItem,
  BreadcrumbLink,
  BreadcrumbList,
  BreadcrumbPage,
  BreadcrumbSeparator
} from "~/components/ui/breadcrumb";
import { Button } from "~/components/ui/button";
import { Input } from "~/components/ui/input";
import { Separator } from "~/components/ui/separator";
import { SPIN_DELAY_DEFAULT_OPTIONS } from "~/lib/constants";
import { isNotFoundError, notFound } from "~/lib/helpers";
import { projectQueries } from "~/lib/queries";
import { queryClient } from "~/root";
import { metaTitle, timeAgoFormatter } from "~/utils";
import { type Route } from "./+types/project-detail";

export function meta({ error }: Route.MetaArgs) {
  const title = !error
    ? `Project Detail`
    : isNotFoundError(error)
      ? "Error 404 - Project does not exist"
      : "Oops";
  return [metaTitle(title)] satisfies ReturnType<Route.MetaFunction>;
}

export async function clientLoader({
  request,
  params
}: Route.ClientLoaderArgs) {
  const searchParams = new URL(request.url).searchParams;

  const queryString = searchParams.get("query") ?? "";

  let project = queryClient.getQueryData(
    projectQueries.single(params.projectSlug).queryKey
  );

  if (!project) {
    // fetch the data on first load to prevent showing the loading fallback
    [project] = await Promise.all([
      queryClient.ensureQueryData(projectQueries.single(params.projectSlug)),
      queryClient.ensureQueryData(
        projectQueries.serviceList(params.projectSlug, {
          query: queryString
        })
      )
    ]);
  }

  return { project };
}

export default function ProjectDetail({
  params,
  loaderData
}: Route.ComponentProps) {
  const { projectSlug: slug } = params;

  const { data: project } = useQuery({
    ...projectQueries.single(params.projectSlug),
    initialData: loaderData.project
  });
  const [searchParams, setSearchParams] = useSearchParams();
  const query = searchParams.get("query") ?? "";

  const projectServiceListQuery = useQuery(
    projectQueries.serviceList(slug, {
      query
    })
  );
  const serviceList = projectServiceListQuery.data?.data;

  const filterServices = useDebouncedCallback((query: string) => {
    searchParams.set("query", query);
    setSearchParams(searchParams, { replace: true });
  }, 300);

  const isFetchingServices = useSpinDelay(
    projectServiceListQuery.isFetching,
    SPIN_DELAY_DEFAULT_OPTIONS
  );

  const inputRef = React.useRef<React.ComponentRef<"input">>(null);

  return (
    <main>
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
            <BreadcrumbPage>{slug}</BreadcrumbPage>
          </BreadcrumbItem>
        </BreadcrumbList>
      </Breadcrumb>
      <>
        <div className="flex items-center md:flex-nowrap lg:my-0 md:my-1 my-5 flex-wrap  gap-3 justify-between ">
          <div className="flex items-center gap-4">
            <h1 className="text-3xl font-medium">{project.slug}</h1>

            <Button asChild variant="secondary" className="flex gap-2">
              <Link to="create-service" prefetch="intent">
                New Service <PlusIcon size={18} />
              </Link>
            </Button>
          </div>
          <div className="flex my-3 flex-wrap w-full md:w-auto  justify-end items-center md:gap-3 gap-1">
            <div className="flex md:my-5 w-full items-center">
              {isFetchingServices ? (
                <LoaderIcon
                  size={20}
                  className="animate-spin relative left-4"
                />
              ) : (
                <Search size={20} className="relative left-4" />
              )}
              <Input
                onChange={(e) => filterServices(e.currentTarget.value)}
                defaultValue={query}
                className="pl-14 pr-5 -mx-5 w-full my-1 text-sm focus-visible:right-0"
                placeholder="Ex: ZaneOps"
                ref={inputRef}
              />
            </div>
          </div>
        </div>

        <Separator />
        <div className="py-8  grid lg:grid-cols-3 md:grid-cols-2 grid-cols-1 place-content-center  gap-8">
          {serviceList?.length === 0 && (
            <section className="flex gap-3 h-96 col-span-full flex-col items-center justify-center grow py-20">
              <div className="text-center">
                {query.length > 0 ? (
                  <div className="flex flex-col gap-2 items-center">
                    <h2 className="text-2xl font-medium">
                      No services match the filter criteria
                    </h2>
                    <h3 className="text-lg text-gray-500">
                      Your search for`{query}` did not return any results.
                    </h3>
                    <Button asChild variant="outline">
                      <Link
                        to="."
                        onClick={() => {
                          if (inputRef.current) {
                            inputRef.current.value = "";
                          }
                        }}
                      >
                        Clear filters
                      </Link>
                    </Button>
                  </div>
                ) : (
                  <>
                    <div>
                      <h1 className="text-2xl font-bold">
                        No services found in this project
                      </h1>
                      <h2 className="text-lg">
                        Would you like to start by creating one?
                      </h2>
                    </div>
                    <Button asChild>
                      <Link to={`create-service`}>Create a new service</Link>
                    </Button>
                  </>
                )}
              </div>
            </section>
          )}

          {serviceList?.map((service) => {
            if (service.type === "docker") {
              return (
                <DockerServiceCard
                  slug={service.slug}
                  image={service.image}
                  key={service.id}
                  tag={service.tag}
                  volumeNumber={service.volume_number}
                  status={service.status}
                  updatedAt={timeAgoFormatter(service.updated_at)}
                  url={service.url}
                />
              );
            }

            return (
              <GitServiceCard
                slug={service.slug}
                branchName={service.branch}
                repository={service.repository}
                status={service.status}
                key={service.id}
                updatedAt={timeAgoFormatter(service.updated_at)}
                lastCommitMessage={service.last_commit_message}
                url={service.url}
              />
            );
          })}
        </div>
      </>
    </main>
  );
}

export function ErrorBoundary() {
  const error = useRouteError();

  // when true, this is what used to go to `CatchBoundary`
  if (isRouteErrorResponse(error) && error.status === 404) {
    return (
      <section className="col-span-full ">
        <div className="flex flex-col gap-5 h-[70vh] items-center justify-center">
          <div className="flex-col flex gap-3 items-center">
            <h1 className="text-3xl font-bold">Error 404</h1>
            <p className="text-lg">This project does not exist</p>
          </div>
          <Link to="/">
            <Button>Go home</Button>
          </Link>
        </div>
      </section>
    );
  }

  throw error;
}
