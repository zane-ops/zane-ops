import { AlertCircleIcon, LoaderIcon, TriangleAlertIcon } from "lucide-react";
import * as React from "react";
import type { FetcherWithComponents } from "react-router";
import { CopyButton } from "~/components/copy-button";
import { Alert, AlertDescription, AlertTitle } from "~/components/ui/alert";
import { Button, SubmitButton } from "~/components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle
} from "~/components/ui/dialog";
import { cn, getFormErrorsFromResponseData } from "~/lib/utils";

function useConfirmationDialogState({
  fetcher,
  focusFieldName
}: {
  fetcher: FetcherWithComponents<any>;
  focusFieldName?: string;
}) {
  const [isOpen, setIsOpen] = React.useState(false);
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
      } else if (focusFieldName) {
        (
          formRef.current?.elements.namedItem(
            focusFieldName
          ) as HTMLInputElement | null
        )?.focus();
      }
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [fetcher.state, fetcher.data]);

  const close = React.useCallback(() => {
    setIsOpen(false);
    setData(undefined);
  }, []);

  return { isOpen, setIsOpen, formRef, isPending, errors, close };
}

type SharedDialogProps = {
  /** Full trigger node, must include a `DialogTrigger asChild` wrapper */
  trigger: React.ReactNode;
  title: React.ReactNode;
  message: React.ReactNode;
  fetcher: FetcherWithComponents<any>;
  /**
   * The `<fetcher.Form>` built by the caller (method, action, hidden
   * fields, ...). A `ref` and `id` are injected onto it automatically so
   * the dialog's submit button can be linked to it from outside the form.
   */
  form: React.ReactElement<
    React.ComponentProps<"form"> & { ref?: React.Ref<HTMLFormElement> }
  >;
  confirmText?: string;
  pendingText?: string;
  variant?: "danger" | "warning";
};

export type DeleteConfirmationDialogProps = SharedDialogProps & {
  confirmationValue: string;
  /** Name of the caller's confirmation field, used to focus it on error */
  confirmationFieldName?: string;
};

export function DeleteConfirmationDialog({
  trigger,
  title,
  message,
  fetcher,
  form,
  confirmationValue,
  confirmationFieldName,
  confirmText,
  pendingText,
  variant = "danger"
}: DeleteConfirmationDialogProps) {
  const { isOpen, setIsOpen, formRef, isPending, errors, close } =
    useConfirmationDialogState({
      fetcher,
      focusFieldName: confirmationFieldName
    });

  return (
    <Dialog
      open={isOpen}
      onOpenChange={(open) => {
        if (isPending) return;
        setIsOpen(open);
        if (!open) close();
      }}
    >
      {trigger}
      <DialogContent className="gap-0">
        <DialogHeader className="pb-4">
          <DialogTitle>{title}</DialogTitle>

          <Alert variant={variant} className="my-5">
            {variant === "danger" ? (
              <TriangleAlertIcon className="size-4" />
            ) : (
              <AlertCircleIcon className="size-4" />
            )}
            <AlertTitle>
              {variant === "danger" ? "Attention" : "Warning"}
            </AlertTitle>
            <AlertDescription>{message}</AlertDescription>
          </Alert>

          <DialogDescription className="inline-flex gap-1 items-center flex-wrap">
            <span className="whitespace-nowrap">Please type</span>
            <CopyButton
              variant="outline"
              size="sm"
              showLabel
              className="inline-flex gap-1 items-center"
              value={confirmationValue}
              label={confirmationValue}
            />
            <span className="whitespace-nowrap">to confirm :</span>
          </DialogDescription>
        </DialogHeader>

        {errors.non_field_errors && (
          <Alert variant="destructive">
            <AlertCircleIcon className="h-4 w-4" />
            <AlertTitle>Error</AlertTitle>
            <AlertDescription>{errors.non_field_errors}</AlertDescription>
          </Alert>
        )}

        {React.cloneElement(form, {
          ref: formRef,
          id: "delete-form",
          className: cn("flex flex-col w-full mb-5 gap-1", form.props.className)
        })}

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
                  <span>{pendingText ?? "Deleting..."}</span>
                </>
              ) : (
                <span>{confirmText ?? "Delete"}</span>
              )}
            </SubmitButton>

            <Button variant="outline" disabled={isPending} onClick={close}>
              Cancel
            </Button>
          </div>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}

export type SimpleConfirmationDialogProps = SharedDialogProps & {
  /** Extra read-only info shown above the form */
  extraInfo?: React.ReactNode;
};

export function SimpleConfirmationDialog({
  trigger,
  title,
  message,
  fetcher,
  form,
  extraInfo,
  confirmText,
  pendingText,
  variant = "danger"
}: SimpleConfirmationDialogProps) {
  const { isOpen, setIsOpen, formRef, isPending, errors, close } =
    useConfirmationDialogState({ fetcher });

  return (
    <Dialog
      open={isOpen}
      onOpenChange={(open) => {
        if (isPending) return;
        setIsOpen(open);
        if (!open) close();
      }}
    >
      {trigger}
      <DialogContent className="gap-0">
        <DialogHeader>
          <DialogTitle>{title}</DialogTitle>

          <Alert variant={variant} className="my-5">
            {variant === "danger" ? (
              <TriangleAlertIcon className="size-4" />
            ) : (
              <AlertCircleIcon className="size-4" />
            )}
            <AlertTitle>
              {variant === "danger" ? "Attention" : "Warning"}
            </AlertTitle>
            <AlertDescription>{message}</AlertDescription>
          </Alert>
        </DialogHeader>

        {errors.non_field_errors && (
          <Alert variant="destructive">
            <AlertCircleIcon className="h-4 w-4" />
            <AlertTitle>Error</AlertTitle>
            <AlertDescription>{errors.non_field_errors}</AlertDescription>
          </Alert>
        )}

        {extraInfo}

        {React.cloneElement(form, { ref: formRef, id: "confirm-form" })}

        <DialogFooter className="-mx-6 px-6">
          <div className="flex items-center gap-4 w-full">
            <SubmitButton
              isPending={isPending}
              variant="destructive"
              form="confirm-form"
              className={cn(
                "inline-flex gap-1 items-center",
                isPending ? "bg-red-400" : "bg-red-500"
              )}
            >
              {isPending ? (
                <>
                  <LoaderIcon className="animate-spin flex-none" size={15} />
                  <span>{pendingText ?? "Submitting..."}</span>
                </>
              ) : (
                <span>{confirmText ?? "Confirm"}</span>
              )}
            </SubmitButton>

            <Button
              variant="outline"
              type="button"
              disabled={isPending}
              onClick={close}
            >
              Cancel
            </Button>
          </div>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
