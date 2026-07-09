import { href, redirect } from "react-router";
import { toast } from "sonner";
import { apiClient } from "~/api/client";
import {
  environmentQueries,
  resourceQueries,
  serviceQueries,
  userQueries
} from "~/lib/queries";
import { getQueryClient } from "~/lib/query-client";
import type { ErrorResponseFromAPI } from "~/lib/utils";
import { getCsrfTokenHeader } from "~/utils";
import type { Route } from "./+types/archive-docker-service";

export function clientLoader({ params }: Route.ClientLoaderArgs) {
  throw redirect(
    href("/project/:projectSlug/:envSlug/services/:serviceSlug/settings", {
      ...params
    })
  );
}

export async function clientAction({
  request,
  params: {
    projectSlug: project_slug,
    serviceSlug: service_slug,
    envSlug: env_slug
  }
}: Route.ClientActionArgs) {
  const queryClient = getQueryClient();
  const { id: workspaceId } = (await queryClient.ensureQueryData(
    userQueries.currentWorkspace
  ))!;
  const formData = await request.formData();

  if (
    formData.get("service_slug")?.toString().trim() !==
    `${project_slug}/${env_slug}/${service_slug}`
  ) {
    return {
      errors: {
        type: "validation_error",
        errors: [
          {
            attr: "service_slug",
            code: "invalid",
            detail: "The slug does not match"
          }
        ]
      } satisfies ErrorResponseFromAPI
    };
  }

  const { error } = await apiClient.DELETE(
    "/api/projects/{project_slug}/{env_slug}/archive-service/docker/{service_slug}/",
    {
      headers: {
        ...(await getCsrfTokenHeader())
      },
      params: {
        path: {
          project_slug,
          service_slug,
          env_slug
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
    return;
  }

  queryClient.removeQueries({
    queryKey: serviceQueries.single({
      workspaceId,
      project_slug,
      service_slug,
      env_slug
    }).queryKey
  });
  queryClient.invalidateQueries(
    environmentQueries.serviceList(workspaceId, project_slug, env_slug)
  );
  queryClient.invalidateQueries({
    queryKey: resourceQueries.search(workspaceId).queryKey.slice(0, 3)
  });

  toast.success("Success", {
    closeButton: true,
    description: (
      <span>
        Service `<strong>{service_slug}</strong>` has been succesfully deleted.
      </span>
    )
  });
  throw redirect(
    href("/project/:projectSlug/:envSlug", {
      projectSlug: project_slug,
      envSlug: env_slug
    })
  );
}
