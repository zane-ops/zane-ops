import {
  AlertCircleIcon,
  CheckIcon,
  FlameIcon,
  InfoIcon,
  LoaderIcon,
  Trash2Icon
} from "lucide-react";
import { href, redirect, useFetcher } from "react-router";
import { toast } from "sonner";
import { apiClient } from "~/api/client";
import { DeleteConfirmationDialog } from "~/components/delete-confirmation-dialog";
import { Alert, AlertDescription, AlertTitle } from "~/components/ui/alert";
import { Button, SubmitButton } from "~/components/ui/button";
import { DialogTrigger } from "~/components/ui/dialog";
import {
  FieldSet,
  FieldSetInput,
  FieldSetLabel,
  FieldSetTextarea
} from "~/components/ui/fieldset";
import { Separator } from "~/components/ui/separator";
import { projectQueries, resourceQueries } from "~/lib/queries";
import { getQueryClient } from "~/lib/query-client";
import {
  type ErrorResponseFromAPI,
  cn,
  getCsrfTokenHeader,
  getFormErrorsFromResponseData,
  hasMinRole
} from "~/lib/utils";
import {
  getCurrentWorkspace,
  useCurrentWorkspaceMembership
} from "~/lib/workspace-store";
import type { Route } from "./+types/project-settings";

