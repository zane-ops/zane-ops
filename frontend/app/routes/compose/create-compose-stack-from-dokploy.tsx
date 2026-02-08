import {
  AlertCircleIcon,
  ArrowRightIcon,
  CheckIcon,
  ClockArrowUpIcon,
  ExternalLinkIcon,
  InfoIcon,
  LoaderIcon
} from "lucide-react";
import * as React from "react";
import { Form, Link, href, useFetcher, useNavigation } from "react-router";
import { type RequestInput, apiClient } from "~/api/client";
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
import { CodeEditor } from "~/components/ui/code-editor";
import {
  FieldSet,
  FieldSetInput,
  FieldSetLabel,
  FieldSetTextarea
} from "~/components/ui/fieldset";
import { Label } from "~/components/ui/label";
import { RadioGroup, RadioGroupItem } from "~/components/ui/radio-group";
import {
  Tooltip,
  TooltipContent,
  TooltipProvider,
  TooltipTrigger
} from "~/components/ui/tooltip";
import type { BUILDER_DESCRIPTION_MAP } from "~/lib/constants";
import { cn, getFormErrorsFromResponseData } from "~/lib/utils";
import { getCsrfTokenHeader, metaTitle } from "~/utils";
import type { Route } from "./+types/create-compose-stack-from-dokploy";

export function meta() {
  return [
    metaTitle("New Dokploy Compose Stack")
  ] satisfies ReturnType<Route.MetaFunction>;
}

export default function CreateComposeStackFromDokployPage({
  params,
  actionData
}: Route.ComponentProps) {
  const [currentStep, setCurrentStep] = React.useState<
    "FORM" | "CREATED" | "DEPLOYED"
  >("FORM");

  const [composeStackSlug, setComposeStackSlug] = React.useState("");
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
                to={href("/project/:projectSlug/:envSlug", {
                  ...params,
                  envSlug: "production"
                })}
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
                params.envSlug === "production"
                  ? "text-green-500 dark:text-primary"
                  : params.envSlug.startsWith("preview")
                    ? "text-link"
                    : ""
              )}
            >
              <Link
                to={href("/project/:projectSlug/:envSlug", params)}
                prefetch="intent"
              >
                {params.envSlug}
              </Link>
            </BreadcrumbLink>
          </BreadcrumbItem>
          <BreadcrumbSeparator />
          <BreadcrumbItem>
            <BreadcrumbLink>
              <Link
                to={href(
                  "/project/:projectSlug/:envSlug/create-compose-stack",
                  params
                )}
                prefetch="intent"
              >
                Create compose stack
              </Link>
            </BreadcrumbLink>
          </BreadcrumbItem>
          <BreadcrumbSeparator />
          <BreadcrumbItem>
            <BreadcrumbPage>From dokploy template</BreadcrumbPage>
          </BreadcrumbItem>
        </BreadcrumbList>
      </Breadcrumb>

      {currentStep === "FORM" && (
        <FormStep
          actionData={actionData}
          onSuccess={(slug) => {
            setCurrentStep("CREATED");
            setComposeStackSlug(slug);
          }}
        />
      )}

      {currentStep === "CREATED" && (
        <StackCreatedStep
          projectSlug={params.projectSlug}
          envSlug={params.envSlug}
          composeStackSlug={composeStackSlug}
          onSuccess={(hash) => {
            setCurrentStep("DEPLOYED");
            setDeploymentHash(hash);
          }}
        />
      )}

      {currentStep === "DEPLOYED" && (
        <StackDeployedStep
          projectSlug={params.projectSlug}
          envSlug={params.envSlug}
          composeStackSlug={composeStackSlug}
          deploymentHash={deploymentHash}
        />
      )}
    </>
  );
}

