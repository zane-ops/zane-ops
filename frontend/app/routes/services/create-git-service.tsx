import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  AlertCircleIcon,
  ArrowRightIcon,
  CheckIcon,
  ChevronRightIcon,
  ClockArrowUpIcon,
  ContainerIcon,
  InfoIcon,
  LoaderIcon
} from "lucide-react";
import * as React from "react";
import { Form, Link, useFetcher, useNavigation } from "react-router";
import { useDebounce } from "use-debounce";
import { type RequestInput, apiClient } from "~/api/client";
import { Code } from "~/components/code";
import {
  Accordion,
  AccordionContent,
  AccordionItem,
  AccordionTrigger
} from "~/components/ui/accordion";
import { Alert, AlertDescription, AlertTitle } from "~/components/ui/alert";
import {
  Breadcrumb,
  BreadcrumbItem,
  BreadcrumbLink,
  BreadcrumbList,
  BreadcrumbPage,
  BreadcrumbSeparator
} from "~/components/ui/breadcrumb";
import { Button, SubmitButton } from "~/components/ui/button";
import {
  Command,
  CommandInput,
  CommandItem,
  CommandList
} from "~/components/ui/command";
import {
  FieldSet,
  FieldSetCheckbox,
  FieldSetInput,
  FieldSetLabel
} from "~/components/ui/fieldset";
import { Input } from "~/components/ui/input";
import { Label } from "~/components/ui/label";
import { RadioGroup, RadioGroupItem } from "~/components/ui/radio-group";
import {
  Tooltip,
  TooltipContent,
  TooltipProvider,
  TooltipTrigger
} from "~/components/ui/tooltip";
import { type Service, dockerHubQueries } from "~/lib/queries";
import { cn, getFormErrorsFromResponseData } from "~/lib/utils";
import { getCsrfTokenHeader, metaTitle } from "~/utils";
import { type Route } from "./+types/create-git-service";

export function meta() {
  return [
    metaTitle("New Git Service")
  ] satisfies ReturnType<Route.MetaFunction>;
}

export default function CreateServicePage({
  params,
  actionData
}: Route.ComponentProps) {
  const [currentStep, setCurrentStep] = React.useState<
    "FORM" | "CREATED" | "DEPLOYED"
  >("FORM");

  const [serviceSlug, setServiceSlug] = React.useState("");
  const [deploymentHash, setDeploymentHash] = React.useState("");

  return (
    <>
      <Breadcrumb>
        <BreadcrumbList className="text-sm">
          <BreadcrumbItem>
            <BreadcrumbLink asChild>
              <Link to="/" prefetch="intent">
                Projects
              </Link>
            </BreadcrumbLink>
          </BreadcrumbItem>
          <BreadcrumbSeparator />
          <BreadcrumbItem>
            <BreadcrumbLink asChild>
              <Link
                to={`/project/${params.projectSlug}/production`}
                prefetch="intent"
              >
                {params.projectSlug}
              </Link>
            </BreadcrumbLink>
          </BreadcrumbItem>

          <BreadcrumbSeparator />
          <BreadcrumbItem>
            <BreadcrumbLink
              asChild
              className={cn(
                params.envSlug !== "production"
                  ? "text-link"
                  : "text-green-500 dark:text-primary"
              )}
            >
              <Link
                to={`/project/${params.projectSlug}/${params.envSlug}`}
                prefetch="intent"
              >
                {params.envSlug}
              </Link>
            </BreadcrumbLink>
          </BreadcrumbItem>

          <BreadcrumbSeparator />
          <BreadcrumbItem>
            <BreadcrumbLink asChild>
              <Link
                to={`/project/${params.projectSlug}/${params.envSlug}/create-service`}
                prefetch="intent"
              >
                Create service
              </Link>
            </BreadcrumbLink>
          </BreadcrumbItem>

          <BreadcrumbSeparator />
          <BreadcrumbItem>
            <BreadcrumbPage>Git</BreadcrumbPage>
          </BreadcrumbItem>
        </BreadcrumbList>
      </Breadcrumb>

      {currentStep === "FORM" && (
        <StepServiceForm
          actionData={actionData}
          onSuccess={(slug) => {
            setCurrentStep("CREATED");
            setServiceSlug(slug);
          }}
        />
      )}

      {currentStep === "CREATED" && (
        <StepServiceCreated
          projectSlug={params.projectSlug}
          envSlug={params.envSlug}
          serviceSlug={serviceSlug}
          onSuccess={(hash) => {
            setCurrentStep("DEPLOYED");
            setDeploymentHash(hash);
          }}
        />
      )}

      {currentStep === "DEPLOYED" && (
        <StepServiceDeployed
          projectSlug={params.projectSlug}
          envSlug={params.envSlug}
          serviceSlug={serviceSlug}
          deploymentHash={deploymentHash}
        />
      )}
    </>
  );
}