export default function ProjectSettingsPage({
  params,
  matches: {
    "3": {
      loaderData: { project }
    }
  }
}: Route.ComponentProps) {
  const membership = useCurrentWorkspaceMembership();
  const isAdmin = hasMinRole(membership, "Admin");

  return (
    <section className="flex flex-col gap-4">
      <div className="flex items-center gap-4">
        <h2 className="text-2xl">General</h2>
      </div>
      <Separator />
      <p className="text-grey">Update the general details of your project</p>
      <div className="grid lg:grid-cols-12 gap-10 relative">
        <div className="lg:col-span-10 flex flex-col">
          <section id="details" className="flex gap-1 scroll-mt-20">
            <div className="w-16 hidden md:flex flex-col items-center">
              <div className="flex rounded-full size-10 flex-none items-center justify-center p-1 border-2 border-grey/50">
                <InfoIcon size={15} className="flex-none text-grey" />
              </div>
              <div className="h-full border border-grey/50"></div>
              {!isAdmin && <div className="bg-grey/50 rounded-md size-2" />}
            </div>
            <div
              className={cn(
                "w-full flex flex-col gap-5 pt-1",
                isAdmin ? "pb-8" : "pb-4"
              )}
            >
              <h2 className="text-lg text-grey">Details</h2>

              <ProjectDetailsForm
                project_slug={params.projectSlug}
                description={project.description ?? ""}
                isAdmin={isAdmin}
              />
            </div>
          </section>

          {isAdmin && (
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
                      <h3 className="text-lg font-medium">Delete project</h3>
                      <p>
                        Deletes this project along with all its environments and
                        services
                      </p>
                    </div>
                    <ProjectDeleteForm project_slug={params.projectSlug} />
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

type ProjectDetailsFormProps = {
  description: string;
  project_slug: string;
  isAdmin?: boolean;
};

function ProjectDetailsForm({
  description,
  project_slug,
  isAdmin = false
}: ProjectDetailsFormProps) {
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
        errors={errors.slug}
        name="slug"
        className="flex flex-col gap-1.5 flex-1"
      >
        <FieldSetLabel>Project slug</FieldSetLabel>
        <FieldSetInput
          placeholder="project slug"
          defaultValue={project_slug}
          disabled={!isAdmin}
        />
      </FieldSet>

      <FieldSet
        name="description"
        errors={errors.description}
        className="my-2 flex flex-col gap-1"
      >
        <FieldSetLabel>Description</FieldSetLabel>
        <FieldSetTextarea
          className="placeholder:text-gray-400"
          placeholder="Ex: A self hosted PaaS"
          defaultValue={description}
          disabled={!isAdmin}
        />
      </FieldSet>

      {isAdmin && (
        <SubmitButton
          isPending={isPending}
          variant="secondary"
          className="self-start"
          name="intent"
          value="update_project"
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
      )}
    </fetcher.Form>
  );
}

function ProjectDeleteForm({ project_slug }: { project_slug: string }) {
  const fetcher = useFetcher<typeof clientAction>();
  const errors = getFormErrorsFromResponseData(fetcher.data?.errors);

  return (
    <div className="flex flex-col gap-2 items-start">
      <DeleteConfirmationDialog
        fetcher={fetcher}
        title="Delete this project ?"
        message="Deleting this project will also delete all its services and delete all the deployments related to the services, This action is irreversible."
        confirmationValue={project_slug}
        confirmationFieldName="project_slug"
        form={
          <fetcher.Form method="post">
            <FieldSet name="project_slug" errors={errors.project_slug}>
              <FieldSetInput />
            </FieldSet>
            <input type="hidden" name="intent" value="archive_project" />
          </fetcher.Form>
        }
        trigger={
          <DialogTrigger asChild>
            <Button
              variant="destructive"
              type="button"
              className={cn("inline-flex gap-1 items-center")}
            >
              <Trash2Icon size={15} className="flex-none" />
              <span>Delete this project</span>
            </Button>
          </DialogTrigger>
        }
      />
    </div>
  );
}

export async function clientAction({
  request,
  params
}: Route.ClientActionArgs) {
  const queryClient = getQueryClient();
  const { id: workspaceId } = await getCurrentWorkspace(queryClient);
  const formData = await request.formData();
  const intent = formData.get("intent")?.toString();

  switch (intent) {
    case "update_project": {
      return updateProject(workspaceId, params, formData);
    }
    case "archive_project": {
      if (
        formData.get("project_slug")?.toString().trim() !== params.projectSlug
      ) {
        return {
          errors: {
            type: "validation_error",
            errors: [
              {
                attr: "project_slug",
                code: "invalid",
                detail: "The project slug does not match"
              }
            ]
          } satisfies ErrorResponseFromAPI
        };
      }
      return archiveProject(workspaceId, params);
    }
    default: {
      throw new Error("Unexpected intent");
    }
  }
}

async function updateProject(
  workspaceId: string,
  params: Route.ClientActionArgs["params"],
  formData: FormData
) {
  const queryClient = getQueryClient();
  const userData = {
    slug: formData.get("slug")?.toString() ?? "",
    description: formData.get("description")?.toString()
  };
  const apiResponse = await apiClient.PUT("/api/projects/{slug}/", {
    headers: {
      ...(await getCsrfTokenHeader())
    },
    params: {
      path: {
        slug: params.projectSlug
      }
    },
    body: userData
  });

  if (apiResponse.error) {
    return {
      userData,
      errors: apiResponse.error
    };
  }

  queryClient.invalidateQueries(
    projectQueries.single(workspaceId, params.projectSlug)
  );
  toast.success("Project updated successfully!", { closeButton: true });

  if (apiResponse.data.slug !== params.projectSlug) {
    queryClient.setQueryData(
      projectQueries.single(workspaceId, userData.slug).queryKey,
      apiResponse.data
    );
    throw redirect(
      href("/workspace/project/:projectSlug/settings", {
        projectSlug: apiResponse.data.slug
      })
    );
  }
}

async function archiveProject(
  workspaceId: string,
  params: Route.ClientActionArgs["params"]
) {
  const queryClient = getQueryClient();
  const apiResponse = await apiClient.DELETE("/api/projects/{slug}/", {
    headers: {
      ...(await getCsrfTokenHeader())
    },
    params: {
      path: {
        slug: params.projectSlug
      }
    }
  });

  if (apiResponse.error) {
    return {
      errors: apiResponse.error
    };
  }
  await Promise.all([
    queryClient.invalidateQueries(
      projectQueries.single(workspaceId, params.projectSlug)
    ),
    queryClient.invalidateQueries({
      queryKey: resourceQueries.search(workspaceId).queryKey.slice(0, 3)
    }),
    queryClient.invalidateQueries({
      queryKey: projectQueries.list({ workspaceId }).queryKey.slice(0, 3)
    })
  ]);

  toast.success("Success", {
    closeButton: true,
    description: (
      <span>
        Project `<strong>{params.projectSlug}</strong>` has been successfully
        deleted.
      </span>
    )
  });
  throw redirect(href("/workspace"));
}
