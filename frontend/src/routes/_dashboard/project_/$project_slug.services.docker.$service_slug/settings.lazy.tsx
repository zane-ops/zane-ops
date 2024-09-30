import * as Form from "@radix-ui/react-form";
import { createLazyFileRoute } from "@tanstack/react-router";
import {
  Check,
  ContainerIcon,
  GitBranchIcon,
  InfoIcon,
  PencilLineIcon,
  XIcon
} from "lucide-react";
import * as React from "react";
import { withAuthRedirect } from "~/components/helper/auth-redirect";
import { Button, SubmitButton } from "~/components/ui/button";
import { Input } from "~/components/ui/input";
import { cn } from "~/lib/utils";

export const Route = createLazyFileRoute(
  "/_dashboard/project/$project_slug/services/docker/$service_slug/settings"
)({
  component: withAuthRedirect(SettingsPage)
});

function SettingsPage() {
  return (
    <div className="my-6 grid grid-cols-12 gap-10">
      <div className="col-span-10 flex flex-col">
        <section id="details" className="flex gap-1">
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

        <section id="source" className="flex gap-1">
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
        <section id="networking"></section>
        <section id="deploy"></section>
        <section id="volumes"></section>
        <section id="danger-zone"></section>
      </div>

      <aside className="col-span-2 sticky top-0 flex flex-col">
        <nav>
          <ul className="flex flex-col gap-2 text-grey">
            <li>
              <a href="#details">Details</a>
            </li>
            <li>
              <a href="#source">Source</a>
            </li>
            <li>
              <a href="#networking">Networking</a>
            </li>
            <li>
              <a href="#deploy">Deploy</a>
            </li>
            <li>
              <a href="#volumes">Volumes</a>
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

type ServiceSlugFormProps = {
  className?: string;
};

function ServiceSlugForm({ className }: ServiceSlugFormProps) {
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

type ServiceImageFormProps = {
  className?: string;
};

function ServiceImageForm({ className }: ServiceImageFormProps) {
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

function ServiceImageCredentialsForm({ className }: ServiceImageFormProps) {
  const [isEditing, setIsEditing] = React.useState(false);
  const [hasChanged, setHasChanged] = React.useState(false);
  return (
    <Form.Root
      action={() => {
        setHasChanged(true);
        setIsEditing(false);
      }}
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
          <Form.Control asChild>
            <Input
              placeholder="service slug"
              type="password"
              defaultValue="nginxdemos/hello"
            />
          </Form.Control>
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