async function createStackFromDokployBase64(
  projectSlug: string,
  envSlug: string,
  formData: FormData
) {
  const userData = {
    slug: formData.get("slug")?.toString().trim() ?? "",
    user_content: formData.get("user_content")?.toString() ?? ""
  } satisfies RequestInput<
    "post",
    "/api/compose/stacks/{project_slug}/{env_slug}/create-from-dokploy/base-64/"
  >;

  const { error: errors, data } = await apiClient.POST(
    "/api/compose/stacks/{project_slug}/{env_slug}/create-from-dokploy/base-64/",
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
    stackSlug: data?.slug,
    deploymentHash: undefined,
    userData
  };
}

async function createStackFromDokployObject(
  projectSlug: string,
  envSlug: string,
  formData: FormData
) {
  const userData = {
    slug: formData.get("slug")?.toString().trim() ?? "",
    compose: formData.get("compose")?.toString() ?? "",
    config: formData.get("config")?.toString() ?? ""
  } satisfies RequestInput<
    "post",
    "/api/compose/stacks/{project_slug}/{env_slug}/create-from-dokploy/object/"
  >;

  const { error: errors, data } = await apiClient.POST(
    "/api/compose/stacks/{project_slug}/{env_slug}/create-from-dokploy/object/",
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
    stackSlug: data?.slug,
    deploymentHash: undefined,
    userData
  };
}

async function deployStack(
  projectSlug: string,
  envSlug: string,
  formData: FormData
) {
  const stackSlug = formData.get("stack_slug")?.toString()!;
  const { error: errors, data } = await apiClient.PUT(
    "/api/compose/stacks/{project_slug}/{env_slug}/{slug}/deploy/",
    {
      headers: {
        ...(await getCsrfTokenHeader())
      },
      params: {
        path: {
          project_slug: projectSlug,
          env_slug: envSlug,
          slug: stackSlug
        }
      }
    }
  );

  return {
    errors,
    stackSlug,
    deploymentHash: data?.hash,
    userData: undefined
  };
}

export async function clientAction({
  request,
  params
}: Route.ClientActionArgs) {
  const formData = await request.formData();

  const intent = formData.get("intent")?.toString();
  switch (intent) {
    case "create-stack-from-base-64": {
      return createStackFromDokployBase64(
        params.projectSlug,
        params.envSlug,
        formData
      );
    }
    case "create-stack-from-object": {
      return createStackFromDokployObject(
        params.projectSlug,
        params.envSlug,
        formData
      );
    }
    case "deploy-stack": {
      return deployStack(params.projectSlug, params.envSlug, formData);
    }
    default: {
      throw new Error("Unexpected intent");
    }
  }
}

type FormStepProps = {
  onSuccess: (slug: string) => void;
  actionData?: Route.ComponentProps["actionData"];
};

