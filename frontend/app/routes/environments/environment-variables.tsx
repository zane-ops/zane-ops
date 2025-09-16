import { useQuery } from "@tanstack/react-query";
import {
  AlertCircleIcon,
  CheckIcon,
  EditIcon,
  EllipsisVerticalIcon,
  EyeIcon,
  EyeOffIcon,
  LoaderIcon,
  Trash2Icon,
  XIcon
} from "lucide-react";
import * as React from "react";
import { useFetcher } from "react-router";
import { toast } from "sonner";
import { apiClient } from "~/api/client";
import { Code } from "~/components/code";
import { CopyButton } from "~/components/copy-button";
import { Alert, AlertDescription, AlertTitle } from "~/components/ui/alert";
import { Button } from "~/components/ui/button";
import { SubmitButton } from "~/components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle
} from "~/components/ui/dialog";
import { Input } from "~/components/ui/input";
import {
  Menubar,
  MenubarContent,
  MenubarMenu,
  MenubarTrigger
} from "~/components/ui/menubar";
import { MenubarContentItem } from "~/components/ui/menubar";
import { Separator } from "~/components/ui/separator";
import {
  Tooltip,
  TooltipContent,
  TooltipProvider,
  TooltipTrigger
} from "~/components/ui/tooltip";
import { environmentQueries } from "~/lib/queries";
import {
  type ErrorResponseFromAPI,
  cn,
  getFormErrorsFromResponseData
} from "~/lib/utils";
import { queryClient } from "~/root";
import { getCsrfTokenHeader, pluralize } from "~/utils";
import type { Route } from "./+types/environment-variables";

export default function EnvironmentVariablesPage({
  matches: {
    "2": { loaderData: matchData }
  },
  params
}: Route.ComponentProps) {
  const { data: environment } = useQuery({
    ...environmentQueries.single(params.projectSlug, params.envSlug),
    initialData: matchData.environment
  });
  const { variables: env_variables } = environment;
  return (
    <section className="py-8 flex flex-col gap-4">
      <h2 className="text-lg inline-flex gap-2 items-center">
        {env_variables.length > 0 ? (
          <>
            <span>
              {env_variables.length} shared&nbsp;
              {pluralize("variable", env_variables.length)}
              &nbsp;in <span className="text-grey">`</span>
              <strong className="font-medium">{environment.name}</strong>
              <span className="text-grey">`</span> environment
            </span>
            <CopyButton
              variant="outline"
              size="sm"
              showLabel
              label={(hasCopied) => (hasCopied ? "Copied" : "Copy as .env")}
              value={env_variables
                .map((env) => `${env.key}="${env.value}"`)
                .join("\n")}
            />
          </>
        ) : (
          <span>
            No shared variables in <span className="text-grey">`</span>
            <strong className="font-medium">{environment.name}</strong>
            <span className="text-grey">`</span> environment
          </span>
        )}
      </h2>

      <Separator />

      <p className="text-muted-foreground border-border">
        Shared variables are inherited by all the services in this environment.
        If a service has the same variable, that will take precedence over the
        variable defined in this environment. You can reference these variables
        in services with <Code>{"{{env.VARIABLE_NAME}}"}</Code>.
      </p>

      <Separator />

      <div className="flex flex-col gap-2">
        {environment.variables.map((variable) => (
          <EnVariableRow
            key={variable.id}
            name={variable.key}
            value={variable.value}
            id={variable.id}
            env_slug={environment.name}
          />
        ))}
        <EditVariableForm env_slug={environment.name} editType="add" />
      </div>
    </section>
  );
}

type EnvVariableRowProps = {
  id: string;
  name: string;
  value: string;
  env_slug: string;
};

function EnVariableRow({ name, value, id, env_slug }: EnvVariableRowProps) {
  const [isEnvValueShown, setIsEnvValueShown] = React.useState(false);
  const [isEditing, setIsEditing] = React.useState(false);
  const [isOpen, setIsOpen] = React.useState(false);

  return (
    <div
      className={cn(
        "grid gap-4 items-center md:grid-cols-7 grid-cols-3 group pt-2 md:py-1",
        isEditing && "items-start"
      )}
    >
      {isEditing ? (
        <EditVariableForm
          name={name}
          value={value}
          id={id}
          env_slug={env_slug}
          quitEditMode={() => setIsEditing(false)}
        />
      ) : (
        <>
          <div className={cn("col-span-3 md:col-span-2 flex flex-col")}>
            <span className="font-mono break-all">{name}</span>
          </div>

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
                  <CopyButton
                    variant="ghost"
                    value={value}
                    label="Copy variable value"
                  />
                </TooltipTrigger>
                <TooltipContent>Copy variable value</TooltipContent>
              </Tooltip>
            </TooltipProvider>
          </div>
        </>
      )}

      {!isEditing && (
        <div className="flex justify-end">
          <DeleteVariableConfirmationDialog
            env_slug={env_slug}
            id={id}
            name={name}
            isOpen={isOpen}
            onOpenChange={setIsOpen}
          />
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
                <MenubarContentItem
                  icon={EditIcon}
                  text="Edit"
                  onClick={() => setIsEditing(true)}
                />
                <MenubarContentItem
                  icon={Trash2Icon}
                  text="Delete"
                  className="text-red-400"
                  onClick={() => setIsOpen(true)}
                />
              </MenubarContent>
            </MenubarMenu>
          </Menubar>
        </div>
      )}
    </div>
  );
}

