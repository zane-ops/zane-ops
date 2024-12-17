import { useMutation, useQueryClient } from "@tanstack/react-query";
import { Link, createFileRoute, useNavigate } from "@tanstack/react-router";
import { AlertCircle, LoaderIcon } from "lucide-react";
import * as React from "react";
import { type RequestInput, apiClient } from "~/api/client";
import { withAuthRedirect } from "~/components/helper/auth-redirect";

import { MetaTitle } from "~/components/meta-title";
import { Alert, AlertDescription, AlertTitle } from "~/components/ui/alert";
import {
  Breadcrumb,
  BreadcrumbItem,
  BreadcrumbLink,
  BreadcrumbList,
  BreadcrumbPage,
  BreadcrumbSeparator
} from "~/components/ui/breadcrumb";
import { SubmitButton } from "~/components/ui/button";
import { Input } from "~/components/ui/input";
import { Textarea } from "~/components/ui/textarea";
import { projectQueries } from "~/lib/queries";
import { getFormErrorsFromResponseData } from "~/lib/utils";
import { getCsrfTokenHeader } from "~/utils";

export const Route = createFileRoute("/_dashboard/create-project")({
  component: withAuthRedirect(CreateProject)
});

export function CreateProject() {
  return (
    <main>
      <MetaTitle title="Create Project" />
      <Breadcrumb>
        <BreadcrumbList className="text-sm">
          <BreadcrumbItem>
            <BreadcrumbLink asChild>
              <Link to="/">Projects</Link>
            </BreadcrumbLink>
          </BreadcrumbItem>
          <BreadcrumbSeparator />
          <BreadcrumbItem>
            <BreadcrumbPage>Create project</BreadcrumbPage>
          </BreadcrumbItem>
        </BreadcrumbList>
      </Breadcrumb>
      <CreateForm />
    </main>
  );
}

function CreateForm() {
  const navigate = useNavigate();
  const queryClient = useQueryClient();

  const { mutateAsync, data } = useMutation({
    mutationFn: async (input: RequestInput<"post", "/api/projects/">) => {
      const { error, data } = await apiClient.POST("/api/projects/", {
        headers: {
          ...(await getCsrfTokenHeader())
        },
        body: input
      });

      if (error) return error;
      if (data) {
        queryClient.invalidateQueries(projectQueries.list());
        await navigate({ to: `/project/${data.slug}` });
        return;
      }
    }
  });

  const [state, formAction, isPending] = React.useActionState(
    async (prev: any, formData: FormData) => {
      const data = {
        slug: formData.get("slug")?.toString().trim(),
        description: formData.get("description")?.toString() || undefined
      };
      const errors = await mutateAsync(data);

      if (errors) {
        return data;
      }
    },
    null
  );
  const errors = getFormErrorsFromResponseData(data);
  return (
    <form
      action={formAction}
      className="flex h-[60vh] grow justify-center items-center"
    >
      <div className="card flex lg:w-[30%] md:w-[50%] w-full flex-col gap-3">
        <h1 className="text-3xl font-bold">New Project</h1>

        {errors.non_field_errors && (
          <Alert variant="destructive">
            <AlertCircle className="h-4 w-4" />
            <AlertTitle>Error</AlertTitle>
            <AlertDescription>{errors.non_field_errors}</AlertDescription>
          </Alert>
        )}
        <div className="my-2 flex flex-col gap-1">
          <label htmlFor="slug">Slug</label>
          <Input
            className="p-1.5"
            placeholder="Ex: Zaneops"
            name="slug"
            id="slug"
            type="text"
            defaultValue={state?.slug}
            aria-describedby="slug-error"
          />
          {errors.slug && (
            <span id="slug-error" className="text-red-500 text-sm">
              {errors.slug}
            </span>
          )}
        </div>

        <div className="my-2 flex flex-col gap-1">
          <label htmlFor="description">Description</label>
          <Textarea
            className="placeholder:text-gray-400"
            name="description"
            id="description"
            placeholder="Ex: A self hosted PaaS"
            defaultValue={state?.description}
            aria-describedby="description-error"
          />
          {errors.description && (
            <span id="description-error" className="text-red-500 text-sm">
              {errors.description}
            </span>
          )}
        </div>

        <SubmitButton
          className="lg:w-fit w-full lg:ml-auto p-3 rounded-lg gap-2"
          isPending={isPending}
        >
          {isPending ? (
            <>
              <span>Creating Project...</span>
              <LoaderIcon className="animate-spin" size={15} />
            </>
          ) : (
            "Create a new project"
          )}
        </SubmitButton>
      </div>
    </form>
  );
}
