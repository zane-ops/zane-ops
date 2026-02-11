import { useQuery } from "@tanstack/react-query";
import { composeStackQueries } from "~/lib/queries";
import { queryClient } from "~/root";
import type { Route } from "./+types/compose-stack-deployment-list";

export async function clientLoader({
  request,
  params
}: Route.ClientLoaderArgs) {
  const deploymentList = await queryClient.ensureQueryData(
    composeStackQueries.deploymentList({
      project_slug: params.projectSlug,
      env_slug: params.envSlug,
      stack_slug: params.composeStackSlug
    })
  );

  return { deploymentList };
}

export default function ComposeStackDeploymentListPage({
  loaderData,
  params
}: Route.ComponentProps) {
  const { data: deploymentList } = useQuery({
    ...composeStackQueries.deploymentList({
      project_slug: params.projectSlug,
      env_slug: params.envSlug,
      stack_slug: params.composeStackSlug
    }),
    initialData: loaderData.deploymentList
  });

  return <section className="mt-8">compose-stack-deployment-list Page</section>;
}