async function createService(
  projectSlug: string,
  envSlug: string,
  formData: FormData
) {
  type Body = RequestInput<
    "post",
    "/api/projects/{project_slug}/{env_slug}/create-service/git/"
  >;
  const userData = {
    slug: formData.get("slug")?.toString().trim() ?? "",
    repository_url: formData.get("repository_url")?.toString() ?? "",
    branch_name: formData.get("branch_name")?.toString() ?? "",
    builder: formData.get("builder")?.toString() as Body["builder"],
    build_context_dir: formData.get("build_context_dir")?.toString(),
    dockerfile_path: formData.get("dockerfile_path")?.toString(),
    base_directory: formData.get("base_directory")?.toString(),
    index_page: formData.get("index_page")?.toString(),
    not_found_page: formData.get("not_found_page")?.toString(),
    is_spa: formData.get("is_spa")?.toString() === "on"
  } satisfies Body;

  const { error: errors, data } = await apiClient.POST(
    "/api/projects/{project_slug}/{env_slug}/create-service/git/",
    {
      headers: {
        ...(await getCsrfTokenHeader())
      },
      params: {
        path: {
          project_slug: projectSlug,
          env_slug: envSlug
        }
      },
      body: userData
    }
  );

  return {
    errors,
    serviceSlug: data?.slug,
    deploymentHash: undefined,
    userData
  };
}

async function deployService(
  projectSlug: string,
  envSlug: string,
  formData: FormData
) {
  const serviceSlug = formData.get("service_slug")?.toString()!;
  const { error: errors, data } = await apiClient.PUT(
    "/api/projects/{project_slug}/{env_slug}/deploy-service/git/{service_slug}/",
    {
      headers: {
        ...(await getCsrfTokenHeader())
      },
      params: {
        path: {
          project_slug: projectSlug,
          service_slug: serviceSlug,
          env_slug: envSlug
        }
      }
    }
  );

  return {
    errors,
    serviceSlug,
    deploymentHash: data?.hash,
    userData: undefined
  };
}

export async function clientAction({
  request,
  params
}: Route.ClientActionArgs) {
  const formData = await request.formData();

  const step = formData.get("step")?.toString();
  switch (step) {
    case "create-service": {
      return createService(params.projectSlug, params.envSlug, formData);
    }
    case "deploy-service": {
      return deployService(params.projectSlug, params.envSlug, formData);
    }
    default: {
      throw new Error("Unexpected step");
    }
  }
}

type StepServiceFormProps = {
  onSuccess: (slug: string) => void;
  actionData?: Route.ComponentProps["actionData"];
};

type ServiceBuilder = Exclude<NonNullable<Service["builder"]>, "">;

