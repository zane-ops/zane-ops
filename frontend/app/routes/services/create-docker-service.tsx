import { useQuery } from "@tanstack/react-query";
import {
  AlertCircleIcon,
  ArrowRightIcon,
  CheckIcon,
  ClockArrowUpIcon,
  ContainerIcon,
  LoaderIcon
} from "lucide-react";
import * as React from "react";
import { Form, Link, useFetcher, useNavigation } from "react-router";
import { useDebounce } from "use-debounce";
import { apiClient } from "~/api/client";
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
  FieldSetHidableInput,
  FieldSetInput,
  FieldSetLabel
} from "~/components/ui/fieldset";
import { dockerHubQueries } from "~/lib/queries";
import { cn, getFormErrorsFromResponseData } from "~/lib/utils";
import { getCsrfTokenHeader, metaTitle } from "~/utils";
import type { Route } from "./+types/create-docker-service";

export function meta() {
  return [
    metaTitle("New Docker Service")
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
            <BreadcrumbPage>Docker</BreadcrumbPage>
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
  const userData = {
    slug: formData.get("slug")?.toString().trim() ?? "",
    image: formData.get("image")?.toString() ?? "",
    credentials: {
      password: formData.get("credentials.password")?.toString(),
      username: formData.get("credentials.username")?.toString().trim()
    }
  };

  const { error: errors, data } = await apiClient.POST(
    "/api/projects/{project_slug}/{env_slug}/create-service/docker/",
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
    "/api/projects/{project_slug}/{env_slug}/deploy-service/docker/{service_slug}/",
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

function StepServiceForm({ onSuccess, actionData }: StepServiceFormProps) {
  const [isComboxOpen, setComboxOpen] = React.useState(false);
  const [imageSearchQuery, setImageSearchQuery] = React.useState("");
  const formRef = React.useRef<React.ComponentRef<"form">>(null);
  const [isPasswordShown, setIsPasswordShown] = React.useState(false);

  const [debouncedValue] = useDebounce(imageSearchQuery, 150);
  const { data: imageListData } = useQuery(
    dockerHubQueries.images(debouncedValue)
  );

  const errors = getFormErrorsFromResponseData(actionData?.errors);

  const imageList = imageListData?.data?.images ?? [];
  const navigation = useNavigation();
  const isPending = navigation.state === "submitting";

  if (actionData?.serviceSlug) {
    onSuccess(actionData.serviceSlug);
  }

  React.useEffect(() => {
    const key = Object.keys(errors ?? {})[0];
    if (key !== "image") {
      const field = formRef.current?.elements.namedItem(
        key
      ) as HTMLInputElement;
      field?.focus();
    }
  }, [errors]);

  return (
    <Form
      ref={formRef}
      method="post"
      className="flex my-10 grow justify-center items-center"
    >
      <div className="card flex lg:w-[30%] md:w-[50%] w-full flex-col gap-3">
        <h1 className="text-3xl font-bold">New Docker Service</h1>

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
            placeholder="ex: db"
            type="text"
            defaultValue={actionData?.userData?.slug}
            autoFocus
          />
        </FieldSet>

        <div className="my-2 flex flex-col gap-1">
          <label aria-hidden="true" htmlFor="image">
            Image
            <span className="text-amber-600 dark:text-yellow-500">&nbsp;*</span>
          </label>
          <Command shouldFilter={false} label="Image">
            <CommandInput
              id="image"
              onFocus={() => setComboxOpen(true)}
              onValueChange={(query) => {
                setImageSearchQuery(query);
                setComboxOpen(true);
              }}
              onBlur={() => setComboxOpen(false)}
              className="p-3"
              value={imageSearchQuery}
              placeholder="ex: bitnami/redis"
              name="image"
              aria-describedby="image-error"
              aria-invalid={!!errors.image}
            />
            <CommandList
              className={cn({
                "hidden!":
                  imageList.length === 0 ||
                  imageSearchQuery.trim().length === 0 ||
                  !isComboxOpen
              })}
            >
              {imageList.map((image) => (
                <CommandItem
                  key={image.full_image}
                  value={image.full_image}
                  className="flex items-start gap-2"
                  onSelect={(value) => {
                    setImageSearchQuery(value);

                    const image_name = value.split("/").at(-1);
                    const slugInput = formRef.current?.elements.namedItem(
                      "slug"
                    ) as HTMLInputElement | null;

                    if (slugInput && image_name && !slugInput.value.trim()) {
                      slugInput.value = image_name;
                    }
                    setComboxOpen(false);
                  }}
                >
                  <ContainerIcon
                    size={15}
                    className="flex-none relative top-1"
                  />
                  <div className="flex flex-col gap-1">
                    <span>{image.full_image}</span>
                    <small className="text-xs text-gray-400/80">
                      {image.description}
                    </small>
                  </div>
                </CommandItem>
              ))}
            </CommandList>
          </Command>

          {errors.image && (
            <span id="image-error" className="text-red-500 text-sm">
              {errors.image}
            </span>
          )}
        </div>

        <div className="flex flex-col gap-3">
          <h2 className="text-lg">
            Credentials <span className="text-gray-400">(optional)</span>
          </h2>
          <p className="text-gray-400">
            If your image is on a private registry, please provide the
            information below.
          </p>
        </div>

        <FieldSet
          className="my-2 flex flex-col gap-1"
          name="credentials.username"
          errors={errors.credentials?.username}
        >
          <FieldSetLabel className="dark:text-card-foreground">
            Username for registry
          </FieldSetLabel>
          <FieldSetInput className="p-3" placeholder="ex: mocherif" />
        </FieldSet>

        <FieldSet
          name="credentials.password"
          errors={errors.credentials?.password}
          className="my-2 flex flex-col gap-1"
        >
          <FieldSetLabel className="dark:text-card-foreground">
            Password for registry
          </FieldSetLabel>
          <FieldSetHidableInput label="password" placeholder="*******" />
        </FieldSet>

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
  const navigation = useNavigation();
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
