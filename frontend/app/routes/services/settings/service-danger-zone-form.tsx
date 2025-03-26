import { useQuery } from "@tanstack/react-query";
import {
  AlertCircleIcon,
  CheckIcon,
  CopyIcon,
  LoaderIcon,
  PauseIcon,
  PlayIcon,
  PowerIcon,
  SunriseIcon,
  SunsetIcon,
  Trash2Icon
} from "lucide-react";
import * as React from "react";
import { Form, useFetcher, useNavigation } from "react-router";
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
import { serviceQueries } from "~/lib/queries";
import { cn, getFormErrorsFromResponseData } from "~/lib/utils";
import type { clientAction } from "~/routes/services/archive-docker-service";
import { useServiceQuery } from "~/routes/services/settings/services-settings";
import type { clientAction as toggleClientAction } from "~/routes/services/toggle-service-state";
import { wait } from "~/utils";

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
  const deploymentListQuery = useQuery(
    serviceQueries.deploymentList({ project_slug, service_slug, env_slug })
  );

  const deploymentList = deploymentListQuery.data?.results ?? [];
  const currentProductionDeployment = deploymentList.find(
    (dpl) => dpl.is_current_production
  );

  const fetcher = useFetcher<typeof toggleClientAction>();
  const isPending = fetcher.state !== "idle";

  const isSleeping = currentProductionDeployment?.status == "SLEEPING";
  return (
    <div className="flex flex-col gap-4 items-start max-w-4xl w-full rounded-md border border-border p-4">
      {currentProductionDeployment !== undefined && (
        <>
          <div className="flex md:flex-row justify-between items-center w-full">
            <div className="flex flex-col gap-1">
              <h3 className="text-lg font-medium">
                {isSleeping
                  ? "Wake up your service"
                  : "Put your service service to sleep"}
              </h3>
              <p>
                {isSleeping
                  ? "Restart your service"
                  : "Stop your service make it unavailable to the outside."}
              </p>
            </div>

            {!isSleeping ? (
              <StopServiceConfirmationDialog />
            ) : (
              <fetcher.Form method="post" action="../toggle-service-state">
                <input type="hidden" name="desired_state" value="start" />
                <SubmitButton
                  isPending={isPending}
                  className="inline-flex gap-1 items-center"
                >
                  {isPending ? (
                    <>
                      <LoaderIcon
                        className="animate-spin flex-none"
                        size={15}
                      />
                      <span>Submitting...</span>
                    </>
                  ) : (
                    <>
                      <PlayIcon size={15} className="flex-none" />
                      <span>Restart your service</span>
                    </>
                  )}
                </SubmitButton>
              </fetcher.Form>
            )}
          </div>
          <hr className="w-[calc(100%_+_calc(var(--spacing)_*_8))] border-border self-center" />
        </>
      )}

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

function StopServiceConfirmationDialog() {
  const [isOpen, setIsOpen] = React.useState(false);
  const fetcher = useFetcher<typeof toggleClientAction>();
  const formRef = React.useRef<React.ComponentRef<"form">>(null);

  const isPending = fetcher.state !== "idle";

  React.useEffect(() => {
    // only focus on the correct input in case of error
    if (fetcher.state === "idle" && fetcher.data && !fetcher.data.errors) {
      formRef.current?.reset();
      setIsOpen(false);
    }
  }, [fetcher.state, fetcher.data]);

  return (
    <Dialog open={isOpen} onOpenChange={setIsOpen}>
      <DialogTrigger asChild>
        <Button
          type="button"
          variant="warning"
          className="inline-flex gap-1 items-center"
        >
          <PauseIcon size={15} className="flex-none" />
          <span>Put service to sleep</span>
        </Button>
      </DialogTrigger>

      <DialogContent className="gap-0">
        <DialogHeader>
          <DialogTitle>Put this service to sleep ?</DialogTitle>

          <Alert variant="warning" className="my-5">
            <AlertCircleIcon className="h-4 w-4" />
            <AlertTitle>Warning</AlertTitle>
            <AlertDescription>
              Putting your service to sleep will stop it and make it unavailable
              to the outside.
            </AlertDescription>
          </Alert>
        </DialogHeader>

        <DialogFooter className="-mx-6 px-6">
          <fetcher.Form
            action="../toggle-service-state"
            method="post"
            className="flex items-center gap-4 w-full"
          >
            <input type="hidden" name="desired_state" value="stop" />

            <SubmitButton
              isPending={isPending}
              variant="destructive"
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
          </fetcher.Form>
        </DialogFooter>
      </DialogContent>
    </Dialog>
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
            <AlertTitle>Attention !</AlertTitle>
            <AlertDescription>
              Deleting this service will permanently delete all its deployments,
              This action is irreversible.
            </AlertDescription>
          </Alert>

          <DialogDescription className="flex items-center gap-1">
            <span>Please type</span>
            <CopyButton
              variant="outline"
              size="sm"
              showLabel
              className="inline-flex gap-1 items-center"
              value={`${project_slug}/${env_slug}/${service_slug}`}
              label={`${project_slug}/${env_slug}/${service_slug}`}
            />
            <span>to confirm :</span>
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
