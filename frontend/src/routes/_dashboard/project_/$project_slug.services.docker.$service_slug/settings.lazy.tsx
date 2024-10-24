import * as Form from "@radix-ui/react-form";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { Link, createLazyFileRoute, useNavigate } from "@tanstack/react-router";
import {
  AlertCircleIcon,
  ArrowRightIcon,
  CableIcon,
  CheckIcon,
  ContainerIcon,
  CopyIcon,
  EditIcon,
  ExternalLinkIcon,
  Eye,
  EyeOffIcon,
  FlameIcon,
  GlobeLockIcon,
  HammerIcon,
  HardDrive,
  InfoIcon,
  LoaderIcon,
  PencilLineIcon,
  Plus,
  PlusIcon,
  SunsetIcon,
  Trash2Icon,
  TriangleAlertIcon,
  Undo2Icon,
  XIcon
} from "lucide-react";
import * as React from "react";
import { toast } from "sonner";
import { type RequestInput, apiClient } from "~/api/client";
import { Code } from "~/components/code";
import { withAuthRedirect } from "~/components/helper/auth-redirect";
import {
  Accordion,
  AccordionContent,
  AccordionItem,
  AccordionTrigger
} from "~/components/ui/accordion";
import { Alert, AlertDescription, AlertTitle } from "~/components/ui/alert";
import { Button, SubmitButton } from "~/components/ui/button";
import { Checkbox } from "~/components/ui/checkbox";
import { Input } from "~/components/ui/input";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue
} from "~/components/ui/select";
import {
  Tooltip,
  TooltipContent,
  TooltipProvider,
  TooltipTrigger
} from "~/components/ui/tooltip";
import { serviceKeys } from "~/key-factories";
import { useCancelDockerServiceChangeMutation } from "~/lib/hooks/use-cancel-docker-service-change-mutation";
import {
  type DockerService,
  useDockerServiceSingleQuery
} from "~/lib/hooks/use-docker-service-single-query";
import { useRequestServiceChangeMutation } from "~/lib/hooks/use-request-service-change-mutation";
import { cn, getFormErrorsFromResponseData } from "~/lib/utils";
import { getCsrfTokenHeader, wait } from "~/utils";

export const Route = createLazyFileRoute(
  "/_dashboard/project/$project_slug/services/docker/$service_slug/settings"
)({
  component: withAuthRedirect(SettingsPage)
});

function SettingsPage() {
  return (
    <div className="my-6 grid lg:grid-cols-12 gap-10 relative">
      <div className="lg:col-span-10 flex flex-col">
        <section id="details" className="flex gap-1 scroll-mt-20">
          <div className="w-16 hidden md:flex flex-col items-center">
            <div className="flex rounded-full size-10 flex-none items-center justify-center p-1 border-2 border-grey/50">
              <InfoIcon size={15} className="flex-none text-grey" />
            </div>
            <div className="h-full border border-grey/50"></div>
          </div>

          <div className="w-full flex flex-col gap-5 pt-1 pb-8">
            <h2 className="text-lg text-grey">Details</h2>
            <ServiceSlugForm className="w-full max-w-4xl" />
          </div>
        </section>

        <section id="source" className="flex gap-1 scroll-mt-20">
          <div className="w-16 hidden md:flex flex-col items-center">
            <div className="flex rounded-full size-10 flex-none items-center justify-center p-1 border-2 border-grey/50">
              <ContainerIcon size={15} className="flex-none text-grey" />
            </div>
            <div className="h-full border border-grey/50"></div>
          </div>

          <div className="w-full flex flex-col gap-5 pt-1 pb-14">
            <h2 className="text-lg text-grey">Source</h2>
            <ServiceImageForm className="w-full max-w-4xl" />
            <ServiceImageCredentialsForm className="w-full max-w-4xl" />
          </div>
        </section>

        <section id="networking" className="flex gap-1 scroll-mt-20">
          <div className="w-16 hidden md:flex flex-col items-center">
            <div className="flex rounded-full size-10 flex-none items-center justify-center p-1 border-2 border-grey/50">
              <CableIcon size={15} className="flex-none text-grey" />
            </div>
            <div className="h-full border border-grey/50"></div>
          </div>
          <div className="w-full flex flex-col gap-12 pt-1 pb-14">
            <h2 className="text-lg text-grey">Networking</h2>
            <ServicePortsForm className="w-full max-w-4xl" />
            <hr className="w-full max-w-4xl border-border" />
            <ServiceURLsForm className="w-full max-w-4xl" />
            <hr className="w-full max-w-4xl border-border" />
            <NetworkAliasesGroup className="w-full max-w-4xl border-border" />
          </div>
        </section>

        <section id="deploy" className="flex gap-1 scroll-mt-20">
          <div className="w-16 hidden md:flex flex-col items-center">
            <div className="flex rounded-full size-10 flex-none items-center justify-center p-1 border-2 border-grey/50">
              <HammerIcon size={15} className="flex-none text-grey" />
            </div>
            <div className="h-full border border-grey/50"></div>
          </div>
          <div className="w-full flex flex-col gap-12 pt-1 pb-14">
            <h2 className="text-lg text-grey">Deploy</h2>
            <ServiceCommandForm className="w-full max-w-4xl border-border" />
            <ServiceHealthcheckForm className="w-full max-w-4xl border-border" />
          </div>
        </section>

        <section id="volumes" className="flex gap-1 scroll-mt-20">
          <div className="w-16 hidden md:flex flex-col items-center">
            <div className="flex rounded-full size-10 flex-none items-center justify-center p-1 border-2 border-grey/50">
              <HardDrive size={15} className="flex-none text-grey" />
            </div>
            <div className="h-full border border-grey/50"></div>
          </div>
          <div className="w-full flex flex-col gap-5 pt-1 pb-14">
            <h2 className="text-lg text-grey">Volumes</h2>
            <ServiceVolumesForm />
          </div>
        </section>

        <section id="danger-zone" className="flex gap-1 scroll-mt-20">
          <div className="w-16 hidden md:flex flex-col items-center">
            <div className="flex rounded-full size-10 flex-none items-center justify-center p-1 border-2 border-red-500">
              <FlameIcon size={15} className="flex-none text-red-500" />
            </div>
          </div>
          <div className="w-full flex flex-col gap-5 pt-1 pb-14">
            <h2 className="text-lg text-red-400">Danger Zone</h2>
            <ServiceDangerZoneForm className="w-full max-w-4xl" />
          </div>
        </section>
      </div>

      <aside className="col-span-2 hidden lg:flex flex-col h-full">
        <nav className="sticky top-20">
          <ul className="flex flex-col gap-2 text-grey">
            <li>
              <Link to="#details">Details</Link>
            </li>
            <li>
              <Link to="#source">Source</Link>
            </li>
            <li>
              <Link to="#networking">Networking</Link>
            </li>
            <li>
              <Link to="#deploy">Deploy</Link>
            </li>
            <li>
              <Link to="#volumes">Volumes</Link>
            </li>
            <li className="text-red-400">
              <a href="#danger-zone">Danger Zone</a>
            </li>
          </ul>
        </nav>
      </aside>
    </div>
  );
}

type ServiceFormProps = {
  className?: string;
};

function ServiceSlugForm({ className }: ServiceFormProps) {
  const { project_slug, service_slug } = Route.useParams();
  const queryClient = useQueryClient();
  const navigate = useNavigate();
  const { mutate, isPending, data, reset } = useMutation({
    mutationFn: async (
      input: Required<
        RequestInput<
          "patch",
          "/api/projects/{project_slug}/service-details/docker/{service_slug}/"
        >
      >
    ) => {
      await queryClient.cancelQueries({
        queryKey: serviceKeys.single(project_slug, service_slug, "docker"),
        exact: true
      });

      const { error, data } = await apiClient.PATCH(
        "/api/projects/{project_slug}/service-details/docker/{service_slug}/",
        {
          headers: {
            ...(await getCsrfTokenHeader())
          },
          params: {
            path: {
              project_slug,
              service_slug
            }
          },
          body: input
        }
      );
      if (error) {
        return error;
      }

      if (data) {
        queryClient.setQueryData(
          serviceKeys.single(project_slug, input.slug, "docker"),
          () => ({
            data
          })
        );

        await navigate({
          to: `/project/${project_slug}/services/docker/${input.slug}/settings`,
          replace: true
        });
        return;
      }
    },
    onSettled: async (error) => {
      if (!error) {
        await queryClient.invalidateQueries({
          queryKey: serviceKeys.single(project_slug, service_slug, "docker")
        });
        setIsEditing(false);
      }
    }
  });

  const [isEditing, setIsEditing] = React.useState(false);

  const errors = getFormErrorsFromResponseData(data);

  return (
    <div className={className}>
      {isEditing ? (
        <Form.Root
          action={(formData) => {
            mutate({
              slug: formData.get("slug")?.toString() ?? ""
            });
          }}
          className="flex flex-col md:flex-row gap-2 w-full"
        >
          <Form.Field name="slug" className="flex flex-col gap-1.5 flex-1">
            <Form.Label>Service slug</Form.Label>
            <Form.Control asChild>
              <Input placeholder="service slug" defaultValue={service_slug} />
            </Form.Control>
            {errors.slug && (
              <Form.Message className="text-red-500 text-sm">
                {errors.slug}
              </Form.Message>
            )}
          </Form.Field>

          <div className="flex gap-2 md:relative top-8">
            <SubmitButton
              isPending={isPending}
              variant="outline"
              className="bg-inherit"
            >
              {isPending ? (
                <>
                  <LoaderIcon className="animate-spin" size={15} />
                  <span className="sr-only">Updating service slug...</span>
                </>
              ) : (
                <>
                  <CheckIcon size={15} className="flex-none" />
                  <span className="sr-only">Update service slug</span>
                </>
              )}
            </SubmitButton>
            <Button
              onClick={() => {
                setIsEditing(false);
                reset();
              }}
              variant="outline"
              className="bg-inherit"
              type="button"
            >
              <XIcon size={15} className="flex-none" />
              <span className="sr-only">Cancel</span>
            </Button>
          </div>
        </Form.Root>
      ) : (
        <div className="flex flex-col gap-1.5">
          <span>Service slug</span>
          <div
            className={cn(
              "w-full rounded-md flex justify-between items-center gap-2 py-1 pl-4 pr-2",
              "bg-muted"
            )}
          >
            <span>{service_slug}</span>
            <Button
              variant="outline"
              onClick={() => {
                setIsEditing(true);
              }}
              className="bg-inherit inline-flex items-center gap-2 border-muted-foreground py-0.5"
            >
              <span>Edit</span>
              <PencilLineIcon size={15} />
            </Button>
          </div>
        </div>
      )}
    </div>
  );
}

