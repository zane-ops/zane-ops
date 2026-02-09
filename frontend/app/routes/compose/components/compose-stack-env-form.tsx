import {
  AlertCircle,
  CheckIcon,
  CopyIcon,
  EditIcon,
  EllipsisVerticalIcon,
  ExternalLinkIcon,
  EyeIcon,
  EyeOffIcon,
  LoaderIcon,
  PlusIcon,
  Trash2Icon,
  Undo2Icon,
  XIcon
} from "lucide-react";
import * as React from "react";
import { useFetcher } from "react-router";
import type { ComposeStack } from "~/api/types";
import { Code } from "~/components/code";
import { Alert, AlertDescription, AlertTitle } from "~/components/ui/alert";
import { Button, SubmitButton } from "~/components/ui/button";
import {
  FieldSet,
  FieldSetInput,
  FieldSetLabel
} from "~/components/ui/fieldset";
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
import { cn, getFormErrorsFromResponseData } from "~/lib/utils";
import type { clientAction } from "~/routes/compose/compose-stack-settings";
import { wait } from "~/utils";

export type ComposeStackEnvFormProps = {
  stack: ComposeStack;
};

type EnvVariableUI = {
  change_id?: string;
  id?: string | null;
  name: string;
  value: string;
  change_type?: "UPDATE" | "DELETE" | "ADD";
};

