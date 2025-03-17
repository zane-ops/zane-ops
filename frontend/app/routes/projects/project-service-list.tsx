import { useQuery } from "@tanstack/react-query";
import { Link, useSearchParams } from "react-router";
import { DockerServiceCard, GitServiceCard } from "~/components/service-cards";
import { Button } from "~/components/ui/button";
import { projectQueries } from "~/lib/queries";
import { queryClient } from "~/root";
import { timeAgoFormatter } from "~/utils";
import { type Route } from "./+types/project-service-list";

export async function clientLoader({
  request,
  params
}: Route.ClientLoaderArgs) {
  const searchParams = new URL(request.url).searchParams;

  const queryString = searchParams.get("query") ?? "";

  const serviceList = await queryClient.ensureQueryData(
    projectQueries.serviceList(params.projectSlug, params.envSlug, {
      query: queryString
    })
  );

  return { serviceList };
}

export default function ProjectServiceListPage({
  params: { projectSlug: project_slug, envSlug: env_slug },
  loaderData
}: Route.ComponentProps) {
  const [searchParams] = useSearchParams();
  const query = searchParams.get("query") ?? "";

  const { data: serviceList } = useQuery({
    ...projectQueries.serviceList(project_slug, env_slug, {
      query
    }),
    initialData: loaderData.serviceList
  });

  return (
    <section className="py-8  grid lg:grid-cols-3 md:grid-cols-2 grid-cols-1 place-content-center  gap-8">
      {serviceList.length === 0 && (
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
                  <Link to="./" prefetch="intent">
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
    </section>
  );
}