function ServiceImageForm({ className }: ServiceFormProps) {
  const { project_slug, service_slug } = Route.useParams();

  const [isEditing, setIsEditing] = React.useState(false);
  const serviceSingleQuery = useDockerServiceSingleQuery(
    project_slug,
    service_slug
  );
  const cancelImageChangeMutation = useCancelDockerServiceChangeMutation(
    project_slug,
    service_slug
  );

  const updateImageMutation = useRequestServiceChangeMutation({
    project_slug,
    service_slug,
    field: "image",
    onSuccess() {
      setIsEditing(false);
    }
  });

  const service = serviceSingleQuery.data?.data;
  const serviceImageChange = service?.unapplied_changes.find(
    (change) => change.field === "image"
  );

  const serviceImage =
    (serviceImageChange?.new_value as string) ?? service?.image;

  const imageParts = serviceImage.split(":");

  const tag = imageParts.length > 1 ? imageParts.pop() : "latest";
  const image = imageParts.join(":");

  const errors = getFormErrorsFromResponseData(updateImageMutation.data);

  return (
    <div className={className}>
      {isEditing ? (
        <Form.Root
          action={(formData) => {
            updateImageMutation.mutate({
              type: "UPDATE",
              new_value: formData.get("image")?.toString() ?? ""
            });
          }}
          className="flex flex-col md:flex-row  gap-2 w-full"
        >
          <Form.Field name="image" className="flex flex-col gap-1.5 flex-1">
            <Form.Label className="text-lg">Source image</Form.Label>
            <Form.Control asChild>
              <Input placeholder="service slug" defaultValue={serviceImage} />
            </Form.Control>
            {errors.new_value && (
              <Form.Message className="text-red-500 text-sm">
                {errors.new_value}
              </Form.Message>
            )}
          </Form.Field>

          <div className="flex gap-2 md:relative top-8">
            <SubmitButton
              isPending={updateImageMutation.isPending}
              variant="outline"
              className="bg-inherit"
            >
              {updateImageMutation.isPending ? (
                <>
                  <LoaderIcon className="animate-spin" size={15} />
                  <span className="sr-only">Updating service image...</span>
                </>
              ) : (
                <>
                  <CheckIcon size={15} className="flex-none" />
                  <span className="sr-only">Update service image</span>
                </>
              )}
            </SubmitButton>
            <Button
              onClick={() => {
                setIsEditing(false);
                updateImageMutation.reset();
              }}
              variant="outline"
              className="bg-inherit"
              type="button"
            >
              <XIcon size={15} className="flex-none" />
              <span className="sr-only">Cancel</span>
            </Button>
          </div>
        </Form.Root>
      ) : (
        <div className="flex flex-col gap-1.5 flex-wrap">
          <h3 className="text-lg">Source image</h3>
          <div
            className={cn(
              "w-full rounded-md flex justify-between items-center gap-2 py-1 pl-4 pr-2",
              serviceImageChange !== undefined
                ? "dark:bg-secondary-foreground bg-secondary/60"
                : "bg-muted"
            )}
          >
            <span>
              {image}
              <span className="text-grey">:{tag}</span>
            </span>
            {serviceImageChange !== undefined ? (
              <form
                action={() => {
                  cancelImageChangeMutation.mutate(serviceImageChange.id, {
                    onError(error) {
                      toast.error("Error", {
                        closeButton: true,
                        description: error.message
                      });
                    }
                  });
                }}
              >
                <SubmitButton
                  isPending={cancelImageChangeMutation.isPending}
                  variant="outline"
                  className="bg-inherit inline-flex items-center gap-2 border-muted-foreground py-0.5"
                >
                  {cancelImageChangeMutation.isPending ? (
                    <>
                      <span>Reverting change...</span>
                      <LoaderIcon className="animate-spin" size={15} />
                    </>
                  ) : (
                    <>
                      <span>Revert change</span>
                      <Undo2Icon size={15} />
                    </>
                  )}
                </SubmitButton>
              </form>
            ) : (
              <Button
                variant="outline"
                onClick={() => {
                  setIsEditing(true);
                }}
                className="bg-inherit inline-flex items-center gap-2 border-muted-foreground py-0.5"
              >
                <span>Edit</span>
                <PencilLineIcon size={15} />
              </Button>
            )}
          </div>
        </div>
      )}
    </div>
  );
}

function ServiceImageCredentialsForm({ className }: ServiceFormProps) {
  const { project_slug, service_slug } = Route.useParams();

  const serviceSingleQuery = useDockerServiceSingleQuery(
    project_slug,
    service_slug
  );

  const cancelCredentialsChangeMutation = useCancelDockerServiceChangeMutation(
    project_slug,
    service_slug
  );

  const updateCredentialsMutation = useRequestServiceChangeMutation({
    project_slug,
    service_slug,
    field: "credentials",
    onSuccess() {
      setIsPasswordShown(false);
    }
  });

  const service = serviceSingleQuery.data?.data;
  const serviceCredentialsChange = service?.unapplied_changes.find(
    (change) => change.field === "credentials"
  );
  const credentials =
    (serviceCredentialsChange?.new_value as DockerService["credentials"]) ??
    service?.credentials;

  const [isPasswordShown, setIsPasswordShown] = React.useState(false);

  const errors = getFormErrorsFromResponseData(updateCredentialsMutation.data);

  let non_field_errors: string[] = [];
  if (errors.non_field_errors) {
    non_field_errors = non_field_errors.concat(errors.non_field_errors);
  }
  if (Array.isArray(errors.new_value)) {
    non_field_errors = non_field_errors.concat(errors.new_value);
  }

  const formRef = React.useRef<React.ElementRef<"form">>(null);
  const newCredentialsValue =
    serviceCredentialsChange?.new_value as DockerService["credentials"];

  const isEmptyChange =
    serviceCredentialsChange !== undefined &&
    (newCredentialsValue === null ||
      (newCredentialsValue?.username.trim() === "" &&
        newCredentialsValue?.password.trim() === ""));

  return (
    <Form.Root
      ref={formRef}
      action={(formData) => {
        if (serviceCredentialsChange !== undefined) {
          cancelCredentialsChangeMutation.mutate(serviceCredentialsChange.id, {
            onSuccess() {
              formRef.current?.reset();
            },
            onError(error) {
              toast.error("Error", {
                closeButton: true,
                description: error.message
              });
            }
          });
        } else {
          updateCredentialsMutation.mutate({
            type: "UPDATE",
            new_value: {
              username: formData.get("username")?.toString(),
              password: formData.get("password")?.toString()
            }
          });
        }
      }}
      className={cn("flex flex-col gap-4 w-full items-start", className)}
    >
      <fieldset className="w-full flex flex-col gap-4">
        <legend className="text-lg">Credentials</legend>
        <p className="text-gray-400">
          If your image is on a private registry, please provide the information
          below.
        </p>

        {non_field_errors.length > 0 && (
          <Alert variant="destructive">
            <AlertCircleIcon className="h-4 w-4" />
            <AlertTitle>Error</AlertTitle>
            <AlertDescription>{non_field_errors}</AlertDescription>
          </Alert>
        )}
        <Form.Field name="username" className="flex flex-col gap-1.5 flex-1">
          <Form.Label className="text-muted-foreground">
            Username for registry
          </Form.Label>
          <Form.Control asChild>
            <Input
              placeholder={isEmptyChange ? "<empty>" : "username"}
              disabled={serviceCredentialsChange !== undefined}
              defaultValue={credentials?.username}
              className={cn(
                "disabled:placeholder-shown:font-mono disabled:bg-secondary/60",
                "disabled:dark:bg-secondary-foreground disabled:opacity-100",
                "disabled:border-transparent"
              )}
            />
          </Form.Control>
          {errors.new_value?.username && (
            <Form.Message className="text-red-500 text-sm">
              {errors.new_value.username}
            </Form.Message>
          )}
        </Form.Field>
        <Form.Field name="password" className="flex flex-col gap-1.5 flex-1">
          <Form.Label className="text-muted-foreground">
            Password for registry
          </Form.Label>
          <div className="flex gap-2">
            <Form.Control asChild>
              <Input
                placeholder={isEmptyChange ? "<empty>" : "*******"}
                disabled={serviceCredentialsChange !== undefined}
                type={isPasswordShown ? "text" : "password"}
                defaultValue={credentials?.password}
                className={cn(
                  "disabled:placeholder-shown:font-mono disabled:bg-secondary/60",
                  "disabled:dark:bg-secondary-foreground disabled:opacity-100",
                  "disabled:border-transparent"
                )}
              />
            </Form.Control>
            <TooltipProvider>
              <Tooltip delayDuration={0}>
                <TooltipTrigger asChild>
                  <Button
                    variant="outline"
                    type="button"
                    onClick={() => setIsPasswordShown(!isPasswordShown)}
                    className="p-4"
                  >
                    {isPasswordShown ? (
                      <EyeOffIcon size={15} className="flex-none" />
                    ) : (
                      <Eye size={15} className="flex-none" />
                    )}
                    <span className="sr-only">
                      {isPasswordShown ? "Hide" : "Show"} password
                    </span>
                  </Button>
                </TooltipTrigger>
                <TooltipContent>
                  {isPasswordShown ? "Hide" : "Show"} password
                </TooltipContent>
              </Tooltip>
            </TooltipProvider>
          </div>
          {errors.new_value?.password && (
            <Form.Message className="text-red-500 text-sm">
              {errors.new_value.password}
            </Form.Message>
          )}
        </Form.Field>
      </fieldset>

      {serviceCredentialsChange !== undefined ? (
        <SubmitButton
          isPending={cancelCredentialsChangeMutation.isPending}
          variant="outline"
        >
          {cancelCredentialsChangeMutation.isPending ? (
            <>
              <LoaderIcon className="animate-spin" size={15} />
              <span>Reverting...</span>
            </>
          ) : (
            <>
              <Undo2Icon size={15} className="flex-none" />
              <span>Revert change</span>
            </>
          )}
        </SubmitButton>
      ) : (
        <SubmitButton
          isPending={updateCredentialsMutation.isPending}
          variant="secondary"
        >
          {updateCredentialsMutation.isPending ? (
            <>
              <LoaderIcon className="animate-spin" size={15} />
              <span>Updating ...</span>
            </>
          ) : (
            <>
              <CheckIcon size={15} className="flex-none" />
              <span>Update</span>
            </>
          )}
        </SubmitButton>
      )}
    </Form.Root>
  );
}