function StepServiceForm({ onSuccess, actionData }: StepServiceFormProps) {
  const errors = getFormErrorsFromResponseData(actionData?.errors);

  const formRef = React.useRef<React.ComponentRef<"form">>(null);

  const navigation = useNavigation();
  const isPending = navigation.state === "submitting";

  if (actionData?.serviceSlug) {
    onSuccess(actionData.serviceSlug);
  }

  const [serviceBuilder, setServiceBuilder] =
    React.useState<ServiceBuilder>("DOCKERFILE");

  const [isSpaChecked, setIsSpaChecked] = React.useState(false);

  React.useEffect(() => {
    const key = Object.keys(errors ?? {})[0];
    const field = formRef.current?.elements.namedItem(key) as HTMLInputElement;
    field?.focus();
  }, [errors]);

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
    <Form
      ref={formRef}
      method="post"
      className="flex my-10 grow justify-center items-center"
    >
      <div className="card flex lg:w-[35%] md:w-[50%] w-full flex-col gap-3">
        <h1 className="text-3xl font-bold">New Git Service</h1>

        {errors.non_field_errors && (
          <Alert variant="destructive">
            <AlertCircleIcon className="h-4 w-4" />
            <AlertTitle>Error</AlertTitle>
            <AlertDescription>{errors.non_field_errors}</AlertDescription>
          </Alert>
        )}

        <FieldSet
          name="slug"
          required
          className="my-2 flex flex-col gap-1"
          errors={errors.slug}
        >
          <FieldSetLabel className="dark:text-card-foreground">
            Slug
          </FieldSetLabel>

          <FieldSetInput
            className="p-3"
            placeholder="ex: zaneops-web-app"
            autoFocus
          />
        </FieldSet>

        <h2 className="text-lg text-grey mt-2">Source</h2>

        <FieldSet
          required
          className="flex flex-col gap-1"
          name="repository_url"
          errors={errors.repository_url}
        >
          <FieldSetLabel className="dark:text-card-foreground">
            Repository URL
          </FieldSetLabel>
          <FieldSetInput
            className="p-3"
            placeholder="ex: https://github.com/zane-ops/zane-ops"
          />
        </FieldSet>
        <FieldSet
          name="branch_name"
          className="flex flex-col gap-1.5 flex-1"
          required
          errors={errors.branch_name}
        >
          <FieldSetLabel className="dark:text-card-foreground">
            Branch name
          </FieldSetLabel>
          <FieldSetInput placeholder="ex: master" defaultValue="main" />
        </FieldSet>

        <h2 className="text-lg text-grey mt-4">Builder</h2>

        <input type="hidden" name="builder" value={serviceBuilder} />

        <Accordion type="single" collapsible>
          <AccordionItem value={`builder`} className="border-none">
            <AccordionTrigger
              className={cn(
                "w-full px-3 bg-muted rounded-md gap-2 flex items-center justify-between text-start",
                "data-[state=open]:rounded-b-none [&[data-state=open]_svg]:rotate-90 pr-4"
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
                        Dockerfile for you
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
              errors={errors.build_context_dir}
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
                <FieldSetInput placeholder="ex: ./apps/web" defaultValue="./" />
              </div>
            </FieldSet>

            <FieldSet
              className="flex flex-col gap-1.5 flex-1"
              required
              name="dockerfile_path"
              errors={errors.dockerfile_path}
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
                  placeholder="ex: ./apps/web/Dockerfile"
                  defaultValue="./Dockerfile"
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
              errors={errors.base_directory}
            >
              <FieldSetLabel className=" inline-flex items-center gap-0.5">
                Publish directory
              </FieldSetLabel>
              <div className="relative">
                <FieldSetInput
                  placeholder="ex: ./public"
                  defaultValue="./"
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
                errors={errors.not_found_page}
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
                    placeholder="ex: ./404.html"
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
              errors={errors.is_spa}
              className="flex-1 inline-flex gap-2 flex-col"
            >
              <div className="inline-flex gap-2 items-center">
                <FieldSetCheckbox
                  defaultChecked={isSpaChecked}
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
                errors={errors.index_page}
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
                    placeholder="ex: ./index.html"
                    defaultValue="./index.html"
                    className={cn(
                      "disabled:bg-secondary/60",
                      "dark:disabled:bg-secondary-foreground",
                      "disabled:border-transparent disabled:opacity-100"
                    )}
                  />
                </div>
              </FieldSet>
            )}
          </>
        )}
        <SubmitButton
          className="p-3 rounded-lg gap-2"
          isPending={isPending}
          name="step"
          value="create-service"
        >
          {isPending ? (
            <>
              <span>Creating Service...</span>
              <LoaderIcon className="animate-spin" size={15} />
            </>
          ) : (
            " Create New Service"
          )}
        </SubmitButton>
      </div>
    </Form>
  );
}

