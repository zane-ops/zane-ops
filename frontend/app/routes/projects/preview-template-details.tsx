import { Editor } from "@monaco-editor/react";
import { useQuery } from "@tanstack/react-query";
import {
  AlertCircleIcon,
  ChevronDownIcon,
  ChevronRightIcon,
  LoaderIcon
} from "lucide-react";
import * as React from "react";
import { href, redirect, useFetcher, useParams } from "react-router";
import { toast } from "sonner";
import { type RequestInput, apiClient } from "~/api/client";
import { Code } from "~/components/code";
import { MultiSelect } from "~/components/multi-select";
import {
  Accordion,
  AccordionContent,
  AccordionItem,
  AccordionTrigger
} from "~/components/ui/accordion";
import { Alert, AlertDescription, AlertTitle } from "~/components/ui/alert";
import { SubmitButton } from "~/components/ui/button";
import {
  FieldSet,
  FieldSetCheckbox,
  FieldSetHidableInput,
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
import { Separator } from "~/components/ui/separator";
import {
  type PreviewTemplate,
  type Project,
  environmentQueries,
  previewTemplatesQueries
} from "~/lib/queries";
import type { Writeable } from "~/lib/types";
import {
  cn,
  getFormErrorsFromResponseData,
  isNotFoundError
} from "~/lib/utils";
import { queryClient } from "~/root";
import { getCsrfTokenHeader, metaTitle } from "~/utils";
import type { Route } from "./+types/preview-template-details";
import { DeleteConfirmationFormDialog } from "./delete-preview-template";

export function meta({ error, params }: Route.MetaArgs) {
  const title = !error
    ? `\`${params.projectSlug}\` preview templates`
    : isNotFoundError(error)
      ? "Error 404 - Project does not exist"
      : "Oops";
  return [metaTitle(title)] satisfies ReturnType<Route.MetaFunction>;
}

export async function clientLoader({ params }: Route.ClientLoaderArgs) {
  const template = await queryClient.ensureQueryData(
    previewTemplatesQueries.single(params.projectSlug, params.templateSlug)
  );

  return {
    template
  };
}

export default function PreviewTemplateDetailsPage({
  loaderData,
  params,
  matches: {
    "2": {
      loaderData: { project }
    }
  }
}: Route.ComponentProps) {
  const { data: template } = useQuery({
    ...previewTemplatesQueries.single(params.projectSlug, params.templateSlug),
    initialData: loaderData.template
  });

  const environments = project.environments.filter((env) => !env.is_preview);

  return (
    <section className="flex flex-col gap-4">
      <div className="flex items-center gap-4">
        <h2 className="text-2xl">Edit Preview template</h2>
      </div>
      <Separator />
      <p className="text-grey">Edit the data for the preview template</p>

      <EditPreviewTemplateForm
        template={template}
        environments={environments}
      />
    </section>
  );
}

type EditPreviewTemplateFormProps = Route.ComponentProps["loaderData"] & {
  environments: Project["environments"];
};

function EditPreviewTemplateForm({
  template,
  environments
}: EditPreviewTemplateFormProps) {
  const fetcher = useFetcher<typeof clientAction>();
  const params = useParams<Route.ComponentProps["params"]>();
  const formRef = React.useRef<React.ComponentRef<"form">>(null);

  const [isPasswordShown, setPasswordShown] = React.useState(false);
  const [authEnabled, setAuthEnabled] = React.useState(template.auth_enabled);
  const [isDefault, setIsDefaultChecked] = React.useState(template.is_default);
  const [autoTeardown, setAutoTeardown] = React.useState(
    template.auto_teardown
  );
  const [accordionValue, setAccordionValue] = React.useState("");

  const [baseEnvironment, setBaseEnvironment] = React.useState<
    Pick<typeof template.base_environment, "id" | "name">
  >(template.base_environment);

  const [cloneStrategy, setCloneStrategy] = React.useState(
    template.clone_strategy
  );

  const { data } = useQuery({
    ...environmentQueries.serviceList(params.projectSlug!, baseEnvironment.name)
  });

  const serviceListPerEnv = data ?? [];

  const [servicesToClone, setServicesToClone] = React.useState(
    template.services_to_clone
  );

  const defaultValue = `# paste your .env values here\n`;
  const [contents, setContents] = React.useState(
    defaultValue +
      template.variables.map(({ key, value }) => `${key}=${value}`).join("\n")
  );

  const errors = getFormErrorsFromResponseData(fetcher.data?.errors);

  React.useEffect(() => {
    // only focus on the correct input in case of error
    if (fetcher.state === "idle" && fetcher.data) {
      if (fetcher.data.errors) {
        const errors = getFormErrorsFromResponseData(fetcher.data.errors);
        const key = Object.keys(errors ?? {})[0];
        const field = formRef.current?.querySelector(
          `input[name="${key}"]:not([type="hidden"])`
        ) as HTMLInputElement | null;
        field?.focus();
        return;
      }
      formRef.current?.reset();
    }
  }, [fetcher.state, fetcher.data]);

  return (
    <fetcher.Form
      method="post"
      className="flex flex-col gap-5 items-start lg:w-7/8 xl:w-4/5"
      ref={formRef}
    >
      {errors.non_field_errors && (
        <Alert variant="destructive" className="my-2">
          <AlertCircleIcon className="h-4 w-4" />
          <AlertTitle>Error</AlertTitle>
          <AlertDescription>{errors.non_field_errors}</AlertDescription>
        </Alert>
      )}

      <input
        type="hidden"
        name="is_default"
        value={isDefault ? "on" : "off"}
        disabled={isDefault}
      />
      <FieldSet
        errors={errors.is_default}
        name="is_default"
        className="flex-1 inline-flex gap-2 flex-col"
      >
        <div className="inline-flex gap-2 items-start">
          <FieldSetCheckbox
            className="relative top-1"
            defaultChecked={isDefault}
            onCheckedChange={(state) => {
              setIsDefaultChecked(state === true);
            }}
          />

          <div className="flex flex-col gap-0.5">
            <FieldSetLabel className="inline-flex gap-1 items-center dark:text-card-foreground">
              Set as default ?
            </FieldSetLabel>

            <small className="text-grey text-sm">
              If checked, this template will be applied to pull requests and
              used as the default for API requests when no template is
              specified.
            </small>
          </div>
        </div>
      </FieldSet>

      <FieldSet
        className="w-full  flex flex-col gap-1"
        required
        name="slug"
        errors={errors.slug}
      >
        <FieldSetLabel className="flex items-center gap-0.5 dark:text-card-foreground">
          Slug
        </FieldSetLabel>
        <FieldSetInput
          autoFocus
          defaultValue={template.slug}
          placeholder="ex: staging-prs"
        />
      </FieldSet>

      <FieldSet
        name="preview_env_limit"
        required
        className="inline-flex gap-2 flex-col w-full"
        errors={errors.preview_env_limit}
      >
        <FieldSetLabel className="flex items-center gap-0.5 dark:text-card-foreground">
          Max previews
        </FieldSetLabel>

        <small className="text-grey text-sm">
          The maximum number of preview environments that can be created from
          this template at the same time
        </small>

        <FieldSetInput
          defaultValue={template.preview_env_limit}
          placeholder="ex: 5"
        />
      </FieldSet>

      <FieldSet
        className="w-full  flex flex-col gap-1"
        name="preview_root_domain"
        errors={errors.preview_root_domain}
      >
        <FieldSetLabel className="flex items-center gap-0.5 dark:text-card-foreground">
          Root domain
        </FieldSetLabel>
        <small className="text-grey text-sm mb-2">
          The root domain used for all preview environments. If left empty,
          ZaneOps will use the instance's <Code>ROOT_DOMAIN</Code>.
        </small>
        <FieldSetInput
          defaultValue={template.preview_root_domain}
          placeholder="ex: *.zn-previews.dev"
        />
      </FieldSet>

      <input
        type="hidden"
        name="auth_enabled"
        value={authEnabled ? "on" : "off"}
        disabled={!accordionValue ? false : authEnabled}
      />
      <input
        type="hidden"
        name="auto_teardown"
        value={autoTeardown ? "on" : "off"}
        disabled={!accordionValue ? false : autoTeardown}
      />

      <Accordion
        type="single"
        collapsible
        value={accordionValue}
        onValueChange={(state) => {
          setAccordionValue(state);
        }}
        className="border-t border-border w-full"
      >
        <AccordionItem value="system" className="border-none">
          <AccordionTrigger className="text-muted-foreground font-normal hover:underline gap-1">
            <ChevronRightIcon
              className="flex-none transition-transform duration-200"
              size={15}
            />
            Advanced options
          </AccordionTrigger>
          <AccordionContent className="flex flex-col gap-5 text-base">
            <FieldSet
              name="env_variables"
              className="flex flex-col gap-1.5 flex-1 mt-5"
              errors={errors.env_variables}
            >
              <FieldSetLabel className="text-muted-foreground dark:text-card-foreground">
                Default Environment Variables
              </FieldSetLabel>
              <FieldSetTextarea className="sr-only" value={contents} readOnly />

              <div
                className={cn(
                  "resize-y h-52 min-h-52 overflow-y-auto overflow-x-clip max-w-full",
                  "w-full"
                )}
              >
                <Editor
                  className="w-full h-full max-w-full"
                  language="shell"
                  value={contents}
                  theme="vs-dark"
                  options={{
                    fontSize: 14,
                    minimap: {
                      enabled: false
                    }
                  }}
                  onChange={(value) => setContents(value ?? "")}
                />
              </div>
            </FieldSet>

            <hr className="border w-full border-dashed border-border" />

            <FieldSet
              name="auto_teardown"
              errors={errors.auto_teardown}
              className="flex-1 inline-flex gap-2 flex-col"
            >
              <div className="inline-flex gap-2 items-start">
                <FieldSetCheckbox
                  className="relative top-1"
                  defaultChecked={autoTeardown}
                  onCheckedChange={(state) => {
                    setAutoTeardown(state === true);
                  }}
                />

                <div className="flex flex-col gap-0.5">
                  <FieldSetLabel className="inline-flex gap-1 items-center dark:text-card-foreground">
                    Auto teardown ?
                  </FieldSetLabel>

                  <small className="text-grey text-sm">
                    If checked, ZaneOps will automatically tear down preview
                    environments created from this template when their
                    associated branch or pull request is deleted.
                  </small>
                </div>
              </div>
            </FieldSet>

            <FieldSet
              name="ttl_seconds"
              errors={errors.ttl_seconds}
              className="inline-flex gap-2 flex-col w-full"
            >
              <FieldSetLabel className="flex items-center gap-0.5 dark:text-card-foreground">
                Time to live (in seconds)
              </FieldSetLabel>
              <small className="text-grey text-sm">
                After this time has elapsed, preview environments created from
                this template will be automatically deleted. If left empty, they
                will not be deleted.
              </small>

              <FieldSetInput
                defaultValue={template.ttl_seconds}
                placeholder="<no ttl>"
              />
            </FieldSet>

            <hr className="border w-full border-dashed border-border" />

            <input
              type="hidden"
              name="base_environment_id"
              value={baseEnvironment.id}
            />

            <div className="flex items-start gap-4 w-full">
              <FieldSet
                name="base_environment"
                errors={errors.base_environment_id}
                className="flex flex-col gap-2  w-full"
              >
                <FieldSetLabel htmlFor="base_environment">
                  Base environment
                </FieldSetLabel>

                <FieldSetSelect
                  name="base_environment"
                  defaultValue={template.base_environment.name}
                  onValueChange={(name) => {
                    const found = environments.find((env) => env.name === name);
                    if (found) {
                      setBaseEnvironment(found);
                    }
                  }}
                >
                  <SelectTrigger id="base_environment">
                    <SelectValue placeholder="Select environment" />
                  </SelectTrigger>
                  <SelectContent className="z-999">
                    {environments.map((env) => (
                      <SelectItem value={env.name} key={env.id}>
                        {env.name}
                      </SelectItem>
                    ))}
                  </SelectContent>
                </FieldSetSelect>
              </FieldSet>

              <FieldSet
                name="clone_strategy"
                errors={errors.clone_strategy}
                className="flex flex-col gap-2  w-full"
              >
                <FieldSetLabel htmlFor="clone_strategy">
                  Clone strategy
                </FieldSetLabel>

                <FieldSetSelect
                  name="clone_strategy"
                  defaultValue={template.clone_strategy}
                  onValueChange={(value) => {
                    setCloneStrategy(value as typeof template.clone_strategy);
                    if (value === "ALL") {
                      setServicesToClone([]);
                    }
                  }}
                >
                  <SelectTrigger id="clone_strategy">
                    <SelectValue placeholder="Select strategy" />
                  </SelectTrigger>
                  <SelectContent className="z-999">
                    <SelectItem value="ALL">All services</SelectItem>
                    <SelectItem value="ONLY">Only selected services</SelectItem>
                  </SelectContent>
                </FieldSetSelect>
              </FieldSet>
            </div>

            {cloneStrategy === "ONLY" && (
              <>
                {servicesToClone.map((srv) => (
                  <input
                    type="hidden"
                    name="services_to_clone_ids"
                    value={srv.id}
                    key={srv.id}
                  />
                ))}
                <FieldSet
                  name="selected_services"
                  errors={errors.services_to_clone_ids}
                  className="flex flex-col gap-2  w-full"
                >
                  <FieldSetLabel htmlFor="selected_services">
                    Selected services
                  </FieldSetLabel>

                  <MultiSelect
                    value={servicesToClone.map((srv) => srv.slug)}
                    align="start"
                    id="selected_services"
                    className="w-full border-border border-solid"
                    options={serviceListPerEnv.map((service) => service.slug)}
                    Icon={ChevronDownIcon}
                    label=""
                    order="icon-label"
                    onValueChange={(newVal) => {
                      const newServices: Writeable<
                        typeof template.services_to_clone
                      > = [];

                      for (const slug of newVal) {
                        const found = serviceListPerEnv.find(
                          (srv) => srv.slug === slug
                        );
                        if (found) {
                          newServices.push(found);
                        }
                      }
                      setServicesToClone(newServices);
                    }}
                  />
                </FieldSet>
              </>
            )}

            <FieldSet
              name="auth_enabled"
              errors={errors.auth_enabled}
              className="flex-1 inline-flex gap-2 flex-col"
            >
              <div className="inline-flex gap-2 items-start">
                <FieldSetCheckbox
                  defaultChecked={authEnabled}
                  onCheckedChange={(checked) =>
                    setAuthEnabled(
                      checked !== "indeterminate" ? checked : false
                    )
                  }
                  className="relative top-1"
                />

                <div className="flex flex-col gap-0.5">
                  <FieldSetLabel className="inline-flex gap-1 items-center dark:text-card-foreground">
                    Enable Authentication
                  </FieldSetLabel>

                  <small className="text-grey text-sm">
                    Enable Authentication for all preview environments that will
                    use this template
                  </small>
                </div>
              </div>
            </FieldSet>

            {authEnabled && (
              <>
                <FieldSet
                  className="w-full  flex flex-col gap-1"
                  required
                  name="auth_user"
                  errors={errors.auth_user}
                >
                  <FieldSetLabel className="flex items-center gap-0.5 dark:text-card-foreground">
                    Username
                  </FieldSetLabel>
                  <FieldSetInput
                    defaultValue={template.auth_user}
                    placeholder="ex: ceasarthegreat"
                  />
                </FieldSet>

                <FieldSet
                  className="w-full  flex flex-col gap-1"
                  required
                  name="auth_password"
                  errors={errors.auth_password}
                >
                  <FieldSetLabel className="flex items-center gap-0.5 dark:text-card-foreground">
                    Password
                  </FieldSetLabel>

                  <FieldSetHidableInput defaultValue={template.auth_password} />
                </FieldSet>
              </>
            )}
          </AccordionContent>
        </AccordionItem>
      </Accordion>

      <div className="flex items-center gap-2">
        <SubmitButton isPending={fetcher.state !== "idle"}>
          {fetcher.state !== "idle" ? (
            <>
              <LoaderIcon className="animate-spin" size={15} />
              <span>Updating preview template ...</span>
            </>
          ) : (
            "Update template"
          )}
        </SubmitButton>

        <DeleteConfirmationFormDialog />
      </div>
    </fetcher.Form>
  );
}

export async function clientAction({
  request,
  params
}: Route.ClientActionArgs) {
  const formData = await request.formData();

  const ttl_seconds_string = formData.get("ttl_seconds")?.toString();
  const preview_env_limit_string = formData
    .get("preview_env_limit")
    ?.toString();

  const services_to_clone_ids = formData
    .getAll("services_to_clone_ids")
    .map((val) => val.toString());

  const rootDomainString = formData
    .get("preview_root_domain")
    ?.toString()
    .trim();

  const auth_enabled = formData.get("auth_enabled")?.toString();
  const auto_teardown = formData.get("auto_teardown")?.toString();
  const is_default = formData.get("is_default")?.toString();

  const userData = {
    auth_enabled: auth_enabled ? auth_enabled === "on" : undefined,
    is_default: is_default ? is_default === "on" : undefined,
    auto_teardown: auto_teardown ? auto_teardown === "on" : undefined,

    auth_password: formData.get("auth_password")?.toString(),
    auth_user: formData.get("auth_user")?.toString(),
    // @ts-expect-error
    ttl_seconds: ttl_seconds_string ? ttl_seconds_string : undefined,
    base_environment_id: formData.get("base_environment_id")?.toString(),
    clone_strategy: formData
      .get("clone_strategy")
      ?.toString() as PreviewTemplate["clone_strategy"],
    env_variables: formData.get("env_variables")?.toString(),
    // @ts-expect-error
    preview_env_limit: preview_env_limit_string
      ? preview_env_limit_string
      : undefined,
    preview_root_domain: !rootDomainString ? undefined : rootDomainString,
    slug: formData.get("slug")?.toString(),
    services_to_clone_ids
  } satisfies RequestInput<
    "patch",
    "/api/projects/{project_slug}/preview-templates/{template_slug}/"
  >;

  const { error } = await apiClient.PATCH(
    "/api/projects/{project_slug}/preview-templates/{template_slug}/",
    {
      params: {
        path: {
          project_slug: params.projectSlug,
          template_slug: params.templateSlug
        }
      },
      headers: {
        ...(await getCsrfTokenHeader())
      },
      // @ts-expect-error
      body: userData
    }
  );

  if (error) {
    return {
      errors: error
    };
  }

  await queryClient.invalidateQueries(
    previewTemplatesQueries.list(params.projectSlug)
  );

  toast.success("Success", {
    dismissible: true,
    closeButton: true,
    description: "Preview template udpated succesfully"
  });
  throw redirect(
    href("/project/:projectSlug/settings/preview-templates", {
      projectSlug: params.projectSlug
    })
  );
}
