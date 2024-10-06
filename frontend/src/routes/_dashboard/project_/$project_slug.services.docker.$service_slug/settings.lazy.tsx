import * as Form from "@radix-ui/react-form";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { Link, createLazyFileRoute, useNavigate } from "@tanstack/react-router";
import {
  ArrowRightIcon,
  CableIcon,
  CheckIcon,
  ContainerIcon,
  CopyIcon,
  EditIcon,
  EllipsisVerticalIcon,
  ExternalLinkIcon,
  Eye,
  EyeOffIcon,
  FlameIcon,
  GlobeLockIcon,
  HammerIcon,
  HardDrive,
  InfoIcon,
  LoaderIcon,
  PaintRollerIcon,
  PencilLineIcon,
  Plus,
  PlusIcon,
  SunriseIcon,
  SunsetIcon,
  Trash2,
  Trash2Icon,
  TriangleAlertIcon,
  Undo2Icon,
  XIcon
} from "lucide-react";
import * as React from "react";
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
  Menubar,
  MenubarContent,
  MenubarContentItem,
  MenubarMenu,
  MenubarTrigger
} from "~/components/ui/menubar";
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
import { useDockerServiceSingleQuery } from "~/lib/hooks/use-docker-service-single-query";
import { cn, getFormErrorsFromResponseData } from "~/lib/utils";
import { getCsrfTokenHeader } from "~/utils";

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
  const queryClient = useQueryClient();
  const [isEditing, setIsEditing] = React.useState(false);
  const serviceSingleQuery = useDockerServiceSingleQuery(
    project_slug,
    service_slug
  );
  const cancelImageChangeMutation = useCancelDockerServiceChangeMutation(
    project_slug,
    service_slug
  );

  const updateImageMutation = useMutation({
    mutationFn: async (new_image: string) => {
      const { error, data } = await apiClient.PUT(
        "/api/projects/{project_slug}/request-service-changes/docker/{service_slug}/",
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
          body: {
            type: "UPDATE",
            new_value: new_image,
            field: "image"
          }
        }
      );
      if (error) {
        return error;
      }

      if (data) {
        await queryClient.invalidateQueries({
          queryKey: serviceKeys.single(project_slug, service_slug, "docker"),
          exact: true
        });
        setIsEditing(false);
        return;
      }
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
            updateImageMutation.mutate(formData.get("image")?.toString() ?? "");
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
                action={() =>
                  cancelImageChangeMutation.mutate(serviceImageChange.id)
                }
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
  const [isPasswordShown, setIsPasswordShown] = React.useState(false);
  return (
    <Form.Root
      action={() => {}}
      className={cn("flex flex-col gap-4 w-full items-start", className)}
    >
      <fieldset className="w-full flex flex-col gap-4">
        <legend className="text-lg">Credentials</legend>
        <p className="text-gray-400">
          If your image is on a private registry, please provide the information
          below.
        </p>
        <Form.Field name="username" className="flex flex-col gap-1.5 flex-1">
          <Form.Label className="text-muted-foreground">
            Username for registry
          </Form.Label>
          <Form.Control asChild>
            <Input placeholder="username" defaultValue="fredkiss" />
          </Form.Control>
        </Form.Field>
        <Form.Field name="password" className="flex flex-col gap-1.5 flex-1">
          <Form.Label className="text-muted-foreground">
            Password for registry
          </Form.Label>
          <div className="flex gap-2">
            <Form.Control asChild>
              <Input
                placeholder="service slug"
                type={isPasswordShown ? "text" : "password"}
                defaultValue="password"
              />
            </Form.Control>
            <TooltipProvider>
              <Tooltip delayDuration={0}>
                <TooltipTrigger asChild>
                  <Button
                    variant="outline"
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
        </Form.Field>
      </fieldset>

      <SubmitButton isPending={false} variant="secondary">
        {/* {isUpdatingVariableValue ? (
               <>
                 <LoaderIcon className="animate-spin" size={15} />
                 <span className="sr-only">Updating variable value...</span>
               </>
             ) : ( */}
        <>
          <CheckIcon size={15} className="flex-none" />
          <span>Update</span>
        </>
        {/* )} */}
      </SubmitButton>
    </Form.Root>
  );
}

function ServicePortsForm({ className }: ServiceFormProps) {
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
      <hr className="border-border" />
      <ul className="flex flex-col gap-1">
        <li>
          <ServicePortItem host={81} forwarded={8080} />
        </li>
        <li>
          <ServicePortItem
            host={82}
            forwarded={8080}
            change_type="UPDATE"
            change_id="1"
          />
        </li>
        <li>
          <ServicePortItem
            host={83}
            forwarded={8080}
            change_type="DELETE"
            change_id="1"
          />
        </li>
        <li>
          <ServicePortItem
            host={84}
            forwarded={8080}
            change_type="ADD"
            change_id="1"
          />
        </li>
      </ul>
      <hr className="border-border" />
      <h3 className="text-lg">Add new port</h3>
      <NewServicePortForm />
    </div>
  );
}