type PortItem = {
  change_id?: string;
  id?: string | null;
  change_type?: "UPDATE" | "DELETE" | "ADD";
} & Omit<DockerService["ports"][number], "id">;

function ServicePortsForm({ className }: ServiceFormProps) {
  const { project_slug, service_slug } = Route.useParams();
  const serviceSingleQuery = useDockerServiceSingleQuery(
    project_slug,
    service_slug
  );

  const ports: Map<string, PortItem> = new Map();
  for (const port of serviceSingleQuery.data?.data?.ports ?? []) {
    ports.set(port.id, {
      id: port.id,
      host: port.host,
      forwarded: port.forwarded
    });
  }
  for (const ch of (
    serviceSingleQuery.data?.data?.unapplied_changes ?? []
  ).filter((ch) => ch.field === "ports")) {
    const hostForwarded = (ch.new_value ?? ch.old_value) as {
      host: number;
      forwarded: number;
    };
    ports.set(ch.item_id ?? ch.id, {
      change_id: ch.id,
      id: ch.item_id,
      host: hostForwarded.host,
      forwarded: hostForwarded.forwarded,
      change_type: ch.type
    });
  }

  return (
    <div className={cn("flex flex-col gap-5", className)}>
      <div className="flex flex-col gap-3">
        <h3 className="text-lg">Exposed ports</h3>
        <p className="text-gray-400">
          This makes the service reachable externally via the ports defined
          in&nbsp;
          <Code>host port</Code>. Using&nbsp;
          <Code>80</Code>
          &nbsp;or&nbsp;
          <Code>443</Code>
          &nbsp;will create a default URL for the service.
        </p>

        <Alert variant="warning">
          <TriangleAlertIcon size={15} />
          <AlertTitle>Warning</AlertTitle>
          <AlertDescription>
            Using a host value other than 80 or 443 will disable&nbsp;
            <a href="#" className="underline inline-flex gap-1 items-center">
              zero-downtime deployments <ExternalLinkIcon size={12} />
            </a>
            .
          </AlertDescription>
        </Alert>
      </div>

      {ports.size > 0 && (
        <>
          <hr className="border-border" />
          <ul className="flex flex-col gap-1">
            {[...ports.entries()].map(([key, value]) => (
              <li key={key}>
                <ServicePortItem
                  host={value.host}
                  forwarded={value.forwarded}
                  change_type={value.change_type}
                  change_id={value.change_id}
                  id={value.id}
                />
              </li>
            ))}
          </ul>
        </>
      )}
      <hr className="border-border" />
      <h3 className="text-lg">Add new port</h3>
      <NewServicePortForm />
    </div>
  );
}

type ServicePortItemProps = {
  change_id?: string;
  id?: string | null;
  change_type?: "UPDATE" | "DELETE" | "ADD";
} & Omit<DockerService["ports"][number], "id">;

function ServicePortItem({
  host,
  forwarded,
  change_id,
  id,
  change_type
}: ServicePortItemProps) {
  const { project_slug, service_slug } = Route.useParams();
  const cancelPortChangeMutation = useCancelDockerServiceChangeMutation(
    project_slug,
    service_slug
  );

  const { mutateAsync: removeExposedPort } = useRequestServiceChangeMutation({
    project_slug,
    service_slug,
    field: "ports",
    onSuccess() {
      setAccordionValue("");
    }
  });

  const {
    mutate: editExposedPort,
    isPending: isUpdatingExposedPort,
    data,
    reset
  } = useRequestServiceChangeMutation({
    project_slug,
    service_slug,
    field: "ports",
    onSuccess() {
      setAccordionValue("");
    }
  });

  const errors = getFormErrorsFromResponseData(data);
  const [accordionValue, setAccordionValue] = React.useState("");

  return (
    <div className="relative group">
      <div className="absolute top-1 right-2">
        <TooltipProvider>
          {change_id !== undefined ? (
            <Tooltip delayDuration={0}>
              <TooltipTrigger asChild>
                <Button
                  variant="ghost"
                  className="px-2.5 py-0.5 md:opacity-0 focus-visible:opacity-100 group-hover:opacity-100 group-focus:opacity-100"
                  onClick={() =>
                    toast.promise(
                      cancelPortChangeMutation.mutateAsync(change_id),
                      {
                        loading: `Cancelling exposed port change...`,
                        success: "Success",
                        error: "Error",
                        closeButton: true,
                        description(data) {
                          if (data instanceof Error) {
                            return data.message;
                          }
                          return "Done.";
                        }
                      }
                    )
                  }
                >
                  <Undo2Icon size={15} className="flex-none" />
                  <span className="sr-only">Revert change</span>
                </Button>
              </TooltipTrigger>
              <TooltipContent>Revert change</TooltipContent>
            </Tooltip>
          ) : (
            id && (
              <Tooltip delayDuration={0}>
                <TooltipTrigger asChild>
                  <Button
                    variant="ghost"
                    className="px-2.5 py-0.5 md:opacity-0 focus-visible:opacity-100 group-hover:opacity-100"
                    onClick={() =>
                      toast.promise(
                        removeExposedPort({
                          type: "DELETE",
                          item_id: id
                        }),
                        {
                          loading: `Requesting change...`,
                          success: "Success",
                          error: "Error",
                          closeButton: true,
                          description(data) {
                            if (data instanceof Error) {
                              return data.message;
                            }
                            return "Done.";
                          }
                        }
                      )
                    }
                  >
                    <Trash2Icon size={15} className="flex-none text-red-400" />
                    <span className="sr-only">Delete exposed port</span>
                  </Button>
                </TooltipTrigger>
                <TooltipContent>Delete exposed port</TooltipContent>
              </Tooltip>
            )
          )}
        </TooltipProvider>
      </div>

      <Accordion
        type="single"
        collapsible
        value={accordionValue}
        onValueChange={(state) => {
          setAccordionValue(state);
        }}
      >
        <AccordionItem
          value={`${host}:${forwarded}`}
          className="border-none"
          disabled={!!change_id}
        >
          <AccordionTrigger
            className={cn(
              "w-full px-3 bg-muted rounded-md inline-flex gap-2 items-center text-start flex-wrap pr-24",
              "[&[data-state=open]]:rounded-b-none",
              {
                "dark:bg-secondary-foreground bg-secondary/60 ":
                  change_type === "UPDATE",
                "dark:bg-primary-foreground bg-primary/60":
                  change_type === "ADD",
                "dark:bg-red-500/30 bg-red-400/60": change_type === "DELETE"
              }
            )}
          >
            <span>{host}</span>
            <ArrowRightIcon size={15} className="text-grey" />
            <span className="text-grey">{forwarded}</span>
          </AccordionTrigger>
          {id && (
            <AccordionContent className="border-border border-x border-b rounded-b-md p-4 mb-4">
              <Form.Root
                action={(formData) => {
                  editExposedPort({
                    type: "UPDATE",
                    item_id: id,
                    new_value: {
                      host: Number(formData.get("host") ?? ""),
                      forwarded: Number(formData.get("forwarded") ?? "")
                    }
                  });
                }}
                className="flex flex-col gap-4"
              >
                <div className="flex flex-col md:flex-row md:items-center gap-4">
                  <Form.Field
                    name="host"
                    className="flex-1 inline-flex flex-col gap-1"
                  >
                    <Form.Label className="text-gray-400">Host port</Form.Label>
                    <Form.Control asChild>
                      <Input placeholder="ex: 80" defaultValue={host ?? 80} />
                    </Form.Control>
                    {errors.new_value?.host && (
                      <Form.Message className="text-red-500 text-sm">
                        {errors.new_value?.host}
                      </Form.Message>
                    )}
                  </Form.Field>
                  <Form.Field
                    name="forwarded"
                    className="flex-1 inline-flex flex-col gap-1"
                  >
                    <Form.Label className="text-gray-400">
                      Forwarded port
                    </Form.Label>
                    <Form.Control asChild>
                      <Input placeholder="ex: 8080" defaultValue={forwarded} />
                    </Form.Control>
                    {errors.new_value?.forwarded && (
                      <Form.Message className="text-red-500 text-sm">
                        {errors.new_value?.forwarded}
                      </Form.Message>
                    )}
                  </Form.Field>
                </div>

                <div className="flex justify-end items-center gap-2 border-t pt-4 px-4 -mx-4 border-border">
                  <SubmitButton
                    variant="secondary"
                    isPending={isUpdatingExposedPort}
                    className="inline-flex gap-1"
                  >
                    {isUpdatingExposedPort ? (
                      <>
                        <span>Updating...</span>
                        <LoaderIcon className="animate-spin" size={15} />
                      </>
                    ) : (
                      <>
                        Update
                        <CheckIcon size={15} />
                      </>
                    )}
                  </SubmitButton>
                  <Button onClick={reset} variant="outline" type="reset">
                    Reset
                  </Button>
                </div>
              </Form.Root>
            </AccordionContent>
          )}
        </AccordionItem>
      </Accordion>
    </div>
  );
}

