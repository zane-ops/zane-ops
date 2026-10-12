import {
  AlertCircleIcon,
  BrainIcon,
  LoaderIcon,
  PackageIcon,
  PickaxeIcon,
  WrenchIcon
} from "lucide-react";
import * as React from "react";
import { href, redirect, useFetcher } from "react-router";
import { toast } from "sonner";
import { type RequestInput, apiClient } from "~/api/client";
import type { SwarmNode } from "~/api/types";
import { Alert, AlertDescription, AlertTitle } from "~/components/ui/alert";
import { SubmitButton } from "~/components/ui/button";
import {
  FieldSet,
  FieldSetCheckbox,
  FieldSetErrors,
  FieldSetInput,
  FieldSetLabel,
  FieldSetSelect
} from "~/components/ui/fieldset";
import {
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue
} from "~/components/ui/select";
import { Separator } from "~/components/ui/separator";
import { createDevLogger } from "~/lib/logger";
import { swarmQueries } from "~/lib/queries";
import { getQueryClient } from "~/lib/query-client";
import {
  cn,
  getCsrfTokenHeader,
  getFormErrorsFromResponseData,
  metaTitle
} from "~/lib/utils";
import type { Route } from "./+types/create-new-swarm-node";

const logger = createDevLogger(import.meta.url);

export function meta() {
  return [metaTitle("New Server")] satisfies ReturnType<Route.MetaFunction>;
}

export default function CreateNewSwarmNodePage({}: Route.ComponentProps) {
  return (
    <section className="flex flex-col gap-4">
      <div className="flex items-center gap-4">
        <h2 className="text-2xl">Add a new server</h2>
      </div>
      <Separator />
      <h3 className="text-grey">
        Register a new server to join your ZaneOps cluster. Once created, you
        will be able to add an SSH key so that ZaneOps can connect to it and
        provision it as a Docker Swarm node.
      </h3>
      <CreateSwarmNodeForm />
    </section>
  );
}

