import { useMutation, useQueryClient } from "@tanstack/react-query";
import { AlertCircle, LoaderIcon } from "lucide-react";
import React from "react";
import { Form, Link, redirect, useNavigate, useNavigation } from "react-router";
import { type RequestInput, apiClient } from "~/api/client";
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
import { queryClient } from "~/root";
import { getCsrfTokenHeader, metaTitle } from "~/utils";
import { type Route } from "./+types/create-project";

export function meta() {
  return [metaTitle("Create Project")] satisfies ReturnType<Route.MetaFunction>;
}

export default function CreateProjectPage({
  actionData
}: Route.ComponentProps) {
  return (
    <div>
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
      <CreateForm actionData={actionData} />
    </div>
  );
}

export async function clientAction({ request }: Route.ClientActionArgs) {
  let formData = await request.formData();
  const userData = {
    slug: formData.get("slug")?.toString().trim(),
    description: formData.get("description")?.toString() || undefined
  };

  const apiResponse = await apiClient.POST("/api/projects/", {
    headers: {
      ...(await getCsrfTokenHeader())
    },
    body: userData
  });

  if (apiResponse.error) {
    return {
      errors: apiResponse.error,
      userData
    };
  }

  queryClient.invalidateQueries({
    predicate: (query) =>
      query.queryKey.includes(projectQueries.list().queryKey[0])
  });
  throw redirect(`/project/${apiResponse.data.slug}`);
}

function CreateForm({ actionData }: Pick<Route.ComponentProps, "actionData">) {
  const navigation = useNavigation();
  const isPending =
    navigation.state === "loading" || navigation.state === "submitting";
  const errors = getFormErrorsFromResponseData(actionData?.errors);
  return (
    <Form
      method="post"
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
            defaultValue={actionData?.userData?.slug}
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
            defaultValue={actionData?.userData?.description}
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
    </Form>
  );
}