function NewServicePortForm() {
  const { project_slug, service_slug } = Route.useParams();
  const formRef = React.useRef<React.ElementRef<"form">>(null);

  const { mutate, isPending, data, reset } = useRequestServiceChangeMutation({
    project_slug,
    service_slug,
    field: "ports"
  });
  const errors = getFormErrorsFromResponseData(data);
  return (
    <Form.Root
      ref={formRef}
      action={(formData) => {
        mutate(
          {
            type: "ADD",
            new_value: {
              host: Number(formData.get("host") ?? ""),
              forwarded: Number(formData.get("forwarded") ?? "")
            }
          },
          {
            onSuccess(errors) {
              if (!errors) {
                formRef.current?.reset();
              }
            }
          }
        );
      }}
      className="flex md:items-start gap-3 md:flex-row flex-col items-stretch"
    >
      <Form.Field name="host" className="flex-1 inline-flex flex-col gap-1">
        <Form.Label className="text-gray-400">Host port</Form.Label>
        <Form.Control asChild>
          <Input placeholder="ex: 80" />
        </Form.Control>
        {errors.new_value?.host && (
          <Form.Message className="text-red-500 text-sm">
            {errors.new_value?.host}
          </Form.Message>
        )}
      </Form.Field>
      <Form.Field
        name="forwarded"
        className="flex-1 inline-flex flex-col gap-1"
      >
        <Form.Label className="text-gray-400">Forwarded port</Form.Label>
        <Form.Control asChild>
          <Input placeholder="ex: 8080" />
        </Form.Control>
        {errors.new_value?.forwarded && (
          <Form.Message className="text-red-500 text-sm">
            {errors.new_value?.forwarded}
          </Form.Message>
        )}
      </Form.Field>

      <div className="flex gap-3 items-center pt-7 w-full md:w-auto">
        <SubmitButton
          isPending={false}
          variant="secondary"
          className="inline-flex gap-1 flex-1"
        >
          {isPending ? (
            <>
              <span>Adding...</span>
              <LoaderIcon className="animate-spin" size={15} />
            </>
          ) : (
            <>
              <span>Add</span>
              <Plus size={15} />
            </>
          )}
        </SubmitButton>
        <Button
          onClick={reset}
          variant="outline"
          type="reset"
          className="flex-1"
        >
          Reset
        </Button>
      </div>
    </Form.Root>
  );
}

type UrlItem = {
  change_id?: string;
  id?: string | null;
  change_type?: "UPDATE" | "DELETE" | "ADD";
} & Omit<DockerService["urls"][number], "id">;

function ServiceURLsForm({ className }: ServiceFormProps) {
  const { project_slug, service_slug } = Route.useParams();
  const serviceSingleQuery = useDockerServiceSingleQuery(
    project_slug,
    service_slug
  );

  const urls: Map<string, UrlItem> = new Map();
  for (const url of serviceSingleQuery.data?.data?.urls ?? []) {
    urls.set(url.id, {
      ...url,
      id: url.id
    });
  }
  for (const ch of (
    serviceSingleQuery.data?.data?.unapplied_changes ?? []
  ).filter((ch) => ch.field === "urls")) {
    const newUrl = (ch.new_value ?? ch.old_value) as Omit<
      DockerService["urls"][number],
      "id"
    >;
    urls.set(ch.item_id ?? ch.id, {
      ...newUrl,
      change_id: ch.id,
      id: ch.item_id,
      change_type: ch.type
    });
  }

  return (
    <div className={cn("flex flex-col gap-5", className)}>
      <div className="flex flex-col gap-3">
        <h3 className="text-lg">URLs</h3>
        <p className="text-gray-400">
          The domains and base path which are associated to this service. A port
          with a host value of&nbsp;
          <Code>80</Code>
          &nbsp;or&nbsp;
          <Code>443</Code>
          &nbsp; is required to be able to add URLs to this service.
        </p>
      </div>
      {urls.size > 0 && (
        <>
          <hr className="border-border" />
          <ul className="flex flex-col gap-2">
            {[...urls.entries()].map(([key, value]) => (
              <li key={key}>
                <ServiceURLFormItem {...value} />
              </li>
            ))}
          </ul>
        </>
      )}
      <hr className="border-border" />
      <h3 className="text-lg">Add new url</h3>
      <NewServiceURLForm />
    </div>
  );
}

type ServiceURLFormItemProps = {
  id?: string | null;
  change_id?: string;
  change_type?: "UPDATE" | "DELETE" | "ADD";
} & Omit<DockerService["urls"][number], "id">;

