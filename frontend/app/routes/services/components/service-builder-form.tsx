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
import { BUILDER_DESCRIPTION_MAP } from "~/lib/constants";
import type { Service } from "~/lib/queries";
import { cn, getFormErrorsFromResponseData } from "~/lib/utils";
import {
  useFetcherWithCallbacks,
  useServiceQuery
} from "~/routes/services/settings/service-settings";

export type ServiceBuilderFormProps = {
  service_slug: string;
  project_slug: string;
  env_slug: string;
};

type ServiceBuilder = Exclude<NonNullable<Service["builder"]>, "">;
type ServiceBuilderChangeNewValue = {
  builder: ServiceBuilder;
  options: Service["dockerfile_builder_options"] &
    Service["static_dir_builder_options"] &
    Service["nixpacks_builder_options"];
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
          newBuilder === null ? null : (newBuilder ?? srv.builder);

        setServiceBuilder(updatedBuilder ?? "NIXPACKS");
        setAccordionValue("");
        setIsStaticSpaChecked(
          serviceBuilderChange?.new_value.options?.is_spa ??
            srv.static_dir_builder_options?.is_spa ??
            false
        );

        setIsNixpacksSpaChecked(
          serviceBuilderChange?.new_value.options?.is_spa ??
            srv.nixpacks_builder_options?.is_spa ??
            false
        );
        setIsNixpacksStaticChecked(
          serviceBuilderChange?.new_value.options?.is_static ??
            srv.nixpacks_builder_options?.is_static ??
            false
        );

        setIsRailpackSpaChecked(
          serviceBuilderChange?.new_value.options?.is_spa ??
            srv.railpack_builder_options?.is_spa ??
            false
        );
        setIsRailpackStaticChecked(
          serviceBuilderChange?.new_value.options?.is_static ??
            srv.railpack_builder_options?.is_static ??
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

  const [serviceBuilder, setServiceBuilder] = React.useState<ServiceBuilder>(
    serviceBuilderChange?.new_value.builder ?? (service.builder || "NIXPACKS")
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
  const is_static_spa =
    serviceBuilderChange?.new_value.options?.is_spa ??
    service.static_dir_builder_options?.is_spa ??
    false;
  const static_publish_directory =
    serviceBuilderChange?.new_value.options?.publish_directory ??
    service.static_dir_builder_options?.publish_directory ??
    "./";
  const static_not_found_page =
    serviceBuilderChange?.new_value.options?.not_found_page ??
    service.static_dir_builder_options?.not_found_page;
  const static_index_page =
    serviceBuilderChange?.new_value.options?.index_page ??
    service.static_dir_builder_options?.index_page ??
    "./index.html";
  const static_generated_caddyfile =
    serviceBuilderChange?.new_value.options?.generated_caddyfile ??
    service.static_dir_builder_options?.generated_caddyfile ??
    "# this file is read-only";

  const new_custom_build_cmd =
    serviceBuilderChange?.new_value.options?.custom_build_command;
  const new_custom_start_cmd =
    serviceBuilderChange?.new_value.options?.custom_start_command;
  const new_custom_install_cmd =
    serviceBuilderChange?.new_value.options?.custom_install_command;

  // nixpacks builder
  const build_directory =
    serviceBuilderChange?.new_value.options?.build_directory ??
    service.nixpacks_builder_options?.build_directory ??
    "./";

  const custom_build_command =
    new_custom_build_cmd === null
      ? new_custom_build_cmd
      : (new_custom_build_cmd ??
        service.nixpacks_builder_options?.custom_build_command);

  const custom_install_command =
    new_custom_install_cmd === null
      ? new_custom_install_cmd
      : (new_custom_install_cmd ??
        service.nixpacks_builder_options?.custom_install_command);

  const custom_start_command =
    new_custom_start_cmd === null
      ? new_custom_start_cmd
      : (new_custom_start_cmd ??
        service.nixpacks_builder_options?.custom_start_command);

  const is_static =
    serviceBuilderChange?.new_value.options?.is_static ??
    service.nixpacks_builder_options?.is_static ??
    false;
  const is_nixpacks_spa =
    serviceBuilderChange?.new_value.options?.is_spa ??
    service.nixpacks_builder_options?.is_spa ??
    false;
  const nixpacks_publish_directory =
    serviceBuilderChange?.new_value.options?.publish_directory ??
    service.nixpacks_builder_options?.publish_directory ??
    "./dist";
  const nixpacks_not_found_page =
    serviceBuilderChange?.new_value.options?.not_found_page ??
    service.nixpacks_builder_options?.not_found_page ??
    "./404.html";
  const nixpacks_index_page =
    serviceBuilderChange?.new_value.options?.index_page ??
    service.nixpacks_builder_options?.index_page ??
    "./index.html";
  const nixpacks_generated_caddyfile =
    serviceBuilderChange?.new_value.options?.generated_caddyfile ??
    service.nixpacks_builder_options?.generated_caddyfile ??
    "# this file is read-only";

  // railpack builder
  const railpack_build_directory =
    serviceBuilderChange?.new_value.options?.build_directory ??
    service.railpack_builder_options?.build_directory ??
    "./";

  const railpack_custom_build_command =
    new_custom_build_cmd === null
      ? new_custom_build_cmd
      : (new_custom_build_cmd ??
        service.railpack_builder_options?.custom_build_command);

  const railpack_custom_install_command =
    new_custom_install_cmd === null
      ? new_custom_install_cmd
      : (new_custom_install_cmd ??
        service.railpack_builder_options?.custom_install_command);

  const railpack_custom_start_command =
    new_custom_start_cmd === null
      ? new_custom_start_cmd
      : (new_custom_start_cmd ??
        service.railpack_builder_options?.custom_start_command);

  const is_railpack_static =
    serviceBuilderChange?.new_value.options?.is_static ??
    service.railpack_builder_options?.is_static ??
    false;
  const is_railpack_spa =
    serviceBuilderChange?.new_value.options?.is_spa ??
    service.railpack_builder_options?.is_spa ??
    false;
  const railpack_publish_directory =
    serviceBuilderChange?.new_value.options?.publish_directory ??
    service.railpack_builder_options?.publish_directory ??
    "./dist";
  const railpack_not_found_page =
    serviceBuilderChange?.new_value.options?.not_found_page ??
    service.railpack_builder_options?.not_found_page ??
    "./404.html";
  const railpack_index_page =
    serviceBuilderChange?.new_value.options?.index_page ??
    service.railpack_builder_options?.index_page ??
    "./index.html";
  const railpack_generated_caddyfile =
    serviceBuilderChange?.new_value.options?.generated_caddyfile ??
    service.railpack_builder_options?.generated_caddyfile ??
    "# this file is read-only";

  const [isStaticSpaChecked, setIsStaticSpaChecked] =
    React.useState(is_static_spa);

  const [isNixpacksStaticChecked, setIsNixpacksStaticChecked] =
    React.useState(is_static);
  const [isNixpacksSpaChecked, setIsNixpacksSpaChecked] =
    React.useState(is_nixpacks_spa);

  const [isRailpackStaticChecked, setIsRailpackStaticChecked] =
    React.useState(is_railpack_static);
  const [isRailpackSpaChecked, setIsRailpackSpaChecked] =
    React.useState(is_railpack_spa);

  const [accordionValue, setAccordionValue] = React.useState("");

  const errors = getFormErrorsFromResponseData(data?.errors);

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
                  <p>
                    {BUILDER_DESCRIPTION_MAP[serviceBuilder].title}
                    {serviceBuilder === "RAILPACK" && (
                      <sup className="text-link">bêta</sup>
                    )}
                  </p>
                </div>

                <small className="inline-flex gap-2 items-center">
                  <span className="text-grey">
                    {BUILDER_DESCRIPTION_MAP[serviceBuilder].description}
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
                  />
                  <Label
                    htmlFor="nixpacks-builder"
                    className="peer-disabled:text-grey"
                  >
                    <span>{BUILDER_DESCRIPTION_MAP["NIXPACKS"].title}</span>
                  </Label>
                  <TooltipProvider>
                    <Tooltip delayDuration={0}>
                      <TooltipTrigger>
                        <InfoIcon size={15} className="text-grey" />
                      </TooltipTrigger>
                      <TooltipContent className="max-w-64 dark:bg-card">
                        {BUILDER_DESCRIPTION_MAP["NIXPACKS"].description}
                      </TooltipContent>
                    </Tooltip>
                  </TooltipProvider>
                </div>
                <div className="flex items-center space-x-2">
                  <RadioGroupItem
                    value="RAILPACK"
                    id="railback-builder"
                    className="peer"
                  />
                  <Label
                    htmlFor="railback-builder"
                    className="peer-disabled:text-grey"
                  >
                    <span>{BUILDER_DESCRIPTION_MAP["RAILPACK"].title}</span>
                    <sup className="text-link text-sm">bêta</sup>
                  </Label>
                  <TooltipProvider>
                    <Tooltip delayDuration={0}>
                      <TooltipTrigger>
                        <InfoIcon size={15} className="text-grey" />
                      </TooltipTrigger>
                      <TooltipContent className="max-w-64 dark:bg-card">
                        {BUILDER_DESCRIPTION_MAP["RAILPACK"].description}
                      </TooltipContent>
                    </Tooltip>
                  </TooltipProvider>
                </div>
                <div className="flex items-center space-x-2">
                  <RadioGroupItem value="DOCKERFILE" id="dockerfile-builder" />
                  <Label htmlFor="dockerfile-builder">
                    {BUILDER_DESCRIPTION_MAP["DOCKERFILE"].title}
                  </Label>
                  <TooltipProvider>
                    <Tooltip delayDuration={0}>
                      <TooltipTrigger>
                        <InfoIcon size={15} className="text-grey" />
                      </TooltipTrigger>
                      <TooltipContent className="max-w-64 dark:bg-card">
                        {BUILDER_DESCRIPTION_MAP["DOCKERFILE"].description}
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
                    <span>{BUILDER_DESCRIPTION_MAP["STATIC_DIR"].title}</span>
                  </Label>
                  <TooltipProvider>
                    <Tooltip delayDuration={0}>
                      <TooltipTrigger>
                        <InfoIcon size={15} className="text-grey" />
                      </TooltipTrigger>
                      <TooltipContent className="max-w-64 dark:bg-card">
                        {BUILDER_DESCRIPTION_MAP["STATIC_DIR"].description}
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
              name="publish_directory"
              className="flex flex-col gap-1.5 flex-1"
              required
              errors={errors.new_value?.publish_directory}
            >
              <FieldSetLabel className=" inline-flex items-center gap-0.5">
                Publish directory
              </FieldSetLabel>
              <div className="relative">
                <FieldSetInput
                  placeholder="ex: ./public"
                  defaultValue={static_publish_directory}
                  disabled={serviceBuilderChange !== undefined}
                  className={cn(
                    "disabled:bg-secondary/60",
                    "dark:disabled:bg-secondary-foreground",
                    "disabled:border-transparent disabled:opacity-100"
                  )}
                />
              </div>
            </FieldSet>

            {!isStaticSpaChecked && (
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
                        Specify a custom file for 404 errors. This path is
                        relative to the publish directory.
                      </TooltipContent>
                    </Tooltip>
                  </TooltipProvider>
                </FieldSetLabel>
                <div className="relative">
                  <FieldSetInput
                    disabled={serviceBuilderChange !== undefined}
                    placeholder="ex: ./404.html"
                    defaultValue={static_not_found_page}
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
                  checked={isStaticSpaChecked}
                  disabled={serviceBuilderChange !== undefined}
                  onCheckedChange={(state) =>
                    setIsStaticSpaChecked(Boolean(state))
                  }
                />

                <FieldSetLabel className="inline-flex gap-1 items-center">
                  Is this a Single Page Application (SPA) ?
                </FieldSetLabel>
              </div>
            </FieldSet>
            {isStaticSpaChecked && (
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
                        Specify a page to redirect all requests to. This path is
                        relative to the publish directory.
                      </TooltipContent>
                    </Tooltip>
                  </TooltipProvider>
                </FieldSetLabel>
                <div className="relative">
                  <FieldSetInput
                    disabled={serviceBuilderChange !== undefined}
                    placeholder="ex: ./index.html"
                    defaultValue={static_index_page}
                    className={cn(
                      "disabled:bg-secondary/60",
                      "dark:disabled:bg-secondary-foreground",
                      "disabled:border-transparent disabled:opacity-100"
                    )}
                  />
                </div>
              </FieldSet>
            )}
            <span className="text-muted-foreground inline-flex items-center">
              Generated Caddyfile&nbsp;
              <TooltipProvider>
                <Tooltip delayDuration={0}>
                  <TooltipTrigger>
                    <InfoIcon size={15} />
                  </TooltipTrigger>
                  <TooltipContent className="max-w-64">
                    You can overwrite this by providing a file named&nbsp;
                    <span className="text-link">Caddyfile</span> at the root of
                    your repository.
                  </TooltipContent>
                </Tooltip>
              </TooltipProvider>
            </span>
            <div
              className={cn(
                "resize-y h-52 min-h-52 overflow-y-auto overflow-x-clip max-w-full",
                "w-[85dvw] sm:w-[90dvw] md:w-[87dvw] lg:w-[75dvw] xl:w-[855px]"
              )}
            >
              <Editor
                className="w-full h-full max-w-full"
                value={static_generated_caddyfile}
                theme="vs-dark"
                language="ini"
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

        {serviceBuilder === "NIXPACKS" && (
          <>
            <FieldSet
              name="build_directory"
              className="flex flex-col gap-1.5 flex-1"
              required
              errors={errors.new_value?.build_directory}
            >
              <FieldSetLabel className="dark:text-card-foreground inline-flex items-center gap-0.5">
                Build directory&nbsp;
                <TooltipProvider>
                  <Tooltip delayDuration={0}>
                    <TooltipTrigger>
                      <InfoIcon size={15} />
                    </TooltipTrigger>
                    <TooltipContent className="max-w-64">
                      Specify the directory to build. Relative to the root the
                      repository
                    </TooltipContent>
                  </Tooltip>
                </TooltipProvider>
              </FieldSetLabel>
              <div className="relative">
                <FieldSetInput
                  placeholder="ex: ./apps/web"
                  disabled={serviceBuilderChange !== undefined}
                  className={cn(
                    "disabled:bg-secondary/60",
                    "dark:disabled:bg-secondary-foreground",
                    "disabled:border-transparent disabled:opacity-100"
                  )}
                  defaultValue={build_directory}
                />
              </div>
            </FieldSet>

            <FieldSet
              name="custom_install_command"
              className="flex flex-col gap-1.5 flex-1"
              errors={errors.new_value?.custom_install_command}
            >
              <FieldSetLabel className="dark:text-card-foreground inline-flex items-center gap-0.5">
                Custom install command&nbsp;
                <TooltipProvider>
                  <Tooltip delayDuration={0}>
                    <TooltipTrigger>
                      <InfoIcon size={15} />
                    </TooltipTrigger>
                    <TooltipContent className="max-w-64">
                      If you are modifying this, you should probably add a&nbsp;
                      <span className="text-link">nixpacks.toml</span>&nbsp;at
                      the same level as the build directory.
                    </TooltipContent>
                  </Tooltip>
                </TooltipProvider>
              </FieldSetLabel>
              <div className="relative">
                <FieldSetInput
                  placeholder="ex: pnpm run install"
                  disabled={serviceBuilderChange !== undefined}
                  className={cn(
                    "disabled:bg-secondary/60",
                    "dark:disabled:bg-secondary-foreground",
                    "disabled:border-transparent disabled:opacity-100"
                  )}
                  defaultValue={custom_install_command}
                />
              </div>
            </FieldSet>

            <FieldSet
              name="custom_build_command"
              className="flex flex-col gap-1.5 flex-1"
              errors={errors.new_value?.custom_build_command}
            >
              <FieldSetLabel className="dark:text-card-foreground inline-flex items-center gap-0.5">
                Custom build command&nbsp;
                <TooltipProvider>
                  <Tooltip delayDuration={0}>
                    <TooltipTrigger>
                      <InfoIcon size={15} />
                    </TooltipTrigger>
                    <TooltipContent className="max-w-64">
                      If you are modifying this, you should probably add a&nbsp;
                      <span className="text-link">nixpacks.toml</span>&nbsp;at
                      the same level as the build directory.
                    </TooltipContent>
                  </Tooltip>
                </TooltipProvider>
              </FieldSetLabel>
              <div className="relative">
                <FieldSetInput
                  placeholder="ex: pnpm run build"
                  disabled={serviceBuilderChange !== undefined}
                  className={cn(
                    "disabled:bg-secondary/60",
                    "dark:disabled:bg-secondary-foreground",
                    "disabled:border-transparent disabled:opacity-100"
                  )}
                  defaultValue={custom_build_command}
                />
              </div>
            </FieldSet>

            {!isNixpacksStaticChecked && (
              <FieldSet
                name="custom_start_command"
                className="flex flex-col gap-1.5 flex-1"
                errors={errors.new_value?.custom_start_command}
              >
                <FieldSetLabel className="dark:text-card-foreground inline-flex items-center gap-0.5">
                  Custom start command&nbsp;
                  <TooltipProvider>
                    <Tooltip delayDuration={0}>
                      <TooltipTrigger>
                        <InfoIcon size={15} />
                      </TooltipTrigger>
                      <TooltipContent className="max-w-64">
                        If you are modifying this, you should probably add
                        a&nbsp;
                        <span className="text-link">nixpacks.toml</span>&nbsp;
                        at the same level as the build directory.
                      </TooltipContent>
                    </Tooltip>
                  </TooltipProvider>
                </FieldSetLabel>
                <div className="relative">
                  <FieldSetInput
                    disabled={serviceBuilderChange !== undefined}
                    className={cn(
                      "disabled:bg-secondary/60",
                      "dark:disabled:bg-secondary-foreground",
                      "disabled:border-transparent disabled:opacity-100"
                    )}
                    placeholder="ex: pnpm run start"
                    defaultValue={custom_start_command}
                  />
                </div>
              </FieldSet>
            )}

            <FieldSet
              name="is_static"
              errors={errors.new_value?.is_static}
              className="flex-1 inline-flex gap-2 flex-col"
            >
              <div className="inline-flex gap-2 items-center">
                <FieldSetCheckbox
                  checked={isNixpacksStaticChecked}
                  disabled={serviceBuilderChange !== undefined}
                  onCheckedChange={(state) =>
                    setIsNixpacksStaticChecked(Boolean(state))
                  }
                />

                <FieldSetLabel className="inline-flex gap-1 items-center">
                  Is this a static website ?&nbsp;
                  <TooltipProvider>
                    <Tooltip delayDuration={0}>
                      <TooltipTrigger>
                        <InfoIcon size={15} />
                      </TooltipTrigger>
                      <TooltipContent className="max-w-64">
                        If your application is a static site or the final build
                        assets should be served as a static site, enable this.
                      </TooltipContent>
                    </Tooltip>
                  </TooltipProvider>
                </FieldSetLabel>
              </div>
            </FieldSet>

            {isNixpacksStaticChecked && (
              <>
                <FieldSet
                  name="is_spa"
                  errors={errors.new_value?.is_spa}
                  className="flex-1 inline-flex gap-2 flex-col"
                >
                  <div className="inline-flex gap-2 items-center">
                    <FieldSetCheckbox
                      checked={isNixpacksSpaChecked}
                      disabled={serviceBuilderChange !== undefined}
                      onCheckedChange={(state) =>
                        setIsNixpacksSpaChecked(Boolean(state))
                      }
                    />

                    <FieldSetLabel className="inline-flex gap-1 items-center">
                      Is this a Single Page Application (SPA) ?
                    </FieldSetLabel>
                  </div>
                </FieldSet>

                <FieldSet
                  name="publish_directory"
                  className="flex flex-col gap-1.5 flex-1"
                  required
                  errors={errors.new_value?.publish_directory}
                >
                  <FieldSetLabel className=" inline-flex items-center gap-0.5">
                    Publish directory&nbsp;
                    <TooltipProvider>
                      <Tooltip delayDuration={0}>
                        <TooltipTrigger>
                          <InfoIcon size={15} />
                        </TooltipTrigger>
                        <TooltipContent className="max-w-64">
                          If there is a build process involved, please specify
                          the publish directory for the build assets.
                        </TooltipContent>
                      </Tooltip>
                    </TooltipProvider>
                  </FieldSetLabel>
                  <div className="relative">
                    <FieldSetInput
                      placeholder="ex: ./public"
                      defaultValue={nixpacks_publish_directory}
                      disabled={serviceBuilderChange !== undefined}
                      className={cn(
                        "disabled:bg-secondary/60",
                        "dark:disabled:bg-secondary-foreground",
                        "disabled:border-transparent disabled:opacity-100"
                      )}
                    />
                  </div>
                </FieldSet>

                {!isNixpacksSpaChecked ? (
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
                            Specify a custom file for 404 errors. This path is
                            relative to the publish directory.
                          </TooltipContent>
                        </Tooltip>
                      </TooltipProvider>
                    </FieldSetLabel>
                    <div className="relative">
                      <FieldSetInput
                        disabled={serviceBuilderChange !== undefined}
                        placeholder="ex: ./404.html"
                        defaultValue={nixpacks_not_found_page}
                        className={cn(
                          "disabled:bg-secondary/60",
                          "dark:disabled:bg-secondary-foreground",
                          "disabled:border-transparent disabled:opacity-100"
                        )}
                      />
                    </div>
                  </FieldSet>
                ) : (
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
                            Specify a page to redirect all requests to. This
                            path is relative to the publish directory.
                          </TooltipContent>
                        </Tooltip>
                      </TooltipProvider>
                    </FieldSetLabel>
                    <div className="relative">
                      <FieldSetInput
                        disabled={serviceBuilderChange !== undefined}
                        placeholder="ex: ./index.html"
                        defaultValue={nixpacks_index_page}
                        className={cn(
                          "disabled:bg-secondary/60",
                          "dark:disabled:bg-secondary-foreground",
                          "disabled:border-transparent disabled:opacity-100"
                        )}
                      />
                    </div>
                  </FieldSet>
                )}

                <span className="text-muted-foreground inline-flex items-center">
                  Generated Caddyfile&nbsp;
                  <TooltipProvider>
                    <Tooltip delayDuration={0}>
                      <TooltipTrigger>
                        <InfoIcon size={15} />
                      </TooltipTrigger>
                      <TooltipContent className="max-w-64">
                        You can overwrite this by providing a file named&nbsp;
                        <span className="text-link">Caddyfile</span> at the same
                        level as the build directory.
                      </TooltipContent>
                    </Tooltip>
                  </TooltipProvider>
                </span>
                <div
                  className={cn(
                    "resize-y h-52 min-h-52 overflow-y-auto overflow-x-clip max-w-full",
                    "w-[85dvw] sm:w-[90dvw] md:w-[87dvw] lg:w-[75dvw] xl:w-[855px]"
                  )}
                >
                  <Editor
                    className="w-full h-full max-w-full"
                    value={nixpacks_generated_caddyfile}
                    theme="vs-dark"
                    language="ini"
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
          </>
        )}

        {serviceBuilder === "RAILPACK" && (
          <>
            <FieldSet
              name="build_directory"
              className="flex flex-col gap-1.5 flex-1"
              required
              errors={errors.new_value?.build_directory}
            >
              <FieldSetLabel className="dark:text-card-foreground inline-flex items-center gap-0.5">
                Build directory&nbsp;
                <TooltipProvider>
                  <Tooltip delayDuration={0}>
                    <TooltipTrigger>
                      <InfoIcon size={15} />
                    </TooltipTrigger>
                    <TooltipContent className="max-w-64">
                      Specify the directory to build. Relative to the root of
                      the repository
                    </TooltipContent>
                  </Tooltip>
                </TooltipProvider>
              </FieldSetLabel>
              <div className="relative">
                <FieldSetInput
                  placeholder="ex: ./apps/web"
                  disabled={serviceBuilderChange !== undefined}
                  className={cn(
                    "disabled:bg-secondary/60",
                    "dark:disabled:bg-secondary-foreground",
                    "disabled:border-transparent disabled:opacity-100"
                  )}
                  defaultValue={railpack_build_directory}
                />
              </div>
            </FieldSet>

            <FieldSet
              name="custom_install_command"
              className="flex flex-col gap-1.5 flex-1"
              errors={errors.new_value?.custom_install_command}
            >
              <FieldSetLabel className="dark:text-card-foreground inline-flex items-center gap-0.5">
                Custom install command
              </FieldSetLabel>
              <div className="relative">
                <FieldSetInput
                  placeholder={
                    serviceBuilderChange !== undefined
                      ? "<empty>"
                      : "ex: pnpm run install"
                  }
                  disabled={serviceBuilderChange !== undefined}
                  className={cn(
                    "disabled:placeholder-shown:font-mono",
                    "disabled:bg-secondary/60",
                    "dark:disabled:bg-secondary-foreground",
                    "disabled:border-transparent disabled:opacity-100"
                  )}
                  defaultValue={railpack_custom_install_command}
                />
              </div>
            </FieldSet>

            <FieldSet
              name="custom_build_command"
              className="flex flex-col gap-1.5 flex-1"
              errors={errors.new_value?.custom_build_command}
            >
              <FieldSetLabel className="dark:text-card-foreground inline-flex items-center gap-0.5">
                Custom build command
              </FieldSetLabel>
              <div className="relative">
                <FieldSetInput
                  placeholder={
                    serviceBuilderChange !== undefined
                      ? "<empty>"
                      : "ex: pnpm run build"
                  }
                  disabled={serviceBuilderChange !== undefined}
                  className={cn(
                    "disabled:placeholder-shown:font-mono",
                    "disabled:bg-secondary/60",
                    "dark:disabled:bg-secondary-foreground",
                    "disabled:border-transparent disabled:opacity-100"
                  )}
                  defaultValue={railpack_custom_build_command}
                />
              </div>
            </FieldSet>

            {!isRailpackStaticChecked && (
              <FieldSet
                name="custom_start_command"
                className="flex flex-col gap-1.5 flex-1"
                errors={errors.new_value?.custom_start_command}
              >
                <FieldSetLabel className="dark:text-card-foreground inline-flex items-center gap-0.5">
                  Custom start command
                </FieldSetLabel>
                <div className="relative">
                  <FieldSetInput
                    placeholder={
                      serviceBuilderChange !== undefined
                        ? "<empty>"
                        : "ex: pnpm run start"
                    }
                    disabled={serviceBuilderChange !== undefined}
                    className={cn(
                      "disabled:placeholder-shown:font-mono",
                      "disabled:bg-secondary/60",
                      "dark:disabled:bg-secondary-foreground",
                      "disabled:border-transparent disabled:opacity-100"
                    )}
                    defaultValue={railpack_custom_start_command}
                  />
                </div>
              </FieldSet>
            )}

            <FieldSet
              name="is_static"
              errors={errors.new_value?.is_static}
              className="flex-1 inline-flex gap-2 flex-col"
            >
              <div className="inline-flex gap-2 items-center">
                <FieldSetCheckbox
                  checked={isRailpackStaticChecked}
                  disabled={serviceBuilderChange !== undefined}
                  onCheckedChange={(state) =>
                    setIsRailpackStaticChecked(Boolean(state))
                  }
                />

                <FieldSetLabel className="inline-flex gap-1 items-center">
                  Is this a static website ?&nbsp;
                  <TooltipProvider>
                    <Tooltip delayDuration={0}>
                      <TooltipTrigger>
                        <InfoIcon size={15} />
                      </TooltipTrigger>
                      <TooltipContent className="max-w-64">
                        If your application is a static site or the final build
                        assets should be served as a static site, enable this.
                      </TooltipContent>
                    </Tooltip>
                  </TooltipProvider>
                </FieldSetLabel>
              </div>
            </FieldSet>

            {isRailpackStaticChecked && (
              <>
                <FieldSet
                  name="is_spa"
                  errors={errors.new_value?.is_spa}
                  className="flex-1 inline-flex gap-2 flex-col"
                >
                  <div className="inline-flex gap-2 items-center">
                    <FieldSetCheckbox
                      checked={isRailpackSpaChecked}
                      disabled={serviceBuilderChange !== undefined}
                      onCheckedChange={(state) =>
                        setIsRailpackSpaChecked(Boolean(state))
                      }
                    />

                    <FieldSetLabel className="inline-flex gap-1 items-center">
                      Is this a Single Page Application (SPA) ?
                    </FieldSetLabel>
                  </div>
                </FieldSet>

                <FieldSet
                  name="publish_directory"
                  className="flex flex-col gap-1.5 flex-1"
                  required
                  errors={errors.new_value?.publish_directory}
                >
                  <FieldSetLabel className=" inline-flex items-center gap-0.5">
                    Publish directory&nbsp;
                    <TooltipProvider>
                      <Tooltip delayDuration={0}>
                        <TooltipTrigger>
                          <InfoIcon size={15} />
                        </TooltipTrigger>
                        <TooltipContent className="max-w-64">
                          If there is a build process involved, please specify
                          the publish directory for the build assets.
                        </TooltipContent>
                      </Tooltip>
                    </TooltipProvider>
                  </FieldSetLabel>
                  <div className="relative">
                    <FieldSetInput
                      placeholder="ex: ./public"
                      defaultValue={railpack_publish_directory}
                      disabled={serviceBuilderChange !== undefined}
                      className={cn(
                        "disabled:bg-secondary/60",
                        "dark:disabled:bg-secondary-foreground",
                        "disabled:border-transparent disabled:opacity-100"
                      )}
                    />
                  </div>
                </FieldSet>

                {!isRailpackSpaChecked ? (
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
                            Specify a custom file for 404 errors. This path is
                            relative to the publish directory.
                          </TooltipContent>
                        </Tooltip>
                      </TooltipProvider>
                    </FieldSetLabel>
                    <div className="relative">
                      <FieldSetInput
                        disabled={serviceBuilderChange !== undefined}
                        placeholder="ex: ./404.html"
                        defaultValue={railpack_not_found_page}
                        className={cn(
                          "disabled:bg-secondary/60",
                          "dark:disabled:bg-secondary-foreground",
                          "disabled:border-transparent disabled:opacity-100"
                        )}
                      />
                    </div>
                  </FieldSet>
                ) : (
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
                            Specify a page to redirect all requests to. This
                            path is relative to the publish directory.
                          </TooltipContent>
                        </Tooltip>
                      </TooltipProvider>
                    </FieldSetLabel>
                    <div className="relative">
                      <FieldSetInput
                        disabled={serviceBuilderChange !== undefined}
                        placeholder="ex: ./index.html"
                        defaultValue={railpack_index_page}
                        className={cn(
                          "disabled:bg-secondary/60",
                          "dark:disabled:bg-secondary-foreground",
                          "disabled:border-transparent disabled:opacity-100"
                        )}
                      />
                    </div>
                  </FieldSet>
                )}

                <span className="text-muted-foreground inline-flex items-center">
                  Generated Caddyfile&nbsp;
                  <TooltipProvider>
                    <Tooltip delayDuration={0}>
                      <TooltipTrigger>
                        <InfoIcon size={15} />
                      </TooltipTrigger>
                      <TooltipContent className="max-w-64">
                        You can overwrite this by providing a file named&nbsp;
                        <span className="text-link">Caddyfile</span> at the same
                        level as the build directory.
                      </TooltipContent>
                    </Tooltip>
                  </TooltipProvider>
                </span>
                <div
                  className={cn(
                    "resize-y h-52 min-h-52 overflow-y-auto overflow-x-clip max-w-full",
                    "w-[85dvw] sm:w-[90dvw] md:w-[87dvw] lg:w-[75dvw] xl:w-[855px]"
                  )}
                >
                  <Editor
                    className="w-full h-full max-w-full"
                    value={railpack_generated_caddyfile}
                    theme="vs-dark"
                    language="ini"
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
                  setServiceBuilder(service.builder || "NIXPACKS");

                  setIsStaticSpaChecked(
                    service.static_dir_builder_options?.is_spa ?? false
                  );

                  setIsNixpacksSpaChecked(
                    service.nixpacks_builder_options?.is_spa ?? false
                  );
                  setIsNixpacksStaticChecked(
                    service.nixpacks_builder_options?.is_static ?? false
                  );

                  setIsRailpackSpaChecked(
                    service.railpack_builder_options?.is_spa ?? false
                  );
                  setIsRailpackStaticChecked(
                    service.railpack_builder_options?.is_static ?? false
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
