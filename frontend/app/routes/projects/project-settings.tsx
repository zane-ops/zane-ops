import {
  AlertCircleIcon,
  CheckIcon,
  FlameIcon,
  InfoIcon,
  LoaderIcon,
  Trash2Icon
} from "lucide-react";
import { redirect, useFetcher } from "react-router";
import { toast } from "sonner";
import { apiClient } from "~/api/client";
import { Alert, AlertDescription, AlertTitle } from "~/components/ui/alert";
import { SubmitButton } from "~/components/ui/button";
import { Input } from "~/components/ui/input";
import { Textarea } from "~/components/ui/textarea";
import { projectQueries, resourceQueries } from "~/lib/queries";
import { cn, getFormErrorsFromResponseData } from "~/lib/utils";
import { queryClient } from "~/root";
import { getCsrfTokenHeader } from "~/utils";
import { type Route } from "./+types/project-settings";

export default function ProjectSettingsPage({
  params,
  matches: {
    "2": {
      data: { project }
    }
  }
}: Route.ComponentProps) {
  return (
    <div className="my-6 grid lg:grid-cols-12 gap-10 relative">
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
            <ProjectDangerZoneForm />
          </div>
        </section>
      </div>
    </div>
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
    throw redirect(`/project/${userData.slug}/settings`);
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

  toast.success("Project archived successfully!", { closeButton: true });
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

function ProjectDangerZoneForm() {
  const fetcher = useFetcher<typeof clientAction>();
  const isPending = fetcher.state !== "idle";
  const errors = getFormErrorsFromResponseData(fetcher.data?.errors);

  return (
    <fetcher.Form method="post" className="flex flex-col gap-2 items-start">
      <h3 className="text-lg text-red-400">Archive this project</h3>
      <p className="text-red-300">
        Archiving this project will also archive all its services and delete all
        the deployments related to the services, This cannot be undone.
      </p>

      {errors.non_field_errors && (
        <Alert variant="destructive">
          <AlertCircleIcon className="h-4 w-4" />
          <AlertTitle>Error</AlertTitle>
          <AlertDescription>{errors.non_field_errors}</AlertDescription>
        </Alert>
      )}

      <SubmitButton
        variant="destructive"
        className={cn(
          "inline-flex gap-1 items-center",
          isPending ? "bg-red-400" : "bg-red-500"
        )}
        value="archive_project"
        name="intent"
        isPending={isPending}
      >
        {isPending ? (
          <>
            <LoaderIcon className="animate-spin flex-none" size={15} />
            <span>Archiving...</span>
          </>
        ) : (
          <>
            <Trash2Icon size={15} className="flex-none" />
            <span>Archive project</span>
          </>
        )}
      </SubmitButton>
    </fetcher.Form>
  );
}