type DeleteVariableConfirmationDialogProps = {
  id: string;
  env_slug: string;
  name: string;
  isOpen: boolean;
  onOpenChange: (isOpen: boolean) => void;
};

function DeleteVariableConfirmationDialog({
  id,
  env_slug,
  name,
  isOpen,
  onOpenChange
}: DeleteVariableConfirmationDialogProps) {
  const fetcher = useFetcher<typeof clientAction>();
  const isPending = fetcher.state !== "idle";

  const errors = getFormErrorsFromResponseData(fetcher.data?.errors);

  React.useEffect(() => {
    if (fetcher.state === "idle" && fetcher.data && !fetcher.data.errors) {
      onOpenChange(false);
    }
  }, [fetcher.state, fetcher.data]);

  return (
    <Dialog
      open={isOpen}
      onOpenChange={(open) => {
        onOpenChange(open);
      }}
    >
      <DialogContent className="gap-0">
        <DialogHeader className="">
          <DialogTitle>Delete this shared variable ?</DialogTitle>

          <DialogDescription className="my-4 text-card-foreground text-base leading-6.5">
            Are you sure you want to delete <Code>`{name}`</Code> ? This will
            remove it from all the services in the&nbsp;
            <Code>{env_slug}</Code> environment.
          </DialogDescription>
        </DialogHeader>

        {errors.non_field_errors && (
          <Alert variant="destructive">
            <AlertCircleIcon className="h-4 w-4" />
            <AlertTitle>Error</AlertTitle>
            <AlertDescription>{errors.non_field_errors}</AlertDescription>
          </Alert>
        )}

        <DialogFooter className="-mx-6 px-6 pt-4">
          <fetcher.Form
            method="post"
            action="../variables"
            className="flex items-center gap-4 w-full"
          >
            <input type="hidden" name="variable_id" value={id} />
            <input type="hidden" name="env_slug" value={env_slug} />
            <SubmitButton
              variant="destructive"
              className={cn(
                "inline-flex gap-1 items-center",
                isPending ? "bg-red-400" : "bg-red-500"
              )}
              value="delete-env-variable"
              name="intent"
              isPending={isPending}
            >
              {isPending ? (
                <>
                  <LoaderIcon className="animate-spin flex-none" size={15} />
                  <span>Deleting...</span>
                </>
              ) : (
                <>
                  <span>Delete</span>
                </>
              )}
            </SubmitButton>

            <Button
              type="button"
              variant="outline"
              onClick={() => {
                onOpenChange(false);
              }}
            >
              Cancel
            </Button>
          </fetcher.Form>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}

type EditVariableFormProps = {
  name?: string;
  value?: string;
  id?: string | null;
  env_slug: string;
  editType?: "add" | "update";
  quitEditMode?: () => void;
};

function EditVariableForm({
  name,
  value,
  id,
  env_slug,
  editType = "update",
  quitEditMode
}: EditVariableFormProps) {
  const fetcher = useFetcher<typeof clientAction>();
  const idPrefix = React.useId();
  const isPending = fetcher.state !== "idle";
  const errors = getFormErrorsFromResponseData(fetcher.data?.errors);
  const formRef = React.useRef<React.ComponentRef<"form">>(null);

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

        if (errors.key) {
          nameInput?.focus();
        }
        if (errors.value) {
          valueInput?.focus();
        }

        return;
      }

      formRef.current?.reset();
      nameInput?.focus();
      quitEditMode?.();
    }
  }, [fetcher.state, fetcher.data, errors]);

  return (
    <fetcher.Form
      method="post"
      action="../variables"
      ref={formRef}
      className="col-span-3 md:col-span-7 flex flex-col md:flex-row items-start gap-4 pr-4"
    >
      {id && <input type="hidden" name="variable_id" value={id} />}

      <input type="hidden" name="env_slug" value={env_slug} />

      <fieldset className={cn("inline-flex flex-col gap-1 w-full md:w-2/7")}>
        <label id={`${idPrefix}-name`} className="sr-only">
          variable name
        </label>
        <Input
          placeholder="VARIABLE_NAME"
          defaultValue={name}
          autoFocus={editType === "add"}
          id="variable-name"
          name="key"
          className="font-mono"
          aria-labelledby={`${idPrefix}-name-error`}
          aria-invalid={!!errors.key}
        />
        {errors.key && (
          <span id={`${idPrefix}-name-error`} className="text-red-500 text-sm">
            {errors.key}
          </span>
        )}
      </fieldset>

      <fieldset className="flex-1 inline-flex flex-col gap-1 w-full">
        <label id={`${idPrefix}-value`} className="sr-only">
          variable value
        </label>
        <Input
          autoFocus={editType === "update"}
          placeholder="value"
          id="variable-value"
          defaultValue={value}
          name="value"
          className="font-mono"
          aria-labelledby={`${idPrefix}-value-error`}
          aria-invalid={!!errors.value}
        />
        {errors.value && (
          <span id={`${idPrefix}-value-error`} className="text-red-500 text-sm">
            {errors.value}
          </span>
        )}
      </fieldset>

      <div className="flex gap-3">
        {editType === "add" ? (
          <SubmitButton
            isPending={isPending}
            variant="secondary"
            name="intent"
            value="add-env-variable"
          >
            {isPending ? (
              <>
                <LoaderIcon className="animate-spin" size={15} />
                <span>Adding...</span>
              </>
            ) : (
              <>
                <CheckIcon size={15} className="flex-none" />
                <span>Add</span>
              </>
            )}
          </SubmitButton>
        ) : (
          <>
            <SubmitButton
              isPending={isPending}
              variant="outline"
              className="bg-inherit"
              name="intent"
              value="update-env-variable"
            >
              {isPending ? (
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
                quitEditMode?.();
              }}
              variant="outline"
              className="bg-inherit"
              type="button"
            >
              <XIcon size={15} className="flex-none" />
              <span className="sr-only">Cancel</span>
            </Button>
          </>
        )}
      </div>
    </fetcher.Form>
  );
}

