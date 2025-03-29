import {
  AlertCircleIcon,
  ArrowRightIcon,
  CheckIcon,
  CopyIcon,
  ExternalLinkIcon,
  GlobeIcon,
  InfoIcon,
  LoaderIcon,
  Plus,
  Trash2Icon,
  Undo2Icon
} from "lucide-react";
import * as React from "react";
import { Code } from "~/components/code";
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
  FieldSetCheckbox,
  FieldSetErrors,
  FieldSetInput,
  FieldSetLabel
} from "~/components/ui/fieldset";
import {
  Tooltip,
  TooltipContent,
  TooltipProvider,
  TooltipTrigger
} from "~/components/ui/tooltip";
import { type Service } from "~/lib/queries";
import { cn, getFormErrorsFromResponseData } from "~/lib/utils";
import {
  useFetcherWithCallbacks,
  useServiceQuery
} from "~/routes/services/settings/services-settings";
import { wait } from "~/utils";

type UrlItem = {
  change_id?: string;
  id?: string | null;
  change_type?: "UPDATE" | "DELETE" | "ADD";
} & Omit<Service["urls"][number], "id">;

export type ServiceURLsFormProps = {
  project_slug: string;
  service_slug: string;
  env_slug: string;
};

export function ServiceURLsForm({
  project_slug,
  service_slug,
  env_slug
}: ServiceURLsFormProps) {
  const { data: service } = useServiceQuery({
    project_slug,
    service_slug,
    env_slug
  });

  const urls: Map<string, UrlItem> = new Map();
  for (const url of service?.urls ?? []) {
    urls.set(url.id, {
      ...url,
      id: url.id
    });
  }
  for (const ch of (service?.unapplied_changes ?? []).filter(
    (ch) => ch.field === "urls"
  )) {
    const newUrl = (ch.new_value ?? ch.old_value) as Omit<
      Service["urls"][number],
      "id"
    >;
    urls.set(ch.item_id ?? ch.id, {
      ...newUrl,
      change_id: ch.id,
      id: ch.item_id,
      change_type: ch.type
    });
  }

  return (
    <div className="w-full max-w-4xl flex flex-col gap-5">
      <div className="flex flex-col gap-3">
        <h3 className="text-lg">URLs</h3>
        <p className="text-gray-400">
          The domains and base path which are associated to this service. Use{" "}
          <Code>*.example.com</Code> for wildcard support.
        </p>
      </div>
      {urls.size > 0 && (
        <>
          <hr className="border-border" />
          <ul className="flex flex-col gap-2">
            {[...urls.entries()].map(([key, value]) => (
              <li key={key}>
                <ServiceURLFormItem {...value} />
              </li>
            ))}
          </ul>
        </>
      )}
      <hr className="border-border" />
      <h3 className="text-lg">Add new url</h3>
      <NewServiceURLForm />
    </div>
  );
}

type ServiceURLFormItemProps = {
  id?: string | null;
  change_id?: string;
  change_type?: "UPDATE" | "DELETE" | "ADD";
} & Omit<Service["urls"][number], "id">;

