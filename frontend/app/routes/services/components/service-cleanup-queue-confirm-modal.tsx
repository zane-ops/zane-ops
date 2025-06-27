import { AlertCircleIcon, LoaderIcon, PaintbrushIcon } from "lucide-react";
import * as React from "react";
import { useFetcher } from "react-router";
import { Alert, AlertDescription, AlertTitle } from "~/components/ui/alert";
import { Button, SubmitButton } from "~/components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogFooter,
  DialogHeader,
  DialogTitle,
  DialogTrigger
} from "~/components/ui/dialog";
import {
  FieldSet,
  FieldSetCheckbox,
  FieldSetLabel
} from "~/components/ui/fieldset";
import { cn, getFormErrorsFromResponseData } from "~/lib/utils";
import type { clientAction } from "~/routes/services/cleanup-deploy-queue";

export type ServiceCleanupQueueConfirmProps = {};

export function ServiceCleanupQueueConfirmModal({}: ServiceCleanupQueueConfirmProps) {
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
    <Dialog open={isOpen} onOpenChange={setIsOpen}>
      <DialogTrigger asChild>
        <Button
          type="button"
          variant="ghost"
          size="sm"
          className="flex items-center gap-2 justify-start text-red-500"
        >
          <PaintbrushIcon size={15} className="opacity-50 flex-none" />
          <span>Cleanup deploy queue</span>
        </Button>
      </DialogTrigger>

      <DialogContent className="gap-0">
        <DialogHeader>
          <DialogTitle>Cleanup the deployment queue ?</DialogTitle>

          <Alert variant="warning" className="my-5">
            <AlertCircleIcon className="h-4 w-4" />
            <AlertTitle>WARNING</AlertTitle>
            <AlertDescription>
              This will stop all currently Queued deployments !
            </AlertDescription>
          </Alert>

          <fetcher.Form
            action="./cleanup-deploy-queue"
            method="post"
            id="cleanup-deploy-queue-form"
            className="flex items-center gap-4 w-full mb-4"
          >
            <FieldSet
              errors={errors.cancel_running_deployments}
              className="flex-1 inline-flex gap-2 flex-col"
            >
              <div className="inline-flex gap-2 items-start">
                <FieldSetCheckbox
                  name="cancel_running_deployments"
                  className="relative top-1"
                />

                <div className="flex flex-col gap-1">
                  <FieldSetLabel className="inline-flex gap-1 items-center">
                    Cancel running deployments ?
                  </FieldSetLabel>
                  <small className="text-grey">
                    If checked, this will cancel all deployments, including
                    running ones
                  </small>
                </div>
              </div>
            </FieldSet>
          </fetcher.Form>
        </DialogHeader>

        <DialogFooter className="-mx-6 px-6">
          <div className="flex items-center gap-4 w-full">
            <SubmitButton
              isPending={isPending}
              variant="destructive"
              form="cleanup-deploy-queue-form"
              className={cn(
                "inline-flex gap-1 items-center",
                isPending ? "bg-red-400" : "bg-red-500"
              )}
            >
              {isPending ? (
                <>
                  <LoaderIcon className="animate-spin flex-none" size={15} />
                  <span>Submitting...</span>
                </>
              ) : (
                <>
                  <span>Confirm</span>
                </>
              )}
            </SubmitButton>

            <Button
              variant="outline"
              type="button"
              onClick={() => setIsOpen(false)}
            >
              Cancel
            </Button>
          </div>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