type ServicePortItemProps = {
  host: number;
  forwarded: number;
  change_id?: string;
  change_type?: "UPDATE" | "DELETE" | "ADD";
};

function ServicePortItem({
  host,
  forwarded,
  change_id,
  change_type
}: ServicePortItemProps) {
  return (
    <div
      className={cn(
        "w-full rounded-md flex justify-between items-center gap-2 py-1 pl-4 pr-2 bg-muted",
        {
          "dark:bg-secondary-foreground bg-secondary/60 rounded-md":
            change_type === "UPDATE",
          "dark:bg-primary-foreground bg-primary/60 rounded-md":
            change_type === "ADD",
          "dark:bg-red-500/30 bg-red-400/60 rounded-md":
            change_type === "DELETE"
        }
      )}
    >
      <div className="flex gap-2 items-center">
        <span>{host}</span>
        <ArrowRightIcon size={15} className="text-grey" />
        <span>{forwarded}</span>
      </div>
      <Menubar className="border-none h-auto w-fit">
        <MenubarMenu>
          <MenubarTrigger
            className="flex justify-center items-center gap-2"
            asChild
          >
            <Button variant="ghost" className="px-2.5 py-0.5 hover:bg-inherit">
              <EllipsisVerticalIcon size={15} />
            </Button>
          </MenubarTrigger>

          <MenubarContent
            side="bottom"
            align="start"
            sideOffset={0}
            alignOffset={0}
            className="border min-w-0 mx-9 border-border"
          >
            {change_id !== undefined ? (
              <>
                <MenubarContentItem
                  icon={Undo2Icon}
                  text="Revert change"
                  className="text-red-400"
                  onClick={() => {}}
                />
              </>
            ) : (
              <>
                {" "}
                <MenubarContentItem
                  icon={EditIcon}
                  text="Edit"
                  onClick={() => {}}
                />
                <MenubarContentItem
                  icon={Trash2}
                  text="Remove"
                  className="text-red-400"
                  onClick={() => {}}
                />
              </>
            )}
          </MenubarContent>
        </MenubarMenu>
      </Menubar>
    </div>
  );
}

function NewServicePortForm() {
  return (
    <Form.Root
      action={(formData) => {
        // ...
      }}
      className="flex md:items-end  gap-3 md:flex-row flex-col items-stretch"
    >
      <Form.Field name="host" className="flex-1 inline-flex flex-col gap-1">
        <Form.Label className="text-gray-400">Host port</Form.Label>
        <Form.Control asChild>
          <Input placeholder="ex: 80" />
        </Form.Control>
        {/* {errors.new_value?.key && (
          <Form.Message className="text-red-500 text-sm">
            {errors.new_value?.key}
          </Form.Message>
        )} */}
      </Form.Field>
      <Form.Field
        name="forwarded"
        className="flex-1 inline-flex flex-col gap-1"
      >
        <Form.Label className="text-gray-400">Forwarded port</Form.Label>
        <Form.Control asChild>
          <Input placeholder="ex: 8080" />
        </Form.Control>
        {/* {errors.new_value?.value && (
          <Form.Message className="text-red-500 text-sm">
            {errors.new_value?.value}
          </Form.Message>
        )} */}
      </Form.Field>

      <div className="flex gap-3 items-center w-full md:w-auto">
        <SubmitButton
          isPending={false}
          variant="secondary"
          className="inline-flex gap-1 flex-1"
        >
          {/* {isPending ? (
            <>
              <span>Adding...</span>
              <LoaderIcon className="animate-spin" size={15} />
            </>
          ) : ( */}
          <>
            <span>Add</span>
            <Plus size={15} />
          </>
          {/* )} */}
        </SubmitButton>
        <Button variant="outline" type="reset" className="flex-1">
          Cancel
        </Button>
      </div>
    </Form.Root>
  );
}

function ServiceURLsForm({ className }: ServiceFormProps) {
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
      <hr className="border-border" />
      <ul className="flex flex-col gap-2">
        <li>
          <ServiceURLFormItem domain="nginx-demo.127-0-0-1.sslip.io" />
        </li>
        <li>
          <ServiceURLFormItem
            domain="nginx-demo2.127-0-0-1.sslip.io"
            redirect_to={{ url: "https://nginx-demo.127-0-0-1.sslip.io" }}
            change_type="UPDATE"
            change_id="1"
          />
        </li>
        <li>
          <ServiceURLFormItem
            domain="nginx-demo3.127-0-0-1.sslip.io"
            base_path="/api"
            change_type="ADD"
            change_id="1"
          />
        </li>
      </ul>
      <hr className="border-border" />
      <h3 className="text-lg">Add new url</h3>
      <NewServiceURLForm />
    </div>
  );
}