function ServiceURLFormItem({
  domain,
  redirect_to,
  associated_port,
  base_path,
  change_id,
  change_type,
  strip_prefix,
  id
}: ServiceURLFormItemProps) {
  const [isRedirect, setIsRedirect] = React.useState(Boolean(redirect_to));
  const [hasCopied, startTransition] = React.useTransition();
  const formRef = React.useRef<React.ComponentRef<"form">>(null);
  const [accordionValue, setAccordionValue] = React.useState("");

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
        field?.focus();
      }
    }
  });

  const { fetcher: cancelFetcher } = useFetcherWithCallbacks({
    onSuccess() {
      setAccordionValue("");
    }
  });
  const { fetcher: deleteFetcher } = useFetcherWithCallbacks({
    onSuccess() {
      setAccordionValue("");
    }
  });

  const errors = getFormErrorsFromResponseData(data?.errors);
  const isPending = updateFetcher.state !== "idle";

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
            <input type="hidden" name="change_field" value="urls" />
            <input type="hidden" name="change_id" value={change_id} />
          </cancelFetcher.Form>
        )}
        {id && (
          <deleteFetcher.Form
            method="post"
            id={`delete-${id}-form`}
            className="hidden"
          >
            <input type="hidden" name="change_field" value="urls" />
            <input type="hidden" name="change_type" value="DELETE" />
            <input type="hidden" name="item_id" value={id} />
          </deleteFetcher.Form>
        )}
        <TooltipProvider>
          <Tooltip delayDuration={0}>
            <TooltipTrigger asChild>
              <Button
                variant="ghost"
                className={cn(
                  "px-2.5 py-0.5 focus-visible:opacity-100 group-hover:opacity-100",
                  hasCopied ? "opacity-100" : "md:opacity-0"
                )}
                onClick={() => {
                  window.open(`//${domain}${base_path}`, "_blank")?.focus();
                }}
              >
                <ExternalLinkIcon size={15} className="flex-none" />
                <span className="sr-only">Navigate to this url</span>
              </Button>
            </TooltipTrigger>
            <TooltipContent>Navigate to this url</TooltipContent>
          </Tooltip>
          <Tooltip delayDuration={0}>
            <TooltipTrigger asChild>
              <Button
                variant="ghost"
                className={cn(
                  "px-2.5 py-0.5 focus-visible:opacity-100 group-hover:opacity-100",
                  hasCopied ? "opacity-100" : "md:opacity-0"
                )}
                onClick={() => {
                  navigator.clipboard
                    .writeText(`${domain}${base_path}`)
                    .then(() => {
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
                    type="submit"
                    form={`delete-${id}-form`}
                    name="intent"
                    value="request-service-change"
                    className="px-2.5 py-0.5 md:opacity-0 focus-visible:opacity-100 group-hover:opacity-100"
                  >
                    <Trash2Icon size={15} className="flex-none text-red-400" />
                    <span className="sr-only">Delete url</span>
                  </Button>
                </TooltipTrigger>
                <TooltipContent>Delete url</TooltipContent>
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
          value={`${domain}/${base_path}`}
          className="border-none"
          disabled={!!change_id}
        >
          <AccordionTrigger
            className={cn(
              "w-full px-3 bg-muted rounded-md gap-2 flex flex-col items-start text-start pr-24",
              "data-[state=open]:rounded-b-none [&[data-state=open]_svg]:rotate-90",
              {
                "dark:bg-secondary-foreground bg-secondary/60 ":
                  change_type === "UPDATE",
                "dark:bg-primary-foreground bg-primary/60":
                  change_type === "ADD",
                "dark:bg-red-500/30 bg-red-400/60": change_type === "DELETE"
              }
            )}
          >
            <div className="inline-flex gap-2 items-center flex-wrap">
              <GlobeIcon size={15} className="text-grey flex-none" />
              <p>
                {domain}
                <span className="text-grey">{base_path ?? "/"}</span>
              </p>
            </div>
            {redirect_to && (
              <small className="inline-flex gap-2 items-center">
                <ArrowRightIcon size={15} className="text-grey flex-none" />
                <span className="text-grey">
                  <span>{redirect_to.url}</span>
                  &nbsp;&nbsp;
                  <span className="text-card-foreground">
                    [
                    {redirect_to.permanent
                      ? "permanent redirect"
                      : "temporary redirect"}
                    ]
                  </span>
                </span>
              </small>
            )}
            {associated_port && (
              <small className="inline-flex gap-2 items-center">
                <ArrowRightIcon size={15} className="text-grey flex-none" />
                <span className="text-grey">{associated_port}</span>
              </small>
            )}
          </AccordionTrigger>
          {id && (
            <AccordionContent className="border-border border-x border-b rounded-b-md p-4 mb-4">
              <updateFetcher.Form
                method="post"
                className="flex flex-col gap-4"
                ref={formRef}
              >
                <input type="hidden" name="change_field" value="urls" />
                <input type="hidden" name="change_type" value="UPDATE" />
                <input type="hidden" name="item_id" value={id} />

                {errors.new_value?.non_field_errors && (
                  <Alert variant="destructive">
                    <AlertCircleIcon className="h-4 w-4" />
                    <AlertTitle>Error</AlertTitle>
                    <AlertDescription>
                      {errors.new_value.non_field_errors}
                    </AlertDescription>
                  </Alert>
                )}
                {!isRedirect && (
                  <FieldSet
                    required
                    errors={errors.new_value?.associated_port}
                    className="flex-1 inline-flex flex-col gap-1"
                  >
                    <FieldSetLabel>Forwarded port</FieldSetLabel>
                    <FieldSetInput
                      placeholder="ex: /"
                      name="associated_port"
                      defaultValue={associated_port ?? ""}
                    />
                  </FieldSet>
                )}

                <FieldSet
                  required
                  errors={errors.new_value?.domain}
                  className="flex-1 inline-flex flex-col gap-1"
                >
                  <FieldSetLabel>Domain</FieldSetLabel>
                  <FieldSetInput
                    name="domain"
                    placeholder="ex: www.mysupersaas.co"
                    defaultValue={domain}
                  />
                </FieldSet>
                <FieldSet
                  required
                  errors={errors.new_value?.base_path}
                  className="flex-1 inline-flex flex-col gap-1"
                >
                  <FieldSetLabel>Base path</FieldSetLabel>
                  <FieldSetInput
                    placeholder="ex: /"
                    name="base_path"
                    defaultValue={base_path ?? "/"}
                  />
                </FieldSet>

                <FieldSet
                  className="flex-1 inline-flex gap-2 flex-col"
                  errors={errors.new_value?.strip_prefix}
                >
                  <div className="inline-flex gap-2 items-center">
                    <FieldSetCheckbox
                      name="strip_prefix"
                      defaultChecked={strip_prefix}
                    />

                    <FieldSetLabel className="inline-flex gap-1 items-center">
                      <span>Strip path prefix ?</span>
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
                    </FieldSetLabel>
                  </div>
                  <FieldSetErrors className="relative left-6" />
                </FieldSet>

                <FieldSet
                  errors={errors.new_value?.redirect_to?.non_field_errors}
                  className="flex-1 inline-flex gap-2 flex-col"
                >
                  <div className="inline-flex gap-2 items-center">
                    <FieldSetCheckbox
                      name="is_redirect"
                      defaultChecked={isRedirect}
                      onCheckedChange={(state) => setIsRedirect(Boolean(state))}
                    />

                    <FieldSetLabel className="inline-flex gap-1 items-center">
                      Is redirect ?
                    </FieldSetLabel>
                  </div>
                </FieldSet>

                {isRedirect && (
                  <div className="flex flex-col gap-4 pl-4">
                    <FieldSet
                      required
                      errors={errors.new_value?.redirect_to?.url}
                      className="flex-1 inline-flex flex-col gap-1"
                    >
                      <FieldSetLabel>Redirect to url</FieldSetLabel>
                      <FieldSetInput
                        name="redirect_to_url"
                        placeholder="ex: https://mysupersaas.co/"
                        defaultValue={redirect_to?.url}
                      />
                    </FieldSet>

                    <FieldSet
                      errors={errors.new_value?.redirect_to?.permanent}
                      className="flex-1 inline-flex gap-2 flex-col"
                    >
                      <div className="inline-flex items-center gap-2">
                        <FieldSetCheckbox
                          name="redirect_to_permanent"
                          defaultChecked={redirect_to?.permanent}
                        />

                        <FieldSetLabel className=" inline-flex gap-1 items-center">
                          Permanent redirect
                          <TooltipProvider>
                            <Tooltip delayDuration={0}>
                              <TooltipTrigger>
                                <InfoIcon size={15} />
                              </TooltipTrigger>
                              <TooltipContent className="max-w-64 text-balance">
                                If checked, ZaneOps will redirect with a 308
                                status code; otherwise, it will redirect with a
                                307 status code.
                              </TooltipContent>
                            </Tooltip>
                          </TooltipProvider>
                        </FieldSetLabel>
                      </div>
                    </FieldSet>
                  </div>
                )}
                <div className="flex justify-end items-center gap-2 border-t pt-4 px-4 -mx-4 border-border">
                  <SubmitButton
                    variant="secondary"
                    isPending={isPending}
                    className="inline-flex gap-1"
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
                        Update
                        <CheckIcon size={15} />
                      </>
                    )}
                  </SubmitButton>

                  <Button onClick={reset} variant="outline" type="reset">
                    Reset
                  </Button>
                </div>
              </updateFetcher.Form>
            </AccordionContent>
          )}
        </AccordionItem>
      </Accordion>
    </div>
  );
}

