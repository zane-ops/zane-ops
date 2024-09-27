import { createLazyFileRoute } from "@tanstack/react-router";
import {
  Check,
  Copy,
  Edit,
  EllipsisVertical,
  Eye,
  EyeOffIcon,
  Plus,
  Trash2,
  X
} from "lucide-react";
import * as React from "react";
import { withAuthRedirect } from "~/components/helper/auth-redirect";
import {
  Accordion,
  AccordionContent,
  AccordionItem,
  AccordionTrigger
} from "~/components/ui/accordion";
import { Button, SubmitButton } from "~/components/ui/button";
import { Input } from "~/components/ui/input";
import {
  Menubar,
  MenubarContent,
  MenubarContentItem,
  MenubarMenu,
  MenubarTrigger
} from "~/components/ui/menubar";
import {
  Tooltip,
  TooltipContent,
  TooltipProvider,
  TooltipTrigger
} from "~/components/ui/tooltip";
import { cn } from "~/lib/utils";
import { wait } from "~/utils";

export const Route = createLazyFileRoute(
  "/_dashboard/project/$project_slug/services/docker/$service_slug/env-variables"
)({
  component: withAuthRedirect(EnvVariablesPage)
});

function EnvVariablesPage() {
  return (
    <div className="my-6 flex flex-col gap-4">
      <section>
        <h1 className="text-lg">4 User defined service variables</h1>
      </section>
      <section>
        <Accordion type="single" collapsible className="border-y border-border">
          <AccordionItem value="system">
            <AccordionTrigger className="text-muted-foreground font-normal text-sm">
              5 System env variables
            </AccordionTrigger>
            <AccordionContent className="flex flex-col gap-2">
              <p className="text-muted-foreground py-4 border-y border-border">
                ZaneOps provides additional system environment variables to all
                builds and deployments.
              </p>
              <div className="flex flex-col gap-2">
                <EnVariableRow
                  name="ZANE"
                  value="1"
                  isLocked
                  description="Is the service deployed on zaneops?"
                />
                <EnVariableRow
                  name="ZANE_PRIVATE_DOMAIN"
                  value="nginx-demo.zaneops.internal"
                  description="The domain used to reach this service on the same project"
                  isLocked
                />
                <EnVariableRow
                  name="ZANE_DEPLOYMENT_TYPE"
                  value="docker"
                  description="The type of the service"
                  isLocked
                />
                <EnVariableRow
                  name="ZANE_SERVICE_ID"
                  value="abc123"
                  isLocked
                  description="The service ID"
                />
                <EnVariableRow
                  name="ZANE_PROJECT_ID"
                  value="def123"
                  isLocked
                  description="The project ID"
                />
              </div>
            </AccordionContent>
          </AccordionItem>
        </Accordion>
      </section>
      <section className="flex flex-col gap-4">
        <div>
          <EnVariableRow name="POSTGRES_USER" value="postgres" />
          <EnVariableRow name="POSTGRES_DB" value="postgres" />
          <EnVariableRow
            name="POSTGRES_PASSWORD"
            value="password"
            description="database url"
          />
          <EnVariableRow
            name="DATABASE_URL"
            value="postgresql://postgres:password@localhost:5433/gh_next"
            isNotValidated
          />
        </div>
        <NewEnvVariableForm />
      </section>
    </div>
  );
}

type EnVariableRowProps = {
  isLocked?: boolean;
  name: string;
  value: string;
  description?: string;
  isNotValidated?: boolean;
};

