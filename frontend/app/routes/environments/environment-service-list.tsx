import * as Dialog from "@radix-ui/react-dialog";
import { PopoverContent } from "@radix-ui/react-popover";
import { useQuery } from "@tanstack/react-query";
import {
  ChevronUpIcon,
  LoaderIcon,
  PauseIcon,
  PlayIcon,
  RocketIcon
} from "lucide-react";
import * as React from "react";
import { Link, href, useFetcher, useSearchParams } from "react-router";
import { toast } from "sonner";
import { DockerServiceCard, GitServiceCard } from "~/components/service-cards";
import { Button, SubmitButton } from "~/components/ui/button";
import { Popover, PopoverTrigger } from "~/components/ui/popover";
import { environmentQueries } from "~/lib/queries";
import { cn } from "~/lib/utils";
import { queryClient } from "~/root";
import { timeAgoFormatter } from "~/utils";
import { type Route } from "./+types/environment-service-list";

export async function clientLoader({
  request,
  params
}: Route.ClientLoaderArgs) {
  const searchParams = new URL(request.url).searchParams;

  const queryString = searchParams.get("query") ?? "";

  const serviceList = await queryClient.ensureQueryData(
    environmentQueries.serviceList(params.projectSlug, params.envSlug, {
      query: queryString
    })
  );

  return { serviceList };
}

