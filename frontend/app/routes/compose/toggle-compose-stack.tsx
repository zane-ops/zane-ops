import { href, redirect } from "react-router";
import { toast } from "sonner";
import { type RequestInput, apiClient } from "~/api/client";
import { getComposeStackStatus } from "~/components/compose-stack-cards";
import { composeStackQueries } from "~/lib/queries";
import { queryClient } from "~/root";
import { durationToMs, getCsrfTokenHeader, wait } from "~/utils";
import type { Route } from "./+types/toggle-compose-stack";

export async function clientLoader({ params }: Route.ClientLoaderArgs) {
  throw redirect(
    href(
      "/project/:projectSlug/:envSlug/compose-stacks/:composeStackSlug",
      params
    )
  );
}

export type ToggleStackState = RequestInput<
  "put",
  "/api/compose/stacks/{project_slug}/{env_slug}/{slug}/toggle/"
>["desired_state"];

export async function clientAction({
  request,
  params: {
    projectSlug: project_slug,
    composeStackSlug: stack_slug,
    envSlug: env_slug
  }
}: Route.ClientActionArgs) {
  const formData = await request.formData();

  const userData = {
    desired_state: formData.get("desired_state")?.toString() as "start" | "stop"
  } satisfies RequestInput<
    "put",
    "/api/compose/stacks/{project_slug}/{env_slug}/{slug}/toggle/"
  >;

  const { error, data } = await apiClient.PUT(
    "/api/compose/stacks/{project_slug}/{env_slug}/{slug}/toggle/",
    {
      headers: {
        ...(await getCsrfTokenHeader())
      },
      body: userData,
      params: {
        path: {
          project_slug,
          env_slug,
          slug: stack_slug
        }
      }
    }
  );

  if (error) {
    const fullErrorMessage = error.errors.map((err) => err.detail).join(" ");

    toast.error("Error", {
      description: fullErrorMessage,
      closeButton: true
    });
    return {
      errors: error
    };
  }

  await queryClient.invalidateQueries(
    composeStackQueries.single({ project_slug, stack_slug, env_slug })
  );

  return { data: { queued: true } };
}
