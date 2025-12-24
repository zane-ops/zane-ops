import {
  AlertCircleIcon,
  CheckIcon,
  FlameIcon,
  InfoIcon,
  LoaderIcon,
  Trash2Icon
} from "lucide-react";
import * as React from "react";
import { href, redirect, useFetcher } from "react-router";
import { toast } from "sonner";
import { apiClient } from "~/api/client";
import { CopyButton } from "~/components/copy-button";
import { Alert, AlertDescription, AlertTitle } from "~/components/ui/alert";
import { Button, SubmitButton } from "~/components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
  DialogTrigger
} from "~/components/ui/dialog";
import { FieldSet, FieldSetInput } from "~/components/ui/fieldset";
import { Input } from "~/components/ui/input";
import { Separator } from "~/components/ui/separator";
import { Textarea } from "~/components/ui/textarea";
import { projectQueries, resourceQueries } from "~/lib/queries";
import {
  type ErrorResponseFromAPI,
  cn,
  getFormErrorsFromResponseData
} from "~/lib/utils";
import { queryClient } from "~/root";
import { getCsrfTokenHeader } from "~/utils";
import type { Route } from "./+types/project-settings";

export default function ProjectSettingsPage({
  params,
  matches: {
    "2": {
      loaderData: { project }
    }
  }
}: Route.ComponentProps) {
  return (
    <section className="flex flex-col gap-4">
      <div className="flex items-center gap-4">
        <h2 className="text-2xl">General</h2>
      </div>
      <Separator />
      <p className="text-grey">Update the general details of your service</p>
      <div className="grid lg:grid-cols-12 gap-10 relative">
        <div className="lg:col-span-10 flex flex-col">
          <section id="details" className="flex gap-1 scroll-mt-20">
            <div className="w-16 hidden md:flex flex-col items-center">
              <div className="flex rounded-full size-10 flex-none items-center justify-center p-1 border-2 border-grey/50">
                <InfoIcon size={15} className="flex-none text-grey" />
              </div>
              <div className="h-full border border-grey/50"></div>
            </div>
            <div className="w-full flex flex-col gap-5 pt-1 pb-8">
              <h2 className="text-lg text-grey">Details</h2>

              <ProjectDetailsForm
                project_slug={params.projectSlug}
                description={project.description ?? ""}
              />
            </div>
          </section>

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
                  <ProjectDangerZoneForm project_slug={params.projectSlug} />
                </div>
              </div>
            </div>
          </section>
        </div>
      </div>
    </section>
  );
}

export async function clientAction({
  request,
  params
}: Route.ClientActionArgs) {
  const formData = await request.formData();
  const intent = formData.get("intent")?.toString();

  switch (intent) {
    case "update_project": {
      return updateProject(params.projectSlug, formData);
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
      return archiveProject(params.projectSlug);
    }
    default: {
      throw new Error("Unexpected intent");
    }
  }
}

