import { href, redirect } from "react-router";
import { toast } from "sonner";
import { type RequestInput, apiClient } from "~/api/client";
import { gitAppsQueries } from "~/lib/queries";
import { getQueryClient } from "~/lib/query-client";
import { getCsrfTokenHeader } from "~/lib/utils";
import { getCurrentWorkspace } from "~/lib/workspace-store";
import type { Route } from "./+types/github-app-details";

export function clientLoader() {
  throw redirect(href("/settings/git-apps"));
}

export async function clientAction({
  params,
  request
}: Route.ClientActionArgs) {
  const queryClient = getQueryClient();
  const { id: workspaceId } = await getCurrentWorkspace(queryClient);
  const formData = await request.formData();

  const intent = formData.get("intent")?.toString();

  switch (intent) {
    case "test_github_app_connection": {
      return testGithubAppConnection(params);
    }
    case "rename_github_app": {
      return renameGithubApp(formData, params, workspaceId);
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
  params: Route.ClientActionArgs["params"],
  workspaceId: string
) {
  const queryClient = getQueryClient();
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
    queryKey: gitAppsQueries.list(workspaceId).queryKey
  });

  toast.success("Success", {
    description: `Succesfully renamed the GitHub app`,
    closeButton: true
  });
  return { data };
}
