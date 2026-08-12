import { useQuery } from "@tanstack/react-query";
import { systemQueries } from "~/lib/queries";
import { getQueryClient } from "~/lib/query-client";
import type { Route } from "./+types/jobs-and-schedules";

export async function clientLoader({}: Route.ClientLoaderArgs) {
  const queryClient = getQueryClient();
  const settings = await queryClient.ensureQueryData(systemQueries.settings);
  return {
    settings
  };
}

export default function JobsAndSchedulesPage({
  loaderData
}: Route.ComponentProps) {
  const { data: settings } = useQuery({
    ...systemQueries.settings,
    initialData: loaderData.settings
  });

  return <>automations Page</>;
}