async function updateProject(project_slug: string, formData: FormData) {
  const userData = {
    slug: formData.get("slug")?.toString() ?? "",
    description: formData.get("description")?.toString() || undefined
  };
  const apiResponse = await apiClient.PATCH("/api/projects/{slug}/", {
    headers: {
      ...(await getCsrfTokenHeader())
    },
    params: {
      path: {
        slug: project_slug
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

  queryClient.invalidateQueries(projectQueries.single(project_slug));
  toast.success("Project updated successfully!", { closeButton: true });

  if (apiResponse.data.slug !== project_slug) {
    queryClient.setQueryData(
      projectQueries.single(userData.slug).queryKey,
      apiResponse.data
    );
    throw redirect(
      href("/project/:projectSlug/settings", {
        projectSlug: apiResponse.data.slug
      })
    );
  }
}

async function archiveProject(project_slug: string) {
  const apiResponse = await apiClient.DELETE("/api/projects/{slug}/", {
    headers: {
      ...(await getCsrfTokenHeader())
    },
    params: {
      path: {
        slug: project_slug
      }
    }
  });

  if (apiResponse.error) {
    return {
      errors: apiResponse.error
    };
  }

  queryClient.invalidateQueries(projectQueries.single(project_slug));
  queryClient.invalidateQueries({
    predicate: (query) =>
      query.queryKey[0] === resourceQueries.search().queryKey[0] ||
      query.queryKey[0] === projectQueries.list().queryKey[0]
  });

  toast.success("Success", {
    closeButton: true,
    description: (
      <span>
        Project `<strong>{project_slug}</strong>` has been successfully deleted.
      </span>
    )
  });
  throw redirect(`/`);
}

type ProjectDetailsFormProps = {
  description: string;
  project_slug: string;
};

function ProjectDetailsForm({
  description,
  project_slug
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

      <fieldset className="flex flex-col gap-1.5 flex-1">
        <label htmlFor="slug">Project slug</label>
        <Input
          id="slug"
          name="slug"
          placeholder="project slug"
          defaultValue={project_slug}
          aria-labelledby="slug-error"
          aria-invalid={!!errors.slug}
        />

        {errors.slug && (
          <span id="slug-error" className="text-red-500 text-sm">
            {errors.slug}
          </span>
        )}
      </fieldset>

      <fieldset className="my-2 flex flex-col gap-1">
        <label htmlFor="description">Description</label>
        <Textarea
          className="placeholder:text-gray-400"
          name="description"
          id="description"
          placeholder="Ex: A self hosted PaaS"
          defaultValue={description}
          aria-describedby="description-error"
        />
        {errors.description && (
          <span id="description-error" className="text-red-500 text-sm">
            {errors.description}
          </span>
        )}
      </fieldset>

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
    </fetcher.Form>
  );
}

function ProjectDangerZoneForm({ project_slug }: { project_slug: string }) {
  const fetcher = useFetcher<typeof clientAction>();

  return (
    <fetcher.Form method="post" className="flex flex-col gap-2 items-start">
      <DeleteConfirmationFormDialog project_slug={project_slug} />
    </fetcher.Form>
  );
}

function DeleteConfirmationFormDialog({
  project_slug
}: { project_slug: string }) {
  const [isOpen, setIsOpen] = React.useState(false);
  const fetcher = useFetcher<typeof clientAction>();
  const formRef = React.useRef<React.ComponentRef<"form">>(null);

  const [data, setData] = React.useState(fetcher.data);
  const isPending = fetcher.state !== "idle";
  const errors = getFormErrorsFromResponseData(data?.errors);

  React.useEffect(() => {
    setData(fetcher.data);

    // only focus on the correct input in case of error
    if (fetcher.state === "idle" && fetcher.data && !fetcher.data.errors) {
      formRef.current?.reset();
      setIsOpen(false);
    }
  }, [fetcher.state, fetcher.data]);

  return (
    <Dialog
      open={isOpen}
      onOpenChange={(open) => {
        if (isPending) return; // prevent closing if form is being submitted
        setIsOpen(open);
        if (!open) {
          setData(undefined);
        }
      }}
    >
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
      <DialogContent className="gap-0">
        <DialogHeader className="pb-4">
          <DialogTitle>Delete this project ?</DialogTitle>

          <Alert variant="danger" className="my-5">
            <AlertCircleIcon className="h-4 w-4" />
            <AlertTitle>Attention !</AlertTitle>
            <AlertDescription>
              Deleting this project will also delete all its services and delete
              all the deployments related to the services, This action is
              irreversible.
            </AlertDescription>
          </Alert>

          <DialogDescription className="inline-flex gap-1 items-center flex-wrap">
            <span className="whitespace-nowrap">Please type</span>
            <CopyButton
              variant="outline"
              size="sm"
              showLabel
              value={project_slug}
              label={project_slug}
            />
            <span className="whitespace-nowrap">to confirm :</span>
          </DialogDescription>
        </DialogHeader>

        {errors.non_field_errors && (
          <Alert variant="destructive">
            <AlertCircleIcon className="h-4 w-4" />
            <AlertTitle>Error</AlertTitle>
            <AlertDescription>{errors.non_field_errors}</AlertDescription>
          </Alert>
        )}

        <fetcher.Form
          className="flex flex-col w-full mb-5 gap-1"
          method="post"
          id="delete-form"
          ref={formRef}
        >
          <FieldSet name="project_slug" errors={errors.project_slug}>
            <FieldSetInput />
          </FieldSet>
        </fetcher.Form>

        <DialogFooter className="-mx-6 px-6 pt-4">
          <div className="flex items-center gap-4 w-full">
            <SubmitButton
              variant="destructive"
              className={cn(
                "inline-flex gap-1 items-center",
                isPending ? "bg-red-400" : "bg-red-500"
              )}
              value="archive_project"
              name="intent"
              form="delete-form"
              isPending={isPending}
            >
              {isPending ? (
                <>
                  <LoaderIcon className="animate-spin flex-none" size={15} />
                  <span>Deleting...</span>
                </>
              ) : (
                <>
                  <span>Delete</span>
                </>
              )}
            </SubmitButton>

            <Button
              variant="outline"
              onClick={() => {
                setIsOpen(false);
                setData(undefined);
              }}
            >
              Cancel
            </Button>
          </div>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
