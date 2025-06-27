import { ChevronDownIcon, LoaderIcon, RocketIcon } from "lucide-react";
import * as React from "react";
import { useFetcher, useNavigate } from "react-router";
import { Button } from "~/components/ui/button";
import { SubmitButton } from "~/components/ui/button";
import {
  Popover,
  PopoverContent,
  PopoverTrigger
} from "~/components/ui/popover";
import type { Service } from "~/lib/queries";
import { cn } from "~/lib/utils";
import { ServiceCleanupQueueConfirmModal } from "~/routes/services/components/service-cleanup-queue-confirm-modal";
import type { clientAction as deployClientAction } from "~/routes/services/deploy-docker-service";

export type ServiceActionsPopupProps = {
  service: Service;
  project_slug?: string;
  env_slug?: string;
};

export function ServiceActionsPopup({
  service,
  project_slug,
  env_slug
}: ServiceActionsPopupProps) {
  const deployFetcher = useFetcher<typeof deployClientAction>();

  const navigate = useNavigate();

  React.useEffect(() => {
    if (deployFetcher.state === "idle" && deployFetcher.data) {
      if (!deployFetcher.data.errors) {
        navigate(
          `/project/${project_slug}/${env_slug}/services/${service.slug}`
        );
      }
    }
  }, [
    service.slug,
    project_slug,
    env_slug,
    deployFetcher.data,
    deployFetcher.state
  ]);
  return (
    <Popover>
      <PopoverTrigger asChild>
        <Button
          type="button"
          variant="secondary"
          className="flex-1 md:flex-auto gap-1 rounded-md"
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
      </PopoverContent>
    </Popover>
  );
}
