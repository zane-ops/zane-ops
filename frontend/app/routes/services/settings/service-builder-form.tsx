import Editor from "@monaco-editor/react";
import {
  CheckIcon,
  ChevronRightIcon,
  InfoIcon,
  LoaderIcon,
  Undo2Icon
} from "lucide-react";
import * as React from "react";
import {
  Accordion,
  AccordionContent,
  AccordionItem,
  AccordionTrigger
} from "~/components/ui/accordion";
import { Button } from "~/components/ui/button";
import { SubmitButton } from "~/components/ui/button";
import {
  FieldSet,
  FieldSetCheckbox,
  FieldSetInput,
  FieldSetLabel
} from "~/components/ui/fieldset";
import { Label } from "~/components/ui/label";
import { RadioGroup, RadioGroupItem } from "~/components/ui/radio-group";
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
} from "~/routes/services/settings/services-settings";

export type ServiceBuilderFormProps = {
  service_slug: string;
  project_slug: string;
  env_slug: string;
};

type ServiceBuilder = Exclude<NonNullable<Service["builder"]>, "">;
type ServiceBuilderChangeNewValue = {
  builder: ServiceBuilder;
  options: Service["dockerfile_builder_options"] &
    Service["static_dir_builder_options"];
};

export function ServiceBuilderForm({
  service_slug,
  project_slug,
  env_slug
}: ServiceBuilderFormProps) {
  const { data: service } = useServiceQuery({
    project_slug,
    service_slug,
    env_slug
  });

  const { fetcher, data, reset } = useFetcherWithCallbacks({
    onSettled(data) {
      if (!data.errors) {
        formRef.current?.reset();
        let srv = data.data;
        if (!srv.slug) {
          srv = service;
        }
        const serviceBuilderChange = srv.unapplied_changes.find(
          (change) => change.field === "builder"
        ) as
          | {
              new_value: ServiceBuilderChangeNewValue;
              id: string;
            }
          | undefined;
        const newBuilder = serviceBuilderChange?.new_value
          .builder as ServiceBuilder;
        const updatedBuilder =
          newBuilder === null ? null : newBuilder ?? srv.builder;

        setServiceBuilder(updatedBuilder ?? "DOCKERFILE");
        setAccordionValue("");
        setIsSpaChecked(
          serviceBuilderChange?.new_value.options?.is_spa ??
            srv.static_dir_builder_options?.is_spa ??
            false
        );
      } else {
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

  const formRef = React.useRef<React.ComponentRef<"form">>(null);

  const serviceBuilderChange = service.unapplied_changes.find(
    (change) => change.field === "builder"
  ) as
    | {
        new_value: ServiceBuilderChangeNewValue;
        id: string;
      }
    | undefined;

  console.log({ serviceBuilderChange });
  const [serviceBuilder, setServiceBuilder] = React.useState<ServiceBuilder>(
    serviceBuilderChange?.new_value.builder ?? (service.builder || "DOCKERFILE")
  );

  // dockerfile builder
  const dockerfile_path =
    serviceBuilderChange?.new_value.options?.dockerfile_path ??
    service.dockerfile_builder_options?.dockerfile_path ??
    "./Dockerfile";
  const build_context_dir =
    serviceBuilderChange?.new_value.options?.build_context_dir ??
    service.dockerfile_builder_options?.build_context_dir ??
    "./";

  const build_stage_target =
    serviceBuilderChange?.new_value.options?.build_stage_target ??
    service.dockerfile_builder_options?.build_stage_target;

  // static directory builder
  const base_directory =
    serviceBuilderChange?.new_value.options?.base_directory ??
    service.static_dir_builder_options?.base_directory ??
    "./";
  const is_spa =
    serviceBuilderChange?.new_value.options?.is_spa ??
    service.static_dir_builder_options?.is_spa ??
    false;
  const custom_caddyfile =
    serviceBuilderChange?.new_value.options?.custom_caddyfile ??
    service.static_dir_builder_options?.custom_caddyfile;
  const not_found_page =
    serviceBuilderChange?.new_value.options?.not_found_page ??
    service.static_dir_builder_options?.not_found_page;
  const index_page =
    serviceBuilderChange?.new_value.options?.index_page ??
    service.static_dir_builder_options?.index_page ??
    "./index.html";
  const generated_caddyfile =
    serviceBuilderChange?.new_value.options?.generated_caddyfile ??
    service.static_dir_builder_options?.generated_caddyfile ??
    "# this file is read-only";

  const [isSpaChecked, setIsSpaChecked] = React.useState(is_spa);
  const [accordionValue, setAccordionValue] = React.useState("");

  const errors = getFormErrorsFromResponseData(data?.errors);

  const builder_description_map = {
    DOCKERFILE: {
      title: "Dockerfile",
      description: "Build your app using a Dockerfile"
    },
    STATIC_DIR: {
      title: "Static directory",
      description: "Deploy a simple HTML/CSS/JS website"
    }
  } satisfies Record<ServiceBuilder, { title: string; description: string }>;

  return (
    <div className="w-full max-w-4xl">
      <fetcher.Form
        method="post"
        className="flex flex-col gap-4 w-full"
        ref={formRef}
      >
        <input type="hidden" name="change_field" value="builder" />
        <input type="hidden" name="change_type" value="UPDATE" />
        <input
          type="hidden"
          name="change_id"
          value={serviceBuilderChange?.id}
        />
        <input type="hidden" name="builder" value={serviceBuilder} />

        <Accordion
          type="single"
          collapsible
          value={accordionValue}
          onValueChange={setAccordionValue}
        >
          <AccordionItem
            value="builder"
            className="border-none"
            disabled={!!serviceBuilderChange}
          >
            <AccordionTrigger
              className={cn(
                "w-full px-3 bg-muted rounded-md gap-2 flex items-center justify-between text-start",
                "data-[state=open]:rounded-b-none [&[data-state=open]_svg]:rotate-90 pr-4",
                {
                  "dark:bg-secondary-foreground bg-secondary/60 ":
                    !!serviceBuilderChange
                }
              )}
            >
              <div className="flex flex-col gap-2 items-start">
                <div className="inline-flex gap-2 items-center flex-wrap">
                  <p>{builder_description_map[serviceBuilder].title}</p>
                </div>

                <small className="inline-flex gap-2 items-center">
                  <span className="text-grey">
                    {builder_description_map[serviceBuilder].description}
                  </span>
                </small>
              </div>

              <ChevronRightIcon size={20} className="text-grey" />
            </AccordionTrigger>
            <AccordionContent className="border-border border-x border-b rounded-b-md p-4 mb-4">
              <RadioGroup
                value={serviceBuilder}
                onValueChange={(value) =>
                  setServiceBuilder(value as ServiceBuilder)
                }
              >
                <div className="flex items-center space-x-2">
                  <RadioGroupItem
                    value="NIXPACKS"
                    id="nixpacks-builder"
                    className="peer"
                    disabled
                  />
                  <Label
                    htmlFor="nixpacks-builder"
                    className="peer-disabled:text-grey"
                  >
                    <span>Nixpacks</span>
                  </Label>
                  <TooltipProvider>
                    <Tooltip delayDuration={0}>
                      <TooltipTrigger>
                        <InfoIcon size={15} className="text-grey" />
                      </TooltipTrigger>
                      <TooltipContent className="max-w-64 dark:bg-card">
                        <em className="text-link">Coming very soon</em> --
                        Automatically detect your stack and generate a
                        Dockerfile
                      </TooltipContent>
                    </Tooltip>
                  </TooltipProvider>
                </div>
                <div className="flex items-center space-x-2">
                  <RadioGroupItem value="DOCKERFILE" id="dockerfile-builder" />
                  <Label htmlFor="dockerfile-builder">
                    {builder_description_map["DOCKERFILE"].title}
                  </Label>
                  <TooltipProvider>
                    <Tooltip delayDuration={0}>
                      <TooltipTrigger>
                        <InfoIcon size={15} className="text-grey" />
                      </TooltipTrigger>
                      <TooltipContent className="max-w-64 dark:bg-card">
                        {builder_description_map["DOCKERFILE"].description}
                      </TooltipContent>
                    </Tooltip>
                  </TooltipProvider>
                </div>

                <div className="flex items-center space-x-2">
                  <RadioGroupItem
                    value="STATIC_DIR"
                    id="static-builder"
                    className="peer"
                  />
                  <Label
                    htmlFor="static-builder"
                    className="peer-disabled:text-grey inline-flex gap-1 items-center"
                  >
                    <span>{builder_description_map["STATIC_DIR"].title}</span>
                  </Label>
                  <TooltipProvider>
                    <Tooltip delayDuration={0}>
                      <TooltipTrigger>
                        <InfoIcon size={15} className="text-grey" />
                      </TooltipTrigger>
                      <TooltipContent className="max-w-64 dark:bg-card">
                        {builder_description_map["STATIC_DIR"].description}
                      </TooltipContent>
                    </Tooltip>
                  </TooltipProvider>
                </div>
              </RadioGroup>
            </AccordionContent>
          </AccordionItem>
        </Accordion>

        {serviceBuilder === "DOCKERFILE" && (
          <>
            <FieldSet
              name="build_context_dir"
              className="flex flex-col gap-1.5 flex-1"
              required
              errors={errors.new_value?.build_context_dir}
            >
              <FieldSetLabel className=" inline-flex items-center gap-0.5">
                Build context directory&nbsp;
                <TooltipProvider>
                  <Tooltip delayDuration={0}>
                    <TooltipTrigger>
                      <InfoIcon size={15} />
                    </TooltipTrigger>
                    <TooltipContent className="max-w-64">
                      Specify the directory to build relative to the root the
                      repository
                    </TooltipContent>
                  </Tooltip>
                </TooltipProvider>
              </FieldSetLabel>
              <div className="relative">
                <FieldSetInput
                  disabled={serviceBuilderChange !== undefined}
                  placeholder="ex: ./apps/web"
                  defaultValue={build_context_dir}
                  className={cn(
                    "disabled:bg-secondary/60",
                    "dark:disabled:bg-secondary-foreground",
                    "disabled:border-transparent disabled:opacity-100"
                  )}
                />
              </div>
            </FieldSet>

            <FieldSet
              name="dockerfile_path"
              className="flex flex-col gap-1.5 flex-1"
              required
              errors={errors.new_value?.dockerfile_path}
            >
              <FieldSetLabel className="  inline-flex items-center gap-0.5">
                Dockerfile location&nbsp;
                <TooltipProvider>
                  <Tooltip delayDuration={0}>
                    <TooltipTrigger>
                      <InfoIcon size={15} />
                    </TooltipTrigger>
                    <TooltipContent className="max-w-64">
                      Relative to the root of the repository
                    </TooltipContent>
                  </Tooltip>
                </TooltipProvider>
              </FieldSetLabel>
              <div className="relative">
                <FieldSetInput
                  disabled={serviceBuilderChange !== undefined}
                  placeholder="ex: ./apps/web/Dockerfile"
                  defaultValue={dockerfile_path}
                  className={cn(
                    "disabled:bg-secondary/60",
                    "dark:disabled:bg-secondary-foreground",
                    "disabled:border-transparent disabled:opacity-100"
                  )}
                />
              </div>
            </FieldSet>

            <FieldSet
              name="build_stage_target"
              className="flex flex-col gap-1.5 flex-1"
              errors={errors.new_value?.build_stage_target}
            >
              <FieldSetLabel className=" inline-flex items-center gap-0.5">
                Docker build stage target&nbsp;
                <TooltipProvider>
                  <Tooltip delayDuration={0}>
                    <TooltipTrigger>
                      <InfoIcon size={15} />
                    </TooltipTrigger>
                    <TooltipContent className="max-w-64">
                      Useful if you have a multi-staged dockerfile
                    </TooltipContent>
                  </Tooltip>
                </TooltipProvider>
              </FieldSetLabel>
              <div className="relative">
                <FieldSetInput
                  disabled={serviceBuilderChange !== undefined}
                  placeholder={
                    serviceBuilderChange && !build_stage_target
                      ? "<empty>"
                      : "ex: builder"
                  }
                  defaultValue={build_stage_target ?? ""}
                  className={cn(
                    "disabled:placeholder-shown:font-mono disabled:bg-secondary/60",
                    "dark:disabled:bg-secondary-foreground",
                    "disabled:border-transparent disabled:opacity-100"
                  )}
                />
              </div>
            </FieldSet>
          </>
        )}

        {serviceBuilder === "STATIC_DIR" && (
          <>
            <FieldSet
              name="base_directory"
              className="flex flex-col gap-1.5 flex-1"
              required
              errors={errors.new_value?.base_directory}
            >
              <FieldSetLabel className=" inline-flex items-center gap-0.5">
                Publish directory
              </FieldSetLabel>
              <div className="relative">
                <FieldSetInput
                  disabled={serviceBuilderChange !== undefined}
                  placeholder="ex: ./public"
                  defaultValue={base_directory}
                  className={cn(
                    "disabled:bg-secondary/60",
                    "dark:disabled:bg-secondary-foreground",
                    "disabled:border-transparent disabled:opacity-100"
                  )}
                />
              </div>
            </FieldSet>
            {!isSpaChecked && (
              <FieldSet
                name="not_found_page"
                className="flex flex-col gap-1.5 flex-1"
                errors={errors.new_value?.not_found_page}
              >
                <FieldSetLabel className=" inline-flex items-center gap-0.5">
                  Not found page &nbsp;
                  <TooltipProvider>
                    <Tooltip delayDuration={0}>
                      <TooltipTrigger>
                        <InfoIcon size={15} />
                      </TooltipTrigger>
                      <TooltipContent className="max-w-64">
                        Specify a custom file for 404 errors
                      </TooltipContent>
                    </Tooltip>
                  </TooltipProvider>
                </FieldSetLabel>
                <div className="relative">
                  <FieldSetInput
                    disabled={serviceBuilderChange !== undefined}
                    placeholder="ex: ./404.html"
                    defaultValue={not_found_page}
                    className={cn(
                      "disabled:bg-secondary/60",
                      "dark:disabled:bg-secondary-foreground",
                      "disabled:border-transparent disabled:opacity-100"
                    )}
                  />
                </div>
              </FieldSet>
            )}
            <FieldSet
              name="is_spa"
              errors={errors.new_value?.is_spa}
              className="flex-1 inline-flex gap-2 flex-col"
            >
              <div className="inline-flex gap-2 items-center">
                <FieldSetCheckbox
                  defaultChecked={isSpaChecked}
                  disabled={serviceBuilderChange !== undefined}
                  onCheckedChange={(state) => setIsSpaChecked(Boolean(state))}
                />

                <FieldSetLabel className="inline-flex gap-1 items-center">
                  Is this a Single Page Application (SPA) ?
                </FieldSetLabel>
              </div>
            </FieldSet>

            {isSpaChecked && (
              <FieldSet
                name="index_page"
                className="flex flex-col gap-1.5 flex-1"
                errors={errors.new_value?.index_page}
                required
              >
                <FieldSetLabel className=" inline-flex items-center gap-0.5">
                  Index page&nbsp;
                  <TooltipProvider>
                    <Tooltip delayDuration={0}>
                      <TooltipTrigger>
                        <InfoIcon size={15} />
                      </TooltipTrigger>
                      <TooltipContent className="max-w-64">
                        Specify a page to redirect all requests to
                      </TooltipContent>
                    </Tooltip>
                  </TooltipProvider>
                </FieldSetLabel>
                <div className="relative">
                  <FieldSetInput
                    disabled={serviceBuilderChange !== undefined}
                    placeholder="ex: ./index.html"
                    defaultValue={index_page}
                    className={cn(
                      "disabled:bg-secondary/60",
                      "dark:disabled:bg-secondary-foreground",
                      "disabled:border-transparent disabled:opacity-100"
                    )}
                  />
                </div>
              </FieldSet>
            )}

            <label className="text-muted-foreground">Generated Caddyfile</label>
            <div
              className={cn(
                "resize-y h-52 min-h-52 overflow-y-auto overflow-x-clip max-w-full",
                "w-[85dvw] sm:w-[90dvw] md:w-[87dvw] lg:w-[75dvw] xl:w-[855px]"
              )}
            >
              <Editor
                className="w-full h-full max-w-full"
                value={generated_caddyfile}
                theme="vs-dark"
                options={{
                  readOnly: true,
                  minimap: {
                    enabled: false
                  }
                }}
              />
            </div>
          </>
        )}

        <div className="flex items-center gap-4">
          {serviceBuilderChange !== undefined ? (
            <SubmitButton
              isPending={isPending}
              variant="outline"
              name="intent"
              value="cancel-service-change"
            >
              {isPending ? (
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
          ) : (
            <>
              <SubmitButton
                isPending={isPending}
                variant="secondary"
                name="intent"
                value="request-service-change"
              >
                {isPending ? (
                  <>
                    <LoaderIcon className="animate-spin" size={15} />
                    <span>Updating ...</span>
                  </>
                ) : (
                  <>
                    <CheckIcon size={15} className="flex-none" />
                    <span>Update</span>
                  </>
                )}
              </SubmitButton>
              <Button
                variant="outline"
                onClick={() => {
                  setAccordionValue("");
                  setServiceBuilder(service.builder || "DOCKERFILE");
                  setIsSpaChecked(
                    service.static_dir_builder_options?.is_spa ?? false
                  );
                  reset();
                }}
                type="reset"
              >
                Reset
              </Button>
            </>
          )}
        </div>
      </fetcher.Form>
    </div>
  );
}
