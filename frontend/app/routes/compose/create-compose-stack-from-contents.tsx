import {
  AlertCircleIcon,
  ArrowRightIcon,
  CheckIcon,
  ClockArrowUpIcon,
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
import { useLocalStorage } from "~/lib/use-local-storage";
import { cn, getFormErrorsFromResponseData } from "~/lib/utils";
import { getCsrfTokenHeader, metaTitle } from "~/utils";
import type { Route } from "./+types/create-compose-stack-from-contents";

export function meta() {
  return [
    metaTitle("New Compose Stack")
  ] satisfies ReturnType<Route.MetaFunction>;
}

const SAVED_COMPOSE_CONTENTS_KEY = "compose:last-user-contents";
const DEFAULT_COMPOSE_CONTENTS = `# ZaneOps Compose Stack Example
# ==============================
# This is a complete example showing how to deploy a web app with a database.
# Delete this and paste your own compose file, or modify it to fit your needs.

# Environment variables (x-zane-env)
# ----------------------------------
# Define shared variables here. ZaneOps supports these template functions:
#   {{ generate_domain }}        - generates a unique domain for your app
#   {{ generate_password | N }}  - generates a secure password of N characters (N must be even)
#   {{ generate_username }}      - generates a random username
#   {{ generate_slug }}          - generates a URL-safe slug
#   {{ generate_uuid }}          - generates a UUID
#   {{ network_alias | 'svc' }}  - resolves to the service's network alias
#   {{ global_alias | 'svc' }}   - resolves to the service's global alias

x-zane-env:
  APP_DOMAIN: "{{ generate_domain }}"
  DB_PORT: 5432
  DB_USER: "{{ generate_username }}"
  DB_NAME: app
  DB_HOST: db
  DB_PASSWORD: "{{ generate_password | 32 }}"

services:
  app:
    image: nginxdemos/hello:latest
    environment:
      # Reference x-zane-env variables with \${VAR_NAME}
      DATABASE_URL: "postgres://\${DB_USER}:\${DB_PASSWORD}@\${DB_HOST}:\${DB_PORT}/\${DB_NAME}"
    depends_on:
      - db
    deploy:
      # Expose your service to the internet with labels
      labels:
        zane.http.routes.0.port: "80"
        zane.http.routes.0.domain: "\${APP_DOMAIN}"
        zane.http.routes.0.base_path: "/"

  db:
    image: postgres:18-alpine
    environment:
      POSTGRES_USER: \${DB_USER}
      POSTGRES_PASSWORD: \${DB_PASSWORD}
      POSTGRES_DB: \${DB_NAME}
    volumes:
      - db-data:/var/lib/postgresql
    healthcheck:
      test: ["CMD", "pg_isready", "-U", "\$\$DB_USER", "-d", "\$\$DB_NAME"]
      interval: 10s
      timeout: 5s
      retries: 5

volumes:
  db-data:
`;

export default function CreateComposeStackFromContentsPage({
  params,
  actionData
}: Route.ComponentProps) {
  const [currentStep, setCurrentStep] = React.useState<
    "FORM" | "CREATED" | "DEPLOYED"
  >("FORM");

  const [composeStackSlug, setComposeStackSlug] = React.useState("");
  const [deploymentHash, setDeploymentHash] = React.useState("");
  const [, setSavedUserContents] = useLocalStorage(
    SAVED_COMPOSE_CONTENTS_KEY,
    DEFAULT_COMPOSE_CONTENTS
  );

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
            <BreadcrumbPage>From compose contents</BreadcrumbPage>
          </BreadcrumbItem>
        </BreadcrumbList>
      </Breadcrumb>

      {currentStep === "FORM" && (
        <FormStep
          actionData={actionData}
          onSuccess={(slug) => {
            setCurrentStep("CREATED");
            setComposeStackSlug(slug);
            setSavedUserContents(DEFAULT_COMPOSE_CONTENTS);
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
};

function FormStep({ actionData, onSuccess }: FormStepProps) {
  const formRef = React.useRef<React.ComponentRef<"form">>(null);
  const navigation = useNavigation();
  const isPending = navigation.state === "submitting";

  const [userContents, setUserContents] = useLocalStorage(
    SAVED_COMPOSE_CONTENTS_KEY,
    DEFAULT_COMPOSE_CONTENTS
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
      <div className="card flex  lg:w-1/2 md:w-2/3 w-full flex-col gap-5 items-stretch">
        <h1 className="text-3xl font-bold">New Compose stack</h1>

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
            defaultValue={actionData?.userData?.slug}
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
        <input type="hidden" name="service_slug" value={composeStackSlug} />
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
