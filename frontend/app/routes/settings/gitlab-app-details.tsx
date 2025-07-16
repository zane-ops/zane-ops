import { EyeIcon, EyeOffIcon, LoaderIcon } from "lucide-react";
import React from "react";
import { redirect, useFetcher } from "react-router";
import { toast } from "sonner";
import { type RequestInput, apiClient } from "~/api/client";
import { Button, SubmitButton } from "~/components/ui/button";
import {
  FieldSet,
  FieldSetInput,
  FieldSetLabel
} from "~/components/ui/fieldset";
import { Separator } from "~/components/ui/separator";
import {
  Tooltip,
  TooltipContent,
  TooltipProvider,
  TooltipTrigger
} from "~/components/ui/tooltip";
import { gitAppsQueries } from "~/lib/queries";
import { queryClient } from "~/root";
import { getCsrfTokenHeader, metaTitle } from "~/utils";
import type { Route } from "./+types/gitlab-app-details";

export function meta() {
  return [
    metaTitle("Update Gitlab app")
  ] satisfies ReturnType<Route.MetaFunction>;
}

export async function clientLoader({ params }: Route.ClientLoaderArgs) {
  const app = await queryClient.ensureQueryData(
    gitAppsQueries.gitlab(params.id)
  );
  return { app };
}

export default function GitlabAppDetailsPage({
  loaderData
}: Route.ComponentProps) {
  return (
    <section className="flex flex-col gap-4">
      <div className="flex items-center gap-4">
        <h2 className="text-2xl">Edit Gitlab app</h2>
      </div>
      <Separator />

      <EditGitlabAppForm {...loaderData} />
    </section>
  );
}

type EditGitlabAppFormProps = Route.ComponentProps["loaderData"];

function EditGitlabAppForm({ app }: EditGitlabAppFormProps) {
  const fetcher = useFetcher<typeof clientAction>();

  const [isSecretShown, setIsSecretShown] = React.useState(false);

  return (
    <>
      <p>
        If you have renewed the gitlab secret, please paste the new key down
        below:
      </p>

      <fetcher.Form method="post" className="flex flex-col gap-4 items-start">
        <FieldSet
          className="w-full md:w-4/5 flex flex-col gap-1"
          required
          name="name"
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
          required
          name="app_secret"
        >
          <FieldSetLabel className="flex items-center gap-0.5">
            Application Secret
          </FieldSetLabel>
          <div className="flex items-center gap-2">
            <FieldSetInput
              type={!isSecretShown ? "password" : "text"}
              defaultValue={app.secret}
            />
            <TooltipProvider>
              <Tooltip delayDuration={0}>
                <TooltipTrigger asChild>
                  <Button
                    variant="outline"
                    type="button"
                    onClick={() => setIsSecretShown(!isSecretShown)}
                    className="p-4"
                  >
                    {isSecretShown ? (
                      <EyeOffIcon size={15} className="flex-none" />
                    ) : (
                      <EyeIcon size={15} className="flex-none" />
                    )}
                    <span className="sr-only">
                      {isSecretShown ? "Hide" : "Show"} secret
                    </span>
                  </Button>
                </TooltipTrigger>
                <TooltipContent>
                  {isSecretShown ? "Hide" : "Show"} secret
                </TooltipContent>
              </Tooltip>
            </TooltipProvider>
          </div>
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
  const formData = await request.formData();

  const intent = formData.get("intent")?.toString();

  switch (intent) {
    case "test_gitlab_app_connection": {
      return testGitlabAppConnection(params);
    }
    case "update_gitlab_app": {
      return updateGitlabApp(params, formData);
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
  formData: FormData
) {
  const userData = {
    app_secret: formData.get("app_secret")?.toString() ?? "",
    name: formData.get("name")?.toString()?.toString() ?? "",
    redirect_uri: formData.get("redirect_uri")?.toString() ?? ""
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
    gitAppsQueries.gitlab(params.id).queryKey
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
}