type ServiceURLFormItemProps = {
  domain: string;
  redirect_to?: {
    url: string;
    permanent?: boolean;
  };
  base_path?: string;
  strip_prefix?: boolean;
  change_id?: string;
  change_type?: "UPDATE" | "DELETE" | "ADD";
};

function ServiceURLFormItem({
  domain,
  redirect_to,
  base_path,
  change_id,
  change_type,
  strip_prefix
}: ServiceURLFormItemProps) {
  const [isRedirect, setIsRedirect] = React.useState(Boolean(redirect_to));

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
                className="px-2.5 py-0.5 md:opacity-0 focus-visible:opacity-100 group-hover:opacity-100"
              >
                <CopyIcon size={15} className="flex-none" />
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
                >
                  <Undo2Icon size={15} className="flex-none" />
                  <span className="sr-only">Revert change</span>
                </Button>
              </TooltipTrigger>
              <TooltipContent>Revert change</TooltipContent>
            </Tooltip>
          ) : (
            <Tooltip delayDuration={0}>
              <TooltipTrigger asChild>
                <Button
                  variant="ghost"
                  className="px-2.5 py-0.5 md:opacity-0 focus-visible:opacity-100 group-hover:opacity-100"
                >
                  <Trash2Icon size={15} className="flex-none text-red-400" />
                  <span className="sr-only">Delete url</span>
                </Button>
              </TooltipTrigger>
              <TooltipContent>Delete url</TooltipContent>
            </Tooltip>
          )}
        </TooltipProvider>
      </div>

      <Accordion type="single" collapsible>
        <AccordionItem
          value={`${domain}/${base_path}`}
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
          <AccordionContent className="border-border border-x border-b rounded-b-md p-4 mb-4">
            <Form.Root action={() => {}} className="flex flex-col gap-4">
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
              </Form.Field>
              <Form.Field
                name="base_path"
                className="flex-1 inline-flex flex-col gap-1"
              >
                <Form.Label className="text-gray-400">Base path</Form.Label>
                <Form.Control asChild>
                  <Input placeholder="ex: /" defaultValue={base_path ?? "/"} />
                </Form.Control>
              </Form.Field>

              <Form.Field
                name="strip_prefix"
                className="flex-1 inline-flex gap-2 items-center"
              >
                <Form.Control asChild>
                  <Checkbox defaultChecked={strip_prefix ?? true} />
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
              </Form.Field>

              <Form.Field
                name="is_redirect"
                className="flex-1 inline-flex gap-2 items-center"
              >
                <Form.Control asChild>
                  <Checkbox
                    defaultChecked={isRedirect}
                    onCheckedChange={(state) => setIsRedirect(Boolean(state))}
                  />
                </Form.Control>

                <Form.Label className="text-gray-400 inline-flex gap-1 items-center">
                  Is redirect ?
                </Form.Label>
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
                  </Form.Field>

                  <Form.Field
                    name="redirect_to_permanent"
                    className="flex-1 inline-flex gap-2 items-center"
                  >
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
                            If checked, ZaneoOps will redirect with a 308 status
                            code; otherwise, it will redirect with a 307 status
                            code.
                          </TooltipContent>
                        </Tooltip>
                      </TooltipProvider>
                    </Form.Label>
                  </Form.Field>
                </div>
              )}

              <div className="flex justify-end items-center gap-2 border-t pt-4 px-4 -mx-4 border-border">
                <SubmitButton
                  variant="secondary"
                  isPending={false}
                  className="inline-flex gap-1"
                >
                  Update
                  <CheckIcon size={15} />
                </SubmitButton>
              </div>
            </Form.Root>
          </AccordionContent>
        </AccordionItem>
      </Accordion>
    </div>
  );
}