type StepServiceCreatedProps = {
  serviceSlug: string;
  projectSlug: string;
  envSlug: string;
  onSuccess: (deploymentHash: string) => void;
};

function StepServiceCreated({
  serviceSlug,
  projectSlug,
  envSlug,
  onSuccess
}: StepServiceCreatedProps) {
  // const navigation = useNavigation();
  const fetcher = useFetcher<typeof clientAction>();
  const errors = getFormErrorsFromResponseData(fetcher.data?.errors);
  const isPending = fetcher.state !== "idle";

  if (fetcher.data?.deploymentHash) {
    onSuccess(fetcher.data.deploymentHash);
  }
  return (
    <div className="flex flex-col h-[70vh] justify-center items-center">
      {errors.non_field_errors && (
        <Alert variant="destructive">
          <AlertCircleIcon className="h-4 w-4" />
          <AlertTitle>Error</AlertTitle>
          <AlertDescription>{errors.non_field_errors}</AlertDescription>
        </Alert>
      )}

      <fetcher.Form
        method="post"
        className="flex flex-col gap-4 lg:w-1/3 md:w-1/2 w-full"
      >
        <input type="hidden" name="service_slug" value={serviceSlug} />
        <Alert variant="success">
          <CheckIcon className="h-5 w-5" />
          <AlertTitle className="text-lg">Success</AlertTitle>

          <AlertDescription>
            Service `<strong>{serviceSlug}</strong>` Created Successfuly
          </AlertDescription>
        </Alert>

        <div className="flex gap-3 md:flex-row flex-col items-stretch">
          <SubmitButton
            className="p-3 rounded-lg gap-2 flex-1"
            isPending={isPending}
            name="step"
            value="deploy-service"
          >
            {isPending ? (
              <>
                <span>Deploying service...</span>
                <LoaderIcon className="animate-spin" size={15} />
              </>
            ) : (
              "Deploy Now"
            )}
          </SubmitButton>

          <Button asChild className="flex-1" variant="outline">
            <Link
              to={`/project/${projectSlug}/${envSlug}/services/${serviceSlug}`}
              className="flex gap-2  items-center"
            >
              Go to service details <ArrowRightIcon size={20} />
            </Link>
          </Button>
        </div>
      </fetcher.Form>
    </div>
  );
}

type StepServiceDeployedProps = {
  projectSlug: string;
  serviceSlug: string;
  envSlug: string;
  deploymentHash: string;
};

function StepServiceDeployed({
  projectSlug,
  serviceSlug,
  envSlug,
  deploymentHash
}: StepServiceDeployedProps) {
  return (
    <div className="flex  flex-col h-[70vh] justify-center items-center">
      <div className="flex flex-col gap-4 lg:w-1/3 md:w-1/2 w-full">
        <Alert variant="info">
          <ClockArrowUpIcon className="h-5 w-5" />
          <AlertTitle className="text-lg">Queued</AlertTitle>

          <AlertDescription>
            Deployment queued for service&nbsp; `<strong>{serviceSlug}</strong>`
          </AlertDescription>
        </Alert>

        <div className="flex gap-3 md:flex-row flex-col items-stretch">
          <Button asChild className="flex-1">
            <Link
              to={`/project/${projectSlug}/${envSlug}/services/${serviceSlug}/deployments/${deploymentHash}/build-logs`}
              className="flex gap-2  items-center"
            >
              Inspect deployment <ArrowRightIcon size={20} />
            </Link>
          </Button>
        </div>
      </div>
    </div>
  );
}