export default function EnvironmentServiceListPage({
  params: { projectSlug: project_slug, envSlug: env_slug },
  loaderData
}: Route.ComponentProps) {
  const [searchParams] = useSearchParams();
  const query = searchParams.get("query") ?? "";

  const { data: serviceList = loaderData.serviceList } = useQuery({
    ...environmentQueries.serviceList(project_slug, env_slug, {
      query
    }),
    initialData: loaderData.serviceList
  });

  const [selectedServiceIds, setSelectedServiceIds] = React.useState<
    Array<string>
  >([]);
  const allServiceIds = serviceList.map((service) => service.id);

  const fetcher = useFetcher();

  React.useEffect(() => {
    if (fetcher.state === "idle" && fetcher.data?.success) {
      setSelectedServiceIds([]);
      toast.dismiss("service-selection");
      return;
    }
  }, [fetcher.state, fetcher.data]);

  React.useEffect(() => {
    if (selectedServiceIds.length > 0) {
      toast(
        <div className="dark:bg-card rounded-md flex items-center justify-between gap-2 w-full text-card-foreground">
          <strong>{selectedServiceIds.length} selected</strong>
          <div className="flex items-center gap-2">
            <Popover>
              <PopoverTrigger asChild>
                <Button
                  size="xs"
                  variant="outline"
                  className="inline-flex items-center"
                >
                  <span>actions</span>
                  <ChevronUpIcon
                    size={15}
                    className="text-grey relative -right-1"
                  />
                </Button>
              </PopoverTrigger>
              <PopoverContent
                side="top"
                sideOffset={5}
                className={cn(
                  "flex flex-col gap-0 p-2",
                  "z-50 rounded-md border border-border bg-popover text-popover-foreground shadow-md outline-hidden",
                  "data-[state=open]:animate-in data-[state=closed]:animate-out data-[state=closed]:fade-out-0 data-[state=open]:fade-in-0 data-[state=closed]:zoom-out-95 data-[state=open]:zoom-in-95",
                  "data-[side=bottom]:slide-in-from-top-2 data-[side=left]:slide-in-from-right-2 data-[side=right]:slide-in-from-left-2 data-[side=top]:slide-in-from-bottom-2"
                )}
              >
                <fetcher.Form
                  method="post"
                  className="bg-popover flex flex-col items-stretch"
                  action={href(
                    "/project/:projectSlug/:envSlug/bulk-deploy-services",
                    {
                      envSlug: env_slug,
                      projectSlug: project_slug
                    }
                  )}
                >
                  {selectedServiceIds.map((id) => (
                    <input
                      key={id}
                      type="hidden"
                      name="service_id"
                      value={id}
                    />
                  ))}
                  <SubmitButton
                    isPending={fetcher.state !== "idle"}
                    variant="ghost"
                    size="sm"
                    className="flex items-center gap-2 justify-start dark:text-card-foreground"
                  >
                    {fetcher.state !== "idle" ? (
                      <LoaderIcon className="animate-spin" size={15} />
                    ) : (
                      <RocketIcon size={15} className="flex-none" />
                    )}
                    <span>Deploy services</span>
                  </SubmitButton>
                </fetcher.Form>
                <fetcher.Form
                  method="post"
                  className="bg-popover flex flex-col items-stretch"
                  action={href(
                    "/project/:projectSlug/:envSlug/bulk-toggle-service-state",
                    {
                      envSlug: env_slug,
                      projectSlug: project_slug
                    }
                  )}
                >
                  {selectedServiceIds.map((id) => (
                    <input
                      key={id}
                      type="hidden"
                      name="service_id"
                      value={id}
                    />
                  ))}
                  <SubmitButton
                    isPending={fetcher.state !== "idle"}
                    variant="ghost"
                    size="sm"
                    name="desired_state"
                    value="start"
                    className="flex items-center gap-2 justify-start text-grey dark:text-foreground"
                  >
                    {fetcher.state !== "idle" ? (
                      <LoaderIcon className="animate-spin" size={15} />
                    ) : (
                      <PlayIcon size={15} className="flex-none" />
                    )}
                    <span>Restart services</span>
                  </SubmitButton>

                  <input type="hidden" name="desired_state" value="stop" />
                  <SubmitButton
                    isPending={fetcher.state !== "idle"}
                    variant="ghost"
                    size="sm"
                    className="flex items-center gap-2 justify-start text-amber-600 dark:text-yellow-500"
                  >
                    {fetcher.state !== "idle" ? (
                      <LoaderIcon className="animate-spin" size={15} />
                    ) : (
                      <PauseIcon size={15} className="flex-none" />
                    )}
                    <span>Stop services</span>
                  </SubmitButton>
                </fetcher.Form>
              </PopoverContent>
            </Popover>
            <Button
              size="xs"
              variant="ghost"
              onClick={() => {
                setSelectedServiceIds([...allServiceIds]);
              }}
            >
              Select all
            </Button>
            <button
              className="underline relative"
              onClick={() => {
                setSelectedServiceIds([]);
              }}
            >
              cancel
            </button>
          </div>
        </div>,
        {
          duration: Infinity,
          id: "service-selection",
          dismissible: false
        }
      );
    } else {
      toast.dismiss("service-selection");
    }
  }, [
    selectedServiceIds,
    fetcher.state,
    allServiceIds,
    env_slug,
    project_slug
  ]);

  React.useEffect(() => {
    return () => {
      toast.dismiss("service-selection");
    };
  }, []);

  return (
    <>
      <section className="py-8 grid lg:grid-cols-3 md:grid-cols-2 grid-cols-1 place-content-center  gap-8">
        {serviceList.length === 0 && (
          <section className="flex gap-3 h-96 col-span-full flex-col items-center justify-center grow py-20">
            <div className="flex flex-col gap-2 items-center text-center">
              {query.length > 0 ? (
                <>
                  <h2 className="text-2xl font-medium">
                    No services match the filter criteria
                  </h2>
                  <h3 className="text-lg text-gray-500">
                    Your search for <em>`{query}`</em> did not return any
                    results.
                  </h3>
                  <Button asChild variant="outline">
                    <Link to="./" prefetch="intent" replace>
                      Clear filters
                    </Link>
                  </Button>
                </>
              ) : (
                <>
                  <h1 className="text-2xl font-bold">
                    No services found in this environment
                  </h1>
                  <h2 className="text-lg">
                    Would you like to start by creating one?
                  </h2>
                  <Button asChild>
                    <Link to="./create-service" prefetch="intent">
                      Create a new service
                    </Link>
                  </Button>
                </>
              )}
            </div>
          </section>
        )}

        {serviceList.map((service) => {
          if (service.type === "docker") {
            return (
              <DockerServiceCard
                slug={service.slug}
                image={service.image}
                key={service.id}
                tag={service.tag}
                volumeNumber={service.volume_number}
                status={service.status}
                selected={selectedServiceIds.includes(service.id)}
                updatedAt={timeAgoFormatter(service.updated_at)}
                url={service.url}
                id={service.id}
                onToggleSelect={(id) => {
                  setSelectedServiceIds((selectedServiceIds) => {
                    if (selectedServiceIds.includes(id)) {
                      return selectedServiceIds.filter(
                        (serviceId) => serviceId !== id
                      );
                    } else {
                      return [...selectedServiceIds, id];
                    }
                  });
                }}
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
              id={service.id}
              updatedAt={timeAgoFormatter(service.updated_at)}
              selected={selectedServiceIds.includes(service.id)}
              lastCommitMessage={service.last_commit_message}
              url={service.url}
              git_provider={service.git_provider}
              onToggleSelect={(id) => {
                setSelectedServiceIds((selectedServiceIds) => {
                  if (selectedServiceIds.includes(id)) {
                    return selectedServiceIds.filter(
                      (serviceId) => serviceId !== id
                    );
                  } else {
                    return [...selectedServiceIds, id];
                  }
                });
              }}
            />
          );
        })}
      </section>
    </>
  );
}
