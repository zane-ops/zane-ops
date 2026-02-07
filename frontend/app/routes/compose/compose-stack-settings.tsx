import { useQuery } from "@tanstack/react-query";
import { composeStackQueries } from "~/lib/queries";
import type { Route } from "./+types/compose-stack-settings";

export default function ComposeStackSettingsPage({
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

  return <div className="mt-8">compose-stack-settings Page</div>;
}
