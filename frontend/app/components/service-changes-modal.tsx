import {
  ActivityIcon,
  ContainerIcon,
  EthernetPortIcon,
  GlobeIcon,
  HardDriveIcon,
  HourglassIcon,
  KeyRoundIcon,
  LoaderIcon,
  TerminalIcon,
  TriangleAlert
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

  const IconFieldMap: Record<
    DockerService["unapplied_changes"][number]["field"],
    React.ComponentType<React.ComponentProps<typeof HardDriveIcon>>
  > = {
    source: ContainerIcon,
    volumes: HardDriveIcon,
    ports: EthernetPortIcon,
    command: TerminalIcon,
    env_variables: KeyRoundIcon,
    urls: GlobeIcon,
    resource_limits: HourglassIcon,
    healthcheck: ActivityIcon
  };

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
      <DialogContent className="max-w-[min(var(--container-3xl),calc(100%_-_var(--spacing)*8))] py-4">
        <DialogHeader>
          <DialogTitle>
            {service.unapplied_changes.length}&nbsp;
            {pluralize("change", service.unapplied_changes.length)}&nbsp;to
            apply
          </DialogTitle>
        </DialogHeader>

        <div className="border-t border-border -mx-6 px-6 flex flex-col gap-4 h-112 overflow-auto">
          {Object.entries(serviceChangeGroups).map((item) => {
            const field = item[0] as keyof typeof serviceChangeGroups;
            const changes = item[1] as NonNullable<
              (typeof serviceChangeGroups)[typeof field]
            >;
            const Icon = IconFieldMap[field];
            return (
              <div key={field} className="flex flex-col gap-1.5 flex-1">
                <h3 className="text-lg flex gap-2 items-center border-b py-2 border-border">
                  <Icon size={15} className="flex-none text-grey" />
                  <span>{capitalizeText(field.replaceAll("_", " "))}</span>
                </h3>
                <div className="pl-4 py-2 flex flex-col gap-2">
                  {field === "volumes" &&
                    changes.map((change, index) => (
                      <React.Fragment key={index}>
                        <VolumeChangeItem change={change} />
                        <hr className="border border-dashed border-border" />
                      </React.Fragment>
                    ))}
                  {field === "source" &&
                    changes.map((change, index) => (
                      <React.Fragment key={index}>
                        <SourceChangeField change={change} />
                        <hr className="border border-dashed border-border" />
                      </React.Fragment>
                    ))}
                  {field === "command" &&
                    changes.map((change, index) => (
                      <React.Fragment key={index}>
                        <CommandChangeField change={change} />
                        <hr className="border border-dashed border-border" />
                      </React.Fragment>
                    ))}
                  {field === "ports" &&
                    changes.map((change, index) => (
                      <React.Fragment key={index}>
                        <PortChangeItem change={change} />
                        <hr className="border border-dashed border-border" />
                      </React.Fragment>
                    ))}
                  {field === "env_variables" &&
                    changes.map((change, index) => (
                      <React.Fragment key={index}>
                        <EnvVariableChangeItem
                          change={change}
                          key={change.id}
                        />
                        <hr className="border border-dashed border-border" />
                      </React.Fragment>
                    ))}
                  {field === "urls" &&
                    changes.map((change, index) => (
                      <React.Fragment key={index}>
                        <UrlChangeItem change={change} key={change.id} />
                        <hr className="border border-dashed border-border" />
                      </React.Fragment>
                    ))}
                  {field === "healthcheck" &&
                    changes.map((change, index) => (
                      <React.Fragment key={index}>
                        <HealthcheckChangeField
                          change={change}
                          key={change.id}
                        />
                        <hr className="border border-dashed border-border" />
                      </React.Fragment>
                    ))}
                  {field === "resource_limits" &&
                    changes.map((change, index) => (
                      <React.Fragment key={index}>
                        <ResourceLimitChangeField
                          change={change}
                          key={change.id}
                        />
                        <hr className="border border-dashed border-border" />
                      </React.Fragment>
                    ))}
                </div>
              </div>
            );
          })}
        </div>
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
              placeholder="deployment message"
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