function EnVariableRow({
  isLocked = false,
  name,
  value,
  description,
  isNotValidated = false
}: EnVariableRowProps) {
  const [isOpen, setIsOpen] = React.useState(false);
  const [isEditing, setIsEditing] = React.useState(false);
  const [hasCopied, startTransition] = React.useTransition();

  return (
    <div
      className={cn(
        "grid items-center gap-4 grid-cols-7 group pl-4 py-2",
        isNotValidated &&
          "dark:bg-secondary-foreground bg-secondary/60 rounded-md"
      )}
    >
      <div className="col-span-2 flex flex-col">
        <span className="font-mono">{name}</span>
        {description && (
          <small className="text-muted-foreground">{description}</small>
        )}
      </div>
      {isEditing ? (
        <form className="col-span-5 flex items-center gap-3" action={() => {}}>
          <Input
            placeholder="value"
            defaultValue={value}
            name="value"
            className="font-mono"
          />
          <SubmitButton
            isPending={false}
            variant="ghost"
            className="bg-inherit"
          >
            <Check size={15} className="flex-none" />
            <span className="sr-only">Update variable value</span>
          </SubmitButton>
          <Button
            onClick={() => setIsEditing(false)}
            variant="ghost"
            className="bg-inherit"
          >
            <X size={15} className="flex-none" />
            <span className="sr-only">Cancel</span>
          </Button>
        </form>
      ) : (
        <div className="font-mono flex items-center gap-2 col-span-4">
          {isOpen ? (
            <p className="whitespace-nowrap overflow-x-auto">{value}</p>
          ) : (
            <span className="relative top-1">*********</span>
          )}
          <TooltipProvider>
            <Tooltip delayDuration={0}>
              <TooltipTrigger asChild>
                <Button
                  variant="ghost"
                  onClick={() => setIsOpen(!isOpen)}
                  className="px-2.5 py-0.5 opacity-0 focus-visible:opacity-100 group-hover:opacity-100"
                >
                  {isOpen ? (
                    <EyeOffIcon size={15} className="flex-none" />
                  ) : (
                    <Eye size={15} className="flex-none" />
                  )}
                  <span className="sr-only">
                    {isOpen ? "Hide" : "Reveal"} variable value
                  </span>
                </Button>
              </TooltipTrigger>
              <TooltipContent>
                {isOpen ? "Hide" : "Reveal"} variable value
              </TooltipContent>
            </Tooltip>

            <Tooltip delayDuration={0}>
              <TooltipTrigger asChild>
                <Button
                  variant="ghost"
                  className={cn(
                    "px-2.5 py-0.5",
                    "focus-visible:opacity-100 group-hover:opacity-100",
                    hasCopied ? "opacity-100" : "opacity-0"
                  )}
                  onClick={() => {
                    navigator.clipboard.writeText(value).then(() => {
                      // show pending state (which is success state), until the user has stopped clicking the button
                      startTransition(() => wait(1000));
                    });
                  }}
                >
                  {hasCopied ? (
                    <Check size={15} className="flex-none" />
                  ) : (
                    <Copy size={15} className="flex-none" />
                  )}
                  <span className="sr-only">Copy variable value</span>
                </Button>
              </TooltipTrigger>
              <TooltipContent>Copy variable value</TooltipContent>
            </Tooltip>
          </TooltipProvider>
        </div>
      )}

      {!isLocked && !isEditing && (
        <div className="flex justify-end">
          <Menubar className="border-none h-auto w-fit">
            <MenubarMenu>
              <MenubarTrigger
                className="flex justify-center items-center gap-2"
                asChild
              >
                <Button
                  variant="ghost"
                  className="px-2.5 py-0.5 hover:bg-inherit"
                >
                  <EllipsisVertical size={15} />
                </Button>
              </MenubarTrigger>
              <MenubarContent
                side="bottom"
                align="start"
                className="border min-w-0 mx-9 border-border"
              >
                <MenubarContentItem
                  icon={Edit}
                  text="Edit"
                  onClick={() => setIsEditing(true)}
                />
                <MenubarContentItem
                  icon={Trash2}
                  text="Remove"
                  className="text-red-400"
                  onClick={() => {}}
                />
              </MenubarContent>
            </MenubarMenu>
          </Menubar>
        </div>
      )}
    </div>
  );
}

function NewEnvVariableForm() {
  return (
    <form action={() => {}} className="flex items-center gap-3">
      <Input placeholder="VARIABLE_NAME" name="name" className="font-mono" />
      <Input placeholder="value" name="value" className="font-mono" />
      <SubmitButton
        isPending={false}
        variant="secondary"
        className="inline-flex gap-1"
      >
        <span>Add</span>
        <Plus size={15} />
      </SubmitButton>
      <Button variant="outline" type="reset">
        Cancel
      </Button>
    </form>
  );
}
