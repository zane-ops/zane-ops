import { useQuery } from "@tanstack/react-query";
import { AlertCircleIcon, GitlabIcon, LoaderIcon } from "lucide-react";
import React from "react";
import { redirect, useFetcher } from "react-router";
import { toast } from "sonner";
import { type RequestInput, apiClient } from "~/api/client";
import { GitlabLogo } from "~/components/gitlab-logo";
import { Alert, AlertDescription, AlertTitle } from "~/components/ui/alert";
import { SubmitButton } from "~/components/ui/button";
import {
  FieldSet,
  FieldSetInput,
  FieldSetLabel,
  FieldSetPasswordToggleInput
} from "~/components/ui/fieldset";
import { Separator } from "~/components/ui/separator";
import { ensureMinRole, gitAppsQueries } from "~/lib/queries";
import { getQueryClient } from "~/lib/query-client";
import {
  getCsrfTokenHeader,
  getFormErrorsFromResponseData,
  metaTitle
} from "~/lib/utils";
import {
  getCurrentWorkspace,
  useCurrentWorkspace
} from "~/lib/workspace-store";
import type { Route } from "./+types/gitlab-app-details";

export function meta() {
  return [
    metaTitle("Update Gitlab app")
  ] satisfies ReturnType<Route.MetaFunction>;
}

export async function clientLoader({ params }: Route.ClientLoaderArgs) {
  const queryClient = getQueryClient();
  await ensureMinRole(queryClient, "Admin");
  const { id: workspaceId } = await getCurrentWorkspace(queryClient);
  const app = await queryClient.ensureQueryData(
    gitAppsQueries.gitlab(workspaceId, params.id)
  );
  return { app };
}

export default function GitlabAppDetailsPage({
  loaderData,
  params
}: Route.ComponentProps) {
  const { id: workspaceId } = useCurrentWorkspace();

  const { data: app } = useQuery({
    ...gitAppsQueries.gitlab(workspaceId, params.id),
    initialData: loaderData.app
  });

  return (
    <section className="flex flex-col gap-4">
      <div className="flex items-center gap-2">
        <div className="max-w-5 max-h-5 flex items-center flex-none justify-center">
          <GitlabLogo className="flex-none size-10 [&_path]:fill-orange-400!" />
        </div>

        <h2 className="text-2xl">Edit Gitlab app</h2>
      </div>
      <Separator />

      <p className="text-grey">Update gitlab app credentials.</p>

      <EditGitlabAppForm app={app} />
    </section>
  );
}

type EditGitlabAppFormProps = Route.ComponentProps["loaderData"];

