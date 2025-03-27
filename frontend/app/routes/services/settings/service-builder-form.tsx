import {
  CheckIcon,
  ChevronDownIcon,
  ChevronRightIcon,
  EyeIcon,
  EyeOffIcon,
  InfoIcon,
  LoaderIcon,
  PencilLineIcon,
  Undo2Icon,
  XIcon
} from "lucide-react";
import * as React from "react";
import { flushSync } from "react-dom";
import { useFetcher } from "react-router";
import { toast } from "sonner";
import { Code } from "~/components/code";
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
  FieldSetInput,
  FieldSetLabel,
  FieldSetSelect
} from "~/components/ui/fieldset";
import { Input } from "~/components/ui/input";
import { Label } from "~/components/ui/label";
import { RadioGroup, RadioGroupItem } from "~/components/ui/radio-group";
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
  type clientAction,
  useFetcherWithCallbacks,
  useServiceQuery
} from "~/routes/services/settings/services-settings";
import { capitalizeText } from "~/utils";

export type ServiceBuilderFormProps = {
  service_slug: string;
  project_slug: string;
  env_slug: string;
};

type ServiceBuilderChangeNewValue = Pick<Service, "builder"> & {
  options: Service["dockerfile_builder_options"];
};

export function ServiceBuilderForm({
  service_slug,
  project_slug,
  env_slug
}: ServiceBuilderFormProps) {
  const { fetcher, data, reset } = useFetcherWithCallbacks({
    onSettled(data) {
      if (!data.errors) {
        formRef.current?.reset();
        const service = data.data;

        const serviceBuilderChange = service.unapplied_changes.find(
          (change) => change.field === "builder"
        ) as
          | {
              new_value: ServiceBuilderChangeNewValue;
              id: string;
            }
          | undefined;
        const newBuilder = serviceBuilderChange?.new_value
          .builder as Service["builder"];
        const updatedBuilder =
          newBuilder === null ? null : newBuilder ?? service.builder;

        setServiceBuilder(updatedBuilder ?? "DOCKERFILE");
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

  const { data: service } = useServiceQuery({
    project_slug,
    service_slug,
    env_slug
  });

  const serviceBuilderChange = service.unapplied_changes.find(
    (change) => change.field === "builder"
  ) as
    | {
        new_value: ServiceBuilderChangeNewValue;
        id: string;
      }
    | undefined;

  const [serviceBuilder, setServiceBuilder] = React.useState<
    NonNullable<Service["builder"]>
  >(serviceBuilderChange?.new_value.builder ?? service.builder ?? "DOCKERFILE");
  const dockerfile_path =
    serviceBuilderChange?.new_value.options?.dockerfile_path ??
    service.dockerfile_builder_options?.dockerfile_path;
  const build_context_dir =
    serviceBuilderChange?.new_value.options?.build_context_dir ??
    service.dockerfile_builder_options?.build_context_dir;
  const build_stage_target =
    serviceBuilderChange?.new_value.options?.build_stage_target ??
    service.dockerfile_builder_options?.build_stage_target;

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

        <Accordion type="single" collapsible>
          <AccordionItem
            value={`builder`}
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
                  {serviceBuilder === "DOCKERFILE" && <p>Dockerfile</p>}
                </div>

                <small className="inline-flex gap-2 items-center">
                  {serviceBuilder === "DOCKERFILE" && (
                    <span className="text-grey">
                      Build your app using a Dockerfile
                    </span>
                  )}
                </small>
              </div>

              <ChevronRightIcon size={20} className="text-grey" />
            </AccordionTrigger>
            <AccordionContent className="border-border border-x border-b rounded-b-md p-4 mb-4">
              <RadioGroup
                value={serviceBuilder}
                onValueChange={(value) =>
                  setServiceBuilder(value as NonNullable<Service["builder"]>)
                }
              >
                <div className="flex items-center space-x-2">
                  <RadioGroupItem value="DOCKERFILE" id="dockerfile-builder" />
                  <Label htmlFor="dockerfile-builder">Dockerfile</Label>
                </div>
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
                      <TooltipContent className="max-w-64 bg-card">
                        Coming very soon
                      </TooltipContent>
                    </Tooltip>
                  </TooltipProvider>
                </div>
                <div className="flex items-center space-x-2">
                  <RadioGroupItem
                    value="STATIC_DIR"
                    id="static-builder"
                    className="peer"
                    disabled
                  />
                  <Label
                    htmlFor="static-builder"
                    className="peer-disabled:text-grey inline-flex gap-1 items-center"
                  >
                    <span>Static directory</span>
                  </Label>
                  <TooltipProvider>
                    <Tooltip delayDuration={0}>
                      <TooltipTrigger>
                        <InfoIcon size={15} className="text-grey" />
                      </TooltipTrigger>
                      <TooltipContent className="max-w-64 bg-card">
                        Coming very soon
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
              <FieldSetLabel className="dark:text-card-foreground inline-flex items-center gap-0.5">
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
              <FieldSetLabel className="dark:text-card-foreground  inline-flex items-center gap-0.5">
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
              required
              errors={errors.new_value?.build_stage_target}
            >
              <FieldSetLabel className="dark:text-card-foreground inline-flex items-center gap-0.5">
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
                  setServiceBuilder(service.builder ?? "DOCKERFILE");
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
