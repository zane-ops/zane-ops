import { useQuery } from "@tanstack/react-query";
import {
  AlertCircleIcon,
  ChevronDownIcon,
  LoaderIcon,
  PauseIcon,
  PlayIcon,
  RocketIcon
} from "lucide-react";
import * as React from "react";
import { href, useFetcher, useNavigate } from "react-router";
import { Button } from "~/components/ui/button";
import { SubmitButton } from "~/components/ui/button";
import {
  Popover,
  PopoverContent,
  PopoverTrigger
} from "~/components/ui/popover";
import { type Service, serviceQueries } from "~/lib/queries";
import type {
  ToggleServiceState,
  clientAction as toggleClientAction
} from "~/routes/services/toggle-service-state";

import { Alert, AlertDescription, AlertTitle } from "~/components/ui/alert";
import {
  Dialog,
  DialogContent,
  DialogFooter,
  DialogHeader,
  DialogTitle,
  DialogTrigger
} from "~/components/ui/dialog";
import { cn } from "~/lib/utils";
import { ServiceCleanupQueueConfirmModal } from "~/routes/services/components/service-cleanup-queue-confirm-modal";
import type { clientAction as deployClientAction } from "~/routes/services/deploy-docker-service";

export type ServiceActionsPopoverProps = {
  service: Service;
  projectSlug: string;
  envSlug: string;
};

export function ServiceActionsPopover({
  service,
  projectSlug,
  envSlug
}: ServiceActionsPopoverProps) {
  const deployFetcher = useFetcher<typeof deployClientAction>();

  const navigate = useNavigate();

  React.useEffect(() => {
    if (deployFetcher.state === "idle" && deployFetcher.data) {
      if (!deployFetcher.data.errors) {
        navigate(
          href("/project/:projectSlug/:envSlug/services/:serviceSlug", {
            projectSlug,
            envSlug,
            serviceSlug: service.slug
          })
        );
      }
    }
  }, [
    service.slug,
    projectSlug,
    envSlug,
    deployFetcher.data,
    deployFetcher.state
  ]);
  return (
    <Popover>
      <PopoverTrigger asChild>
        <Button
          type="button"
          variant="secondary"
          className=" md:flex-auto gap-1 rounded-md"
        >
          <span>Actions</span>
          <ChevronDownIcon size={15} />
        </Button>
      </PopoverTrigger>
      <PopoverContent
        side="bottom"
        align="end"
        sideOffset={5}
        className={cn(
          "w-min",
          "flex flex-col gap-0 p-2",
          "z-50 rounded-md border border-border bg-popover text-popover-foreground shadow-md outline-hidden",
          "data-[state=open]:animate-in data-[state=closed]:animate-out data-[state=closed]:fade-out-0 data-[state=open]:fade-in-0 data-[state=closed]:zoom-out-95 data-[state=open]:zoom-in-95",
          "data-[side=bottom]:slide-in-from-top-2 data-[side=left]:slide-in-from-right-2 data-[side=right]:slide-in-from-left-2 data-[side=top]:slide-in-from-bottom-2"
        )}
      >
        <deployFetcher.Form
          method="post"
          action={
            service.type === "DOCKER_REGISTRY"
              ? "./deploy-docker-service"
              : "./deploy-git-service"
          }
        >
          <SubmitButton
            isPending={deployFetcher.state !== "idle"}
            variant="ghost"
            size="sm"
            className="flex items-center gap-2 justify-start dark:text-card-foreground w-full"
          >
            {deployFetcher.state !== "idle" ? (
              <LoaderIcon
                className="animate-spin opacity-50 flex-none"
                size={15}
              />
            ) : (
              <RocketIcon size={15} className="flex-none opacity-50" />
            )}
            <span>Deploy now</span>
          </SubmitButton>
        </deployFetcher.Form>
        <ServiceCleanupQueueConfirmModal />
        <ToggleServiceForm
          serviceSlug={service.slug}
          projectSlug={projectSlug}
          envSlug={envSlug}
        />
      </PopoverContent>
    </Popover>
  );
}

type ToggleServiceFormProps = {
  serviceSlug: string;
  projectSlug: string;
  envSlug: string;
};

function ToggleServiceForm({
  serviceSlug,
  projectSlug,
  envSlug
}: ToggleServiceFormProps) {
  const fetcher = useFetcher<typeof toggleClientAction>();
  const deploymentListQuery = useQuery(
    serviceQueries.deploymentList({
      project_slug: projectSlug,
      service_slug: serviceSlug,
      env_slug: envSlug
    })
  );

  const deploymentList = deploymentListQuery.data?.results ?? [];
  const currentProductionDeployment = deploymentList.find(
    (dpl) => dpl.is_current_production
  );
  const isPending = fetcher.state !== "idle";
  const desiredState: ToggleServiceState = !currentProductionDeployment
    ? "start"
    : currentProductionDeployment?.status === "SLEEPING"
      ? "start"
      : "stop";

  return desiredState === "start" ? (
    <fetcher.Form method="post" action="./toggle-service-state">
      <SubmitButton
        isPending={fetcher.state !== "idle"}
        variant="ghost"
        size="sm"
        disabled={!currentProductionDeployment}
        className="flex items-center gap-2 justify-start dark:text-card-foreground w-full text-link"
      >
        <input type="hidden" name="desired_state" value="start" />
        {isPending ? (
          <>
            <LoaderIcon className="animate-spin flex-none" size={15} />
            <span>Restarting...</span>
          </>
        ) : (
          <>
            <PlayIcon size={15} className="flex-none" />
            <span>Restart your service</span>
          </>
        )}
      </SubmitButton>
    </fetcher.Form>
  ) : (
    <StopServiceConfirmationDialog />
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
          variant="ghost"
          size="sm"
          className="inline-flex gap-2 items-center justify-start text-amber-600 dark:text-yellow-500"
        >
          <PauseIcon size={15} className="flex-none opacity-50" />
          <span>Put service to sleep</span>
        </Button>
      </DialogTrigger>

      <DialogContent className="gap-0">
        <DialogHeader>
          <DialogTitle>Put this service to sleep ?</DialogTitle>

          <Alert variant="warning" className="my-5">
            <AlertCircleIcon className="h-4 w-4" />
            <AlertTitle>WARNING</AlertTitle>
            <AlertDescription>
              Putting your service to sleep will stop it and make it unavailable
              on the web.
            </AlertDescription>
          </Alert>
        </DialogHeader>

        <DialogFooter className="-mx-6 px-6">
          <fetcher.Form
            action="./toggle-service-state"
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
                  <span>Stopping...</span>
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
              Close
            </Button>
          </fetcher.Form>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
