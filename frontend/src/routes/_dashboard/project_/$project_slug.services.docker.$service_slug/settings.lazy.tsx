import * as Form from "@radix-ui/react-form";
import { Link, createLazyFileRoute } from "@tanstack/react-router";
import {
  ArrowRight,
  ArrowRightIcon,
  CableIcon,
  Check,
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
  PencilLineIcon,
  Plus,
  Trash2,
  Trash2Icon,
  TriangleAlertIcon,
  Undo2Icon,
  XIcon
} from "lucide-react";
import * as React from "react";
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
import { Switch } from "~/components/ui/switch";
import {
  Tooltip,
  TooltipContent,
  TooltipProvider,
  TooltipTrigger
} from "~/components/ui/tooltip";
import { cn } from "~/lib/utils";

export const Route = createLazyFileRoute(
  "/_dashboard/project/$project_slug/services/docker/$service_slug/settings"
)({
  component: withAuthRedirect(SettingsPage)
});

function SettingsPage() {
  return (
    <div className="my-6 grid grid-cols-12 gap-10 relative">
      <div className="col-span-10 flex flex-col">
        <section id="details" className="flex gap-1 scroll-mt-20">
          <div className="w-16 flex flex-col items-center">
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
          <div className="w-16 flex flex-col items-center">
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

        <section id="networking" className="flex gap-1 scroll-mt-22">
          <div className="w-16 flex flex-col items-center">
            <div className="flex rounded-full size-10 flex-none items-center justify-center p-1 border-2 border-grey/50">
              <CableIcon size={15} className="flex-none text-grey" />
            </div>
            <div className="h-full border border-grey/50"></div>
          </div>
          <div className="w-full flex flex-col gap-8 pt-1 pb-14">
            <h2 className="text-lg text-grey">Networking</h2>
            <ServicePortsForm className="w-full max-w-4xl" />
            <hr className="w-full max-w-4xl border-border" />
            <ServiceURLsForm className="w-full max-w-4xl" />
            <hr className="w-full max-w-4xl border-border" />
            <NetworkAliasesGroup className="w-full max-w-4xl border-border" />
          </div>
        </section>

        <section id="deploy" className="flex gap-1 scroll-mt-22">
          <div className="w-16 flex flex-col items-center">
            <div className="flex rounded-full size-10 flex-none items-center justify-center p-1 border-2 border-grey/50">
              <HammerIcon size={15} className="flex-none text-grey" />
            </div>
            <div className="h-full border border-grey/50"></div>
          </div>
          <div className="w-full flex flex-col gap-5 pt-1 pb-14">
            <h2 className="text-lg text-grey">Deploy</h2>
          </div>
        </section>

        <section id="volumes" className="flex gap-1 scroll-mt-22">
          <div className="w-16 flex flex-col items-center">
            <div className="flex rounded-full size-10 flex-none items-center justify-center p-1 border-2 border-grey/50">
              <HardDrive size={15} className="flex-none text-grey" />
            </div>
            <div className="h-full border border-grey/50"></div>
          </div>
          <div className="w-full flex flex-col gap-5 pt-1 pb-14">
            <h2 className="text-lg text-grey">Volumes</h2>
          </div>
        </section>

        <section id="danger-zone" className="flex gap-1 scroll-mt-22">
          <div className="w-16 flex flex-col items-center">
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

      <aside className="col-span-2 flex flex-col h-full">
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
  const [isEditing, setIsEditing] = React.useState(false);
  return (
    <div className={className}>
      {isEditing ? (
        <Form.Root
          action={() => {
            setIsEditing(false);
          }}
          className="flex gap-2 w-full items-end"
        >
          <Form.Field name="slug" className="flex flex-col gap-1.5 flex-1">
            <Form.Label>Service slug</Form.Label>
            <Form.Control asChild>
              <Input placeholder="service slug" defaultValue="nginx-demo" />
            </Form.Control>
          </Form.Field>

          <SubmitButton
            isPending={false}
            variant="outline"
            className="bg-inherit"
          >
            {/* {isUpdatingVariableValue ? (
               <>
                 <LoaderIcon className="animate-spin" size={15} />
                 <span className="sr-only">Updating variable value...</span>
               </>
             ) : ( */}
            <>
              <Check size={15} className="flex-none" />
              <span className="sr-only">Update variable value</span>
            </>
            {/* )} */}
          </SubmitButton>
          <Button
            onClick={() => {
              setIsEditing(false);
            }}
            variant="outline"
            className="bg-inherit"
            type="button"
          >
            <XIcon size={15} className="flex-none" />
            <span className="sr-only">Cancel</span>
          </Button>
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
            <span>nginx-demo</span>
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
  const [isEditing, setIsEditing] = React.useState(false);
  const [hasChanged, setHasChanged] = React.useState(false);
  return (
    <div className={className}>
      {isEditing ? (
        <Form.Root
          action={() => {
            setHasChanged(true);
            setIsEditing(false);
          }}
          className="flex gap-2 w-full items-end"
        >
          <Form.Field name="image" className="flex flex-col gap-1.5 flex-1">
            <Form.Label className="text-lg">Source image</Form.Label>
            <Form.Control asChild>
              <Input
                placeholder="service slug"
                defaultValue="nginxdemos/hello"
              />
            </Form.Control>
          </Form.Field>

          <SubmitButton
            isPending={false}
            variant="outline"
            className="bg-inherit"
          >
            {/* {isUpdatingVariableValue ? (
               <>
                 <LoaderIcon className="animate-spin" size={15} />
                 <span className="sr-only">Updating variable value...</span>
               </>
             ) : ( */}
            <>
              <Check size={15} className="flex-none" />
              <span className="sr-only">Update variable value</span>
            </>
            {/* )} */}
          </SubmitButton>
          <Button
            onClick={() => {
              setIsEditing(false);
            }}
            variant="outline"
            className="bg-inherit"
            type="button"
          >
            <XIcon size={15} className="flex-none" />
            <span className="sr-only">Cancel</span>
          </Button>
        </Form.Root>
      ) : (
        <div className="flex flex-col gap-1.5">
          <h3 className="text-lg">Source image</h3>
          <div
            className={cn(
              "w-full rounded-md flex justify-between items-center gap-2 py-1 pl-4 pr-2",
              hasChanged
                ? "dark:bg-secondary-foreground bg-secondary/60"
                : "bg-muted"
            )}
          >
            <span>
              nginxdemos/hello<span className="text-grey">:latest</span>
            </span>
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
          <Check size={15} className="flex-none" />
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
      <ul className="flex flex-col gap-1">
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
                <Form.Label className="text-gray-400">domain</Form.Label>
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
                <Form.Label className="text-gray-400">base path</Form.Label>
                <Form.Control asChild>
                  <Input placeholder="ex: /" defaultValue={base_path ?? "/"} />
                </Form.Control>
              </Form.Field>

              <Form.Field
                name="strip_prefix"
                className="flex-1 inline-flex gap-2 items-center"
              >
                <Form.Control asChild>
                  <Checkbox defaultChecked={strip_prefix} />
                </Form.Control>

                <Form.Label className="text-gray-400 inline-flex gap-1 items-center">
                  strip path prefix ?
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
                  is redirect ?
                </Form.Label>
              </Form.Field>

              {isRedirect && (
                <div className="flex flex-col gap-4 pl-4">
                  <Form.Field
                    name="redirect_to_url"
                    className="flex-1 inline-flex flex-col gap-1"
                  >
                    <Form.Label className="text-gray-400">
                      redirect to url
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
                      permenant redirect
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

function NewServiceURLForm({ className }: ServiceFormProps) {
  return <></>;
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
      <div className="border border-border p-4 rounded-md flex items-center gap-4 group">
        <GlobeLockIcon className="text-grey" size={20} />
        <div className="flex flex-col gap-0.5">
          <div className="flex gap-2 items-center">
            <span className="text-lg">
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

function ServiceDangerZoneForm({ className }: ServiceFormProps) {
  return (
    <div className={cn("flex flex-col gap-2 items-start", className)}>
      <p className="text-red-400 ">
        Archive this service will permanently delete all its deployments and
        remove it, This cannot be undone.
      </p>

      <Button
        variant="destructive"
        className="bg-red-500 inline-flex gap-1 items-center"
      >
        <Trash2Icon size={15} className="flex-none" />
        <span>Archive service</span>
      </Button>
    </div>
  );
}