function ServiceURLFormItem({
  domain,
  redirect_to,
  base_path,
  change_id,
  change_type,
  strip_prefix,
  id
}: ServiceURLFormItemProps) {
  const { project_slug, service_slug } = Route.useParams();
  const cancelUrlChangeMutation = useCancelDockerServiceChangeMutation(
    project_slug,
    service_slug
  );
  const [isRedirect, setIsRedirect] = React.useState(Boolean(redirect_to));
  const [hasCopied, startTransition] = React.useTransition();

  const { mutateAsync: removeUrl } = useRequestServiceChangeMutation({
    project_slug,
    service_slug,
    field: "urls",
    onSuccess() {
      setAccordionValue("");
    }
  });

  const {
    mutate: editUrl,
    isPending: isUpdatingUrl,
    data,
    reset
  } = useRequestServiceChangeMutation({
    project_slug,
    service_slug,
    field: "urls",
    onSuccess() {
      setAccordionValue("");
    }
  });

  const errors = getFormErrorsFromResponseData(data);
  const [accordionValue, setAccordionValue] = React.useState("");

  return (
    <div className="relative group">
      <div
        className="absolute top-2 right-2 inline-flex gap-1 items-center"
        role="none"
      >
        <TooltipProvider>
          <Tooltip delayDuration={0}>
            <TooltipTrigger asChild>
              <Button
                variant="ghost"
                className={cn(
                  "px-2.5 py-0.5 focus-visible:opacity-100 group-hover:opacity-100",
                  hasCopied ? "opacity-100" : "md:opacity-0"
                )}
                onClick={() => {
                  navigator.clipboard
                    .writeText(`${domain}${base_path}`)
                    .then(() => {
                      // show pending state (which is success state), until the user has stopped clicking the button
                      startTransition(() => wait(1000));
                    });
                }}
              >
                {hasCopied ? (
                  <CheckIcon size={15} className="flex-none" />
                ) : (
                  <CopyIcon size={15} className="flex-none" />
                )}
                <span className="sr-only">Copy url</span>
              </Button>
            </TooltipTrigger>
            <TooltipContent>Copy url</TooltipContent>
          </Tooltip>
          {change_id !== undefined ? (
            <Tooltip delayDuration={0}>
              <TooltipTrigger asChild>
                <Button
                  variant="ghost"
                  className="px-2.5 py-0.5 md:opacity-0 focus-visible:opacity-100 group-hover:opacity-100"
                  onClick={() =>
                    toast.promise(
                      cancelUrlChangeMutation.mutateAsync(change_id),
                      {
                        loading: `Cancelling url change...`,
                        success: "Success",
                        error: "Error",
                        closeButton: true,
                        description(data) {
                          if (data instanceof Error) {
                            return data.message;
                          }
                          return "Done.";
                        }
                      }
                    )
                  }
                >
                  <Undo2Icon size={15} className="flex-none" />
                  <span className="sr-only">Revert change</span>
                </Button>
              </TooltipTrigger>
              <TooltipContent>Revert change</TooltipContent>
            </Tooltip>
          ) : (
            id && (
              <Tooltip delayDuration={0}>
                <TooltipTrigger asChild>
                  <Button
                    variant="ghost"
                    className="px-2.5 py-0.5 md:opacity-0 focus-visible:opacity-100 group-hover:opacity-100"
                    onClick={() =>
                      toast.promise(
                        removeUrl({
                          type: "DELETE",
                          item_id: id
                        }),
                        {
                          loading: `Requesting change...`,
                          success: "Success",
                          error: "Error",
                          closeButton: true,
                          description(data) {
                            if (data instanceof Error) {
                              return data.message;
                            }
                            return "Done.";
                          }
                        }
                      )
                    }
                  >
                    <Trash2Icon size={15} className="flex-none text-red-400" />
                    <span className="sr-only">Delete url</span>
                  </Button>
                </TooltipTrigger>
                <TooltipContent>Delete url</TooltipContent>
              </Tooltip>
            )
          )}
        </TooltipProvider>
      </div>

      <Accordion
        type="single"
        collapsible
        value={accordionValue}
        onValueChange={(state) => {
          setAccordionValue(state);
        }}
      >
        <AccordionItem
          value={`${domain}/${base_path}`}
          className="border-none"
          disabled={!!change_id}
        >
          <AccordionTrigger
            className={cn(
              "w-full px-3 bg-muted rounded-md inline-flex gap-2 items-center text-start flex-wrap pr-24",
              "[&[data-state=open]]:rounded-b-none [&[data-state=open]_svg]:rotate-90",
              {
                "dark:bg-secondary-foreground bg-secondary/60 ":
                  change_type === "UPDATE",
                "dark:bg-primary-foreground bg-primary/60":
                  change_type === "ADD",
                "dark:bg-red-500/30 bg-red-400/60": change_type === "DELETE"
              }
            )}
          >
            <p>
              {domain}
              <span className="text-grey">{base_path ?? "/"}</span>
            </p>
            {redirect_to && (
              <div className="inline-flex gap-2 items-center">
                <ArrowRightIcon size={15} className="text-grey flex-none" />
                <span className="text-grey">{redirect_to.url}</span>
              </div>
            )}
          </AccordionTrigger>
          {id && (
            <AccordionContent className="border-border border-x border-b rounded-b-md p-4 mb-4">
              <Form.Root
                action={(formData) => {
                  editUrl({
                    type: "UPDATE",
                    item_id: id,
                    new_value: {
                      domain: formData.get("domain")?.toString() ?? "",
                      base_path: formData.get("base_path")?.toString(),
                      strip_prefix:
                        formData.get("strip_prefix")?.toString() === "on",
                      redirect_to: !isRedirect
                        ? undefined
                        : {
                            url:
                              formData.get("redirect_to_url")?.toString() ?? "",
                            permanent:
                              formData
                                .get("redirect_to_permanent")
                                ?.toString() === "on"
                          }
                    }
                  });
                }}
                className="flex flex-col gap-4"
              >
                {errors.new_value?.non_field_errors && (
                  <Alert variant="destructive">
                    <AlertCircleIcon className="h-4 w-4" />
                    <AlertTitle>Error</AlertTitle>
                    <AlertDescription>
                      {errors.new_value.non_field_errors}
                    </AlertDescription>
                  </Alert>
                )}

                <Form.Field
                  name="domain"
                  className="flex-1 inline-flex flex-col gap-1"
                >
                  <Form.Label className="text-gray-400">Domain</Form.Label>
                  <Form.Control asChild>
                    <Input
                      placeholder="ex: www.mysupersaas.co"
                      defaultValue={domain}
                    />
                  </Form.Control>
                  {errors.new_value?.domain && (
                    <Form.Message className="text-red-500 text-sm">
                      {errors.new_value?.domain}
                    </Form.Message>
                  )}
                </Form.Field>
                <Form.Field
                  name="base_path"
                  className="flex-1 inline-flex flex-col gap-1"
                >
                  <Form.Label className="text-gray-400">Base path</Form.Label>
                  <Form.Control asChild>
                    <Input
                      placeholder="ex: /"
                      defaultValue={base_path ?? "/"}
                    />
                  </Form.Control>
                  {errors.new_value?.base_path && (
                    <Form.Message className="text-red-500 text-sm">
                      {errors.new_value?.base_path}
                    </Form.Message>
                  )}
                </Form.Field>

                <Form.Field
                  name="strip_prefix"
                  className="flex-1 inline-flex gap-2 flex-col"
                >
                  <div className="inline-flex gap-2 items-center">
                    <Form.Control asChild>
                      <Checkbox defaultChecked={strip_prefix} />
                    </Form.Control>

                    <Form.Label className="text-gray-400 inline-flex gap-1 items-center">
                      Strip path prefix ?
                      <TooltipProvider>
                        <Tooltip delayDuration={0}>
                          <TooltipTrigger>
                            <InfoIcon size={15} />
                          </TooltipTrigger>
                          <TooltipContent className="max-w-48">
                            Wether or not to omit the base path when passing the
                            request to your service.
                          </TooltipContent>
                        </Tooltip>
                      </TooltipProvider>
                    </Form.Label>
                  </div>
                  {errors.new_value?.strip_prefix && (
                    <Form.Message className="text-red-500 text-sm relative left-6">
                      {errors.new_value.strip_prefix}
                    </Form.Message>
                  )}
                </Form.Field>

                <Form.Field
                  name="is_redirect"
                  className="flex-1 inline-flex gap-2 flex-col"
                >
                  <div className="inline-flex gap-2 items-center">
                    <Form.Control asChild>
                      <Checkbox
                        defaultChecked={isRedirect}
                        onCheckedChange={(state) =>
                          setIsRedirect(Boolean(state))
                        }
                      />
                    </Form.Control>

                    <Form.Label className="text-gray-400 inline-flex gap-1 items-center">
                      Is redirect ?
                    </Form.Label>
                  </div>
                  {errors.new_value?.redirect_to?.non_field_errors && (
                    <Form.Message className="text-red-500 text-sm relative left-6">
                      {errors.new_value.redirect_to.non_field_errors}
                    </Form.Message>
                  )}
                </Form.Field>

                {isRedirect && (
                  <div className="flex flex-col gap-4 pl-4">
                    <Form.Field
                      name="redirect_to_url"
                      className="flex-1 inline-flex flex-col gap-1"
                    >
                      <Form.Label className="text-gray-400">
                        Redirect to url
                      </Form.Label>
                      <Form.Control asChild>
                        <Input
                          placeholder="ex: https://mysupersaas.co/"
                          defaultValue={redirect_to?.url}
                        />
                      </Form.Control>
                      {errors.new_value?.redirect_to?.url && (
                        <Form.Message className="text-red-500 text-sm">
                          {errors.new_value.redirect_to.url}
                        </Form.Message>
                      )}
                    </Form.Field>

                    <Form.Field
                      name="redirect_to_permanent"
                      className="flex-1 inline-flex gap-2 flex-col"
                    >
                      <div className="inline-flex items-center gap-2">
                        <Form.Control asChild>
                          <Checkbox defaultChecked={redirect_to?.permanent} />
                        </Form.Control>

                        <Form.Label className="text-gray-400 inline-flex gap-1 items-center">
                          Permanent redirect
                          <TooltipProvider>
                            <Tooltip delayDuration={0}>
                              <TooltipTrigger>
                                <InfoIcon size={15} />
                              </TooltipTrigger>
                              <TooltipContent className="max-w-64 text-balance">
                                If checked, ZaneoOps will redirect with a 308
                                status code; otherwise, it will redirect with a
                                307 status code.
                              </TooltipContent>
                            </Tooltip>
                          </TooltipProvider>
                        </Form.Label>
                      </div>
                      {errors.new_value?.redirect_to?.permanent && (
                        <Form.Message className="text-red-500 text-sm ">
                          {errors.new_value.redirect_to.permanent}
                        </Form.Message>
                      )}
                    </Form.Field>
                  </div>
                )}
                <div className="flex justify-end items-center gap-2 border-t pt-4 px-4 -mx-4 border-border">
                  <SubmitButton
                    variant="secondary"
                    isPending={isUpdatingUrl}
                    className="inline-flex gap-1"
                  >
                    {isUpdatingUrl ? (
                      <>
                        <span>Updating...</span>
                        <LoaderIcon className="animate-spin" size={15} />
                      </>
                    ) : (
                      <>
                        Update
                        <CheckIcon size={15} />
                      </>
                    )}
                  </SubmitButton>

                  <Button onClick={reset} variant="outline" type="reset">
                    Reset
                  </Button>
                </div>
              </Form.Root>
            </AccordionContent>
          )}
        </AccordionItem>
      </Accordion>
    </div>
  );
}

