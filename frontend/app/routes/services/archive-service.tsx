import { redirect } from "react-router";
import { toast } from "sonner";
import { apiClient } from "~/api/client";
import { projectQueries, resourceQueries, serviceQueries } from "~/lib/queries";
import type { ErrorResponseFromAPI } from "~/lib/utils";
import { queryClient } from "~/root";
import { getCsrfTokenHeader } from "~/utils";
import { type Route } from "./+types/archive-service";

export function clientLoader({ params }: Route.ClientLoaderArgs) {
  throw redirect(
    `/project/${params.projectSlug}/services/${params.serviceSlug}/settings`
  );
}

export async function clientAction({
  request,
  params: { projectSlug: project_slug, serviceSlug: service_slug }
}: Route.ClientActionArgs) {
  const formData = await request.formData();

  console.log({
    service_slug: formData.get("service_slug")?.toString().trim()
  });
  if (
    formData.get("service_slug")?.toString().trim() !==
    `${project_slug}/${service_slug}`
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
    "/api/projects/{project_slug}/archive-service/docker/{service_slug}/",
    {
      headers: {
        ...(await getCsrfTokenHeader())
      },
      params: {
        path: {
          project_slug,
          service_slug
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
    queryKey: serviceQueries.single({ project_slug, service_slug }).queryKey
  });
  queryClient.invalidateQueries(projectQueries.serviceList(project_slug));
  queryClient.invalidateQueries({
    predicate: (query) =>
      query.queryKey[0] === resourceQueries.search().queryKey[0]
  });

  toast.success("Success", {
    closeButton: true,
    description: (
      <span>
        Service `<strong>{service_slug}</strong>` has been succesfully deleted.
      </span>
    )
  });
  throw redirect(`/project/${project_slug}`);
}
