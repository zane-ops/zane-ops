import { useQuery } from "@tanstack/react-query";
import { AlertCircleIcon, GithubIcon, LoaderIcon } from "lucide-react";
import React from "react";
import { href, redirect, useFetcher } from "react-router";
import { toast } from "sonner";
import { type RequestInput, apiClient } from "~/api/client";
import { Alert, AlertDescription, AlertTitle } from "~/components/ui/alert";
import { SubmitButton } from "~/components/ui/button";
import {
  FieldSet,
  FieldSetInput,
  FieldSetLabel
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
import type { Route } from "./+types/github-app-details";
import { GithubLogo } from "~/components/github-logo";

export function meta() {
  return [
    metaTitle("Update GitHub app")
  ] satisfies ReturnType<Route.MetaFunction>;
}

export async function clientLoader({ params }: Route.ClientLoaderArgs) {
  const queryClient = getQueryClient();
  await ensureMinRole(queryClient, "Admin");
  const { id: workspaceId } = await getCurrentWorkspace(queryClient);
  const app = await queryClient.ensureQueryData(
    gitAppsQueries.github(workspaceId, params.id)
  );
  return { app };
}

export default function GithubAppDetailsPage({
  loaderData,
  params
}: Route.ComponentProps) {
  const { id: workspaceId } = useCurrentWorkspace();

  const { data: app } = useQuery({
    ...gitAppsQueries.github(workspaceId, params.id),
    initialData: loaderData.app
  });

  return (
    <section className="flex flex-col gap-4">
      <div className="flex items-center gap-2">
        <GithubLogo className="size-5 flex-none" />
        <h2 className="text-2xl">Edit GitHub app</h2>
      </div>
      <Separator />

      <p className="text-grey">Update github app credentials.</p>

      <EditGithubAppForm app={app} />
    </section>
  );
}

type EditGithubAppFormProps = Route.ComponentProps["loaderData"];

function EditGithubAppForm({ app }: EditGithubAppFormProps) {
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

      <fetcher.Form
        ref={formRef}
        method="post"
        className="flex flex-col gap-4 items-start"
      >
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
            placeholder="ex: zn-github"
          />
        </FieldSet>

        <FieldSet
          className="w-full md:w-4/5 flex flex-col gap-1"
          name="app_url"
        >
          <FieldSetLabel className="flex items-center gap-0.5">
            App URL
          </FieldSetLabel>
          <FieldSetInput
            value={app.app_url}
            readOnly
            disabled
            className="bg-muted"
          />
        </FieldSet>

        <FieldSet className="w-full md:w-4/5 flex flex-col gap-1" name="app_id">
          <FieldSetLabel className="flex items-center gap-0.5">
            Application ID
          </FieldSetLabel>
          <FieldSetInput
            value={app.app_id}
            readOnly
            disabled
            className="bg-muted"
          />
        </FieldSet>

        <SubmitButton
          isPending={fetcher.state !== "idle"}
          name="intent"
          value="update_github_app"
        >
          {fetcher.state !== "idle" ? (
            <>
              <LoaderIcon className="animate-spin" size={15} />
              <span>Updating GitHub app...</span>
            </>
          ) : (
            "Update GitHub app"
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
    case "test_github_app_connection": {
      return testGithubAppConnection(params);
    }
    case "update_github_app": {
      return updateGithubApp(formData, params, workspaceId);
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

async function updateGithubApp(
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
    return { errors: error };
  }

  await queryClient.invalidateQueries({
    queryKey: gitAppsQueries.list(workspaceId).queryKey
  });

  toast.success("Success", {
    description: `Succesfully updated the GitHub app`,
    closeButton: true
  });
  throw redirect(href("/workspace/settings/git-apps"));
}