function NewServiceURLForm() {
  const [isRedirect, setIsRedirect] = React.useState(false);
  const { project_slug, service_slug } = Route.useParams();
  const formRef = React.useRef<React.ElementRef<"form">>(null);

  const { mutate, isPending, data, reset } = useRequestServiceChangeMutation({
    project_slug,
    service_slug,
    field: "urls"
  });

  const errors = getFormErrorsFromResponseData(data);

  return (
    <Form.Root
      action={(formData) => {
        mutate(
          {
            type: "ADD",
            new_value: {
              domain: formData.get("domain")?.toString() ?? "",
              base_path: formData.get("base_path")?.toString(),
              strip_prefix: formData.get("strip_prefix")?.toString() === "on",
              redirect_to: !isRedirect
                ? undefined
                : {
                    url: formData.get("redirect_to_url")?.toString() ?? "",
                    permanent:
                      formData.get("redirect_to_permanent")?.toString() === "on"
                  }
            }
          },
          {
            onSuccess(errors) {
              if (!errors) {
                formRef.current?.reset();
              } else {
                console.log({
                  errors
                });
              }
            }
          }
        );
      }}
      className="flex flex-col gap-4 border border-border p-4 rounded-md"
      ref={formRef}
    >
      {errors.new_value?.non_field_errors && (
        <Alert variant="destructive">
          <AlertCircleIcon className="h-4 w-4" />
          <AlertTitle>Error</AlertTitle>
          <AlertDescription>
            {errors.new_value.non_field_errors}
          </AlertDescription>
        </Alert>
      )}
      <Form.Field name="domain" className="flex-1 inline-flex flex-col gap-1">
        <Form.Label className="text-gray-400">Domain</Form.Label>
        <Form.Control asChild>
          <Input placeholder="ex: www.mysupersaas.co" />
        </Form.Control>
        {errors.new_value?.domain && (
          <Form.Message className="text-red-500 text-sm">
            {errors.new_value.domain}
          </Form.Message>
        )}
      </Form.Field>
      <Form.Field
        name="base_path"
        className="flex-1 inline-flex flex-col gap-1"
      >
        <Form.Label className="text-gray-400">Base path</Form.Label>
        <Form.Control asChild>
          <Input placeholder="ex: /api" defaultValue="/" />
        </Form.Control>
        {errors.new_value?.base_path && (
          <Form.Message className="text-red-500 text-sm">
            {errors.new_value.base_path}
          </Form.Message>
        )}
      </Form.Field>

      <Form.Field
        name="strip_prefix"
        className="flex-1 inline-flex gap-2 flex-col"
      >
        <div className="inline-flex gap-2 items-center">
          <Form.Control asChild>
            <Checkbox defaultChecked />
          </Form.Control>

          <Form.Label className="text-gray-400 inline-flex gap-1 items-center">
            Strip path prefix ?
            <TooltipProvider>
              <Tooltip delayDuration={0}>
                <TooltipTrigger>
                  <InfoIcon size={15} />
                </TooltipTrigger>
                <TooltipContent className="max-w-48">
                  Wether or not to omit the base path when passing the request
                  to your service.
                </TooltipContent>
              </Tooltip>
            </TooltipProvider>
          </Form.Label>
        </div>
        {errors.new_value?.strip_prefix && (
          <Form.Message className="text-red-500 text-sm relative left-6">
            {errors.new_value.strip_prefix}
          </Form.Message>
        )}
      </Form.Field>

      <Form.Field
        name="is_redirect"
        className="flex-1 inline-flex gap-2 flex-col"
      >
        <div className="inline-flex gap-2 items-center">
          <Form.Control asChild>
            <Checkbox
              defaultChecked={isRedirect}
              onCheckedChange={(state) => setIsRedirect(Boolean(state))}
            />
          </Form.Control>

          <Form.Label className="text-gray-400 inline-flex gap-1 items-center">
            Is redirect ?
          </Form.Label>
        </div>
        {errors.new_value?.redirect_to?.non_field_errors && (
          <Form.Message className="text-red-500 text-sm relative left-6">
            {errors.new_value.redirect_to.non_field_errors}
          </Form.Message>
        )}
      </Form.Field>

      {isRedirect && (
        <div className="flex flex-col gap-4 pl-4">
          <Form.Field
            name="redirect_to_url"
            className="flex-1 inline-flex flex-col gap-1"
          >
            <Form.Label className="text-gray-400">Redirect to url</Form.Label>
            <Form.Control asChild>
              <Input placeholder="ex: https://mysupersaas.co/" />
            </Form.Control>
            {errors.new_value?.redirect_to?.url && (
              <Form.Message className="text-red-500 text-sm">
                {errors.new_value.redirect_to.url}
              </Form.Message>
            )}
          </Form.Field>

          <Form.Field
            name="redirect_to_permanent"
            className="flex-1 inline-flex gap-2 flex-col"
          >
            <div className="inline-flex items-center gap-2">
              <Form.Control asChild>
                <Checkbox />
              </Form.Control>

              <Form.Label className="text-gray-400 inline-flex gap-1 items-center">
                Permanent redirect
                <TooltipProvider>
                  <Tooltip delayDuration={0}>
                    <TooltipTrigger>
                      <InfoIcon size={15} />
                    </TooltipTrigger>
                    <TooltipContent className="max-w-64 text-balance">
                      If checked, ZaneoOps will redirect with a 308 status code;
                      otherwise, it will redirect with a 307 status code.
                    </TooltipContent>
                  </Tooltip>
                </TooltipProvider>
              </Form.Label>
            </div>
            {errors.new_value?.redirect_to?.permanent && (
              <Form.Message className="text-red-500 text-sm ">
                {errors.new_value.redirect_to.permanent}
              </Form.Message>
            )}
          </Form.Field>
        </div>
      )}

      <div className="flex justify-end items-center gap-2 border-t pt-4 px-4 -mx-4 border-border">
        <SubmitButton
          variant="secondary"
          isPending={isPending}
          className="inline-flex gap-1 flex-1 md:flex-none"
        >
          {isPending ? (
            <>
              <span>Adding...</span>
              <LoaderIcon className="animate-spin" size={15} />
            </>
          ) : (
            <>
              <span>Add</span>
              <Plus size={15} />
            </>
          )}
        </SubmitButton>
        <Button
          variant="outline"
          type="reset"
          className="flex-1 md:flex-none"
          onClick={reset}
        >
          Reset
        </Button>
      </div>
    </Form.Root>
  );
}

function NetworkAliasesGroup({ className }: ServiceFormProps) {
  const { project_slug, service_slug } = Route.useParams();
  const singleServiceQuery = useDockerServiceSingleQuery(
    project_slug,
    service_slug
  );
  const [hasCopied, startTransition] = React.useTransition();
  const service = singleServiceQuery.data?.data;

  if (!service) return null;

  return (
    <div className={cn("flex flex-col gap-5", className)}>
      <div className="flex flex-col gap-3">
        <h3 className="text-lg">Network alias</h3>
        <p className="text-gray-400">
          You can reach this service from within the same project using this
          value
        </p>
      </div>
      <div className="border border-border px-4 pb-4 pt-1 rounded-md flex items-center gap-4 group">
        <GlobeLockIcon
          className="text-grey flex-none hidden md:block"
          size={20}
        />
        <div className="flex flex-col gap-0.5">
          <div className="flex gap-2 items-center">
            <span className="text-lg break-all">
              {service.network_aliases[0]}
            </span>
            <TooltipProvider>
              <Tooltip delayDuration={0}>
                <TooltipTrigger asChild>
                  <Button
                    variant="ghost"
                    className={cn(
                      "px-2.5 py-0.5 focus-visible:opacity-100 group-hover:opacity-100",
                      hasCopied ? "opacity-100" : "md:opacity-0"
                    )}
                    onClick={() => {
                      navigator.clipboard
                        .writeText(service.network_aliases[0])
                        .then(() => {
                          // show pending state (which is success state), until the user has stopped clicking the button
                          startTransition(() => wait(1000));
                        });
                    }}
                  >
                    {hasCopied ? (
                      <CheckIcon size={15} className="flex-none" />
                    ) : (
                      <CopyIcon size={15} className="flex-none" />
                    )}
                    <span className="sr-only">Copy network alias</span>
                  </Button>
                </TooltipTrigger>
                <TooltipContent>Copy network alias</TooltipContent>
              </Tooltip>
            </TooltipProvider>
          </div>
          <small className="text-grey">
            You can also simply use <Code>{service.network_alias}</Code>
          </small>
        </div>
      </div>
    </div>
  );
}

