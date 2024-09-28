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
import { Loader } from "~/components/loader";
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
import { useDockerServiceSingleQuery } from "~/lib/hooks/use-docker-service-single-query";
import { cn } from "~/lib/utils";
import { pluralize, wait } from "~/utils";

export const Route = createLazyFileRoute(
  "/_dashboard/project/$project_slug/services/docker/$service_slug/env-variables"
)({
  component: withAuthRedirect(EnvVariablesPage)
});

function EnvVariablesPage() {
  const { project_slug, service_slug } = Route.useParams();
  const serviceSingleQuery = useDockerServiceSingleQuery(
    project_slug,
    service_slug
  );

  if (serviceSingleQuery.isLoading) {
    return <Loader className="h-[50vh]" />;
  }

  const env_variables = serviceSingleQuery.data?.data?.env_variables ?? [];
  const system_env_variables =
    serviceSingleQuery.data?.data?.system_env_variables ?? [];

  return (
    <div className="my-6 flex flex-col gap-4">
      <section>
        <h2 className="text-lg">
          {env_variables.length > 0 ? (
            <span>
              {env_variables.length} User defined service&nbsp;
              {pluralize("variable", env_variables.length)}
            </span>
          ) : (
            <span>No user defined variables</span>
          )}
        </h2>
      </section>
      <section>
        <Accordion type="single" collapsible className="border-y border-border">
          <AccordionItem value="system">
            <AccordionTrigger className="text-muted-foreground font-normal text-sm">
              {system_env_variables.length} System env&nbsp;
              {pluralize("variable", system_env_variables.length)}
            </AccordionTrigger>
            <AccordionContent className="flex flex-col gap-2">
              <p className="text-muted-foreground py-4 border-y border-border">
                ZaneOps provides additional system environment variables to all
                builds and deployments. variables marked with&nbsp;
                <code>&#123;&#123;&#125;&#125;</code> are specific to each
                deployment.
              </p>
              <div className="flex flex-col gap-2">
                {system_env_variables.map((env) => (
                  <EnVariableRow
                    name={env.key}
                    key={env.key}
                    value={env.value}
                    isLocked
                    comment={env.comment}
                  />
                ))}
              </div>
            </AccordionContent>
          </AccordionItem>
        </Accordion>
      </section>
      <section className="flex flex-col gap-4">
        {env_variables.length > 0 && (
          <>
            <ul>
              {env_variables.map((env) => (
                <li>
                  <EnVariableRow
                    name={env.key}
                    value={env.value}
                    key={env.id}
                  />
                </li>
              ))}
            </ul>
            <hr className="border-border" />
          </>
        )}
        <h3 className="text-lg">Add new variable</h3>
        <NewEnvVariableForm />
      </section>
    </div>
  );
}

type EnVariableRowProps = {
  isLocked?: boolean;
  name: string;
  value: string;
  comment?: string;
  isNotValidated?: boolean;
};

function EnVariableRow({
  isLocked = false,
  name,
  value,
  comment,
  isNotValidated = false
}: EnVariableRowProps) {
  const [isOpen, setIsOpen] = React.useState(false);
  const [isEditing, setIsEditing] = React.useState(false);
  const [hasCopied, startTransition] = React.useTransition();

  return (
    <div
      className={cn(
        "grid items-center gap-4 md:grid-cols-7 grid-cols-3 group pl-4 py-2",
        isNotValidated &&
          "dark:bg-secondary-foreground bg-secondary/60 rounded-md"
      )}
    >
      <div className="col-span-3 md:col-span-2 flex flex-col">
        <span className="font-mono">{name}</span>
        {comment && <small className="text-muted-foreground">{comment}</small>}
      </div>
      {isEditing ? (
        <form
          className="col-span-3 md:col-span-5 flex md:items-center gap-3 md:flex-row flex-col pr-4"
          action={() => {}}
        >
          <Input
            placeholder="value"
            defaultValue={value}
            name="value"
            className="font-mono"
          />
          <div className="flex gap-3">
            <SubmitButton
              isPending={false}
              variant="outline"
              className="bg-inherit"
            >
              <Check size={15} className="flex-none" />
              <span className="sr-only">Update variable value</span>
            </SubmitButton>
            <Button
              onClick={() => setIsEditing(false)}
              variant="outline"
              className="bg-inherit"
            >
              <X size={15} className="flex-none" />
              <span className="sr-only">Cancel</span>
            </Button>
          </div>
        </form>
      ) : (
        <div className="col-span-2 font-mono flex items-center gap-2 md:col-span-4">
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
                  className="px-2.5 py-0.5 md:opacity-0 focus-visible:opacity-100 group-hover:opacity-100"
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
                    hasCopied ? "opacity-100" : "md:opacity-0"
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
    <form
      action={() => {}}
      className="flex md:items-center gap-3 md:flex-row flex-col items-stretch"
    >
      <Input placeholder="VARIABLE_NAME" name="name" className="font-mono" />
      <Input placeholder="value" name="value" className="font-mono" />
      <div className="flex gap-3 items-center w-full md:w-auto">
        <SubmitButton
          isPending={false}
          variant="secondary"
          className="inline-flex gap-1 flex-1"
        >
          <span>Add</span>
          <Plus size={15} />
        </SubmitButton>
        <Button variant="outline" type="reset" className="flex-1">
          Cancel
        </Button>
      </div>
    </form>
  );
}