function NewServiceURLForm() {
  const [isRedirect, setIsRedirect] = React.useState(false);
  return (
    <Form.Root
      action={() => {}}
      className="flex flex-col gap-4 border border-border p-4 rounded-md"
    >
      <Form.Field name="domain" className="flex-1 inline-flex flex-col gap-1">
        <Form.Label className="text-gray-400">Domain</Form.Label>
        <Form.Control asChild>
          <Input placeholder="ex: www.mysupersaas.co" />
        </Form.Control>
      </Form.Field>
      <Form.Field
        name="base_path"
        className="flex-1 inline-flex flex-col gap-1"
      >
        <Form.Label className="text-gray-400">Base path</Form.Label>
        <Form.Control asChild>
          <Input placeholder="ex: /" defaultValue={"/"} />
        </Form.Control>
      </Form.Field>

      <Form.Field
        name="strip_prefix"
        className="flex-1 inline-flex gap-2 items-center"
      >
        <Form.Control asChild>
          <Checkbox />
        </Form.Control>

        <Form.Label className="text-gray-400 inline-flex gap-1 items-center">
          Strip path prefix ?
          <TooltipProvider>
            <Tooltip delayDuration={0}>
              <TooltipTrigger>
                <InfoIcon size={15} />
              </TooltipTrigger>
              <TooltipContent className="max-w-48">
                Wether or not to omit the base path when passing the request to
                your service.
              </TooltipContent>
            </Tooltip>
          </TooltipProvider>
        </Form.Label>
      </Form.Field>

      <Form.Field
        name="is_redirect"
        className="flex-1 inline-flex gap-2 items-center"
      >
        <Form.Control asChild>
          <Checkbox
            defaultChecked={isRedirect}
            onCheckedChange={(state) => setIsRedirect(Boolean(state))}
          />
        </Form.Control>

        <Form.Label className="text-gray-400 inline-flex gap-1 items-center">
          Is redirect ?
        </Form.Label>
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
          </Form.Field>

          <Form.Field
            name="redirect_to_permanent"
            className="flex-1 inline-flex gap-2 items-center"
          >
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
          </Form.Field>
        </div>
      )}

      <div className="flex justify-end items-center gap-2 border-t pt-4 px-4 -mx-4 border-border">
        <SubmitButton
          variant="secondary"
          isPending={false}
          className="inline-flex gap-1 flex-1 md:flex-none"
        >
          Add
          <PlusIcon size={15} />
        </SubmitButton>
        <Button variant="outline" type="reset" className="flex-1 md:flex-none">
          Cancel
        </Button>
      </div>
    </Form.Root>
  );
}

function NetworkAliasesGroup({ className }: ServiceFormProps) {
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
              nginx-demo-npUHRTJ7SvQ.zaneops.internal
            </span>
            <Button
              variant="ghost"
              className="px-2.5 py-0.5 md:opacity-0 focus-visible:opacity-100 group-hover:opacity-100"
            >
              <CopyIcon size={15} className="flex-none" />
              <span className="sr-only">Copy url</span>
            </Button>
          </div>
          <small className="text-grey">
            You can also simply use <Code>nginx-demo-npUHRTJ7SvQ</Code>
          </small>
        </div>
      </div>
    </div>
  );
}

function ServiceCommandForm({ className }: ServiceFormProps) {
  return (
    <Form.Root
      action={() => {}}
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
            <Input placeholder="ex: npm run start" />
          </Form.Control>
        </Form.Field>
      </fieldset>

      <SubmitButton isPending={false} variant="secondary">
        <>
          <CheckIcon size={15} className="flex-none" />
          <span>Update</span>
        </>
      </SubmitButton>
    </Form.Root>
  );
}

function ServiceHealthcheckForm({ className }: ServiceFormProps) {
  return (
    <Form.Root
      action={() => {}}
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
              <Select>
                <SelectTrigger>
                  <SelectValue placeholder="Select a type" />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="PATH">Path</SelectItem>
                  <SelectItem value="COMMAND">Command</SelectItem>
                </SelectContent>
              </Select>
            </Form.Control>
          </Form.Field>
          <Form.Field name="value" className="flex flex-col gap-1.5 flex-1">
            <Form.Label className="text-muted-foreground">Value</Form.Label>
            <Form.Control asChild>
              <Input placeholder="ex: redis-cli ping" />
            </Form.Control>
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
            <Input placeholder="ex: 30" />
          </Form.Control>
        </Form.Field>
        <Form.Field
          name="interval_seconds"
          className="flex flex-col gap-1.5 flex-1"
        >
          <Form.Label className="text-muted-foreground">
            Interval (in seconds)
          </Form.Label>
          <Form.Control asChild>
            <Input placeholder="ex: 30" />
          </Form.Control>
        </Form.Field>
      </fieldset>

      <div className="flex items-center gap-2">
        <SubmitButton isPending={false} variant="secondary">
          <>
            <CheckIcon size={15} className="flex-none" />
            <span>Update</span>
          </>
        </SubmitButton>
        <Button
          type="button"
          variant="outline"
          className="inline-flex gap-1 items-center"
        >
          <>
            <PaintRollerIcon size={15} className="flex-none" />
            <span>Remove healthcheck</span>
          </>
        </Button>
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
