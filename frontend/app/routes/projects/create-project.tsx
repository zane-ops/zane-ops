import { AlertCircleIcon, ArrowLeftIcon, LoaderIcon } from "lucide-react";
import { Form, Link, href, redirect, useNavigation } from "react-router";
import { apiClient } from "~/api/client";
import { Alert, AlertDescription, AlertTitle } from "~/components/ui/alert";
import { SubmitButton } from "~/components/ui/button";
import {
  FieldSet,
  FieldSetInput,
  FieldSetLabel,
  FieldSetTextarea
} from "~/components/ui/fieldset";
import { Input } from "~/components/ui/input";
import { Textarea } from "~/components/ui/textarea";
import { ensureMinRole, projectQueries } from "~/lib/queries";
import { getQueryClient } from "~/lib/query-client";
import {
  cn,
  getCsrfTokenHeader,
  getFormErrorsFromResponseData,
  metaTitle
} from "~/lib/utils";
import { getCurrentWorkspace } from "~/lib/workspace-store";
import type { Route } from "./+types/create-project";

export function meta() {
  return [metaTitle("Create Project")] satisfies ReturnType<Route.MetaFunction>;
}

export async function clientLoader() {
  const queryClient = getQueryClient();
  await ensureMinRole(queryClient, "Admin");
}

export async function clientAction({
  request,
  params
}: Route.ClientActionArgs) {
  const queryClient = getQueryClient();
  const { id: workspaceId } = await getCurrentWorkspace(queryClient);

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
    href(`/workspace/project/:projectSlug/:envSlug`, {
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
      <FieldSet className="card flex lg:w-[30%] md:w-[50%] w-full flex-col gap-3">
        <Link
          to={href("/workspace")}
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
        <FieldSet
          errors={errors.slug}
          name="slug"
          className="my-2 flex flex-col gap-1"
        >
          <FieldSetLabel>Slug</FieldSetLabel>
          <FieldSetInput
            className="p-1.5"
            placeholder="Ex: Zaneops"
            autoFocus
            defaultValue={actionData?.userData?.slug}
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
            name="description"
            placeholder="Ex: A self hosted PaaS"
            defaultValue={actionData?.userData?.description}
          />
        </FieldSet>

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
      </FieldSet>
    </Form>
  );
}