function ServiceCommandForm({ className }: ServiceFormProps) {
  const { project_slug, service_slug } = Route.useParams();

  const serviceSingleQuery = useDockerServiceSingleQuery(
    project_slug,
    service_slug
  );

  const cancelStartingCommandChangeMutation =
    useCancelDockerServiceChangeMutation(project_slug, service_slug);

  const updateStartingCommandMutation = useRequestServiceChangeMutation({
    project_slug,
    service_slug,
    field: "command",
    onSuccess() {}
  });

  const service = serviceSingleQuery.data?.data;
  const startingCommandChange = service?.unapplied_changes.find(
    (change) => change.field === "command"
  );

  const command =
    (startingCommandChange?.new_value as string) ?? service?.command;

  const errors = getFormErrorsFromResponseData(
    updateStartingCommandMutation.data
  );

  const isEmptyChange =
    startingCommandChange !== undefined &&
    startingCommandChange.new_value === null;

  return (
    <Form.Root
      action={(formData) => {
        if (startingCommandChange !== undefined) {
          cancelStartingCommandChangeMutation.mutate(startingCommandChange.id, {
            onError(error) {
              toast.error("Error", {
                closeButton: true,
                description: error.message
              });
            }
          });
        } else {
          updateStartingCommandMutation.mutate({
            type: "UPDATE",
            new_value: formData.get("command")?.toString().trim() || null // empty should be considered as `null`
          });
        }
      }}
      className={cn("flex flex-col gap-4 w-full items-start", className)}
    >
      <fieldset className="w-full flex flex-col gap-4">
        <legend className="text-lg">Custom start command</legend>
        <p className="text-gray-400">
          Command executed at the start of each new deployment.
        </p>
        <Form.Field name="command" className="flex flex-col gap-1.5 flex-1">
          <Form.Label className="text-muted-foreground sr-only">
            Value
          </Form.Label>
          <Form.Control asChild>
            <Input
              placeholder={isEmptyChange ? "<empty>" : "ex: npm run start"}
              disabled={startingCommandChange !== undefined}
              className={cn(
                "disabled:placeholder-shown:font-mono disabled:bg-secondary/60",
                "disabled:dark:bg-secondary-foreground disabled:opacity-100",
                "disabled:border-transparent"
              )}
              defaultValue={command}
            />
          </Form.Control>
          {errors.new_value && (
            <Form.Message className="text-red-500 text-sm">
              {errors.new_value}
            </Form.Message>
          )}
        </Form.Field>
      </fieldset>

      <div className="inline-flex items-center gap-2">
        {startingCommandChange !== undefined ? (
          <SubmitButton
            isPending={cancelStartingCommandChangeMutation.isPending}
            variant="outline"
          >
            {cancelStartingCommandChangeMutation.isPending ? (
              <>
                <LoaderIcon className="animate-spin" size={15} />
                <span>Reverting...</span>
              </>
            ) : (
              <>
                <Undo2Icon size={15} className="flex-none" />
                <span>Revert change</span>
              </>
            )}
          </SubmitButton>
        ) : (
          <>
            <SubmitButton
              isPending={updateStartingCommandMutation.isPending}
              variant="secondary"
            >
              {updateStartingCommandMutation.isPending ? (
                <>
                  <LoaderIcon className="animate-spin" size={15} />
                  <span>Updating ...</span>
                </>
              ) : (
                <>
                  <CheckIcon size={15} className="flex-none" />
                  <span>Update</span>
                </>
              )}
            </SubmitButton>
            <Button
              variant="outline"
              onClick={updateStartingCommandMutation.reset}
              type="reset"
              className="flex-1 md:flex-none"
            >
              Reset
            </Button>
          </>
        )}
      </div>
    </Form.Root>
  );
}

function ServiceHealthcheckForm({ className }: ServiceFormProps) {
  const { project_slug, service_slug } = Route.useParams();
  const formRef = React.useRef<React.ElementRef<"form">>(null);

  const serviceSingleQuery = useDockerServiceSingleQuery(
    project_slug,
    service_slug
  );

  const cancelHealthcheckChangeMutation = useCancelDockerServiceChangeMutation(
    project_slug,
    service_slug
  );

  const updateHealthcheckCommandMutation = useRequestServiceChangeMutation({
    project_slug,
    service_slug,
    field: "healthcheck"
  });

  const removeHealthcheckCommandMutation = useRequestServiceChangeMutation({
    project_slug,
    service_slug,
    field: "healthcheck"
  });

  const service = serviceSingleQuery.data?.data;
  const healthcheckChange = service?.unapplied_changes.find(
    (change) => change.field === "healthcheck"
  );

  const newHealthCheck =
    healthcheckChange?.new_value as DockerService["healthcheck"];
  const healthcheck =
    newHealthCheck === null ? null : newHealthCheck ?? service?.healthcheck;

  const errors = getFormErrorsFromResponseData(
    updateHealthcheckCommandMutation.data
  );

  const [healthcheckType, setHealthCheckType] = React.useState<
    NonNullable<DockerService["healthcheck"]>["type"] | "none"
  >(healthcheck?.type ?? "none");

  return (
    <Form.Root
      ref={formRef}
      action={(formData) => {
        console.log({
          formData
        });
        const remove = formData.get("remove")?.toString() === "true";
        if (remove) {
          removeHealthcheckCommandMutation.mutate(
            {
              type: "UPDATE",
              new_value: null
            },
            {
              onSuccess(errors) {
                if (!errors) {
                  formRef.current?.reset();
                  setHealthCheckType("none");
                }
              }
            }
          );
          return;
        }
        const revertChange =
          formData.get("revert_change")?.toString() === "true";
        if (revertChange && healthcheckChange?.id) {
          cancelHealthcheckChangeMutation.mutate(healthcheckChange.id, {
            onSuccess() {
              setHealthCheckType(service?.healthcheck?.type ?? "none");
              formRef.current?.reset();
            }
          });
          return;
        }

        updateHealthcheckCommandMutation.mutate(
          {
            type: "UPDATE",
            new_value: {
              type: formData.get("type")?.toString() as NonNullable<
                DockerService["healthcheck"]
              >["type"],
              value: formData.get("value")?.toString() ?? "",
              timeout_seconds: Number(
                formData.get("timeout_seconds")?.toString() || 30
              ),
              interval_seconds: Number(
                formData.get("interval_seconds")?.toString() || 30
              )
            }
          },
          {
            onSuccess(errors) {
              if (!errors) {
                formRef.current?.reset();
              }
            }
          }
        );
      }}
      className={cn("flex flex-col gap-4 w-full items-start", className)}
    >
      <fieldset className="w-full flex flex-col gap-5">
        <legend className="text-lg">Healthcheck</legend>
        <p className="text-gray-400">
          ZaneOps uses this to verify if your app is running correctly for new
          deployments and ensures the deployment is successful before switching.
          This value will also be used to continously monitor your app.
        </p>

        <div className="flex flex-col md:flex-row md:items-start gap-2">
          <Form.Field name="type" className="flex flex-col gap-1.5 flex-1">
            <Form.Label className="text-muted-foreground">Type</Form.Label>
            <Form.Control asChild>
              <Select
                name="type"
                value={healthcheckType}
                onValueChange={(value) =>
                  setHealthCheckType(
                    value as NonNullable<DockerService["healthcheck"]>["type"]
                  )
                }
              >
                <SelectTrigger
                  className={cn(
                    healthcheckChange &&
                      "bg-secondary/60 dark:bg-secondary-foreground opacity-100 border-transparent",
                    healthcheckType === "none" && "text-muted-foreground"
                  )}
                >
                  <SelectValue placeholder="Select a type" />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem disabled value="none">
                    Select a type
                  </SelectItem>
                  <SelectItem value="PATH">Path</SelectItem>
                  <SelectItem value="COMMAND">Command</SelectItem>
                </SelectContent>
              </Select>
            </Form.Control>
            {errors.new_value?.type && (
              <Form.Message className="text-red-500 text-sm">
                {errors.new_value.type}
              </Form.Message>
            )}
          </Form.Field>
          <Form.Field name="value" className="flex flex-col gap-1.5 flex-1">
            <Form.Label className="text-muted-foreground">Value</Form.Label>
            <Form.Control asChild>
              <Input
                placeholder={
                  healthcheckChange && healthcheck === null
                    ? "<empty>"
                    : healthcheckType === "COMMAND"
                      ? "ex: redis-cli ping"
                      : "ex: /healthcheck"
                }
                className={cn(
                  healthcheckChange &&
                    "bg-secondary/60 dark:bg-secondary-foreground opacity-100 border-transparent placeholder-shown:font-mono"
                )}
                defaultValue={healthcheck?.value}
              />
            </Form.Control>
            {errors.new_value?.value && (
              <Form.Message className="text-red-500 text-sm">
                {errors.new_value.value}
              </Form.Message>
            )}
          </Form.Field>
        </div>
        <Form.Field
          name="timeout_seconds"
          className="flex flex-col gap-1.5 flex-1"
        >
          <Form.Label className="text-muted-foreground">
            Timeout (in seconds)
          </Form.Label>
          <Form.Control asChild>
            <Input
              placeholder={
                healthcheckChange && healthcheck === null ? "<empty>" : "ex: 30"
              }
              defaultValue={
                healthcheckChange && healthcheck === null
                  ? ""
                  : healthcheck?.timeout_seconds
              }
              className={cn(
                healthcheckChange &&
                  "bg-secondary/60 dark:bg-secondary-foreground opacity-100 border-transparent placeholder-shown:font-mono"
              )}
            />
          </Form.Control>
          {errors.new_value?.timeout_seconds && (
            <Form.Message className="text-red-500 text-sm">
              {errors.new_value.timeout_seconds}
            </Form.Message>
          )}
        </Form.Field>
        <Form.Field
          name="interval_seconds"
          className="flex flex-col gap-1.5 flex-1"
        >
          <Form.Label className="text-muted-foreground">
            Interval (in seconds)
          </Form.Label>
          <Form.Control asChild>
            <Input
              placeholder={
                healthcheckChange && healthcheck === null ? "<empty>" : "ex: 30"
              }
              defaultValue={
                healthcheckChange && healthcheck === null
                  ? ""
                  : healthcheck?.interval_seconds
              }
              className={cn(
                healthcheckChange &&
                  "bg-secondary/60 dark:bg-secondary-foreground opacity-100 border-transparent placeholder-shown:font-mono"
              )}
            />
          </Form.Control>
          {errors.new_value?.interval_seconds && (
            <Form.Message className="text-red-500 text-sm">
              {errors.new_value.interval_seconds}
            </Form.Message>
          )}
        </Form.Field>
      </fieldset>

      <div className="flex items-center gap-2">
        <SubmitButton
          isPending={updateHealthcheckCommandMutation.isPending}
          variant="secondary"
        >
          {updateHealthcheckCommandMutation.isPending ? (
            <>
              <LoaderIcon className="animate-spin" size={15} />
              <span>Updating...</span>
            </>
          ) : (
            <>
              <CheckIcon size={15} className="flex-none" />
              <span>Update</span>
            </>
          )}
        </SubmitButton>
        {service?.healthcheck !== null && healthcheck !== null && (
          <SubmitButton
            value="true"
            name="remove"
            isPending={removeHealthcheckCommandMutation.isPending}
            variant="destructive"
            className="inline-flex gap-1 items-center"
          >
            {removeHealthcheckCommandMutation.isPending ? (
              <>
                <LoaderIcon className="animate-spin" size={15} />
                <span>Removing...</span>
              </>
            ) : (
              <>
                <Trash2Icon size={15} className="flex-none" />
                <span>Remove healthcheck</span>
              </>
            )}
          </SubmitButton>
        )}

        <div className="w-px h-8 bg-border" />

        {healthcheckChange && (
          <SubmitButton
            isPending={cancelHealthcheckChangeMutation.isPending}
            variant="outline"
            name="revert_change"
            value="true"
          >
            {cancelHealthcheckChangeMutation.isPending ? (
              <>
                <LoaderIcon className="animate-spin" size={15} />
                <span>Reverting...</span>
              </>
            ) : (
              <>
                <Undo2Icon size={15} className="flex-none" />
                <span>Revert change</span>
              </>
            )}
          </SubmitButton>
        )}
      </div>
    </Form.Root>
  );
}

