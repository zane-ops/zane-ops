import { useQuery } from "@tanstack/react-query";
import { Navigate, href } from "react-router";
import { composeStackQueries } from "~/lib/queries";
import type { Route } from "./+types/compose-stack-service-details";

export default function ComposeStackServiceDetailsPage({
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
  const serviceFound = Object.entries(stack.services).find(
    ([name]) => name === params.serviceSlug
  );

  if (!serviceFound) {
    return (
      <Navigate
        to={href(
          "/project/:projectSlug/:envSlug/compose-stacks/:composeStackSlug",
          params
        )}
      />
    );
  }
  const [, service] = serviceFound;

  return <>compose-stack-service-details Page</>;
}
