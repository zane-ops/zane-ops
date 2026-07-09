import { Trash2Icon } from "lucide-react";
import { useFetcher } from "react-router";
import { DeleteConfirmationDialog } from "~/components/delete-confirmation-dialog";
import { Button } from "~/components/ui/button";
import { DialogTrigger } from "~/components/ui/dialog";
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
  const fetcher = useFetcher<typeof clientAction>();
  const { data: service } = useServiceQuery({
    service_slug,
    project_slug,
    env_slug
  });
  const errors = getFormErrorsFromResponseData(fetcher.data?.errors);

  return (
    <DeleteConfirmationDialog
      fetcher={fetcher}
      title="Delete this service ?"
      message="Deleting this service will permanently delete all its deployments, This action is irreversible."
      confirmationValue={`${project_slug}/${env_slug}/${service_slug}`}
      confirmationFieldName="service_slug"
      form={
        <fetcher.Form
          method="post"
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
      }
      trigger={
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
      }
    />
  );
}
