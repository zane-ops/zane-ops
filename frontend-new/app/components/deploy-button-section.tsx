import { LoaderIcon, TriangleAlert } from "lucide-react";
import * as React from "react";
import { Button, SubmitButton } from "~/components/ui/button";
import type { useDeployDockerServiceMutation } from "~/lib/hooks/use-deploy-docker-service-mutation";
import type { DockerService } from "~/lib/queries";
import { cn } from "~/lib/utils";
import { pluralize } from "~/utils";

export type DeployButtonSectionProps = {
  service: DockerService;
  deploy: ReturnType<typeof useDeployDockerServiceMutation>["mutateAsync"];
  className?: string;
};

export function DeployButtonSection({
  service,
  deploy,
  className
}: DeployButtonSectionProps) {
  const [isDeploying, startTransition] = React.useTransition();
  return (
    <div className={cn("flex items-center gap-2 flex-wrap", className)}>
      {service.unapplied_changes.length > 0 && (
        <Button variant="warning" className="flex-1 md:flex-auto">
          <TriangleAlert size={15} />
          <span className="mx-1">
            {service.unapplied_changes.length}&nbsp;
            {pluralize("unapplied change", service.unapplied_changes.length)}
          </span>
        </Button>
      )}

      <form
        action={async () => {
          startTransition(() => deploy({}));
        }}
        className="flex flex-1 md:flex-auto"
      >
        <SubmitButton
          isPending={isDeploying}
          variant="secondary"
          className="w-full"
        >
          {isDeploying ? (
            <>
              <span>Deploying</span>
              <LoaderIcon className="animate-spin" size={15} />
            </>
          ) : (
            "Deploy now"
          )}
        </SubmitButton>
      </form>
    </div>
  );
}
