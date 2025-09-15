import {
  ChevronRightIcon,
  CircleCheckBigIcon,
  LoaderIcon,
  TriangleAlert,
  Undo2Icon
} from "lucide-react";
import * as React from "react";
import { useFetcher, useNavigate } from "react-router";
import {
  BuilderChangeField,
  CommandChangeField,
  ConfigChangeItem,
  EnvVariableChangeItem,
  GitSourceChangeField,
  HealthcheckChangeField,
  PortChangeItem,
  ResourceLimitChangeField,
  SourceChangeField,
  UrlChangeItem,
  VolumeChangeItem
} from "~/components/change-fields";
import {
  Accordion,
  AccordionContent,
  AccordionItem,
  AccordionTrigger
} from "~/components/ui/accordion";
import { Button } from "~/components/ui/button";
import { SubmitButton } from "~/components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogTitle,
  DialogTrigger
} from "~/components/ui/dialog";
import { DialogFooter, DialogHeader } from "~/components/ui/dialog";
import {
  FieldSet,
  FieldSetCheckbox,
  FieldSetLabel
} from "~/components/ui/fieldset";
import { Input } from "~/components/ui/input";
import type { Service } from "~/lib/queries";
import { cn, getFormErrorsFromResponseData } from "~/lib/utils";
import type { clientAction } from "~/routes/services/deploy-docker-service";
import { capitalizeText, pluralize } from "~/utils";