function NewServiceURLForm() {
  const [isRedirect, setIsRedirect] = React.useState(false);
  const formRef = React.useRef<React.ComponentRef<"form">>(null);

  const { fetcher, data, reset } = useFetcherWithCallbacks({
    onSuccess() {
      formRef.current?.reset();
      (
        formRef.current?.elements.namedItem("domain") as HTMLInputElement
      )?.focus();
    },
    onSettled(data) {
      if (data.errors) {
        const errors = getFormErrorsFromResponseData(data?.errors);
        const key = Object.keys(errors.new_value ?? {})[0];
        const field = formRef.current?.elements.namedItem(
          key
        ) as HTMLInputElement;
        field?.focus();
      }
    }
  });
  const isPending = fetcher.state !== "idle";
  const errors = getFormErrorsFromResponseData(data?.errors);

  return (
    <fetcher.Form
      method="post"
      className="flex flex-col gap-4 border border-border p-4 rounded-md"
      ref={formRef}
    >
      <input type="hidden" name="change_field" value="urls" />
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
      {!isRedirect && (
        <FieldSet
          required
          errors={errors.new_value?.associated_port}
          className="flex-1 inline-flex flex-col gap-1"
        >
          <FieldSetLabel>Forwarded port</FieldSetLabel>
          <FieldSetInput
            placeholder="ex: /"
            name="associated_port"
            defaultValue={80}
          />
        </FieldSet>
      )}

      <FieldSet
        errors={errors.new_value?.domain}
        className="flex-1 inline-flex flex-col gap-1"
      >
        <FieldSetLabel className="inline-flex gap-1">
          <span>Domain</span>
          <span className="dark:text-card-foreground text-grey">
            (leave empty to generate)
          </span>
        </FieldSetLabel>
        <FieldSetInput name="domain" placeholder="ex: www.mysupersaas.co" />
      </FieldSet>

      <FieldSet
        required
        errors={errors.new_value?.base_path}
        className="flex-1 inline-flex flex-col gap-1"
      >
        <FieldSetLabel>Base path</FieldSetLabel>
        <FieldSetInput
          name="base_path"
          placeholder="ex: /api"
          defaultValue="/"
        />
      </FieldSet>

      <FieldSet
        errors={errors.new_value?.strip_prefix}
        className="flex-1 inline-flex gap-2 flex-col"
      >
        <div className="inline-flex gap-2 items-center">
          <FieldSetCheckbox name="strip_prefix" defaultChecked />

          <FieldSetLabel className="inline-flex gap-1 items-center">
            Strip path prefix ?
            <TooltipProvider>
              <Tooltip delayDuration={0}>
                <TooltipTrigger>
                  <InfoIcon size={15} />
                </TooltipTrigger>
                <TooltipContent className="max-w-48">
                  Wether or not to omit the base path when passing the request
                  to your service.
                </TooltipContent>
              </Tooltip>
            </TooltipProvider>
          </FieldSetLabel>
        </div>

        <FieldSetErrors className="relative left-6" />
      </FieldSet>

      <FieldSet
        errors={errors.new_value?.redirect_to?.non_field_errors}
        className="flex-1 inline-flex gap-2 flex-col"
      >
        <div className="inline-flex gap-2 items-center">
          <FieldSetCheckbox
            name="is_redirect"
            defaultChecked={isRedirect}
            onCheckedChange={(state) => setIsRedirect(Boolean(state))}
          />

          <FieldSetLabel className="inline-flex gap-1 items-center">
            Is redirect ?
          </FieldSetLabel>
        </div>
      </FieldSet>

      {isRedirect && (
        <div className="flex flex-col gap-4 pl-4">
          <FieldSet required errors={errors.new_value?.redirect_to?.url}>
            <FieldSetLabel>Redirect to url</FieldSetLabel>

            <FieldSetInput
              name="redirect_to_url"
              placeholder="ex: https://mysupersaas.co/"
            />
          </FieldSet>

          <FieldSet
            errors={errors.new_value?.redirect_to?.permanent}
            className="flex-1 inline-flex gap-2 flex-col"
          >
            <div className="inline-flex items-center gap-2">
              <FieldSetCheckbox name="redirect_to_permanent" />

              <FieldSetLabel className="inline-flex gap-1 items-center">
                Permanent redirect
                <TooltipProvider>
                  <Tooltip delayDuration={0}>
                    <TooltipTrigger>
                      <InfoIcon size={15} />
                    </TooltipTrigger>
                    <TooltipContent className="max-w-64 text-balance">
                      If checked, ZaneoOps will redirect with a 308 status code;
                      otherwise, it will redirect with a 307 status code.
                    </TooltipContent>
                  </Tooltip>
                </TooltipProvider>
              </FieldSetLabel>
            </div>
          </FieldSet>
        </div>
      )}

      <div className="flex justify-end items-center gap-2 border-t pt-4 px-4 -mx-4 border-border">
        <SubmitButton
          variant="secondary"
          isPending={isPending}
          className="inline-flex gap-1 flex-1 md:flex-none"
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
              <Plus size={15} />
            </>
          )}
        </SubmitButton>
        <Button
          variant="outline"
          type="reset"
          className="flex-1 md:flex-none"
          onClick={reset}
        >
          Reset
        </Button>
      </div>
    </fetcher.Form>
  );
}