function ServiceVolumesForm({ className }: ServiceFormProps) {
  return (
    <div className={cn("flex flex-col gap-5", className)}>
      <div className="flex flex-col gap-3">
        <p className="text-gray-400">
          Used for persisting the data from your services.
        </p>

        <Alert variant="warning">
          <TriangleAlertIcon size={15} />
          <AlertTitle>Warning</AlertTitle>
          <AlertDescription>
            Adding volumes will disable&nbsp;
            <a href="#" className="underline inline-flex gap-1 items-center">
              zero-downtime deployments <ExternalLinkIcon size={12} />
            </a>
            .
          </AlertDescription>
        </Alert>
      </div>
      <hr className="border-border" />
      <ul className="flex flex-col gap-2">
        <li>
          <ServiceVolumeItem
            name="redis"
            container_path="/data"
            mode="READ_WRITE"
          />
        </li>
        <li>
          <ServiceVolumeItem
            name="localtime"
            container_path="/etc/localtime"
            host_path="/etc/localtime"
            change_id="1"
            change_type="UPDATE"
            mode="READ_ONLY"
          />
        </li>
      </ul>
      <hr className="border-border" />
      <h3 className="text-lg">Add new volume</h3>
      <NewServiceVolumeForm />
    </div>
  );
}

type ServiceVolumeItemProps = {
  name: string;
  container_path: string;
  mode: "READ_ONLY" | "READ_WRITE";
  host_path?: string;
  change_id?: string;
  change_type?: "UPDATE" | "DELETE" | "ADD";
};

function ServiceVolumeItem({
  name,
  container_path,
  host_path,
  change_type,
  mode,
  change_id
}: ServiceVolumeItemProps) {
  const modeSuffix = mode === "READ_ONLY" ? "read only" : "read write";
  return (
    <div
      className={cn(
        "rounded-md p-4 flex items-start gap-2 group relative bg-muted",
        {
          "dark:bg-secondary-foreground bg-secondary/60 ":
            change_type === "UPDATE",
          "dark:bg-primary-foreground bg-primary/60": change_type === "ADD",
          "dark:bg-red-500/30 bg-red-400/60": change_type === "DELETE"
        }
      )}
    >
      <HardDrive size={20} className="text-grey relative top-1.5" />
      <div className="flex flex-col gap-2">
        <h3 className="text-lg inline-flex gap-1 items-center">
          <span>{name}</span>
        </h3>
        <small className="text-card-foreground inline-flex gap-1 items-center">
          {host_path && (
            <>
              <span>{host_path}</span>
              <ArrowRightIcon size={15} className="text-grey" />
            </>
          )}
          <span className="text-grey">{container_path}</span>
          <Code>{modeSuffix}</Code>
        </small>
      </div>
      <div className="absolute top-4 right-4 flex gap-2 items-center">
        <TooltipProvider>
          {change_id !== undefined ? (
            <Tooltip delayDuration={0}>
              <TooltipTrigger asChild>
                <Button
                  variant="ghost"
                  className="px-2.5 py-0.5 md:opacity-0 focus-visible:opacity-100 group-hover:opacity-100"
                >
                  <Undo2Icon size={15} className="flex-none" />
                  <span className="sr-only">Revert change</span>
                </Button>
              </TooltipTrigger>
              <TooltipContent>Revert change</TooltipContent>
            </Tooltip>
          ) : (
            <>
              <Tooltip delayDuration={0}>
                <TooltipTrigger asChild>
                  <Button
                    variant="ghost"
                    className="px-2.5 py-0.5 md:opacity-0 focus-visible:opacity-100 group-hover:opacity-100"
                  >
                    <EditIcon size={15} className="flex-none" />
                    <span className="sr-only">Edit volume</span>
                  </Button>
                </TooltipTrigger>
                <TooltipContent>Edit volume</TooltipContent>
              </Tooltip>
              <Tooltip delayDuration={0}>
                <TooltipTrigger asChild>
                  <Button
                    variant="ghost"
                    className="px-2.5 py-0.5 md:opacity-0 focus-visible:opacity-100 group-hover:opacity-100"
                  >
                    <Trash2Icon size={15} className="flex-none text-red-400" />
                    <span className="sr-only">Delete volume</span>
                  </Button>
                </TooltipTrigger>
                <TooltipContent>Delete volume</TooltipContent>
              </Tooltip>
            </>
          )}
        </TooltipProvider>
      </div>
    </div>
  );
}

function NewServiceVolumeForm() {
  return (
    <Form.Root
      action={() => {}}
      className={cn(
        "flex flex-col gap-4 w-full border border-border rounded-md p-4"
      )}
    >
      <Form.Field name="type" className="flex flex-col gap-1.5 flex-1">
        <Form.Label className="text-muted-foreground">Mode</Form.Label>
        <Form.Control asChild>
          <Select>
            <SelectTrigger>
              <SelectValue placeholder="Select a volume mode" />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="READ_ONLY">Read only</SelectItem>
              <SelectItem value="READ_WRITE">Read & Write</SelectItem>
            </SelectContent>
          </Select>
        </Form.Control>
      </Form.Field>
      <Form.Field
        name="container_path"
        className="flex flex-col gap-1.5 flex-1"
      >
        <Form.Label className="text-muted-foreground">
          Container path
        </Form.Label>
        <Form.Control asChild>
          <Input placeholder="ex: /data" />
        </Form.Control>
      </Form.Field>
      <Form.Field name="host_path" className="flex flex-col gap-1.5 flex-1">
        <Form.Label className="text-muted-foreground">Host path</Form.Label>
        <Form.Control asChild>
          <Input placeholder="ex: /etc/localtime" />
        </Form.Control>
      </Form.Field>

      <hr className="-mx-4 border-border" />
      <div className="flex justify-end items-center gap-2">
        <SubmitButton
          isPending={false}
          variant="secondary"
          className="flex-1 md:flex-none"
        >
          <span>Add</span>
          <PlusIcon size={15} className="flex-none" />
        </SubmitButton>
        <Button variant="outline" type="reset" className="flex-1 md:flex-none">
          Cancel
        </Button>
      </div>
    </Form.Root>
  );
}

function ServiceDangerZoneForm({ className }: ServiceFormProps) {
  return (
    <div className={cn("flex flex-col gap-4 items-start", className)}>
      <h3 className="text-lg">Toggle service state</h3>
      <form action={() => {}}>
        <SubmitButton
          isPending={false}
          variant="warning"
          className=" inline-flex gap-1 items-center"
        >
          <SunsetIcon size={15} className="flex-none" />
          <span>Put service to sleep</span>
        </SubmitButton>
        {/* <SubmitButton
          isPending={false}
          variant="default"
          className="inline-flex gap-1 items-center"
        >
          <SunriseIcon size={15} className="flex-none" />
          <span>Wake up service</span>
        </SubmitButton> */}
      </form>

      <hr className="w-full border-border" />
      <h3 className="text-lg text-red-400">Archive this service</h3>
      <div className="flex flex-col gap-2 items-start">
        <p className="text-red-400 ">
          Archiving this service will permanently delete all its deployments,
          This cannot be undone.
        </p>

        <Button
          variant="destructive"
          className="bg-red-500 inline-flex gap-1 items-center"
        >
          <Trash2Icon size={15} className="flex-none" />
          <span>Archive service</span>
        </Button>
      </div>
    </div>
  );
}
