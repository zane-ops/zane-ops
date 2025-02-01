import {
  ActivityIcon,
  ChevronRightIcon,
  ContainerIcon,
  EthernetPortIcon,
  GlobeIcon,
  HardDriveIcon,
  HourglassIcon,
  KeyRoundIcon,
  LoaderIcon,
  TerminalIcon,
  TriangleAlert,
  Undo2Icon,
  XIcon
} from "lucide-react";
import * as React from "react";
import { useFetcher } from "react-router";
import {
  CommandChangeField,
  EnvVariableChangeItem,
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
import { Input } from "~/components/ui/input";
import { Label } from "~/components/ui/label";
import type { DockerService } from "~/lib/queries";
import { cn } from "~/lib/utils";
import type { clientAction } from "~/routes/services/deploy-service";
import { capitalizeText, pluralize } from "~/utils";

type ServiceChangeModalProps = {
  service: DockerService;
};
export function ServiceChangesModal({ service }: ServiceChangeModalProps) {
  const fetcher = useFetcher<typeof clientAction>();
  const [isOpen, setIsOpen] = React.useState(false);
  const isDeploying = fetcher.state !== "idle";

  React.useEffect(() => {
    if (fetcher.state === "idle" && fetcher.data) {
      if (!fetcher.data.errors) {
        setIsOpen(false);
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
        <Button
          variant="warning"
          className={cn(
            "flex-1 md:flex-auto",
            service.unapplied_changes.length === 0 && "hidden"
          )}
        >
          <TriangleAlert size={15} />
          <span className="mx-1">
            {service.unapplied_changes.length}&nbsp;
            {pluralize("unapplied change", service.unapplied_changes.length)}
          </span>
        </Button>
      </DialogTrigger>
      <DialogContent className="max-w-[min(var(--container-3xl),calc(100%_-_var(--spacing)*8))] gap-0">
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
                "flex items-center justify-center text-foreground h-120"
              )}
            >
              No changes queued
            </div>
          </div>
        )}
        {service.unapplied_changes.length > 0 && (
          <Accordion
            type="multiple"
            className="border-t border-border -mx-6 px-6 flex flex-col gap-2 h-120 overflow-auto py-4"
          >
            {Object.entries(serviceChangeGroups).map((item) => {
              const field = item[0] as keyof typeof serviceChangeGroups;
              const changes = item[1] as NonNullable<
                (typeof serviceChangeGroups)[typeof field]
              >;
              return (
                <AccordionItem
                  key={field}
                  value={field}
                  className="flex flex-col border rounded-md"
                >
                  <AccordionTrigger className="text-lg flex gap-2 items-center py-2 border-border bg-muted px-4">
                    <ChevronRightIcon
                      size={15}
                      className="flex-none text-grey"
                    />
                    <span>{capitalizeText(field.replaceAll("_", " "))}</span>
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
                    {field === "source" &&
                      changes.map((change) => (
                        <ChangeForm key={change.id} change_id={change.id}>
                          <SourceChangeField unapplied change={change} />
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
              );
            })}
          </Accordion>
        )}
        <DialogFooter className="border-t border-border -mx-6 px-6 pt-4">
          <fetcher.Form
            className="flex items-center gap-4 w-full"
            method="post"
            action="./deploy-service"
          >
            <Label htmlFor="commit_message" className="sr-only">
              deployment message
            </Label>
            <Input
              id="commit_message"
              name="commit_message"
              placeholder="commit message for deployment"
            />

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