function FormStep({ actionData, onSuccess }: FormStepProps) {
  const formRef = React.useRef<React.ComponentRef<"form">>(null);
  const navigation = useNavigation();
  const isPending = navigation.state === "submitting";

  const [intent, setIntent] = React.useState<
    "create-stack-from-base-64" | "create-stack-from-object"
  >("create-stack-from-base-64");
  const [composeContent, setComposeContent] = React.useState(
    "# your docker-compose.yml content here"
  );
  const [configContent, setConfigContent] = React.useState(
    "# your template.toml config here\n" +
      "[variables]\n\n" +
      "[config]\n" +
      "[[config.domains]]\n\n" +
      "[[config.env]]\n"
  );

  const errors = getFormErrorsFromResponseData(actionData?.errors);

  React.useEffect(() => {
    const key = Object.keys(errors ?? {})[0] as keyof typeof errors;
    const field = formRef.current?.elements.namedItem(key) as HTMLInputElement;
    field?.focus();
  }, [errors]);

  if (actionData?.stackSlug) {
    onSuccess(actionData.stackSlug);
  }

  return (
    <Form
      ref={formRef}
      method="post"
      className="flex my-10 grow justify-center items-center"
    >
      <div className="card flex xl:w-[40%] lg:w-1/2 md:w-2/3 w-full flex-col gap-5 items-stretch">
        <h1 className="text-3xl font-bold">New Dokploy Compose stack</h1>

        <p className="text-grey">
          Import a compose stack from a&nbsp;
          <a
            href="https://templates.dokploy.com"
            target="_blank"
            className="text-link underline inline-flex gap-1 items-center"
          >
            Dokploy template
            <ExternalLinkIcon className="size-4" />
          </a>
          . ZaneOps will automatically convert it to a compatible format.
        </p>

        <FieldSet
          name="slug"
          className="my-2 flex flex-col gap-1"
          errors={errors.slug}
          required
        >
          <FieldSetLabel className="dark:text-card-foreground">
            Slug
          </FieldSetLabel>

          <FieldSetInput
            className="p-3"
            placeholder="ex: rybbit"
            type="text"
            defaultValue={actionData?.userData?.slug}
          />
        </FieldSet>

        <RadioGroup
          value={intent}
          onValueChange={(value) => setIntent(value as any)}
        >
          <div className="flex items-center space-x-2">
            <RadioGroupItem
              value="create-stack-from-base-64"
              id="base-64"
              className="peer"
            />
            <Label htmlFor="base-64" className="peer-disabled:text-grey">
              <span>Base64 config</span>
            </Label>
            <TooltipProvider>
              <Tooltip delayDuration={0}>
                <TooltipTrigger>
                  <InfoIcon size={15} className="text-grey" />
                </TooltipTrigger>
                <TooltipContent className="max-w-64 dark:bg-card">
                  Copy base64 configuration of the template
                </TooltipContent>
              </Tooltip>
            </TooltipProvider>
          </div>

          <div className="flex items-center space-x-2">
            <RadioGroupItem value="create-stack-from-object" id="object" />
            <Label htmlFor="object">Compose file contents + TOML config</Label>
            <TooltipProvider>
              <Tooltip delayDuration={0}>
                <TooltipTrigger>
                  <InfoIcon size={15} className="text-grey" />
                </TooltipTrigger>
                <TooltipContent className="max-w-70 dark:bg-card ">
                  Copy the contents of{" "}
                  <span className="text-grey dark:text-card-foreground">
                    `docker-compose.yml`
                  </span>
                  &nbsp;file and&nbsp;
                  <span className="text-grey dark:text-card-foreground">
                    `template.toml`
                  </span>{" "}
                  corresponding to the dokploy template
                </TooltipContent>
              </Tooltip>
            </TooltipProvider>
          </div>
        </RadioGroup>

        {errors.non_field_errors && (
          <Alert variant="destructive">
            <AlertCircleIcon className="h-4 w-4" />
            <AlertTitle>Error</AlertTitle>
            <AlertDescription>{errors.non_field_errors}</AlertDescription>
          </Alert>
        )}
        {intent === "create-stack-from-base-64" ? (
          <FieldSet
            name="user_content"
            className="my-2 flex flex-col gap-1"
            errors={errors.user_content}
            required
          >
            <FieldSetLabel className="dark:text-card-foreground">
              Base64
            </FieldSetLabel>

            <FieldSetInput
              className="p-3"
              placeholder="eyAiY29tcG9zZQ=..."
              type="text"
            />
          </FieldSet>
        ) : (
          <>
            <FieldSet
              name="compose"
              required
              errors={errors.compose}
              className="flex flex-col gap-1.5 flex-1"
            >
              <FieldSetLabel className="dark:text-card-foreground">
                Docker Compose
              </FieldSetLabel>
              <FieldSetTextarea
                className="sr-only"
                value={composeContent}
                readOnly
              />

              <CodeEditor
                hasError={!!errors.compose}
                containerClassName="w-full"
                language="yaml"
                value={composeContent}
                onChange={(value) => setComposeContent(value ?? "")}
              />
            </FieldSet>

            <FieldSet
              name="config"
              required
              errors={errors.config}
              className="flex flex-col gap-1.5 flex-1"
            >
              <FieldSetLabel className="dark:text-card-foreground">
                Configuration
              </FieldSetLabel>
              <FieldSetTextarea
                className="sr-only"
                value={configContent}
                readOnly
              />

              <CodeEditor
                hasError={!!errors.config}
                containerClassName="w-full"
                language="ini"
                value={configContent}
                onChange={(value) => setConfigContent(value ?? "")}
              />
            </FieldSet>
          </>
        )}
        <SubmitButton
          className="p-3 rounded-lg gap-2 self-end"
          isPending={isPending}
          name="intent"
          value={intent}
        >
          {isPending ? (
            <>
              <span>Creating stack...</span>
              <LoaderIcon className="animate-spin" size={15} />
            </>
          ) : (
            "Create New Stack"
          )}
        </SubmitButton>
      </div>
    </Form>
  );
}

