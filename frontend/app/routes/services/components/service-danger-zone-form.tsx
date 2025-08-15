import { AlertCircleIcon, LoaderIcon, Trash2Icon } from "lucide-react";
import * as React from "react";
import { useFetcher } from "react-router";
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
import type { clientAction } from "~/routes/services/archive-docker-service";
import { useServiceQuery } from "~/routes/services/settings/service-settings";

export type ServiceDangerZoneFormProps = {
  project_slug: string;
  service_slug: string;
  env_slug: string;
};

export function ServiceDangerZoneForm({
  project_slug,
  service_slug,
  env_slug
}: ServiceDangerZoneFormProps) {
  return (
    <div className="flex flex-col gap-4 items-start max-w-4xl w-full rounded-md border border-border p-4">
      <div className="flex md:flex-row justify-between items-center w-full">
        <div className="flex flex-col gap-1">
          <h3 className="text-lg font-medium">Delete service</h3>
          <p>Deletes the service and all its deployments</p>
        </div>
        <DeleteConfirmationFormDialog
          service_slug={service_slug}
          project_slug={project_slug}
          env_slug={env_slug}
        />
      </div>
    </div>
  );
}

function DeleteConfirmationFormDialog({
  service_slug,
  project_slug,
  env_slug
}: { service_slug: string; project_slug: string; env_slug: string }) {
  const [isOpen, setIsOpen] = React.useState(false);
  const fetcher = useFetcher<typeof clientAction>();
  const formRef = React.useRef<React.ComponentRef<"form">>(null);
  const { data: service } = useServiceQuery({
    service_slug,
    project_slug,
    env_slug
  });

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
          <span>Delete service</span>
        </Button>
      </DialogTrigger>
      <DialogContent className="gap-0">
        <DialogHeader className="pb-4">
          <DialogTitle>Delete this service ?</DialogTitle>

          <Alert variant="danger" className="my-5">
            <AlertCircleIcon className="h-4 w-4" />
            <AlertTitle>ATTENTION !</AlertTitle>
            <AlertDescription>
              Deleting this service will permanently delete all its deployments,
              This action is irreversible.
            </AlertDescription>
          </Alert>

          <DialogDescription className="inline-flex gap-1 items-center flex-wrap">
            <span className="whitespace-nowrap">Please type</span>
            <CopyButton
              variant="outline"
              size="sm"
              showLabel
              className="inline-flex gap-1 items-center"
              value={`${project_slug}/${env_slug}/${service_slug}`}
              label={`${project_slug}/${env_slug}/${service_slug}`}
            />
            <span className="whitespace-nowrap">to confirm :</span>
          </DialogDescription>
        </DialogHeader>

        <fetcher.Form
          className="flex flex-col w-full mb-5 gap-1"
          method="post"
          id="delete-form"
          ref={formRef}
          action={
            service.type === "DOCKER_REGISTRY"
              ? "../archive-docker-service"
              : "../archive-git-service"
          }
        >
          <FieldSet name="service_slug" errors={errors.service_slug}>
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
