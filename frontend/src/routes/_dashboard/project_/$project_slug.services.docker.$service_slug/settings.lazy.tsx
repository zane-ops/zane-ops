import * as Form from "@radix-ui/react-form";
import { Link, createLazyFileRoute } from "@tanstack/react-router";
import {
  CableIcon,
  Check,
  ContainerIcon,
  Eye,
  EyeOffIcon,
  HammerIcon,
  HardDrive,
  InfoIcon,
  PencilLineIcon,
  Trash2,
  Trash2Icon,
  TriangleAlertIcon,
  XIcon
} from "lucide-react";
import * as React from "react";
import { withAuthRedirect } from "~/components/helper/auth-redirect";
import { Button, SubmitButton } from "~/components/ui/button";
import { Input } from "~/components/ui/input";
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

          <div className="w-full flex flex-col gap-5 pt-1 pb-4">
            <h2 className="text-lg text-grey">Details</h2>
            <ServiceSlugForm className="w-full max-w-2xl" />
          </div>
        </section>

        <section id="source" className="flex gap-1 scroll-mt-20">
          <div className="w-16 flex flex-col items-center">
            <div className="flex rounded-full size-10 flex-none items-center justify-center p-1 border-2 border-grey/50">
              <ContainerIcon size={15} className="flex-none text-grey" />
            </div>
            <div className="h-full border border-grey/50"></div>
          </div>

          <div className="w-full flex flex-col gap-5 pt-1 pb-4">
            <h2 className="text-lg text-grey">Source</h2>
            <ServiceImageForm className="w-full max-w-2xl" />
            <ServiceImageCredentialsForm className="w-full max-w-2xl" />
          </div>
        </section>

        <section id="networking" className="flex gap-1 scroll-mt-22">
          <div className="w-16 flex flex-col items-center">
            <div className="flex rounded-full size-10 flex-none items-center justify-center p-1 border-2 border-grey/50">
              <CableIcon size={15} className="flex-none text-grey" />
            </div>
            <div className="h-full border border-grey/50"></div>
          </div>
          <div className="w-full flex flex-col gap-5 pt-1 pb-4">
            <h2 className="text-lg text-grey">Networking</h2>
          </div>
        </section>

        <section id="deploy" className="flex gap-1 scroll-mt-22">
          <div className="w-16 flex flex-col items-center">
            <div className="flex rounded-full size-10 flex-none items-center justify-center p-1 border-2 border-grey/50">
              <HammerIcon size={15} className="flex-none text-grey" />
            </div>
            <div className="h-full border border-grey/50"></div>
          </div>
          <div className="w-full flex flex-col gap-5 pt-1 pb-4">
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
          <div className="w-full flex flex-col gap-5 pt-1 pb-4">
            <h2 className="text-lg text-grey">Volumes</h2>
          </div>
        </section>

        <section id="danger-zone" className="flex gap-1 scroll-mt-22">
          <div className="w-16 flex flex-col items-center">
            <div className="flex rounded-full size-10 flex-none items-center justify-center p-1 border-2 border-red-500">
              <TriangleAlertIcon size={15} className="flex-none text-red-500" />
            </div>
            <div className="h-full border border-red-500"></div>
          </div>
          <div className="w-full flex flex-col gap-5 pt-1 pb-4">
            <h2 className="text-lg text-red-400">Danger Zone</h2>
            <ServiceDangerZoneForm className="w-full max-w-2xl" />
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
              hasChanged
                ? "dark:bg-secondary-foreground bg-secondary/60"
                : "bg-muted"
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

function ServiceDangerZoneForm({ className }: ServiceFormProps) {
  return (
    <form
      action={() => {}}
      className={cn("flex flex-col gap-2 items-start", className)}
    >
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
    </form>
  );
}