function EditGitlabAppForm({ app }: EditGitlabAppFormProps) {
  const fetcher = useFetcher<typeof clientAction>();
  const formRef = React.useRef<React.ComponentRef<"form">>(null);

  const errors = getFormErrorsFromResponseData(fetcher.data?.errors);

  React.useEffect(() => {
    // only focus on the correct input in case of error
    if (fetcher.state === "idle" && fetcher.data) {
      if (fetcher.data.errors) {
        const errors = getFormErrorsFromResponseData(fetcher.data.errors);
        const key = Object.keys(errors ?? {})[0];
        const field = formRef.current?.elements.namedItem(
          key
        ) as HTMLInputElement;
        field?.focus();
        return;
      }
      formRef.current?.reset();
    }
  }, [fetcher.state, fetcher.data]);

  return (
    <>
      {errors.non_field_errors && (
        <Alert variant="destructive" className="my-2">
          <AlertCircleIcon className="h-4 w-4" />
          <AlertTitle>Error</AlertTitle>
          <AlertDescription>{errors.non_field_errors}</AlertDescription>
        </Alert>
      )}

      <fetcher.Form method="post" className="flex flex-col gap-4 items-start">
        <FieldSet
          className="w-full md:w-4/5 flex flex-col gap-1"
          required
          name="name"
          errors={errors.name}
        >
          <FieldSetLabel className="flex items-center gap-0.5">
            Name
          </FieldSetLabel>
          <FieldSetInput
            defaultValue={app.name}
            autoFocus
            placeholder="ex: zn-gitlab"
          />
        </FieldSet>
        <FieldSet
          className="w-full md:w-4/5 flex flex-col gap-1"
          required
          name="app_id"
        >
          <FieldSetLabel className="flex items-center gap-0.5">
            Application ID
          </FieldSetLabel>
          <FieldSetInput
            disabled
            value={app.app_id}
            readOnly
            className="bg-muted"
          />
        </FieldSet>

        <FieldSet
          className="w-full md:w-4/5 flex flex-col gap-1"
          name="app_secret"
          errors={errors.app_secret}
        >
          <FieldSetLabel className="flex items-center gap-2">
            Application Secret
            <span className="text-card-foreground">
              (Only fill if you need to update the secret)
            </span>
          </FieldSetLabel>
          <FieldSetPasswordToggleInput label="secret" />
        </FieldSet>

        <FieldSet
          className="w-full md:w-4/5 flex flex-col gap-1"
          name="gitlab_url"
          required
        >
          <FieldSetLabel className="flex items-center gap-0.5">
            Gitlab URL
          </FieldSetLabel>
          <FieldSetInput
            value={app.gitlab_url}
            readOnly
            placeholder="ex: https://example.gitlab.com"
            disabled
          />
        </FieldSet>

        <FieldSet
          className="w-full md:w-4/5 flex flex-col gap-1"
          name="redirect_uri"
          errors={errors.redirect_uri}
        >
          <FieldSetLabel className="flex items-center gap-0.5">
            Redirect URI
          </FieldSetLabel>
          <FieldSetInput defaultValue={app.redirect_uri} />
        </FieldSet>

        <SubmitButton
          isPending={fetcher.state !== "idle"}
          name="intent"
          value="update_gitlab_app"
        >
          {fetcher.state !== "idle" ? (
            <>
              <LoaderIcon className="animate-spin" size={15} />
              <span>Updating gitlab app...</span>
            </>
          ) : (
            "Update Gitlab app"
          )}
        </SubmitButton>
      </fetcher.Form>
    </>
  );
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
    case "test_gitlab_app_connection": {
      return testGitlabAppConnection(params);
    }
    case "update_gitlab_app": {
      return updateGitlabApp(params, formData, workspaceId);
    }
    case "sync_gitlab_repositories": {
      return syncGitlabRepositories(params);
    }
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

async function updateGitlabApp(
  params: Route.ClientActionArgs["params"],
  formData: FormData,
  workspaceId: string
) {
  const queryClient = getQueryClient();
  const app_secret = formData.get("app_secret")?.toString()?.trim() ?? "";
  const userData = {
    name: formData.get("name")?.toString()?.toString() ?? "",
    redirect_uri: formData.get("redirect_uri")?.toString() ?? "",
    ...(app_secret && { app_secret })
  } satisfies RequestInput<"put", "/api/connectors/gitlab/{id}/update/">;

  const { data, error } = await apiClient.PUT(
    "/api/connectors/gitlab/{id}/update/",
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
    return {
      errors: error
    };
  }

  const { state } = data;

  const app = await queryClient.getQueryData(
    gitAppsQueries.gitlab(workspaceId, params.id).queryKey
  )!;

  const redirectURL = new URL(`${app.gitlab_url}/oauth/authorize`);

  redirectURL.searchParams.set("client_id", app.app_id);
  redirectURL.searchParams.set("redirect_uri", userData.redirect_uri);
  redirectURL.searchParams.set("response_type", "code");
  redirectURL.searchParams.set("state", state);
  redirectURL.searchParams.set("scope", "api read_user read_repository");

  throw redirect(redirectURL.toString());
}

async function syncGitlabRepositories(
  params: Route.ClientActionArgs["params"]
) {
  const { data, error } = await apiClient.PUT(
    "/api/connectors/gitlab/{id}/sync-repositories/",
    {
      headers: {
        ...(await getCsrfTokenHeader())
      },
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
    description: `Succesfully synched ${data.repositories_count} repositories !`,
    closeButton: true
  });

  return { data };
}