type ServiceChangeModalProps = {
  service: Service;
  project_slug: string;
};
export function ServiceChangesModal({
  service,
  project_slug
}: ServiceChangeModalProps) {
  const fetcher = useFetcher<typeof clientAction>();
  const [isOpen, setIsOpen] = React.useState(false);
  const isDeploying = fetcher.state !== "idle";
  const navigate = useNavigate();

  const errors = getFormErrorsFromResponseData(fetcher.data?.errors);

  React.useEffect(() => {
    if (fetcher.state === "idle" && fetcher.data) {
      if (!fetcher.data.errors) {
        setIsOpen(false);
        navigate(
          `/project/${project_slug}/${service.environment.name}/services/${service.slug}`
        );
      }
    }
  }, [fetcher.data, fetcher.state]);

  const serviceChangeGroups = Object.groupBy(
    service.unapplied_changes,
    ({ field }) => field
  );

  return (
    <Dialog open={isOpen} onOpenChange={setIsOpen}>
      <DialogTrigger asChild>
        {service.unapplied_changes.length === 0 ? (
          <Button variant="ghost">
            <CircleCheckBigIcon size={15} />
            <span className="ml-1 underline">No pending changes</span>
          </Button>
        ) : (
          <Button variant="warning">
            <TriangleAlert size={15} />
            <span className="mx-1">
              {service.unapplied_changes.length}&nbsp;
              {pluralize("pending change", service.unapplied_changes.length)}
            </span>
          </Button>
        )}
      </DialogTrigger>
      <DialogContent className="max-w-[min(var(--container-4xl),calc(100%_-_var(--spacing)*8))] gap-0">
        <DialogHeader className="pb-4">
          <DialogTitle>
            {service.unapplied_changes.length === 0 ? (
              "no changes to apply"
            ) : (
              <>
                {service.unapplied_changes.length}&nbsp;
                {pluralize("change", service.unapplied_changes.length)}&nbsp;to
                apply
              </>
            )}
          </DialogTitle>
        </DialogHeader>
        {service.unapplied_changes.length === 0 && (
          <div className="border-t border-border -mx-6 px-6 py-4">
            <div
              className={cn(
                "border-dashed border border-foreground rounded-md px-4 py-8 font-mono",
                "flex items-center justify-center text-foreground h-100"
              )}
            >
              No changes queued
            </div>
          </div>
        )}
        {service.unapplied_changes.length > 0 && (
          <Accordion
            type="multiple"
            className="border-t border-border -mx-6 px-6 flex flex-col gap-2 h-100 overflow-auto py-4"
          >
            {Object.entries(serviceChangeGroups).map((item) => {
              const field = item[0] as keyof typeof serviceChangeGroups;
              const changes = item[1] as NonNullable<
                (typeof serviceChangeGroups)[typeof field]
              >;
              const fieldName = field === "configs" ? "Config files" : field;
              return (
                <div className="relative" key={field}>
                  <DiscardMultipleForm changes={changes} />
                  <AccordionItem
                    value={field}
                    className="flex flex-col border rounded-md relative"
                  >
                    <AccordionTrigger className="text-lg flex gap-2 items-center py-2 border-border bg-muted px-4">
                      <ChevronRightIcon
                        size={15}
                        className="flex-none text-grey"
                      />
                      <span>
                        {capitalizeText(fieldName.replaceAll("_", " "))}
                      </span>
                      <small className="text-grey">
                        {changes.length} {pluralize("change", changes.length)}
                        &nbsp;will be applied
                      </small>
                    </AccordionTrigger>
                    <AccordionContent className="py-4 flex flex-col gap-2 px-4">
                      {field === "volumes" &&
                        changes.map((change) => (
                          <ChangeForm key={change.id} change_id={change.id}>
                            <VolumeChangeItem unapplied change={change} />
                          </ChangeForm>
                        ))}
                      {field === "configs" &&
                        changes.map((change) => (
                          <ChangeForm key={change.id} change_id={change.id}>
                            <ConfigChangeItem unapplied change={change} />
                          </ChangeForm>
                        ))}
                      {field === "source" &&
                        changes.map((change) => (
                          <ChangeForm key={change.id} change_id={change.id}>
                            <SourceChangeField unapplied change={change} />
                          </ChangeForm>
                        ))}
                      {field === "git_source" &&
                        changes.map((change) => (
                          <ChangeForm key={change.id} change_id={change.id}>
                            <GitSourceChangeField unapplied change={change} />
                          </ChangeForm>
                        ))}
                      {field === "builder" &&
                        changes.map((change) => (
                          <ChangeForm key={change.id} change_id={change.id}>
                            <BuilderChangeField unapplied change={change} />
                          </ChangeForm>
                        ))}
                      {field === "command" &&
                        changes.map((change) => (
                          <ChangeForm key={change.id} change_id={change.id}>
                            <CommandChangeField unapplied change={change} />
                          </ChangeForm>
                        ))}
                      {field === "ports" &&
                        changes.map((change) => (
                          <ChangeForm key={change.id} change_id={change.id}>
                            <PortChangeItem unapplied change={change} />
                          </ChangeForm>
                        ))}
                      {field === "env_variables" &&
                        changes.map((change) => (
                          <ChangeForm key={change.id} change_id={change.id}>
                            <EnvVariableChangeItem
                              change={change}
                              key={change.id}
                              unapplied
                            />
                          </ChangeForm>
                        ))}
                      {field === "urls" &&
                        changes.map((change) => (
                          <ChangeForm key={change.id} change_id={change.id}>
                            <UrlChangeItem
                              unapplied
                              change={change}
                              key={change.id}
                            />
                          </ChangeForm>
                        ))}
                      {field === "healthcheck" &&
                        changes.map((change) => (
                          <ChangeForm key={change.id} change_id={change.id}>
                            <HealthcheckChangeField
                              change={change}
                              key={change.id}
                              unapplied
                            />
                          </ChangeForm>
                        ))}
                      {field === "resource_limits" &&
                        changes.map((change) => (
                          <ChangeForm key={change.id} change_id={change.id}>
                            <ResourceLimitChangeField
                              change={change}
                              key={change.id}
                              unapplied
                            />
                          </ChangeForm>
                        ))}
                    </AccordionContent>
                  </AccordionItem>
                </div>
              );
            })}
          </Accordion>
        )}
        <DialogFooter className="border-t border-border -mx-6 px-6 pt-4">
          <fetcher.Form
            className="flex items-end gap-4 w-full justify-between"
            method="post"
            action={
              service.type === "DOCKER_REGISTRY"
                ? "./deploy-docker-service"
                : "./deploy-git-service"
            }
          >
            <div className="flex flex-col gap-3">
              <h3 className="text-lg dark:text-card-foreground">Deploy now</h3>
              {service.type === "DOCKER_REGISTRY" && (
                <FieldSet
                  errors={errors.commit_message}
                  className="flex flex-col gap-1"
                >
                  <FieldSetLabel htmlFor="commit_message">
                    Commit message
                  </FieldSetLabel>
                  <Input
                    id="commit_message"
                    name="commit_message"
                    placeholder="commit message for deployment"
                  />
                </FieldSet>
              )}

              {service.type === "GIT_REPOSITORY" && (
                <FieldSet
                  // @ts-expect-error
                  errors={errors.ignore_build_cache}
                  className="flex-1 inline-flex gap-2 flex-col"
                >
                  <div className="inline-flex gap-2 items-start">
                    <FieldSetCheckbox
                      name="ignore_build_cache"
                      className="relative top-1"
                    />

                    <div className="flex flex-col gap-1">
                      <FieldSetLabel className="inline-flex gap-1 items-center">
                        Ignore build cache ?
                      </FieldSetLabel>
                      <small className="text-grey">
                        If checked, this will ignore all the cached folders
                        generated by your builds.
                      </small>
                    </div>
                  </div>
                </FieldSet>
              )}

              <FieldSet
                errors={errors.cleanup_queue}
                className="flex-1 inline-flex gap-2 flex-col"
              >
                <div className="inline-flex gap-2 items-start">
                  <FieldSetCheckbox
                    name="cleanup_queue"
                    className="relative top-1"
                  />

                  <div className="flex flex-col gap-1">
                    <FieldSetLabel className="inline-flex gap-1 items-center">
                      Cleanup deployment queue
                    </FieldSetLabel>
                    <small className="text-grey">
                      If checked, this will stop and cancel all deployments,
                      including running ones
                    </small>
                  </div>
                </div>
              </FieldSet>
            </div>

            <SubmitButton isPending={isDeploying} variant="secondary">
              {isDeploying ? (
                <>
                  <span>Deploying</span>
                  <LoaderIcon className="animate-spin" size={15} />
                </>
              ) : (
                "Deploy now"
              )}
            </SubmitButton>
          </fetcher.Form>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}

function DiscardMultipleForm({
  changes
}: { changes: Service["unapplied_changes"] }) {
  const fetcher = useFetcher();
  const isPending = fetcher.state !== "idle";
  return (
    <fetcher.Form
      method="post"
      action="./discard-multiple-changes"
      className="absolute right-4 z-10 top-1"
    >
      {changes.map((ch) => (
        <input type="hidden" name="change_id" value={ch.id} />
      ))}
      <SubmitButton
        isPending={isPending}
        className="bg-transparent"
        variant="outline"
        size="sm"
      >
        {isPending ? (
          <>
            <LoaderIcon className="animate-spin" size={15} />
            <span>Discarding...</span>
          </>
        ) : (
          <>
            <Undo2Icon size={15} className="flex-none" />
            <span>Discard all</span>
          </>
        )}
      </SubmitButton>
    </fetcher.Form>
  );
}

function ChangeForm({
  change_id,
  children
}: { change_id: string; children: React.ReactNode }) {
  const fetcher = useFetcher();
  const isLoading = fetcher.state !== "idle";
  return (
    <fetcher.Form
      method="post"
      action="./discard-change"
      key={change_id}
      className="flex flex-col gap-3"
    >
      <input type="hidden" name="change_id" value={change_id} />
      {children}
      <hr className="border border-dashed border-border" />
      <SubmitButton
        isPending={isLoading}
        variant="outline"
        name="intent"
        value="cancel-service-change"
        className="self-end"
      >
        {isLoading ? (
          <>
            <LoaderIcon className="animate-spin" size={15} />
            <span>Discarding...</span>
          </>
        ) : (
          <>
            <Undo2Icon size={15} className="flex-none" />
            <span>Discard</span>
          </>
        )}
      </SubmitButton>
    </fetcher.Form>
  );
}