type StackCreatedStepProps = {
  composeStackSlug: string;
  projectSlug: string;
  envSlug: string;
  onSuccess: (deploymentHash: string) => void;
};

function StackCreatedStep({
  composeStackSlug,
  projectSlug,
  envSlug,
  onSuccess
}: StackCreatedStepProps) {
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
        <input type="hidden" name="stack_slug" value={composeStackSlug} />
        <Alert variant="success">
          <CheckIcon className="h-5 w-5" />
          <AlertTitle className="text-lg">Success</AlertTitle>

          <AlertDescription>
            Compose Stack `<strong>{composeStackSlug}</strong>` Created
            Successfuly
          </AlertDescription>
        </Alert>

        <div className="flex gap-3 md:flex-row flex-col items-stretch">
          <SubmitButton
            className="p-3 rounded-lg gap-2 flex-1"
            isPending={isPending}
            name="intent"
            value="deploy-stack"
          >
            {isPending ? (
              <>
                <span>Deploying stack...</span>
                <LoaderIcon className="animate-spin" size={15} />
              </>
            ) : (
              "Deploy Now"
            )}
          </SubmitButton>

          <Button asChild className="flex-1" variant="outline">
            <Link
              to={href(
                "/project/:projectSlug/:envSlug/compose-stacks/:composeStackSlug",
                {
                  composeStackSlug,
                  envSlug,
                  projectSlug
                }
              )}
              className="flex gap-2  items-center"
            >
              Go to stack details <ArrowRightIcon size={20} />
            </Link>
          </Button>
        </div>
      </fetcher.Form>
    </div>
  );
}

type StackDeployedStepProps = {
  projectSlug: string;
  composeStackSlug: string;
  envSlug: string;
  deploymentHash: string;
};

function StackDeployedStep({
  projectSlug,
  composeStackSlug,
  envSlug,
  deploymentHash
}: StackDeployedStepProps) {
  const navigation = useNavigation();
  return (
    <div className="flex  flex-col h-[70vh] justify-center items-center">
      <div className="flex flex-col gap-4 lg:w-1/3 md:w-1/2 w-full">
        <Alert variant="info">
          <ClockArrowUpIcon className="h-5 w-5" />
          <AlertTitle className="text-lg">Queued</AlertTitle>

          <AlertDescription>
            Deployment queued for stack&nbsp; `
            <strong>{composeStackSlug}</strong>`
          </AlertDescription>
        </Alert>

        <div className="flex gap-3 md:flex-row flex-col items-stretch">
          <Button asChild className="flex-1">
            {/* TODO: change for build-logs page */}
            <Link
              to={href(
                "/project/:projectSlug/:envSlug/compose-stacks/:composeStackSlug",
                {
                  composeStackSlug,
                  envSlug,
                  projectSlug
                }
              )}
              className="flex gap-2  items-center"
            >
              {navigation.state !== "idle" && (
                <LoaderIcon className="animate-spin" size={15} />
              )}
              Inspect deployment <ArrowRightIcon size={20} />
            </Link>
          </Button>
        </div>
      </div>
    </div>
  );
}
