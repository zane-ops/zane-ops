import { Trash2Icon } from "lucide-react";
import { href, redirect, useFetcher, useParams } from "react-router";
import { toast } from "sonner";
import { apiClient } from "~/api/client";
import { DeleteConfirmationDialog } from "~/components/delete-confirmation-dialog";
import { Button } from "~/components/ui/button";
import { DialogTrigger } from "~/components/ui/dialog";
import { FieldSet, FieldSetInput } from "~/components/ui/fieldset";
import { previewTemplatesQueries, userQueries } from "~/lib/queries";
import { getQueryClient } from "~/lib/query-client";
import {
  type ErrorResponseFromAPI,
  cn,
  getFormErrorsFromResponseData
} from "~/lib/utils";
import { getCsrfTokenHeader } from "~/utils";
import type { Route } from "./+types/delete-preview-template";

export function clientLoader({ params }: Route.ClientLoaderArgs) {
  throw redirect(
    href("/project/:projectSlug/settings/preview-templates/:templateSlug", {
      projectSlug: params.projectSlug,
      templateSlug: params.templateSlug
    })
  );
}

export function DeleteConfirmationFormDialog() {
  const fetcher = useFetcher<typeof clientAction>();
  const params = useParams() as Route.ComponentProps["params"];
  const errors = getFormErrorsFromResponseData(fetcher.data?.errors);

  return (
    <DeleteConfirmationDialog
      fetcher={fetcher}
      title="Delete this preview template ?"
      message={
        <>
          This action <strong>CANNOT</strong> be undone. This will permanently
          delete the preview template in ZaneOps.
        </>
      }
      confirmationValue={`${params.projectSlug}/${params.templateSlug}`}
      confirmationFieldName="template_slug"
      form={
        <fetcher.Form
          method="post"
          action={href(
            "/project/:projectSlug/settings/preview-templates/:templateSlug/delete",
            params
          )}
        >
          <FieldSet name="template_slug" errors={errors.template_slug}>
            <FieldSetInput />
          </FieldSet>
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
            <span>Delete template</span>
          </Button>
        </DialogTrigger>
      }
    />
  );
}

export async function clientAction({
  params,
  request
}: Route.ClientActionArgs) {
  const queryClient = getQueryClient();
  const { id: workspaceId } = (await queryClient.ensureQueryData(
    userQueries.currentWorkspace
  ))!;
  const formData = await request.formData();

  if (
    formData.get("template_slug")?.toString().trim() !==
    `${params.projectSlug}/${params.templateSlug}`
  ) {
    return {
      errors: {
        type: "validation_error",
        errors: [
          {
            attr: "template_slug",
            code: "invalid",
            detail: "The slug does not match"
          }
        ]
      } satisfies ErrorResponseFromAPI
    };
  }

  const { error } = await apiClient.DELETE(
    "/api/projects/{project_slug}/preview-templates/{template_slug}/",
    {
      headers: {
        ...(await getCsrfTokenHeader())
      },
      params: {
        path: {
          project_slug: params.projectSlug,
          template_slug: params.templateSlug
        }
      }
    }
  );
  if (error) {
    const fullErrorMessage = error.errors.map((err) => err.detail).join(" ");

    toast.error("Error", {
      description: fullErrorMessage,
      closeButton: true
    });
    return;
  }

  await queryClient.invalidateQueries(
    previewTemplatesQueries.list(workspaceId, params.projectSlug)
  );

  toast.success("Success", {
    closeButton: true,
    description: (
      <span>
        Preview template `<strong>{params.templateSlug}</strong>` has been
        succesfully deleted.
      </span>
    )
  });
  throw redirect(
    href("/project/:projectSlug/settings/preview-templates", {
      projectSlug: params.projectSlug
    })
  );
}
