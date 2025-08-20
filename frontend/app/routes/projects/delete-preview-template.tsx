import { AlertCircleIcon, LoaderIcon, Trash2Icon } from "lucide-react";
import * as React from "react";
import { href, redirect, useFetcher, useParams } from "react-router";
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
import { previewTemplatesQueries } from "~/lib/queries";
import {
  type ErrorResponseFromAPI,
  cn,
  getFormErrorsFromResponseData
} from "~/lib/utils";
import { queryClient } from "~/root";
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
  const [isOpen, setIsOpen] = React.useState(false);
  const fetcher = useFetcher<typeof clientAction>();
  const formRef = React.useRef<React.ComponentRef<"form">>(null);
  const params = useParams<Route.ComponentProps["params"]>();

  const [data, setData] = React.useState(fetcher.data);
  const isPending = fetcher.state !== "idle";
  const errors = getFormErrorsFromResponseData(data?.errors);

  React.useEffect(() => {
    setData(fetcher.data);

    // only focus on the correct input in case of error
    if (fetcher.state === "idle" && fetcher.data) {
      if (!fetcher.data.errors) {
        formRef.current?.reset();
        setIsOpen(false);
      } else {
        (
          formRef.current?.elements.namedItem(
            "service_slug"
          ) as HTMLInputElement
        )?.focus();
      }
    }
  }, [fetcher.state, fetcher.data]);

  return (
    <Dialog
      open={isOpen}
      onOpenChange={(open) => {
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
          <span>Delete template</span>
        </Button>
      </DialogTrigger>
      <DialogContent className="gap-0">
        <DialogHeader className="pb-4">
          <DialogTitle>Delete this preview template ?</DialogTitle>

          <Alert variant="destructive" className="my-5">
            <AlertCircleIcon className="h-4 w-4" />
            <AlertTitle>Warning</AlertTitle>
            <AlertDescription>
              This action <strong>CANNOT</strong> be undone. This will
              permanently delete the preview template in ZaneOps.
            </AlertDescription>
          </Alert>

          <DialogDescription className="inline-flex gap-1 items-center flex-wrap">
            <span className="whitespace-nowrap">Please type</span>
            <CopyButton
              variant="outline"
              size="sm"
              showLabel
              className="inline-flex gap-1 items-center"
              value={`${params.projectSlug}/${params.templateSlug}`}
              label={`${params.projectSlug}/${params.templateSlug}`}
            />
            <span className="whitespace-nowrap">to confirm :</span>
          </DialogDescription>
        </DialogHeader>

        <fetcher.Form
          className="flex flex-col w-full mb-5 gap-1"
          method="post"
          id="delete-form"
          ref={formRef}
          action={href(
            "/project/:projectSlug/settings/preview-templates/:templateSlug/delete",
            {
              projectSlug: params.projectSlug!,
              templateSlug: params.templateSlug!
            }
          )}
        >
          <FieldSet name="template_slug" errors={errors.template_slug}>
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

export async function clientAction({
  params,
  request
}: Route.ClientActionArgs) {
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
    previewTemplatesQueries.list(params.projectSlug)
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