export function ComposeStackEnvForm({ stack }: ComposeStackEnvFormProps) {
  const env_variables: Map<string, EnvVariableUI> = new Map();
  for (const env of stack?.env_overrides ?? []) {
    env_variables.set(env.id, {
      id: env.id,
      name: env.key,
      value: env.value
    });
  }
  for (const ch of stack.unapplied_changes.filter(
    (ch) => ch.field === "env_overrides"
  )) {
    const keyValue = (ch.new_value ?? ch.old_value) as {
      key: string;
      value: string;
    };
    env_variables.set(ch.item_id ?? ch.id, {
      change_id: ch.id,
      id: ch.item_id,
      name: keyValue.key,
      value: keyValue.value,
      change_type: ch.type
    });
  }
  return (
    <div className="w-full max-w-4xl flex flex-col gap-5">
      <p className="text-gray-400">
        Override environment variables declared in the{" "}
        <Code className="text-sm">x-zane-env</Code> section of your
        docker-compose.yml. More info in{" "}
        <a
          href="#"
          target="_blank"
          className="text-link underline inline-flex gap-1"
        >
          the docs <ExternalLinkIcon className="size-4 flex-none" />
        </a>
      </p>

      <section className="flex flex-col gap-4">
        {env_variables.size > 0 && (
          <>
            <hr className="border-border" />
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
        <h3 className="">Add new variable</h3>
        <p className="text-grey">
          Use <Code className="text-sm">{"{{env.VARIABLE_NAME}}"}</Code> to
          reference shared variables from the parent environment
        </p>
        <NewEnvVariableForm />
      </section>
    </div>
  );
}

function EnVariableRow({
  name: key,
  value,
  change_type,
  change_id,
  id
}: EnvVariableUI) {
  const [isEnvValueShown, setIsEnvValueShown] = React.useState(false);
  const [isEditing, setIsEditing] = React.useState(false);
  const [hasCopied, startTransition] = React.useTransition();

  const cancelFetcher = useFetcher<typeof clientAction>();
  const deleteFetcher = useFetcher<typeof clientAction>();
  const idPrefix = React.useId();

  return (
    <div
      className={cn(
        "grid gap-4 items-center md:grid-cols-7 lg:grid-cols-8 grid-cols-3 group pl-4 pt-2 md:py-1",
        {
          "items-start": isEditing,
          "dark:bg-secondary-foreground bg-secondary/60 rounded-md":
            change_type === "UPDATE",
          "dark:bg-primary-foreground bg-primary/60 rounded-md":
            change_type === "ADD",
          "dark:bg-red-500/30 bg-red-300/60 rounded-md":
            change_type === "DELETE"
        }
      )}
    >
      {isEditing && id ? (
        <EditVariableForm
          name={key}
          value={value}
          id={id}
          quitEditMode={() => setIsEditing(false)}
        />
      ) : (
        <>
          <div
            className={cn(
              "col-span-3 md:col-span-2 lg:col-span-3 flex flex-col",
              isEditing && "md:relative md:top-3"
            )}
          >
            <span className="font-mono break-all">{key}</span>
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
        </>
      )}

      {!isEditing && (
        <div className="flex justify-end">
          {change_id !== undefined && (
            <cancelFetcher.Form
              method="post"
              id={`${idPrefix}-cancel-form`}
              className="hidden"
            >
              <input type="hidden" name="intent" value="cancel-stack-changes" />
              <input type="hidden" name="change_id" value={change_id} />
            </cancelFetcher.Form>
          )}
          {id && (
            <deleteFetcher.Form
              method="post"
              id={`${idPrefix}-delete-form`}
              className="hidden"
            >
              <input type="hidden" name="item_id" value={id} />
              <input type="hidden" name="change_field" value="env_overrides" />
              <input type="hidden" name="change_type" value="DELETE" />
            </deleteFetcher.Form>
          )}
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
                align="end"
                alignOffset={-30}
                className="border min-w-0 mx-9 border-border"
              >
                {change_id !== undefined ? (
                  <>
                    <button
                      form={`${idPrefix}-cancel-form`}
                      disabled={cancelFetcher.state !== "idle"}
                      onClick={(e) => {
                        e.currentTarget.form?.requestSubmit();
                      }}
                    >
                      <MenubarContentItem
                        icon={Undo2Icon}
                        text="Discard change"
                        className="text-red-400"
                        disabled
                      />
                    </button>
                  </>
                ) : (
                  id && (
                    <>
                      <MenubarContentItem
                        icon={EditIcon}
                        text="Edit"
                        onClick={() => setIsEditing(true)}
                      />
                      <button
                        form={`${idPrefix}-delete-form`}
                        disabled={deleteFetcher.state !== "idle"}
                        onClick={(e) => {
                          e.currentTarget.form?.requestSubmit();
                        }}
                      >
                        <MenubarContentItem
                          icon={Trash2Icon}
                          text="Remove"
                          className="text-red-400"
                        />
                      </button>
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

type EditVariableFormProps = {
  name: string;
  value: string;
  id: string;
  quitEditMode: () => void;
};

function EditVariableForm({
  name: key,
  value,
  id,
  quitEditMode
}: EditVariableFormProps) {
  const fetcher = useFetcher<typeof clientAction>();
  const isUpdatingVariableValue = fetcher.state !== "idle";
  const errors = getFormErrorsFromResponseData(fetcher.data?.errors);
  const formRef = React.useRef<React.ComponentRef<"form">>(null);

  React.useEffect(() => {
    // only focus on the correct input in case of error
    if (fetcher.state === "idle" && fetcher.data) {
      if (fetcher.data.errors) {
        const errors = getFormErrorsFromResponseData(fetcher.data?.errors);
        const key = Object.keys(errors.new_value ?? {})[0];
        const field = formRef.current?.elements.namedItem(
          key
        ) as HTMLInputElement;
        field?.focus();
        return;
      }

      quitEditMode();
    }
  }, [fetcher.state, fetcher.data, errors]);

  return (
    <fetcher.Form
      method="post"
      ref={formRef}
      className="col-span-3 md:col-span-7 lg:col-span-8 flex flex-col md:flex-row items-start gap-4 pr-4"
    >
      <input type="hidden" name="item_id" value={id} />
      <input type="hidden" name="change_field" value="env_overrides" />
      <input type="hidden" name="change_type" value="UPDATE" />

      <FieldSet
        name="key"
        className="inline-flex flex-col gap-1 w-full md:w-2/7 lg:w-3/8"
        errors={errors.new_value?.key}
      >
        <FieldSetLabel className="sr-only">variable name</FieldSetLabel>
        <FieldSetInput
          placeholder="VARIABLE_NAME"
          defaultValue={key}
          className="font-mono"
        />
      </FieldSet>

      <FieldSet
        name="value"
        errors={errors.new_value?.value}
        className="flex-1 inline-flex flex-col gap-1 w-full"
      >
        <FieldSetLabel className="sr-only">variable value</FieldSetLabel>
        <FieldSetInput
          autoFocus
          placeholder="value"
          defaultValue={value}
          className="font-mono"
        />
      </FieldSet>

      <div className="flex gap-3">
        <SubmitButton
          isPending={isUpdatingVariableValue}
          variant="outline"
          className="bg-inherit"
          name="intent"
          value="request-stack-change"
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
            quitEditMode();
          }}
          variant="outline"
          className="bg-inherit"
          type="button"
        >
          <XIcon size={15} className="flex-none" />
          <span className="sr-only">Cancel</span>
        </Button>
      </div>
    </fetcher.Form>
  );
}

function NewEnvVariableForm() {
  const formRef = React.useRef<React.ComponentRef<"form">>(null);
  const fetcher = useFetcher<typeof clientAction>();

  const [data, setData] = React.useState(fetcher.data);

  const errors = getFormErrorsFromResponseData(data?.errors);
  const isPending = fetcher.state !== "idle";

  React.useEffect(() => {
    setData(fetcher.data);
    // only focus on the correct input in case of error
    if (fetcher.state === "idle" && fetcher.data) {
      if (fetcher.data.errors) {
        const errors = getFormErrorsFromResponseData(fetcher.data?.errors);
        const key = Object.keys(errors.new_value ?? {})[0];
        const field = formRef.current?.elements.namedItem(
          key
        ) as HTMLInputElement;
        field?.focus();
        return;
      }

      const nameInput = formRef.current?.elements.namedItem(
        "key"
      ) as HTMLInputElement | null;
      // refocus on the initial input so that the user can continue adding more variables
      formRef.current?.reset();
      nameInput?.focus();
    }
  }, [fetcher.state, fetcher.data]);

  return (
    <fetcher.Form
      method="post"
      ref={formRef}
      className="flex md:items-start gap-3 md:flex-row flex-col items-stretch"
    >
      {errors.non_field_errors && (
        <Alert variant="destructive">
          <AlertCircle className="h-4 w-4" />
          <AlertTitle>Error</AlertTitle>
          <AlertDescription>{errors.non_field_errors}</AlertDescription>
        </Alert>
      )}

      <input type="hidden" name="change_field" value="env_overrides" />
      <input type="hidden" name="change_type" value="ADD" />

      <FieldSet
        name="key"
        required
        className="flex-1 inline-flex flex-col gap-1"
        errors={errors.new_value?.key}
      >
        <FieldSetLabel className="sr-only" htmlFor="variable-name">
          variable name
        </FieldSetLabel>
        <FieldSetInput placeholder="VARIABLE_NAME" className="font-mono" />
      </FieldSet>

      <FieldSet
        required
        name="value"
        className="flex-1 inline-flex flex-col gap-1"
        errors={errors.new_value?.value}
      >
        <FieldSetLabel className="sr-only" htmlFor="variable-value">
          variable value
        </FieldSetLabel>
        <FieldSetInput placeholder="value" className="font-mono" />
      </FieldSet>

      <div className="flex gap-3 items-center w-full md:w-auto">
        <SubmitButton
          isPending={isPending}
          variant="secondary"
          name="intent"
          value="request-stack-change"
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
          onClick={() => setData(undefined)}
        >
          Reset
        </Button>
      </div>
    </fetcher.Form>
  );
}