export async function clientAction({
  params,
  request
}: Route.ClientActionArgs) {
  const formData = await request.formData();

  const intent = formData.get("intent")?.toString();
  const env_slug = formData.get("env_slug")?.toString()!;
  const variable_id = formData.get("variable_id")?.toString()!;

  switch (intent) {
    case "add-env-variable": {
      return addEnvVariable(params.projectSlug, env_slug, formData);
    }
    case "update-env-variable": {
      return updateEnvVariable(
        params.projectSlug,
        env_slug,
        variable_id,
        formData
      );
    }
    case "delete-env-variable": {
      return deleteEnvVariable(params.projectSlug, env_slug, variable_id);
    }
    default: {
      throw new Error("Unexpected intent");
    }
  }
}

async function addEnvVariable(
  project_slug: string,
  env_slug: string,
  formData: FormData
) {
  const userData = {
    key: formData.get("key")!.toString(),
    value: formData.get("value")!.toString()
  };
  const { data, error, response } = await apiClient.POST(
    "/api/projects/{project_slug}/{env_slug}/variables/",
    {
      headers: {
        ...(await getCsrfTokenHeader())
      },
      params: {
        path: {
          env_slug,
          project_slug
        }
      },
      body: userData
    }
  );
  if (error) {
    if (response.status === 409) {
      return {
        errors: {
          errors: [
            {
              attr: "key",
              code: "ERROR",
              detail:
                "Duplicate variable names are not allowed in the same environment"
            }
          ],
          type: "validation_error"
        } satisfies ErrorResponseFromAPI
      };
    }
    return {
      errors: error
    };
  }

  await queryClient.invalidateQueries(
    environmentQueries.single(project_slug, env_slug)
  );

  toast.success("Success", {
    description: "New variable added to environment",
    closeButton: true
  });

  return { data };
}

async function updateEnvVariable(
  project_slug: string,
  env_slug: string,
  env_id: string,
  formData: FormData
) {
  const userData = {
    key: formData.get("key")!.toString(),
    value: formData.get("value")!.toString()
  };
  const { data, error, response } = await apiClient.PUT(
    "/api/projects/{project_slug}/{env_slug}/variables/{id}/",
    {
      headers: {
        ...(await getCsrfTokenHeader())
      },
      params: {
        path: {
          env_slug,
          project_slug,
          id: env_id
        }
      },
      body: userData
    }
  );
  if (error) {
    if (response.status === 409) {
      return {
        errors: {
          errors: [
            {
              attr: "key",
              code: "ERROR",
              detail:
                "Duplicate variable names are not allowed in the same environment"
            }
          ],
          type: "validation_error"
        } satisfies ErrorResponseFromAPI
      };
    }
    return {
      errors: error
    };
  }

  await queryClient.invalidateQueries(
    environmentQueries.single(project_slug, env_slug)
  );

  toast.success("Success", {
    description: "Variable updated",
    closeButton: true
  });

  return { data };
}

async function deleteEnvVariable(
  project_slug: string,
  env_slug: string,
  env_id: string
) {
  const { data, error, response } = await apiClient.DELETE(
    "/api/projects/{project_slug}/{env_slug}/variables/{id}/",
    {
      headers: {
        ...(await getCsrfTokenHeader())
      },
      params: {
        path: {
          env_slug,
          project_slug,
          id: env_id
        }
      }
    }
  );

  if (error) {
    return {
      errors: error
    };
  }

  await queryClient.invalidateQueries(
    environmentQueries.single(project_slug, env_slug)
  );

  toast.success("Success", {
    description: "Variable deleted succesfully.",
    closeButton: true
  });

  return { data };
}
