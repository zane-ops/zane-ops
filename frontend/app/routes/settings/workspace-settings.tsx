import { useQuery } from "@tanstack/react-query";
import {
  AlertCircleIcon,
  CheckIcon,
  FlameIcon,
  InfoIcon,
  LoaderIcon
} from "lucide-react";
import { useFetcher } from "react-router";
import { toast } from "sonner";
import { apiClient } from "~/api/client";
import { Alert, AlertDescription, AlertTitle } from "~/components/ui/alert";
import { SubmitButton } from "~/components/ui/button";
import {
  FieldSet,
  FieldSetInput,
  FieldSetLabel
} from "~/components/ui/fieldset";
import { Separator } from "~/components/ui/separator";
import { userQueries } from "~/lib/queries";
import { getQueryClient } from "~/lib/query-client";
import {
  type ErrorResponseFromAPI,
  getFormErrorsFromResponseData,
  notFound
} from "~/lib/utils";
import { getCsrfTokenHeader, hasMinRole, metaTitle } from "~/utils";
import type { Route } from "./+types/workspace-settings";

export function meta() {
  return [
    metaTitle("Workspace Settings")
  ] satisfies ReturnType<Route.MetaFunction>;
}

export async function clientLoader({}: Route.ClientLoaderArgs) {
  const queryClient = getQueryClient();

  const workspace = await queryClient.ensureQueryData(
    userQueries.currentWorkspace
  );
  if (!workspace) {
    throw notFound("Oops !");
  }
  return { workspace };
}

export default function WorkspaceSettingsPage({
  loaderData,
  matches: {
    "1": {
      loaderData: { user }
    }
  }
}: Route.ComponentProps) {
  const { data: workspace } = useQuery({
    ...userQueries.currentWorkspace,
    initialData: loaderData.workspace
  });

  if (!workspace) return null;

  return (
    <section className="flex flex-col gap-4">
      <h2 className="text-2xl">Workspace Settings</h2>
      <Separator />
      <h3 className="text-grey">
        Update the general details of your workspace
      </h3>

      <div className="grid lg:grid-cols-12 gap-10 relative">
        <div className="lg:col-span-10 flex flex-col">
          <section id="details" className="flex gap-1 scroll-mt-20">
            <div className="w-16 hidden md:flex flex-col items-center">
              <div className="flex rounded-full size-10 flex-none items-center justify-center p-1 border-2 border-grey/50">
                <InfoIcon size={15} className="flex-none text-grey" />
              </div>
              {hasMinRole(user, "Owner") && (
                <div className="h-full border border-grey/50"></div>
              )}
            </div>

            <div className="w-full flex flex-col gap-5 pt-1 pb-8">
              <h2 className="text-lg text-grey">Details</h2>

              <WorkspaceDetailsForm name={workspace.name} />
            </div>
          </section>

          {hasMinRole(user, "Owner") && (
            <section id="danger" className="flex gap-1 scroll-mt-20">
              <div className="w-16 hidden md:flex flex-col items-center">
                <div className="flex rounded-full size-10 flex-none items-center justify-center p-1 border-2 border-red-500">
                  <FlameIcon size={15} className="flex-none text-red-500" />
                </div>
              </div>
              <div className="w-full flex flex-col gap-5 pt-1 pb-14">
                <h2 className="text-lg text-red-400">Danger Zone</h2>
                <div className="flex flex-col gap-4 items-start max-w-4xl w-full rounded-md border border-border p-4">
                  <div className="flex md:flex-row gap-4 justify-between items-center w-full">
                    <div className="flex flex-col gap-1">
                      <h3 className="text-lg font-medium">Delete workspace</h3>
                      <p>
                        Deletes this workspace along with all its project and
                        services
                      </p>
                    </div>
                    {/* <ProjectDangerZoneForm project_slug={params.projectSlug} /> */}
                  </div>
                </div>
              </div>
            </section>
          )}
        </div>
      </div>
    </section>
  );
}

async function updateWorkspace(formData: FormData) {
  const queryClient = getQueryClient();
  const userData = {
    name: formData.get("name")?.toString() ?? ""
  };
  const apiResponse = await apiClient.PUT("/api/workspace/", {
    headers: {
      ...(await getCsrfTokenHeader())
    },
    body: userData
  });

  if (apiResponse.error) {
    return {
      userData,
      errors: apiResponse.error
    };
  }

  await Promise.all([
    queryClient.invalidateQueries(userQueries.currentWorkspace),
    queryClient.invalidateQueries(userQueries.memberships)
  ]);
  toast.success("Workspace updated successfully!", { closeButton: true });

  return {
    userData,
    errors: apiResponse.error
  };
}

export async function clientAction({
  request,
  params
}: Route.ClientActionArgs) {
  const formData = await request.formData();
  const intent = formData.get("intent")?.toString();

  switch (intent) {
    case "update_workspace": {
      return updateWorkspace(formData);
    }
    case "archive_workspace": {
      if (formData.get("name")?.toString().trim() !== params.workspaceId) {
        return {
          errors: {
            type: "validation_error",
            errors: [
              {
                attr: "workspace_name",
                code: "invalid",
                detail: "The workspace name does not match"
              }
            ]
          } satisfies ErrorResponseFromAPI
        };
      }
      // return archiveWorkspace(params);
    }
    default: {
      throw new Error("Unexpected intent");
    }
  }
}

type WorkspaceDetailsFormProps = {
  name: string;
};

function WorkspaceDetailsForm({ name }: WorkspaceDetailsFormProps) {
  const fetcher = useFetcher<typeof clientAction>();
  const isPending = fetcher.state !== "idle";
  const errors = getFormErrorsFromResponseData(fetcher.data?.errors);

  return (
    <fetcher.Form method="post" className="flex flex-col gap-4">
      {errors.non_field_errors && (
        <Alert variant="destructive">
          <AlertCircleIcon className="h-4 w-4" />
          <AlertTitle>Error</AlertTitle>
          <AlertDescription>{errors.non_field_errors}</AlertDescription>
        </Alert>
      )}

      <FieldSet
        errors={errors.name}
        name="name"
        className="flex flex-col gap-1.5 flex-1"
      >
        <FieldSetLabel>Workspace name</FieldSetLabel>
        <FieldSetInput
          placeholder="ex: Default workspace"
          defaultValue={name}
        />
      </FieldSet>

      <SubmitButton
        isPending={isPending}
        variant="secondary"
        className="self-start"
        name="intent"
        value="update_workspace"
      >
        {isPending ? (
          <>
            <LoaderIcon className="animate-spin" size={15} />
            <span>Updating ...</span>
          </>
        ) : (
          <>
            <CheckIcon size={15} className="flex-none" />
            <span>Update</span>
          </>
        )}
      </SubmitButton>
    </fetcher.Form>
  );
}
