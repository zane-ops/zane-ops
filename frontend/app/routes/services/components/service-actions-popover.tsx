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
import { Link, href, useFetcher, useNavigate } from "react-router";
import { Button } from "~/components/ui/button";
import { SubmitButton } from "~/components/ui/button";
import {
  Popover,
  PopoverContent,
  PopoverTrigger
} from "~/components/ui/popover";
import { serviceQueries } from "~/lib/queries";
import type {
  ToggleServiceState,
  clientAction as toggleClientAction
} from "~/routes/services/toggle-service-state";

import { toast } from "sonner";
import type { Service } from "~/api/types";
import type { getComposeStackStatus } from "~/components/compose-stack-cards";
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
import { queryClient } from "~/root";
import { ServiceCleanupQueueConfirmModal } from "~/routes/services/components/service-cleanup-queue-confirm-modal";
import type { clientAction as deployClientAction } from "~/routes/services/deploy-docker-service";
import { durationToMs, wait } from "~/utils";

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

  const [queuedAction, setQueuedAction] = React.useState<
    "start" | "stop" | null
  >(null);

  const [isConfirmModalOpen, setIsConfirmModalOpen] = React.useState(false);

  const [, formAction] = React.useActionState(action, null);

  async function action(_: any, formData: FormData) {
    if (queuedAction) {
      toast.info("The service is already being toggled in the background.");
      return;
    }

    await fetcher.submit(formData, {
      action: "./toggle-service-state",
      method: "POST"
    });

    const desiredState = formData.get("desired_state") as "stop" | "start";
    setQueuedAction(desiredState);
    toggleStateToast({
      desiredState,
      projectSlug,
      serviceSlug,
      envSlug
    }).finally(() => setQueuedAction(null));
  }

  React.useEffect(() => {
    if (fetcher.state === "idle" && fetcher.data && !fetcher.data.errors) {
      setIsConfirmModalOpen(false);
    }
  }, [fetcher.state, fetcher.data]);

  return desiredState === "start" ? (
    <form method="post" action={formAction}>
      <input type="hidden" name="desired_state" value="start" />

      <SubmitButton
        isPending={isPending}
        variant="ghost"
        size="sm"
        disabled={!currentProductionDeployment}
        className="flex items-center gap-2 justify-start dark:text-card-foreground w-full text-link"
      >
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
    </form>
  ) : (
    <StopServiceConfirmationDialog
      action={formAction}
      isPending={isPending}
      isOpen={isConfirmModalOpen}
      setIsOpen={setIsConfirmModalOpen}
    />
  );
}

function StopServiceConfirmationDialog({
  action: formAction,
  isPending,
  isOpen,
  setIsOpen
}: {
  action: (payload: FormData) => void;
  isPending: boolean;
  isOpen: boolean;
  setIsOpen: React.Dispatch<React.SetStateAction<boolean>>;
}) {
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
          <form
            method="post"
            action={formAction}
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
          </form>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}

async function toggleStateToast({
  desiredState,
  projectSlug,
  serviceSlug,
  envSlug
}: {
  desiredState: "stop" | "start";
  projectSlug: string;
  serviceSlug: string;
  envSlug: string;
}) {
  const serviceLink = (
    <Link
      className="text-link underline inline break-all"
      to={href("/project/:projectSlug/:envSlug/services/:serviceSlug", {
        projectSlug,
        envSlug,
        serviceSlug
      })}
    >
      {projectSlug}/{envSlug}/{serviceSlug}
    </Link>
  );

  const toastId = toast.loading(
    desiredState === "start" ? (
      <span>Restarting {serviceLink}, this may take up to a minute...</span>
    ) : (
      <span>Stopping {serviceLink}, this may take up to a minute...</span>
    ),
    {
      closeButton: false
    }
  );

  const MAX_TRIES = 12; // wait max for `1min` (12*5s = 60s)
  let total_tries = 0;
  const deploymentList =
    queryClient.getQueryData(
      serviceQueries.deploymentList({
        project_slug: projectSlug,
        service_slug: serviceSlug,
        env_slug: envSlug
      }).queryKey
    )?.results ?? [];

  let currentProductionDeployment =
    deploymentList.find((dpl) => dpl.is_current_production) ?? null;

  let currentState: ToggleServiceState | null = null;

  while (
    total_tries < MAX_TRIES &&
    currentProductionDeployment !== null &&
    currentState !== desiredState
  ) {
    total_tries++;

    // refetch queries to get fresh data
    const deploymentList =
      (
        await queryClient.fetchQuery(
          serviceQueries.deploymentList({
            project_slug: projectSlug,
            service_slug: serviceSlug,
            env_slug: envSlug
          })
        )
      )?.results ?? [];

    currentProductionDeployment =
      deploymentList.find((dpl) => dpl.is_current_production) ?? null;

    if (currentProductionDeployment) {
      currentState =
        currentProductionDeployment.status === "SLEEPING" ? "stop" : "start";
    }

    if (currentState !== desiredState && total_tries < MAX_TRIES) {
      await wait(durationToMs(5, "seconds"));
    }
  }

  if (currentState === desiredState) {
    toast.success("Success", {
      description:
        desiredState === "start" ? (
          <>{serviceLink} restarted successfully</>
        ) : (
          <>{serviceLink} stopped successfully</>
        ),
      closeButton: true,
      id: toastId
    });
  } else {
    toast.warning("Warning", {
      description:
        desiredState === "start" ? (
          <>
            {serviceLink} failed to restart within the time limit. Check the
            deployment logs or try again.
          </>
        ) : (
          <>
            {serviceLink} failed to stop within the time limit. Check the
            deployment logs or try again.
          </>
        ),
      closeButton: true,
      id: toastId
    });
  }
}
