import * as Form from "@radix-ui/react-form";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { createLazyFileRoute } from "@tanstack/react-router";
import {
  Ban,
  Check,
  ChevronRight,
  Copy,
  Edit,
  EllipsisVertical,
  Eye,
  EyeOffIcon,
  LoaderIcon,
  Plus,
  Trash2,
  Undo2,
  X
} from "lucide-react";
import * as React from "react";
import { toast } from "sonner";
import { apiClient } from "~/api/client";
import { Code } from "~/components/code";
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
import { useCancelDockerServiceChangeMutation } from "~/lib/hooks/use-cancel-docker-service-change-mutation";
import { useRequestServiceChangeMutation } from "~/lib/hooks/use-request-service-change-mutation";
import { serviceQueries } from "~/lib/queries";
import { cn, getFormErrorsFromResponseData } from "~/lib/utils";
import { getCsrfTokenHeader, pluralize, wait } from "~/utils";

export const Route = createLazyFileRoute(
  "/_dashboard/project/$project_slug/services/docker/$service_slug/env-variables"
)({
  component: withAuthRedirect(EnvVariablesPage)
});

type EnvVariableUI = {
  change_id?: string;
  id?: string | null;
  name: string;
  value: string;
  change_type?: "UPDATE" | "DELETE" | "ADD";
};

