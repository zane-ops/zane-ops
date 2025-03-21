import { href, redirect } from "react-router";
import { toast } from "sonner";
import { apiClient } from "~/api/client";
import { projectQueries } from "~/lib/queries";
import type { ErrorResponseFromAPI } from "~/lib/utils";
import { queryClient } from "~/root";
import { getCsrfTokenHeader } from "~/utils";
import type { Route } from "./+types/project-env-variables";

export async function clientLoader({ params }: Route.ClientLoaderArgs) {
  throw redirect(href("/project/:projectSlug/:envSlug", params));
}

export async function clientAction({
  params,
  request
}: Route.ClientActionArgs) {
  const formData = await request.formData();

  const intent = formData.get("intent")?.toString();
  const env_slug = formData.get("env_slug")!.toString();
  const variable_id = formData.get("variable_id")!.toString();

  switch (intent) {
    case "add-env-variable": {
      return addEnvVariable(params.projectSlug, env_slug, formData);
    }
    case "update-env-variable": {
      return updateEnvVariable(
        params.projectSlug,
        env_slug,
        variable_id,
        formData
      );
    }
    case "delete-env-variable": {
      return deleteEnvVariable(params.projectSlug, env_slug, variable_id);
    }
    default: {
      throw new Error("Unexpected intent");
    }
  }
}

async function addEnvVariable(
  project_slug: string,
  env_slug: string,
  formData: FormData
) {
  const userData = {
    key: formData.get("key")!.toString(),
    value: formData.get("value")!.toString()
  };
  const { data, error, response } = await apiClient.POST(
    "/api/projects/{project_slug}/{env_slug}/variables/",
    {
      headers: {
        ...(await getCsrfTokenHeader())
      },
      params: {
        path: {
          env_slug,
          project_slug
        }
      },
      body: userData
    }
  );
  if (error) {
    if (response.status === 409) {
      return {
        errors: {
          errors: [
            {
              attr: "key",
              code: "ERROR",
              detail:
                "Duplicate variable names are not allowed in the same environment"
            }
          ],
          type: "validation_error"
        } satisfies ErrorResponseFromAPI
      };
    }
    return {
      errors: error
    };
  }

  await queryClient.invalidateQueries(projectQueries.single(project_slug));

  toast.success("Success", {
    description: "New variable added to environment",
    closeButton: true
  });

  return { data };
}

async function updateEnvVariable(
  project_slug: string,
  env_slug: string,
  env_id: string,
  formData: FormData
) {
  const userData = {
    key: formData.get("key")!.toString(),
    value: formData.get("value")!.toString()
  };
  const { data, error, response } = await apiClient.PUT(
    "/api/projects/{project_slug}/{env_slug}/variables/{id}/",
    {
      headers: {
        ...(await getCsrfTokenHeader())
      },
      params: {
        path: {
          env_slug,
          project_slug,
          id: env_id
        }
      },
      body: userData
    }
  );
  if (error) {
    if (response.status === 409) {
      return {
        errors: {
          errors: [
            {
              attr: "key",
              code: "ERROR",
              detail:
                "Duplicate variable names are not allowed in the same environment"
            }
          ],
          type: "validation_error"
        } satisfies ErrorResponseFromAPI
      };
    }
    return {
      errors: error
    };
  }

  await queryClient.invalidateQueries(projectQueries.single(project_slug));

  toast.success("Success", {
    description: "Variable updated",
    closeButton: true
  });

  return { data };
}

async function deleteEnvVariable(
  project_slug: string,
  env_slug: string,
  env_id: string
) {
  const { data, error, response } = await apiClient.DELETE(
    "/api/projects/{project_slug}/{env_slug}/variables/{id}/",
    {
      headers: {
        ...(await getCsrfTokenHeader())
      },
      params: {
        path: {
          env_slug,
          project_slug,
          id: env_id
        }
      }
    }
  );

  if (error) {
    return {
      errors: error
    };
  }

  await queryClient.invalidateQueries(projectQueries.single(project_slug));

  toast.success("Success", {
    description: "Variable deleted succesfully.",
    closeButton: true
  });

  return { data };
}
