import { useLocalStorage } from "@uidotdev/usehooks";
import {
  AlertCircleIcon,
  ArrowRightIcon,
  CheckIcon,
  ChevronRightIcon,
  ClockArrowUpIcon,
  ExternalLinkIcon,
  LoaderIcon,
  MoveUpRightIcon
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
import { Card } from "~/components/ui/card";
import { CodeEditor } from "~/components/ui/code-editor";
import {
  FieldSet,
  FieldSetInput,
  FieldSetLabel,
  FieldSetTextarea
} from "~/components/ui/fieldset";
import { TEMPLATE_API_HOST } from "~/lib/constants";
import { templateQueries } from "~/lib/queries";
import { cn, getFormErrorsFromResponseData } from "~/lib/utils";
import { queryClient } from "~/root";
import { getCsrfTokenHeader, metaTitle } from "~/utils";
import type { Route } from "./+types/create-compose-stack-from-template";

export function meta({ params }: Route.MetaArgs) {
  return [
    metaTitle(`New compose stack from \`${params.templateSlug}\``)
  ] satisfies ReturnType<Route.MetaFunction>;
}

export async function clientLoader({ params }: Route.ClientLoaderArgs) {
  const template = await queryClient.ensureQueryData(
    templateQueries.single(params.templateSlug)
  );
  return { template };
}

export default function CreateComposeStackFromTemplatePage({
  params,
  loaderData,
  actionData
}: Route.ComponentProps) {
  const [composeStackSlug, setComposeStackSlug] = React.useState("");
  const [deploymentHash, setDeploymentHash] = React.useState("");

  const [currentStep, setCurrentStep] = React.useState<
    "FORM" | "CREATED" | "DEPLOYED"
  >("FORM");

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
                params.envSlug === "production"
                  ? "text-green-500 dark:text-primary"
                  : params.envSlug.startsWith("preview")
                    ? "text-link"
                    : ""
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
            <BreadcrumbLink>
              <Link
                to={href(
                  "/project/:projectSlug/:envSlug/create-compose-stack/template",
                  params
                )}
                prefetch="intent"
              >
                From ZaneOps template
              </Link>
            </BreadcrumbLink>
          </BreadcrumbItem>
          <BreadcrumbSeparator />
          <BreadcrumbItem>
            <BreadcrumbPage>{params.templateSlug}</BreadcrumbPage>
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
          loaderData={loaderData}
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

async function createStack(
  projectSlug: string,
  envSlug: string,
  formData: FormData
) {
  const userData = {
    slug: formData.get("slug")?.toString().trim() ?? "",
    user_content: formData.get("user_content")?.toString() ?? ""
  } satisfies RequestInput<
    "post",
    "/api/compose/stacks/{project_slug}/{env_slug}/create/"
  >;

  const { error: errors, data } = await apiClient.POST(
    "/api/compose/stacks/{project_slug}/{env_slug}/create/",
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

  const step = formData.get("step")?.toString();
  switch (step) {
    case "create-stack": {
      return createStack(params.projectSlug, params.envSlug, formData);
    }
    case "deploy-stack": {
      return deployStack(params.projectSlug, params.envSlug, formData);
    }
    default: {
      throw new Error("Unexpected step");
    }
  }
}

type FormStepProps = {
  onSuccess: (slug: string) => void;
  actionData?: Route.ComponentProps["actionData"];
  loaderData: Route.ComponentProps["loaderData"];
};

function FormStep({
  actionData,
  onSuccess,
  loaderData: { template }
}: FormStepProps) {
  const formRef = React.useRef<React.ComponentRef<"form">>(null);
  const navigation = useNavigation();
  const isPending = navigation.state === "submitting";

  const [userContents, setUserContents] = React.useState(template.compose);

  const errors = getFormErrorsFromResponseData(actionData?.errors);

  if (actionData?.stackSlug) {
    onSuccess(actionData.stackSlug);
  }

  const logoUrl = new URL(template.logoUrl, TEMPLATE_API_HOST);

  React.useEffect(() => {
    const key = Object.keys(errors ?? {})[0] as keyof typeof errors;
    const field = formRef.current?.elements.namedItem(key) as HTMLInputElement;
    field?.focus();
  }, [errors]);

  return (
    <Form
      ref={formRef}
      method="post"
      className="flex my-10 grow justify-center items-center"
    >
      <div className="card flex xl:w-1/2 lg:w-[60%] md:w-2/3 w-full flex-col gap-5 items-stretch">
        <h1 className="text-3xl font-semibold">
          New compose stack from template
        </h1>

        <Card
          className={cn(
            "p-3.5 rounded-md bg-toggle dark:bg-muted relative",
            "ring-1 ring-transparent hover:ring-primary focus-within:ring-primary",
            "transition-colors duration-300 shadow-sm",
            "min-h-28"
          )}
        >
          <div className="flex flex-col items-start gap-2">
            <div className="flex justify-between gap-2 items-center w-full">
              <div className="flex items-center gap-2 border-gray-400/30  w-full">
                <img
                  src={logoUrl.toString()}
                  alt={template.name}
                  className="size-8 object-contain flex-none rounded-sm"
                />
                <a
                  href={`https://zaneops.dev/templates/${template.id}`}
                  target="_blank"
                  className="font-medium truncate after:inset-0 after:absolute  no-underline text-card-foreground"
                >
                  {template.name}
                </a>
              </div>

              <MoveUpRightIcon className="size-4 flex-none text-grey" />
            </div>

            <div>
              <p className="text-sm line-clamp-3 text-grey">
                {template.description}
              </p>
            </div>
          </div>
        </Card>

        {errors.non_field_errors && (
          <Alert variant="destructive">
            <AlertCircleIcon className="h-4 w-4" />
            <AlertTitle>Error</AlertTitle>
            <AlertDescription>{errors.non_field_errors}</AlertDescription>
          </Alert>
        )}

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
            placeholder="ex: immich"
            type="text"
            defaultValue={actionData?.userData?.slug ?? template.id}
          />
        </FieldSet>

        <FieldSet
          name="user_content"
          required
          errors={errors.user_content}
          className="flex flex-col gap-1.5 flex-1"
        >
          <FieldSetLabel className="dark:text-card-foreground">
            Contents
          </FieldSetLabel>
          <FieldSetTextarea className="sr-only" value={userContents} readOnly />

          <CodeEditor
            hasError={!!errors.user_content}
            containerClassName="w-full h-100"
            language="yaml"
            value={userContents}
            onChange={(value) => setUserContents(value ?? "")}
          />
        </FieldSet>

        <SubmitButton
          className="p-3 rounded-lg gap-2 self-end"
          isPending={isPending}
          name="step"
          value="create-stack"
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
            name="step"
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
            <Link
              to={href(
                "/project/:projectSlug/:envSlug/compose-stacks/:composeStackSlug/deployments/:deploymentHash",
                {
                  composeStackSlug,
                  envSlug,
                  projectSlug,
                  deploymentHash
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