function EnvVariablesPage() {
  const { project_slug, service_slug } = Route.useParams();
  const serviceSingleQuery = useQuery(
    serviceQueries.single({ project_slug, service_slug })
  );

  if (serviceSingleQuery.isLoading) {
    return <Loader className="h-[50vh]" />;
  }

  const service = serviceSingleQuery.data;
  const env_variables: Map<string, EnvVariableUI> = new Map();
  for (const env of service?.env_variables ?? []) {
    env_variables.set(env.key, {
      id: env.id,
      name: env.key,
      value: env.value
    });
  }
  for (const ch of (service?.unapplied_changes ?? []).filter(
    (ch) => ch.field === "env_variables"
  )) {
    const keyValue = (ch.new_value ?? ch.old_value) as {
      key: string;
      value: string;
    };
    env_variables.set(keyValue.key, {
      change_id: ch.id,
      id: ch.item_id,
      name: keyValue.key,
      value: keyValue.value,
      change_type: ch.type
    });
  }

  const system_env_variables = service?.system_env_variables ?? [];

  return (
    <div className="my-6 flex flex-col gap-4">
      <section>
        <h2 className="text-lg">
          {env_variables.size > 0 ? (
            <span>
              {env_variables.size} User defined service&nbsp;
              {pluralize("variable", env_variables.size)}
            </span>
          ) : (
            <span>No user defined variables</span>
          )}
        </h2>
      </section>
      <section>
        <Accordion type="single" collapsible className="border-y border-border">
          <AccordionItem value="system">
            <AccordionTrigger className="text-muted-foreground font-normal text-sm hover:underline">
              <ChevronRight className="h-4 w-4 shrink-0 transition-transform duration-200" />
              {system_env_variables.length} System env&nbsp;
              {pluralize("variable", system_env_variables.length)}
            </AccordionTrigger>
            <AccordionContent className="flex flex-col gap-2">
              <p className="text-muted-foreground py-4 border-y border-border">
                ZaneOps provides additional system environment variables to all
                builds and deployments. variables marked with&nbsp;
                <Code>{`{{}}`}</Code> are specific to each deployment.
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
        {env_variables.size > 0 && (
          <>
            <ul className="flex flex-col gap-1">
              {[...env_variables.entries()].map(([, env]) => (
                <li key={env.name}>
                  <EnVariableRow
                    name={env.name}
                    value={env.value}
                    id={env.id}
                    change_id={env.change_id}
                    change_type={env.change_type}
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

type EnVariableRowProps = EnvVariableUI & {
  isLocked?: boolean;
  comment?: string;
};

function EnVariableRow({
  isLocked = false,
  name,
  value,
  comment,
  change_type,
  change_id,
  id
}: EnVariableRowProps) {
  const [isEnvValueShown, setIsEnvValueShown] = React.useState(false);
  const [isEditing, setIsEditing] = React.useState(false);
  const [hasCopied, startTransition] = React.useTransition();

  const { project_slug, service_slug } = Route.useParams();

  const cancelEnvChangeMutation = useCancelDockerServiceChangeMutation(
    project_slug,
    service_slug
  );

  const {
    mutate: editEnvVariable,
    isPending: isUpdatingVariableValue,
    data: editVariableData,
    reset: resetEditionState
  } = useRequestServiceChangeMutation({
    project_slug,
    service_slug,
    field: "env_variables"
  });

  const { mutateAsync: removeVariable } = useRequestServiceChangeMutation({
    project_slug,
    service_slug,
    field: "env_variables"
  });

  const errors = getFormErrorsFromResponseData(editVariableData);

  return (
    <div
      className={cn(
        "grid gap-4 items-center md:grid-cols-7 grid-cols-3 group pl-4 pt-2 md:py-1",
        {
          "items-start": isEditing,
          "dark:bg-secondary-foreground bg-secondary/60 rounded-md":
            change_type === "UPDATE",
          "dark:bg-primary-foreground bg-primary/60 rounded-md":
            change_type === "ADD",
          "dark:bg-red-500/30 bg-red-400/60 rounded-md":
            change_type === "DELETE"
        }
      )}
    >
      <div
        className={cn(
          "col-span-3 md:col-span-2 flex flex-col",
          isEditing && "md:relative md:top-3"
        )}
      >
        <span className="font-mono break-all">{name}</span>
        {comment && <small className="text-muted-foreground">{comment}</small>}
      </div>
      {isEditing && id ? (
        <Form.Root
          className="col-span-3 md:col-span-5 flex md:items-start gap-3 md:flex-row flex-col pr-4"
          action={(formData) => {
            editEnvVariable(
              {
                type: "UPDATE",
                new_value: {
                  value: formData.get("value")?.toString() ?? "",
                  key: name
                },
                item_id: id
              },
              {
                onSuccess(errors) {
                  if (!errors) {
                    setIsEditing(false);
                  }
                }
              }
            );
          }}
        >
          <Form.Field
            name="value"
            className="flex-1 inline-flex flex-col gap-1"
          >
            <Form.Label className="sr-only">variable value</Form.Label>
            <Form.Control asChild>
              <Input
                placeholder="value"
                defaultValue={value}
                name="value"
                className="font-mono"
              />
            </Form.Control>
            {errors.new_value?.value && (
              <Form.Message className="text-red-500 text-sm">
                {errors.new_value?.value}
              </Form.Message>
            )}
          </Form.Field>

          <div className="flex gap-3">
            <SubmitButton
              isPending={isUpdatingVariableValue}
              variant="outline"
              className="bg-inherit"
            >
              {isUpdatingVariableValue ? (
                <>
                  <LoaderIcon className="animate-spin" size={15} />
                  <span className="sr-only">Updating variable value...</span>
                </>
              ) : (
                <>
                  <Check size={15} className="flex-none" />
                  <span className="sr-only">Update variable value</span>
                </>
              )}
            </SubmitButton>
            <Button
              onClick={() => {
                setIsEditing(false);
                resetEditionState();
              }}
              variant="outline"
              className="bg-inherit"
              type="button"
            >
              <X size={15} className="flex-none" />
              <span className="sr-only">Cancel</span>
            </Button>
          </div>
        </Form.Root>
      ) : (
        <div className="col-span-2 font-mono flex items-center gap-2 md:col-span-4">
          {isEnvValueShown ? (
            <p className="whitespace-nowrap overflow-x-auto">
              {value.length > 0 ? (
                value
              ) : (
                <span className="text-grey font-mono">{`<empty>`}</span>
              )}
            </p>
          ) : (
            <span className="relative top-1">*********</span>
          )}
          <TooltipProvider>
            <Tooltip delayDuration={0}>
              <TooltipTrigger asChild>
                <Button
                  variant="ghost"
                  onClick={() => setIsEnvValueShown(!isEnvValueShown)}
                  className="px-2.5 py-0.5 md:opacity-0 focus-visible:opacity-100 group-hover:opacity-100"
                >
                  {isEnvValueShown ? (
                    <EyeOffIcon size={15} className="flex-none" />
                  ) : (
                    <Eye size={15} className="flex-none" />
                  )}
                  <span className="sr-only">
                    {isEnvValueShown ? "Hide" : "Reveal"} variable value
                  </span>
                </Button>
              </TooltipTrigger>
              <TooltipContent>
                {isEnvValueShown ? "Hide" : "Reveal"} variable value
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
                {change_id !== undefined ? (
                  <>
                    <MenubarContentItem
                      icon={Undo2}
                      text="Revert change"
                      className="text-red-400"
                      onClick={() =>
                        toast.promise(
                          cancelEnvChangeMutation.mutateAsync(change_id),
                          {
                            loading: `Cancelling env variable change...`,
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
                    />
                  </>
                ) : (
                  id && (
                    <>
                      <MenubarContentItem
                        icon={Edit}
                        text="Edit"
                        onClick={() => setIsEditing(true)}
                      />
                      <MenubarContentItem
                        icon={Trash2}
                        text="Remove"
                        className="text-red-400"
                        onClick={() =>
                          toast.promise(
                            removeVariable({
                              type: "DELETE",
                              item_id: id
                            }),
                            {
                              loading: `Sending change request...`,
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
                      />
                    </>
                  )
                )}
              </MenubarContent>
            </MenubarMenu>
          </Menubar>
        </div>
      )}
    </div>
  );
}

function NewEnvVariableForm() {
  const { project_slug, service_slug } = Route.useParams();
  const queryClient = useQueryClient();
  const formRef = React.useRef<React.ComponentRef<"form">>(null);

  const { mutate, isPending, data } = useMutation({
    mutationFn: async (input: {
      key: string;
      value: string;
    }) => {
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
            type: "ADD",
            field: "env_variables",
            new_value: input
          }
        }
      );
      if (error) {
        return error;
      }

      if (data) {
        formRef.current?.reset();
        await queryClient.invalidateQueries({
          ...serviceQueries.single({ project_slug, service_slug }),
          exact: true
        });
        return;
      }
    }
  });

  const errors = getFormErrorsFromResponseData(data);

  return (
    <Form.Root
      action={(formData) => {
        mutate({
          key: (formData.get("key") ?? "").toString(),
          value: (formData.get("value") ?? "").toString()
        });
      }}
      ref={formRef}
      className="flex md:items-start gap-3 md:flex-row flex-col items-stretch"
    >
      <Form.Field name="key" className="flex-1 inline-flex flex-col gap-1">
        <Form.Label className="sr-only">variable name</Form.Label>
        <Form.Control asChild>
          <Input placeholder="VARIABLE_NAME" className="font-mono" />
        </Form.Control>
        {errors.new_value?.key && (
          <Form.Message className="text-red-500 text-sm">
            {errors.new_value?.key}
          </Form.Message>
        )}
      </Form.Field>
      <Form.Field name="value" className="flex-1 inline-flex flex-col gap-1">
        <Form.Label className="sr-only">variable value</Form.Label>
        <Form.Control asChild>
          <Input placeholder="value" name="value" className="font-mono" />
        </Form.Control>
        {errors.new_value?.value && (
          <Form.Message className="text-red-500 text-sm">
            {errors.new_value?.value}
          </Form.Message>
        )}
      </Form.Field>

      <div className="flex gap-3 items-center w-full md:w-auto">
        <SubmitButton
          isPending={isPending}
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
        <Button variant="outline" type="reset" className="flex-1">
          Reset
        </Button>
      </div>
    </Form.Root>
  );
}
