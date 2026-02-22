import { AlertCircleIcon, LoaderIcon, Trash2Icon } from "lucide-react";
import * as React from "react";
import { useFetcher } from "react-router";
import type { ComposeStack } from "~/api/types";
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
import { cn, getFormErrorsFromResponseData } from "~/lib/utils";
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
  const [isOpen, setIsOpen] = React.useState(false);
  const fetcher = useFetcher<typeof clientAction>();
  const formRef = React.useRef<React.ComponentRef<"form">>(null);

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
        if (isPending) return;

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
          className="inline-flex gap-1 items-center"
        >
          <Trash2Icon size={15} className="flex-none" />
          <span>Delete stack</span>
        </Button>
      </DialogTrigger>
      <DialogContent className="gap-0">
        <DialogHeader className="pb-4">
          <DialogTitle>Delete this stack ?</DialogTitle>

          <Alert variant="danger" className="my-5">
            <AlertCircleIcon className="h-4 w-4" />
            <AlertTitle>ATTENTION !</AlertTitle>
            <AlertDescription>
              Deleting this stack will permanently delete all its services
              including their volumes and configs. This action is irreversible.
            </AlertDescription>
          </Alert>

          <DialogDescription className="inline-flex gap-1 items-center flex-wrap">
            <span className="whitespace-nowrap">Please type</span>
            <CopyButton
              variant="outline"
              size="sm"
              showLabel
              className="inline-flex gap-1 items-center"
              value={`${projectSlug}/${envSlug}/${stackSlug}`}
              label={`${projectSlug}/${envSlug}/${stackSlug}`}
            />
            <span className="whitespace-nowrap">to confirm :</span>
          </DialogDescription>
        </DialogHeader>

        <fetcher.Form
          className="flex flex-col w-full mb-5 gap-1"
          method="post"
          id="delete-form"
          ref={formRef}
          action="../archive"
        >
          <FieldSet name="stack_slug" errors={errors.stack_slug}>
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
              disabled={isPending}
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
