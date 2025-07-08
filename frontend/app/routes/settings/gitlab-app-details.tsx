import { toast } from "sonner";
import { apiClient } from "~/api/client";
import { gitAppsQueries } from "~/lib/queries";
import { queryClient } from "~/root";
import type { Route } from "./+types/gitlab-app-details";

export async function clientLoader({ params }: Route.ClientLoaderArgs) {
  const app = await queryClient.ensureQueryData(
    gitAppsQueries.gitlab(params.id)
  );

  return { app };
}

export default function GitlabAppDetailsPage({}: Route.ComponentProps) {
  return <>gitlab-app-details Page</>;
}

export async function clientAction({
  params,
  request
}: Route.ClientActionArgs) {
  const formData = await request.formData();

  const intent = formData.get("intent")?.toString();

  switch (intent) {
    case "test_gitlab_app_connection": {
      return testGitlabAppConnection(params);
    }
    // case "rename_github_app": {
    //   return renameGithubApp(formData, params);
    // }
    default: {
      throw new Error("Unexpected intent");
    }
  }
}

async function testGitlabAppConnection(
  params: Route.ClientActionArgs["params"]
) {
  const { data, error } = await apiClient.GET(
    "/api/connectors/gitlab/{id}/test/",
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

  const count =
    data.repositories_count < 10_000
      ? data.repositories_count.toLocaleString("en-GB")
      : "10 000+";

  toast.success("Success", {
    description: `Found ${count} repositories`,
    closeButton: true
  });

  return { data };
}