function CreateSwarmNodeForm() {
  const fetcher = useFetcher<typeof clientAction>();
  const errors = getFormErrorsFromResponseData(fetcher.data?.errors);
  const formRef = React.useRef<React.ComponentRef<"form">>(null);
  const SelectTriggerRef =
    React.useRef<React.ComponentRef<typeof SelectTrigger>>(null);

  const [swarmRole, setSwarmRole] =
    React.useState<SwarmNode["swarm_role"]>("WORKER");

  React.useEffect(() => {
    const key = Object.keys(errors ?? {})[0];
    if (key === "swarm_role") {
      SelectTriggerRef.current?.focus();
      return;
    }

    const field = formRef.current?.elements.namedItem(
      key
    ) as HTMLElement | null;
    field?.focus();
  }, [errors]);

  return (
    <fetcher.Form
      method="post"
      ref={formRef}
      className="flex flex-col gap-4 items-start xl:w-4/5"
    >
      {errors.non_field_errors && (
        <Alert variant="destructive" className="w-full ">
          <AlertCircleIcon className="h-4 w-4" />
          <AlertTitle>Error</AlertTitle>
          <AlertDescription>{errors.non_field_errors}</AlertDescription>
        </Alert>
      )}

      <FieldSet
        errors={errors.private_ip}
        name="private_ip"
        required
        className="w-full  flex flex-col gap-1"
      >
        <FieldSetLabel>Private IP</FieldSetLabel>
        <FieldSetInput autoFocus placeholder="ex: 10.0.0.2" />
        <small className="text-grey text-sm">
          The IP address of the server on your private network. It must be
          reachable from the current ZaneOps server.
        </small>
      </FieldSet>

      <FieldSet
        errors={errors.ssh_port}
        name="ssh_port"
        className="w-full  flex flex-col gap-1"
      >
        <FieldSetLabel>SSH Port</FieldSetLabel>
        <FieldSetInput defaultValue={22} placeholder="ex: 22" />
      </FieldSet>

      <FieldSet
        errors={errors.swarm_role}
        name="swarm_role"
        required
        className="w-full  flex flex-col gap-1.5"
      >
        <FieldSetLabel htmlFor="swarm_role">Docker Swarm Role</FieldSetLabel>
        <FieldSetSelect
          name="swarm_role"
          value={swarmRole}
          onValueChange={(value) =>
            setSwarmRole(value as SwarmNode["swarm_role"])
          }
        >
          <SelectTrigger
            id="swarm_role"
            ref={SelectTriggerRef}
            className={cn("[&_[data-item]]:flex-row [&_[data-item]]:gap-2")}
          >
            <SelectValue placeholder="Select a swarm role" />
          </SelectTrigger>
          <SelectContent>
            <SelectItem
              value="WORKER"
              className="flex items-start [&_[data-indicator]]:relative [&_[data-indicator]]:top-1"
            >
              <div className="inline-flex items-start gap-2">
                <PickaxeIcon className="size-4 flex-none relative top-1" />
                <div className="flex flex-col" data-item>
                  <span>Worker</span>
                  <span className="text-muted-foreground">
                    Only runs workloads assigned by the managers
                  </span>
                </div>
              </div>
            </SelectItem>
            <SelectItem
              value="MANAGER"
              className="flex items-start [&_[data-indicator]]:relative [&_[data-indicator]]:top-1"
            >
              <div className="inline-flex items-start gap-2">
                <BrainIcon className="size-4 flex-none relative top-1" />
                <div className="flex flex-col" data-item>
                  <span>Manager</span>
                  <span className="text-muted-foreground">
                    Runs workloads and takes part in managing the Docker swarm
                    cluster state
                  </span>
                </div>
              </div>
            </SelectItem>
          </SelectContent>
        </FieldSetSelect>
      </FieldSet>

      <Separator />

      <div className="flex flex-col gap-4 w-full">
        <div className="flex flex-col gap-1">
          <h3 className="text-lg">ZaneOps Cluster Roles</h3>
          <small className="text-grey text-sm">
            Choose what this server will be used for. Select at least one.
          </small>
        </div>

        {errors.cluster_roles && (
          <FieldSet
            errors={errors.cluster_roles}
            className="w-full  flex flex-col gap-1"
          >
            <FieldSetErrors />
          </FieldSet>
        )}

        <FieldSet
          name="cluster_roles"
          className="flex-1 inline-flex gap-2 flex-col"
        >
          <div className="inline-flex gap-2 items-start">
            <FieldSetCheckbox
              value="APP_SERVER"
              defaultChecked
              className="relative top-1"
            />

            <div className="flex flex-col gap-0.5">
              <FieldSetLabel className="inline-flex gap-1 items-center dark:text-card-foreground">
                <PackageIcon className="size-4 flex-none" />
                App Server
              </FieldSetLabel>

              <small className="text-grey text-sm">
                Your services can be deployed and run on this server.
              </small>
            </div>
          </div>
        </FieldSet>

        <FieldSet
          name="cluster_roles"
          className="flex-1 inline-flex gap-2 flex-col"
        >
          <div className="inline-flex gap-2 items-start">
            <FieldSetCheckbox value="BUILD_SERVER" className="relative top-1" />

            <div className="flex flex-col gap-0.5">
              <FieldSetLabel className="inline-flex gap-1 items-center dark:text-card-foreground">
                <WrenchIcon className="size-4 flex-none" />
                Build Server
              </FieldSetLabel>

              <small className="text-grey text-sm">
                Docker images for git services can be built on this server.
              </small>
            </div>
          </div>
        </FieldSet>
      </div>

      <SubmitButton isPending={fetcher.state !== "idle"} className="mt-4">
        {fetcher.state !== "idle" ? (
          <>
            <LoaderIcon className="animate-spin" size={15} />
            <span>Adding server...</span>
          </>
        ) : (
          "Add server"
        )}
      </SubmitButton>
    </fetcher.Form>
  );
}

export async function clientAction({ request }: Route.ClientActionArgs) {
  const queryClient = getQueryClient();
  const formData = await request.formData();

  const sshPort = formData.get("ssh_port")?.toString();

  const userData = {
    private_ip: formData.get("private_ip")?.toString() ?? "",
    ssh_port: sshPort?.toString() as unknown as number,
    swarm_role: (formData.get("swarm_role")?.toString() ??
      "WORKER") as SwarmNode["swarm_role"],
    cluster_roles: formData
      .getAll("cluster_roles")
      .map((role) => role.toString()) as SwarmNode["cluster_roles"]
  } satisfies RequestInput<"post", "/api/swarm/nodes/">;

  logger.info({
    userData,
    sshPort
  });

  const { error: errors, data } = await apiClient.POST("/api/swarm/nodes/", {
    headers: {
      ...(await getCsrfTokenHeader())
    },
    body: userData
  });

  if (errors) {
    return {
      errors,
      userData
    };
  }

  toast.success("Success", {
    dismissible: true,
    closeButton: true,
    description: "Server added successfully"
  });
  await queryClient.invalidateQueries({
    queryKey: swarmQueries.nodeList().queryKey.slice(0, 1)
  });
  throw redirect(href("/admin/servers/:serverId", { serverId: data.id }));
}
