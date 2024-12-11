import { useQuery } from "@tanstack/react-query";
import {
  CheckIcon,
  ChevronRightIcon,
  CopyIcon,
  EditIcon,
  EllipsisVerticalIcon,
  EyeIcon,
  EyeOffIcon,
  LoaderIcon,
  PlusIcon,
  Trash2Icon,
  Undo2Icon,
  XIcon
} from "lucide-react";
import * as React from "react";
import { Form, useFetcher } from "react-router";
import { toast } from "sonner";
import { apiClient } from "~/api/client";
import { Code } from "~/components/code";
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
import { serviceQueries } from "~/lib/queries";
import { cn, getFormErrorsFromResponseData } from "~/lib/utils";
import { queryClient } from "~/root";
import { getCsrfTokenHeader, pluralize, wait } from "~/utils";
import { type Route } from "./+types/services-env-variables";

type EnvVariableUI = {
  change_id?: string;
  id?: string | null;
  name: string;
  value: string;
  change_type?: "UPDATE" | "DELETE" | "ADD";
};

export default function ServiceEnvVariablesPage({
  params: { projectSlug: project_slug, serviceSlug: service_slug },
  matches: {
    "2": {
      data: { service: initialData }
    }
  }
}: Route.ComponentProps) {
  const { data: service } = useQuery({
    ...serviceQueries.single({ project_slug, service_slug }),
    initialData
  });

  const env_variables: Map<string, EnvVariableUI> = new Map();
  for (const env of service?.env_variables ?? []) {
    env_variables.set(env.key, {
      id: env.id,
      name: env.key,
      value: env.value
    });
  }
  for (const ch of service.unapplied_changes.filter(
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

  const system_env_variables = service.system_env_variables ?? [];

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
              <ChevronRightIcon className="h-4 w-4 shrink-0 transition-transform duration-200" />
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
        {/* {env_variables.size > 0 && (
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
    )} */}
        <h3 className="text-lg">Add new variable</h3>
        <NewEnvVariableForm />
      </section>
    </div>
  );
}

export async function clientAction({
  request,
  params
}: Route.ClientActionArgs) {
  const formData = await request.formData();
  const intent = formData.get("intent")?.toString();

  console.log({
    formData
  });
  switch (intent) {
    case "create-env-variable": {
      return createEnvVariable({
        project_slug: params.projectSlug,
        service_slug: params.serviceSlug,
        formData
      });
    }
    case "update-env-variable": {
      // return deployService(params.projectSlug, formData);
    }
    default: {
      throw new Error("Unexpected intent");
    }
  }
}

type EnVariableRowProps = EnvVariableUI & {
  isLocked?: boolean;
  comment?: string;
};

async function createEnvVariable({
  project_slug,
  service_slug,
  formData
}: {
  project_slug: string;
  service_slug: string;
  formData: FormData;
}) {
  const userData = {
    key: (formData.get("key") ?? "").toString(),
    value: (formData.get("value") ?? "").toString()
  };
  const { error: errors, data } = await apiClient.PUT(
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
        new_value: userData
      }
    }
  );
  if (errors) {
    return {
      errors,
      userData
    };
  }

  if (data) {
    await queryClient.invalidateQueries({
      ...serviceQueries.single({ project_slug, service_slug }),
      exact: true
    });
    return { data };
  }
}

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

  // const cancelEnvChangeMutation = useCancelDockerServiceChangeMutation(
  //   project_slug,
  //   service_slug
  // );

  // const {
  //   mutate: editEnvVariable,
  //   isPending: isUpdatingVariableValue,
  //   data: editVariableData,
  //   reset: resetEditionState
  // } = useRequestServiceChangeMutation({
  //   project_slug,
  //   service_slug,
  //   field: "env_variables"
  // });

  // const { mutateAsync: removeVariable } = useRequestServiceChangeMutation({
  //   project_slug,
  //   service_slug,
  //   field: "env_variables"
  // });

  const errors = getFormErrorsFromResponseData({});

  const idPrefix = React.useId();

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
        <Form
          className="col-span-3 md:col-span-5 flex md:items-start gap-3 md:flex-row flex-col pr-4"
          // action={(formData) => {
          //   editEnvVariable(
          //     {
          //       type: "UPDATE",
          //       new_value: {
          //         value: formData.get("value")?.toString() ?? "",
          //         key: name
          //       },
          //       item_id: id
          //     },
          //     {
          //       onSuccess(errors) {
          //         if (!errors) {
          //           setIsEditing(false);
          //         }
          //       }
          //     }
          //   );
          // }}
        >
          <fieldset className="flex-1 inline-flex flex-col gap-1">
            <label id={`${idPrefix}-value`} className="sr-only">
              variable value
            </label>
            <Input
              placeholder="value"
              defaultValue={value}
              name="value"
              className="font-mono"
              aria-labelledby={`${idPrefix}-value-error`}
            />
            {errors.new_value?.value && (
              <span
                id={`${idPrefix}-value-error`}
                className="text-red-500 text-sm"
              >
                {errors.new_value?.value}
              </span>
            )}
          </fieldset>

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
                  <CheckIcon size={15} className="flex-none" />
                  <span className="sr-only">Update variable value</span>
                </>
              )}
            </SubmitButton>
            <Button
              onClick={() => {
                setIsEditing(false);
                // resetEditionState();
              }}
              variant="outline"
              className="bg-inherit"
              type="button"
            >
              <XIcon size={15} className="flex-none" />
              <span className="sr-only">Cancel</span>
            </Button>
          </div>
        </Form>
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
                    <EyeIcon size={15} className="flex-none" />
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
                    <CheckIcon size={15} className="flex-none" />
                  ) : (
                    <CopyIcon size={15} className="flex-none" />
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
                  <EllipsisVerticalIcon size={15} />
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
                      icon={Undo2Icon}
                      text="Revert change"
                      className="text-red-400"
                      // onClick={() =>
                      //   toast.promise(
                      //     cancelEnvChangeMutation.mutateAsync(change_id),
                      //     {
                      //       loading: `Cancelling env variable change...`,
                      //       success: "Success",
                      //       error: "Error",
                      //       closeButton: true,
                      //       description(data) {
                      //         if (data instanceof Error) {
                      //           return data.message;
                      //         }
                      //         return "Done.";
                      //       }
                      //     }
                      //   )
                      // }
                    />
                  </>
                ) : (
                  id && (
                    <>
                      <MenubarContentItem
                        icon={EditIcon}
                        text="Edit"
                        onClick={() => setIsEditing(true)}
                      />
                      <MenubarContentItem
                        icon={Trash2Icon}
                        text="Remove"
                        className="text-red-400"
                        // onClick={() =>
                        //   toast.promise(
                        //     removeVariable({
                        //       type: "DELETE",
                        //       item_id: id
                        //     }),
                        //     {
                        //       loading: `Sending change request...`,
                        //       success: "Success",
                        //       error: "Error",
                        //       closeButton: true,
                        //       description(data) {
                        //         if (data instanceof Error) {
                        //           return data.message;
                        //         }
                        //         return "Done.";
                        //       }
                        //     }
                        //   )
                        // }
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
  const formRef = React.useRef<React.ComponentRef<"form">>(null);
  const fetcher = useFetcher<typeof clientAction>();

  const errors = getFormErrorsFromResponseData(fetcher.data?.errors);
  const isPending = fetcher.state !== "idle";

  React.useEffect(() => {
    // only focus on the correct input in case of error
    if (fetcher.state === "idle" && fetcher.data) {
      const nameInput = formRef.current?.[
        "variable-name"
      ] as HTMLInputElement | null;

      if (fetcher.data.errors) {
        const valueInput = formRef.current?.[
          "variable-value"
        ] as HTMLInputElement | null;

        if (errors.new_value?.key) {
          nameInput?.focus();
        }
        if (errors.new_value?.value) {
          valueInput?.focus();
        }

        return;
      }

      // refocus on the initial input so that the user can continue adding more variables
      nameInput?.focus();
      formRef.current?.reset();
    }
  }, [fetcher.state, fetcher.data, errors]);

  return (
    <fetcher.Form
      method="post"
      ref={formRef}
      className="flex md:items-start gap-3 md:flex-row flex-col items-stretch"
    >
      <fieldset name="key" className="flex-1 inline-flex flex-col gap-1">
        <label className="sr-only" htmlFor="variable-name">
          variable name
        </label>
        <Input
          autoFocus
          placeholder="VARIABLE_NAME"
          className="font-mono"
          id="variable-name"
          name="key"
          aria-labelledby="env-name-error"
          defaultValue={fetcher.formData?.get("key")?.toString()}
        />
        {errors.new_value?.key && (
          <span id="variable-name-error" className="text-red-500 text-sm">
            {errors.new_value?.key}
          </span>
        )}
      </fieldset>
      <fieldset name="value" className="flex-1 inline-flex flex-col gap-1">
        <label className="sr-only" htmlFor="variable-value">
          variable value
        </label>
        <Input
          placeholder="value"
          name="value"
          id="variable-value"
          aria-labelledby="variable-value-error"
          className="font-mono"
          defaultValue={fetcher.formData?.get("value")?.toString()}
        />
        {errors.new_value?.value && (
          <span id="variable-value-error" className="text-red-500 text-sm">
            {errors.new_value?.value}
          </span>
        )}
      </fieldset>

      <div className="flex gap-3 items-center w-full md:w-auto">
        <SubmitButton
          isPending={isPending}
          variant="secondary"
          name="intent"
          value="create-env-variable"
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
              <PlusIcon size={15} />
            </>
          )}
        </SubmitButton>
        <Button
          variant="outline"
          type="reset"
          className="flex-1"
          onClick={(e) => {
            const nameInput = e.currentTarget.form?.[
              "variable-name"
            ] as HTMLInputElement | null;
            nameInput?.focus();
          }}
        >
          Reset
        </Button>
      </div>
    </fetcher.Form>
  );
}
