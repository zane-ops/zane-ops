import * as Form from "@radix-ui/react-form";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { Link, createLazyFileRoute, useNavigate } from "@tanstack/react-router";
import { AlertCircle, LoaderIcon } from "lucide-react";
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
import { projectKeys } from "~/key-factories";
import { getFormErrorsFromResponseData } from "~/lib/utils";
import { getCsrfTokenHeader } from "~/utils";

export const Route = createLazyFileRoute("/_dashboard/create-project")({
  component: withAuthRedirect(CreateProject)
});

export function CreateProject() {
  const navigate = useNavigate();
  const queryClient = useQueryClient();

  const { isPending, mutate, data } = useMutation({
    mutationFn: async (input: RequestInput<"post", "/api/projects/">) => {
      const { error, data } = await apiClient.POST("/api/projects/", {
        headers: {
          ...(await getCsrfTokenHeader())
        },
        body: input
      });

      if (error) return error;
      if (data) {
        queryClient.invalidateQueries({
          queryKey: projectKeys.list({})
        });
        await navigate({ to: `/project/${data.slug}` });
        return;
      }
    }
  });

  const errors = getFormErrorsFromResponseData(data);

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
      <Form.Root
        action={(formData) => {
          mutate({
            slug: formData.get("slug")?.toString().trim(),
            description: formData.get("description")?.toString() || undefined
          });
        }}
        className="flex h-[60vh] flex-grow justify-center items-center"
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
          <Form.Field className="my-2 flex flex-col gap-1" name="username">
            <Form.Label>Slug</Form.Label>
            <Form.Control asChild>
              <Input
                className="p-1.5"
                placeholder="Ex: Zaneops"
                name="slug"
                type="text"
              />
            </Form.Control>
            {errors.slug && (
              <Form.Message className="text-red-500 text-sm">
                {errors.slug}
              </Form.Message>
            )}
          </Form.Field>

          <Form.Field className="my-2 flex flex-col gap-1" name="username">
            <Form.Label>Description</Form.Label>
            <Form.Control asChild>
              <Textarea
                className="placeholder:text-gray-400"
                name="description"
                placeholder="Ex: A self hosted PaaS"
              />
            </Form.Control>
            {errors.description && (
              <Form.Message className="text-red-500 text-sm">
                {errors.description}
              </Form.Message>
            )}
          </Form.Field>

          <Form.Submit asChild>
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
          </Form.Submit>
        </div>
      </Form.Root>
    </main>
  );
}
