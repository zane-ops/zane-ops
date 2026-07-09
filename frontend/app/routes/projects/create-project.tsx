import { AlertCircleIcon, ArrowLeftIcon, LoaderIcon } from "lucide-react";
import { Form, Link, href, redirect, useNavigation } from "react-router";
import { apiClient } from "~/api/client";
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
import { projectQueries, userQueries } from "~/lib/queries";
import { getQueryClient } from "~/lib/query-client";
import { cn, getFormErrorsFromResponseData } from "~/lib/utils";
import { getCsrfTokenHeader, metaTitle } from "~/utils";
import type { Route } from "./+types/create-project";

export function meta() {
  return [metaTitle("Create Project")] satisfies ReturnType<Route.MetaFunction>;
}

export async function clientAction({
  request,
  params
}: Route.ClientActionArgs) {
  const queryClient = getQueryClient();
  const { id: workspaceId } = (await queryClient.ensureQueryData(
    userQueries.currentWorkspace
  ))!;
  const formData = await request.formData();
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

  await queryClient.invalidateQueries({
    queryKey: projectQueries.list({ workspaceId }).queryKey.slice(0, 3) // 0...3 include the workspace id & project list key
  });
  throw redirect(
    href(`/project/:projectSlug/:envSlug`, {
      ...params,
      projectSlug: apiResponse.data.slug,
      envSlug: "production"
    })
  );
}

export default function CreateProjectPage({
  actionData
}: Route.ComponentProps) {
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
        <Link
          to={href("/")}
          className={cn(
            "text-sm text-grey w-full",
            "flex items-center gap-0.5 hover:underline"
          )}
        >
          <ArrowLeftIcon className="size-4" />
          Project List
        </Link>
        <h1 className="text-3xl font-bold">New Project</h1>

        {errors.non_field_errors && (
          <Alert variant="destructive">
            <AlertCircleIcon className="h-4 w-4" />
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
            aria-invalid={!!errors.slug}
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
            aria-invalid={!!errors.description}
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
