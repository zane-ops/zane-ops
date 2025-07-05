import { href, redirect } from "react-router";
import { toast } from "sonner";
import { type RequestInput, apiClient } from "~/api/client";
import { gitAppsQueries } from "~/lib/queries";
import { queryClient } from "~/root";
import { getCsrfTokenHeader } from "~/utils";
import type { Route } from "./+types/github-app-details";

export function clientLoader({ params }: Route.ClientLoaderArgs) {
  throw redirect(href("/settings/git-apps"));
}

export async function clientAction({
  params,
  request
}: Route.ClientActionArgs) {
  const formData = await request.formData();

  const intent = formData.get("intent")?.toString();

  switch (intent) {
    case "test_github_app_connection": {
      return testGithubAppConnection(params);
    }
    case "rename_github_app": {
      return renameGithubApp(formData, params);
    }
    default: {
      throw new Error("Unexpected intent");
    }
  }
}

async function testGithubAppConnection(
  params: Route.ClientActionArgs["params"]
) {
  const { data, error } = await apiClient.GET(
    "/api/connectors/github/{id}/test/",
    {
      params: {
        path: params
      }
    }
  );

  if (error) {
    const fullErrorMessage = error.errors.map((err) => err.detail).join(" ");

    toast.error("Error", {
      description: fullErrorMessage,
      closeButton: true
    });
    return { errors: error };
  }

  toast.success("Success", {
    description: `Found ${data.repositories_count} repositories`,
    closeButton: true
  });

  return { data };
}

async function renameGithubApp(
  formData: FormData,
  params: Route.ClientActionArgs["params"]
) {
  const userData = {
    name: formData.get("name")?.toString()
  } satisfies RequestInput<"patch", "/api/connectors/github/{id}/">;

  const { data, error } = await apiClient.PATCH(
    "/api/connectors/github/{id}/",
    {
      headers: {
        ...(await getCsrfTokenHeader())
      },
      params: {
        path: params
      },
      body: userData
    }
  );

  if (error) {
    const fullErrorMessage = error.errors.map((err) => err.detail).join(" ");

    toast.error("Error", {
      description: fullErrorMessage,
      closeButton: true
    });
    return { errors: error };
  }

  await queryClient.invalidateQueries({
    predicate(query) {
      return query.queryKey.includes(gitAppsQueries.list.queryKey[0]);
    }
  });

  toast.success("Success", {
    description: `Succesfully renamed the GitHub app`,
    closeButton: true
  });
  return { data };
}
