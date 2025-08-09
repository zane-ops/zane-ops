import Editor, { useMonaco } from "@monaco-editor/react";
import {
  AlertCircleIcon,
  FileSlidersIcon,
  LoaderIcon,
  PlusIcon,
  Trash2Icon,
  Undo2Icon
} from "lucide-react";
import * as React from "react";
import {
  Accordion,
  AccordionContent,
  AccordionItem,
  AccordionTrigger
} from "~/components/ui/accordion";
import { Alert, AlertDescription, AlertTitle } from "~/components/ui/alert";
import { Button, SubmitButton } from "~/components/ui/button";
import {
  FieldSet,
  FieldSetInput,
  FieldSetLabel,
  FieldSetSelect,
  FieldSetTextarea
} from "~/components/ui/fieldset";
import {
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
import type { Service } from "~/lib/queries";
import { cn, getFormErrorsFromResponseData } from "~/lib/utils";
import {
  useFetcherWithCallbacks,
  useServiceQuery
} from "~/routes/services/settings/service-settings";

export type ServiceConfigsFormProps = {
  project_slug: string;
  service_slug: string;
  env_slug: string;
};

export function ServiceConfigsForm({
  project_slug,
  service_slug,
  env_slug
}: ServiceConfigsFormProps) {
  const { data: service } = useServiceQuery({
    project_slug,
    service_slug,
    env_slug
  });
  const configs: Map<string, ConfigItem> = new Map();
  for (const config of service.configs ?? []) {
    configs.set(config.id, {
      ...config
    });
  }
  for (const ch of (service?.unapplied_changes ?? []).filter(
    (ch) => ch.field === "configs"
  )) {
    const newConfig = (ch.new_value ?? ch.old_value) as Omit<
      Service["configs"][number],
      "id"
    >;
    configs.set(ch.item_id ?? ch.id, {
      ...newConfig,
      change_id: ch.id,
      id: ch.item_id,
      change_type: ch.type
    });
  }
  return (
    <div className="flex flex-col gap-5 max-w-4xl w-full">
      <div className="flex flex-col gap-3">
        <p className="text-gray-400">
          Used for attaching read only configurations into your services or
          simply random files that are required for running your service.
        </p>
      </div>

      {configs.size > 0 && (
        <>
          <hr className="border-border" />
          <ul className="flex flex-col gap-2">
            {[...configs.entries()].map(([key, config]) => (
              <li key={key}>
                <ServiceConfigItem {...config} />
              </li>
            ))}
          </ul>
        </>
      )}

      <hr className="border-border" />
      <h3 className="text-lg">Add new config file</h3>
      <NewServiceConfigForm />
    </div>
  );
}

type ConfigItem = {
  change_id?: string;
  change_type?: "UPDATE" | "DELETE" | "ADD";
  id?: string | null;
} & Omit<Service["configs"][number], "id">;

function ServiceConfigItem({
  id,
  name,
  mount_path,
  contents,
  language,
  change_type,
  change_id
}: ConfigItem) {
  const [accordionValue, setAccordionValue] = React.useState("");
  const formRef = React.useRef<React.ComponentRef<"form">>(null);
  const [changedConfigLanguage, setChangedConfigLanguage] =
    React.useState(language);

  const [changedContents, setChangedContents] = React.useState(contents);
  const SelectTriggerRef =
    React.useRef<React.ComponentRef<typeof SelectTrigger>>(null);

  const {
    fetcher: updateFetcher,
    data,
    reset
  } = useFetcherWithCallbacks({
    onSuccess() {
      formRef.current?.reset();
      setAccordionValue("");
    },
    onSettled(data) {
      if (data.errors) {
        const errors = getFormErrorsFromResponseData(data?.errors);
        const key = Object.keys(errors.new_value ?? {})[0];
        const field = formRef.current?.elements.namedItem(
          key
        ) as HTMLInputElement;

        if (key === "language") {
          SelectTriggerRef.current?.focus();
          return;
        }
        field?.focus();
      }
    }
  });

  const { fetcher: cancelFetcher } = useFetcherWithCallbacks({
    onSuccess() {
      setAccordionValue("");
      setChangedContents(contents);
      setChangedConfigLanguage(language);
    }
  });
  const { fetcher: deleteFetcher } = useFetcherWithCallbacks({
    onSuccess() {
      setAccordionValue("");
    }
  });

  const errors = getFormErrorsFromResponseData(data?.errors);
  const isPending = updateFetcher.state !== "idle";

  const [languageList, setLanguageList] = React.useState(["plaintext"]);
  const monaco = useMonaco();

  React.useEffect(() => {
    setLanguageList(monaco?.languages.getLanguages().map((l) => l.id) ?? []);
  }, [monaco]);

  return (
    <div className="relative group">
      <div
        className="absolute top-2 right-2 inline-flex gap-1 items-center"
        role="none"
      >
        {change_id !== undefined && (
          <cancelFetcher.Form
            method="post"
            id={`cancel-${change_id}-form`}
            className="hidden"
          >
            <input type="hidden" name="change_field" value="configs" />
            <input type="hidden" name="change_id" value={change_id} />
          </cancelFetcher.Form>
        )}
        {id && (
          <deleteFetcher.Form
            method="post"
            id={`delete-${id}-form`}
            className="hidden"
          >
            <input type="hidden" name="change_field" value="configs" />
            <input type="hidden" name="change_type" value="DELETE" />
            <input type="hidden" name="item_id" value={id} />
          </deleteFetcher.Form>
        )}

        <TooltipProvider>
          {change_id !== undefined ? (
            <Tooltip delayDuration={0}>
              <TooltipTrigger asChild>
                <Button
                  variant="ghost"
                  className="px-2.5 py-0.5 md:opacity-0 focus-visible:opacity-100 group-hover:opacity-100"
                  type="submit"
                  name="intent"
                  value="cancel-service-change"
                  form={`cancel-${change_id}-form`}
                >
                  <Undo2Icon size={15} className="flex-none" />
                  <span className="sr-only">Discard change</span>
                </Button>
              </TooltipTrigger>
              <TooltipContent>Discard change</TooltipContent>
            </Tooltip>
          ) : (
            id && (
              <Tooltip delayDuration={0}>
                <TooltipTrigger asChild>
                  <Button
                    variant="ghost"
                    className="px-2.5 py-0.5 md:opacity-0 focus-visible:opacity-100 group-hover:opacity-100"
                    type="submit"
                    form={`delete-${id}-form`}
                    name="intent"
                    value="request-service-change"
                  >
                    <Trash2Icon size={15} className="flex-none text-red-400" />
                    <span className="sr-only">Delete config file</span>
                  </Button>
                </TooltipTrigger>
                <TooltipContent>Delete config file</TooltipContent>
              </Tooltip>
            )
          )}
        </TooltipProvider>
      </div>
      <Accordion
        type="single"
        collapsible
        value={accordionValue}
        onValueChange={(state) => {
          setAccordionValue(state);
        }}
      >
        <AccordionItem
          value={`${name}`}
          className="border-none"
          disabled={!!change_id && change_type === "DELETE"}
        >
          <AccordionTrigger
            className={cn(
              "rounded-md p-4 flex items-start gap-2 bg-muted",
              "aria-expanded:rounded-b-none",
              {
                "dark:bg-secondary-foreground bg-secondary/60 ":
                  change_type === "UPDATE",
                "dark:bg-primary-foreground bg-primary/60":
                  change_type === "ADD",
                "dark:bg-red-500/30 bg-red-400/60": change_type === "DELETE"
              }
            )}
          >
            <FileSlidersIcon size={20} className="text-grey relative top-1.5" />
            <div className="flex flex-col gap-2">
              <h3 className="text-lg inline-flex gap-1 items-center">
                <span>{name}</span>
              </h3>
              <small className="text-card-foreground inline-flex gap-1 items-center">
                <span className="text-grey">{mount_path}</span>
              </small>
            </div>
          </AccordionTrigger>
          <AccordionContent className="border-border border-x border-b rounded-b-md p-4 mb-4">
            <updateFetcher.Form
              method="post"
              ref={formRef}
              className={cn("flex flex-col gap-4 w-full")}
            >
              {id && (
                <>
                  <input type="hidden" name="item_id" value={id} />
                  <input type="hidden" name="change_field" value="configs" />
                  <input type="hidden" name="change_type" value="UPDATE" />
                </>
              )}
              <FieldSet
                errors={errors.new_value?.language}
                name="language"
                className="flex flex-col gap-1.5 flex-1"
              >
                <label
                  htmlFor={`language-${id}`}
                  className="text-muted-foreground"
                >
                  Language
                </label>
                <FieldSetSelect
                  value={changedConfigLanguage}
                  onValueChange={(language) =>
                    setChangedConfigLanguage(language)
                  }
                  disabled={!!change_id}
                >
                  <SelectTrigger
                    id={`language-${id}`}
                    ref={SelectTriggerRef}
                    data-edited={change_type === "UPDATE"}
                    data-added={change_type === "ADD"}
                    className={cn(
                      "disabled:placeholder-shown:font-mono disabled:bg-muted data-[edited=true]:disabled:bg-secondary/60",
                      "data-[edited=true]:dark:disabled:bg-secondary-foreground",
                      "data-[added=true]:dark:disabled:bg-primary-foreground",
                      "disabled:border-transparent disabled:opacity-100"
                    )}
                  >
                    <SelectValue placeholder="Select a language" />
                  </SelectTrigger>
                  <SelectContent>
                    {languageList.map((lang) => (
                      <SelectItem value={lang} key={lang}>
                        {lang}
                      </SelectItem>
                    ))}
                  </SelectContent>
                </FieldSetSelect>
              </FieldSet>

              <FieldSet
                required
                name="mount_path"
                className="flex flex-col gap-1.5 flex-1"
                errors={errors.new_value?.mount_path}
              >
                <FieldSetLabel>mount path</FieldSetLabel>
                <FieldSetInput
                  placeholder="ex: /data"
                  defaultValue={mount_path}
                  disabled={!!change_id}
                  data-edited={change_type === "UPDATE"}
                  data-added={change_type === "ADD"}
                  className={cn(
                    "disabled:placeholder-shown:font-mono disabled:bg-muted data-[edited=true]:disabled:bg-secondary/60",
                    "data-[edited=true]:dark:disabled:bg-secondary-foreground",
                    "data-[added=true]:dark:disabled:bg-primary-foreground",
                    "disabled:border-transparent disabled:opacity-100"
                  )}
                />
              </FieldSet>

              <FieldSet
                errors={errors.new_value?.name}
                name="name"
                className="flex flex-col gap-1.5 flex-1"
              >
                <FieldSetLabel>Name</FieldSetLabel>
                <FieldSetInput
                  placeholder="ex: postgresl-data"
                  defaultValue={name}
                  disabled={!!change_id}
                  data-edited={change_type === "UPDATE"}
                  data-added={change_type === "ADD"}
                  className={cn(
                    "disabled:placeholder-shown:font-mono disabled:bg-muted data-[edited=true]:disabled:bg-secondary/60",
                    "data-[edited=true]:dark:disabled:bg-secondary-foreground",
                    "data-[added=true]:dark:disabled:bg-primary-foreground",
                    "disabled:border-transparent disabled:opacity-100"
                  )}
                />
              </FieldSet>

              <FieldSet
                name="contents"
                errors={errors.new_value?.contents}
                className="flex flex-col gap-1.5 flex-1"
              >
                <FieldSetLabel className="text-muted-foreground">
                  contents
                </FieldSetLabel>
                <FieldSetTextarea
                  className="sr-only"
                  value={changedContents}
                  readOnly
                />

                <div
                  className={cn(
                    "resize-y h-52 min-h-52 overflow-y-auto overflow-x-clip max-w-full",
                    "w-[80dvw] sm:w-[88dvw] md:w-[82dvw] lg:w-[70dvw] xl:w-[855px]"
                  )}
                >
                  <Editor
                    className="w-full h-full max-w-full"
                    language={changedConfigLanguage}
                    value={changedContents}
                    theme="vs-dark"
                    options={{
                      readOnly: !!change_id,
                      minimap: {
                        enabled: false
                      }
                    }}
                    onChange={(value) => setChangedContents(value ?? "")}
                  />
                </div>
              </FieldSet>

              <hr className="-mx-4 border-border" />
              <div className="flex justify-end items-center gap-2">
                {change_id ? (
                  <>
                    <SubmitButton
                      variant="outline"
                      isPending={deleteFetcher.state !== "idle"}
                      name="intent"
                      value="cancel-service-change"
                      form={`cancel-${change_id}-form`}
                    >
                      {deleteFetcher.state !== "idle" ? (
                        <>
                          <LoaderIcon className="animate-spin" size={15} />
                          <span>Discarding...</span>
                        </>
                      ) : (
                        <>
                          <Undo2Icon size={15} className="flex-none" />
                          <span>Discard change</span>
                        </>
                      )}
                    </SubmitButton>
                  </>
                ) : (
                  <>
                    <SubmitButton
                      isPending={isPending}
                      variant="secondary"
                      className="flex-1 md:flex-none"
                      name="intent"
                      value="request-service-change"
                    >
                      {isPending ? (
                        <>
                          <span>Updating...</span>
                          <LoaderIcon className="animate-spin" size={15} />
                        </>
                      ) : (
                        <>
                          <span>Update</span>
                          <PlusIcon size={15} />
                        </>
                      )}
                    </SubmitButton>
                    <Button
                      variant="outline"
                      type="reset"
                      className="flex-1 md:flex-none"
                      onClick={() => {
                        reset();
                        setChangedConfigLanguage(language);
                        setChangedContents(contents);
                      }}
                    >
                      Reset
                    </Button>
                  </>
                )}
              </div>
            </updateFetcher.Form>
          </AccordionContent>
        </AccordionItem>
      </Accordion>
    </div>
  );
}

function NewServiceConfigForm() {
  const formRef = React.useRef<React.ComponentRef<"form">>(null);
  const SelectTriggerRef =
    React.useRef<React.ComponentRef<typeof SelectTrigger>>(null);

  const { fetcher, data, reset } = useFetcherWithCallbacks({
    onSuccess() {
      formRef.current?.reset();
      (
        formRef.current?.elements.namedItem("mount_path") as HTMLInputElement
      )?.focus();
      setLanguage("plaintext");
      setContents("// your text here");
    },
    onSettled(data) {
      if (data.errors) {
        const errors = getFormErrorsFromResponseData(data?.errors);
        const key = Object.keys(errors.new_value ?? {})[0];
        const field = formRef.current?.elements.namedItem(
          key
        ) as HTMLInputElement;

        if (key === "language") {
          SelectTriggerRef.current?.focus();
          return;
        }

        field?.focus();
      }
    }
  });
  const isPending = fetcher.state !== "idle";
  const errors = getFormErrorsFromResponseData(data?.errors);

  const [language, setLanguage] = React.useState("plaintext");
  const [contents, setContents] = React.useState("// your text here");
  const [languageList, setLanguageList] = React.useState(["plaintext"]);
  const monaco = useMonaco();

  React.useEffect(() => {
    setLanguageList(monaco?.languages.getLanguages().map((l) => l.id) ?? []);
  }, [monaco]);

  return (
    <fetcher.Form
      method="post"
      ref={formRef}
      className="flex flex-col gap-4 w-full border border-border rounded-md p-4 max-w-full"
    >
      <input type="hidden" name="change_field" value="configs" />
      <input type="hidden" name="change_type" value="ADD" />

      {errors.new_value?.non_field_errors && (
        <Alert variant="destructive">
          <AlertCircleIcon className="h-4 w-4" />
          <AlertTitle>Error</AlertTitle>
          <AlertDescription>
            {errors.new_value.non_field_errors}
          </AlertDescription>
        </Alert>
      )}

      <FieldSet
        errors={errors.new_value?.language}
        name="language"
        className="flex flex-col gap-1.5 flex-1"
      >
        <label htmlFor="language" className="text-muted-foreground">
          language
        </label>
        <FieldSetSelect
          value={language}
          onValueChange={(mode) => setLanguage(mode)}
        >
          <SelectTrigger id="language" ref={SelectTriggerRef}>
            <SelectValue placeholder="Select a language" />
          </SelectTrigger>
          <SelectContent>
            {languageList.map((lang) => (
              <SelectItem key={lang} value={lang}>
                {lang}
              </SelectItem>
            ))}
          </SelectContent>
        </FieldSetSelect>
      </FieldSet>

      <FieldSet
        required
        errors={errors.new_value?.mount_path}
        name="mount_path"
        className="flex flex-col gap-1.5 flex-1"
      >
        <FieldSetLabel>mount path</FieldSetLabel>
        <FieldSetInput placeholder="ex: /data" />
      </FieldSet>
      <FieldSet
        errors={errors.new_value?.name}
        name="name"
        className="flex flex-col gap-1.5 flex-1"
      >
        <FieldSetLabel>Name</FieldSetLabel>
        <FieldSetInput placeholder="ex: postgresl-data" />
      </FieldSet>

      <FieldSet
        name="contents"
        errors={errors.new_value?.contents}
        className="flex flex-col gap-1.5 flex-1"
      >
        <FieldSetLabel>contents</FieldSetLabel>
        <FieldSetTextarea className="sr-only" value={contents} readOnly />

        <div
          className={cn(
            "resize-y h-52 min-h-52 overflow-y-auto overflow-x-clip max-w-full",
            "w-[80dvw] sm:w-[88dvw] md:w-[82dvw] lg:w-[70dvw] xl:w-[855px]"
          )}
        >
          <Editor
            className="w-full h-full max-w-full"
            language={language}
            value={contents}
            theme="vs-dark"
            options={{
              minimap: {
                enabled: false
              }
            }}
            onChange={(value) => setContents(value ?? "")}
          />
        </div>
      </FieldSet>

      <hr className="-mx-4 border-border" />
      <div className="flex justify-end items-center gap-2">
        <SubmitButton
          isPending={isPending}
          variant="secondary"
          className="flex-1 md:flex-none"
          value="request-service-change"
          name="intent"
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
          className="flex-1 md:flex-none"
          onClick={() => {
            reset();
            setLanguage("plaintext");
            setContents("// your contents here");
          }}
        >
          Reset
        </Button>
      </div>
    </fetcher.Form>
  );
}
