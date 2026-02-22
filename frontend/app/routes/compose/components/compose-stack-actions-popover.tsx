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
import { Button, SubmitButton } from "~/components/ui/button";
import {
  Popover,
  PopoverContent,
  PopoverTrigger
} from "~/components/ui/popover";
import type {
  ToggleStackState,
  clientAction as toggleClientAction
} from "~/routes/compose/toggle-compose-stack";

import { toast } from "sonner";
import type { ComposeStack } from "~/api/types";
import { getComposeStackStatus } from "~/components/compose-stack-cards";
import { Alert, AlertDescription, AlertTitle } from "~/components/ui/alert";
import {
  Dialog,
  DialogContent,
  DialogFooter,
  DialogHeader,
  DialogTitle,
  DialogTrigger
} from "~/components/ui/dialog";
import { composeStackQueries } from "~/lib/queries";
import { useToggleStateQueueStore } from "~/lib/toggle-state-store";
import { cn } from "~/lib/utils";
import { queryClient } from "~/root";
import type { clientAction as deployClientAction } from "~/routes/compose/deploy-compose-stack";
import { durationToMs, wait } from "~/utils";

export type ComposeStackActionsPopoverProps = {
  stack: ComposeStack;
  projectSlug: string;
  envSlug: string;
};

export function ComposeStackActionsPopover({
  stack,
  projectSlug,
  envSlug
}: ComposeStackActionsPopoverProps) {
  const deployFetcher = useFetcher<typeof deployClientAction>();

  const navigate = useNavigate();

  React.useEffect(() => {
    if (deployFetcher.state === "idle" && deployFetcher.data) {
      if (!deployFetcher.data.errors) {
        navigate(
          href(
            "/project/:projectSlug/:envSlug/compose-stacks/:composeStackSlug/deployments",
            {
              projectSlug,
              envSlug,
              composeStackSlug: stack.slug
            }
          ) + "/"
        );
      }
    }
  }, [
    stack.slug,
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
        <deployFetcher.Form method="post" action="./deploy">
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
        <ToggleStackForm
          stack={stack}
          projectSlug={projectSlug}
          envSlug={envSlug}
        />
      </PopoverContent>
    </Popover>
  );
}

type ToggleStackFormProps = {
  stack: ComposeStack;
  projectSlug: string;
  envSlug: string;
};

function ToggleStackForm({
  stack,
  projectSlug,
  envSlug
}: ToggleStackFormProps) {
  const fetcher = useFetcher<typeof toggleClientAction>();

  const { queue, queueToggleItem, dequeueToggleItem } =
    useToggleStateQueueStore();

  const stackStatus = getComposeStackStatus(stack);

  const isPending = fetcher.state !== "idle";
  const desiredState: ToggleStackState =
    stackStatus === "NOT_DEPLOYED_YET"
      ? "start"
      : stackStatus === "SLEEPING"
        ? "start"
        : "stop";

  const [isConfirmModalOpen, setIsConfirmModalOpen] = React.useState(false);

  const [, formAction] = React.useActionState(action, null);

  async function action(_: any, formData: FormData) {
    if (queue.has(stack.id)) {
      toast.info("The stack is already being toggled in the background.");
      return;
    }

    await fetcher.submit(formData, {
      action: "./toggle",
      method: "POST"
    });

    const desiredState = formData.get("desired_state") as "stop" | "start";
    queueToggleItem(stack.id);
    toggleStateToast({
      desiredState,
      projectSlug,
      stackSlug: stack.slug,
      envSlug
    }).finally(() => dequeueToggleItem(stack.id));
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
        disabled={stackStatus === "NOT_DEPLOYED_YET"}
        className="flex items-center gap-2 justify-start w-full text-link"
      >
        {isPending ? (
          <>
            <LoaderIcon className="animate-spin flex-none" size={15} />
            <span>Starting...</span>
          </>
        ) : (
          <>
            <PlayIcon size={15} className="flex-none" />
            <span>Start your stack</span>
          </>
        )}
      </SubmitButton>
    </form>
  ) : (
    <StopStackConfirmationDialog
      action={formAction}
      isPending={isPending}
      isOpen={isConfirmModalOpen}
      setIsOpen={(newValue) => {
        if (queue.has(stack.id)) {
          toast.info("The stack is already being toggled in the background.");
          return;
        }
        setIsConfirmModalOpen(newValue);
      }}
    />
  );
}

async function toggleStateToast({
  desiredState,
  projectSlug,
  stackSlug,
  envSlug
}: {
  desiredState: "stop" | "start";
  projectSlug: string;
  stackSlug: string;
  envSlug: string;
}) {
  const stackLink = (
    <Link
      className="text-link underline inline break-all"
      to={href(
        "/project/:projectSlug/:envSlug/compose-stacks/:composeStackSlug",
        {
          projectSlug,
          envSlug,
          composeStackSlug: stackSlug
        }
      )}
    >
      {projectSlug}/{envSlug}/{stackSlug}
    </Link>
  );

  const toastId = toast.loading(
    desiredState === "start" ? (
      <span>Starting {stackLink}, this may take up to a minute...</span>
    ) : (
      <span>Stopping {stackLink}, this may take up to a minute...</span>
    ),
    {
      closeButton: false
    }
  );

  const MAX_TRIES = 12; // wait max for `1min` (12*5s = 60s)
  let total_tries = 0;

  let currentState: ToggleStackState | null = null;

  while (total_tries < MAX_TRIES && currentState !== desiredState) {
    total_tries++;

    // refetch queries to get fresh data
    let stack;
    try {
      stack = await queryClient.fetchQuery(
        composeStackQueries.single({
          project_slug: projectSlug,
          stack_slug: stackSlug,
          env_slug: envSlug
        })
      );
    } catch (error) {
      break;
    }

    currentState =
      getComposeStackStatus(stack) === "SLEEPING" ? "stop" : "start";

    if (currentState !== desiredState && total_tries < MAX_TRIES) {
      await wait(durationToMs(5, "seconds"));
    }
  }

  if (currentState === desiredState) {
    toast.success("Success", {
      description:
        desiredState === "start" ? (
          <>{stackLink} restarted successfully</>
        ) : (
          <>{stackLink} stopped successfully</>
        ),
      closeButton: true,
      id: toastId
    });
  } else {
    toast.warning("Warning", {
      description:
        desiredState === "start" ? (
          <>
            {stackLink} failed to restart within the time limit. Check the
            service replicas and their logs or try again.
          </>
        ) : (
          <>
            {stackLink} failed to stop within the time limit. Check the service
            replicas and their logs or try again.
          </>
        ),
      closeButton: true,
      id: toastId
    });
  }
}

function StopStackConfirmationDialog({
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
          <span>Put stack to sleep</span>
        </Button>
      </DialogTrigger>

      <DialogContent className="gap-0">
        <DialogHeader>
          <DialogTitle>Put this stack to sleep ?</DialogTitle>

          <Alert variant="warning" className="my-5">
            <AlertCircleIcon className="h-4 w-4" />
            <AlertTitle>WARNING</AlertTitle>
            <AlertDescription>
              Putting your stack to sleep will stop all the services in it and
              make them unavailable on the web.
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
