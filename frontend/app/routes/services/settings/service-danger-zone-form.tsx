import { useQuery } from "@tanstack/react-query";
import { LoaderIcon, SunriseIcon, SunsetIcon, Trash2Icon } from "lucide-react";
import { Form, useNavigation } from "react-router";
import { SubmitButton } from "~/components/ui/button";
import { serviceQueries } from "~/lib/queries";
import { cn } from "~/lib/utils";

export type ServiceDangerZoneFormProps = {
  project_slug: string;
  service_slug: string;
};

export function ServiceDangerZoneForm({
  project_slug,
  service_slug
}: ServiceDangerZoneFormProps) {
  const deploymentListQuery = useQuery(
    serviceQueries.deploymentList({ project_slug, service_slug })
  );

  const deploymentList = deploymentListQuery.data?.results ?? [];
  const currentProductionDeployment = deploymentList.find(
    (dpl) => dpl.is_current_production
  );

  const navigation = useNavigation();
  const isPending = navigation.state !== "idle";

  return (
    <div className="flex flex-col gap-4 items-start max-w-4xl w-full">
      {currentProductionDeployment !== undefined && (
        <>
          <h3 className="text-lg">Toggle service state</h3>

          <Form method="post" action="../toggle-service-state">
            <SubmitButton
              isPending={isPending}
              variant={
                currentProductionDeployment?.status == "SLEEPING"
                  ? "default"
                  : "warning"
              }
              className="inline-flex gap-1 items-center"
            >
              {isPending ? (
                <>
                  <LoaderIcon className="animate-spin flex-none" size={15} />
                  <span>Submitting...</span>
                </>
              ) : currentProductionDeployment?.status == "SLEEPING" ? (
                <>
                  <SunriseIcon size={15} className="flex-none" />
                  <span>Wake up service</span>
                </>
              ) : (
                <>
                  <SunsetIcon size={15} className="flex-none" />
                  <span>Put service to sleep</span>
                </>
              )}
            </SubmitButton>
          </Form>
        </>
      )}

      <hr className="w-full border-border" />
      <h3 className="text-lg text-red-400">Archive this service</h3>

      <Form
        className="flex flex-col gap-2 items-start"
        method="post"
        action="../archive-service"
      >
        <p className="text-red-400 ">
          Archiving this service will permanently delete all its deployments,
          This cannot be undone.
        </p>

        <SubmitButton
          variant="destructive"
          className={cn(
            "inline-flex gap-1 items-center",
            isPending ? "bg-red-400" : "bg-red-500"
          )}
          isPending={isPending}
        >
          {isPending ? (
            <>
              <LoaderIcon className="animate-spin flex-none" size={15} />
              <span>Archiving...</span>
            </>
          ) : (
            <>
              <Trash2Icon size={15} className="flex-none" />
              <span>Archive service</span>
            </>
          )}
        </SubmitButton>
      </Form>
    </div>
  );
}
