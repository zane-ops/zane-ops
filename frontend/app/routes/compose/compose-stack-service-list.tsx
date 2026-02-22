import { useQuery } from "@tanstack/react-query";
import { LoaderIcon } from "lucide-react";
import { useFetcher } from "react-router";
import { ComposeStackServiceCard } from "~/components/compose-stack-service-card";
import { SubmitButton } from "~/components/ui/button";
import { composeStackQueries } from "~/lib/queries";
import type { Route } from "./+types/compose-stack-service-list";

export default function ComposeStackServicesPage({
  params,
  matches: {
    2: { loaderData }
  }
}: Route.ComponentProps) {
  const { data: stack } = useQuery({
    ...composeStackQueries.single({
      project_slug: params.projectSlug,
      stack_slug: params.composeStackSlug,
      env_slug: params.envSlug
    }),
    initialData: loaderData.stack
  });

  const services = Object.entries(stack.services).map(
    ([name, service]) => [name, service] as const
  );

  return (
    <>
      {services.length === 0 ? (
        <div className="flex justify-center items-center">
          <div className="flex gap-2 flex-col items-center my-20">
            <h1 className="text-2xl font-bold">No services running</h1>
            <h2 className="text-lg text-grey">
              Your stack has not been deployed yet
            </h2>
            <DeployForm />
          </div>
        </div>
      ) : (
        <div className="grid lg:grid-cols-2 gap-4 mt-8">
          {services.map(([name, service]) => (
            <ComposeStackServiceCard
              key={name}
              name={name}
              service={service}
              urls={stack.urls[name] ?? []}
              stackId={stack.id}
              {...params}
            />
          ))}
        </div>
      )}
    </>
  );
}

function DeployForm() {
  const fetcher = useFetcher();
  const isDeploying = fetcher.state !== "idle";
  return (
    <fetcher.Form method="post" action="./deploy">
      <SubmitButton isPending={isDeploying}>
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
  );
}
