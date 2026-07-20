import { Trash2Icon } from "lucide-react";
import { useFetcher } from "react-router";
import { DeleteConfirmationDialog } from "~/components/delete-confirmation-dialog";
import { Button } from "~/components/ui/button";
import { DialogTrigger } from "~/components/ui/dialog";
import { FieldSet, FieldSetInput } from "~/components/ui/fieldset";
import { getFormErrorsFromResponseData } from "~/lib/utils";
import type { clientAction } from "~/routes/compose/archive-compose-stack";

export type ComposeStackDangerZoneFormProps = {
  projectSlug: string;
  envSlug: string;
  stackSlug: string;
};

export function ComposeStackDangerZoneForm(
  props: ComposeStackDangerZoneFormProps
) {
  return (
    <div className="flex flex-col gap-4 items-start max-w-4xl w-full rounded-md border border-border p-4">
      <div className="flex md:flex-row justify-between items-center w-full">
        <div className="flex flex-col gap-1">
          <h3 className="text-lg font-medium">Delete compose stack</h3>
          <p>
            Deletes the stack along with all its services and all its
            deployments
          </p>
        </div>
        <DeleteConfirmationFormDialog {...props} />
      </div>
    </div>
  );
}

function DeleteConfirmationFormDialog({
  projectSlug,
  envSlug,
  stackSlug
}: ComposeStackDangerZoneFormProps) {
  const fetcher = useFetcher<typeof clientAction>();
  const errors = getFormErrorsFromResponseData(fetcher.data?.errors);

  return (
    <DeleteConfirmationDialog
      fetcher={fetcher}
      title="Delete this stack ?"
      message="Deleting this stack will permanently delete all its services including their volumes and configs. This action is irreversible."
      confirmationValue={`${projectSlug}/${envSlug}/${stackSlug}`}
      confirmationFieldName="stack_slug"
      form={
        <fetcher.Form method="post" action="../archive">
          <FieldSet name="stack_slug" errors={errors.stack_slug}>
            <FieldSetInput />
          </FieldSet>
        </fetcher.Form>
      }
      trigger={
        <DialogTrigger asChild>
          <Button
            variant="destructive"
            type="button"
            className="inline-flex gap-1 items-center"
          >
            <Trash2Icon size={15} className="flex-none" />
            <span>Delete stack</span>
          </Button>
        </DialogTrigger>
      }
    />
  );
}
