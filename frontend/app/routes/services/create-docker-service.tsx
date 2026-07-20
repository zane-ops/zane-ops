import { useQuery } from "@tanstack/react-query";
import {
  AlertCircleIcon,
  ArrowLeftIcon,
  ArrowRightIcon,
  CheckIcon,
  ClockArrowUpIcon,
  ContainerIcon,
  LoaderIcon,
  PlusIcon
} from "lucide-react";
import * as React from "react";
import {
  Form,
  Link,
  href,
  useFetcher,
  useLoaderData,
  useNavigate,
  useNavigation
} from "react-router";
import { useDebounce } from "use-debounce";
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
import {
  Command,
  CommandInput,
  CommandItem,
  CommandList
} from "~/components/ui/command";
import {
  FieldSet,
  FieldSetInput,
  FieldSetLabel,
  FieldSetSelect
} from "~/components/ui/fieldset";
import {
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue
} from "~/components/ui/select";
import { DEFAULT_REGISTRIES } from "~/lib/constants";
import {
  dockerHubQueries,
  sharedRegistryCredentialsQueries,
  userQueries
} from "~/lib/queries";
import { getQueryClient } from "~/lib/query-client";
import {
  cn,
  getCsrfTokenHeader,
  getFormErrorsFromResponseData,
  metaTitle
} from "~/lib/utils";
import {
  getCurrentWorkspace,
  useCurrentWorkspace
} from "~/lib/workspace-store";
import type { Route } from "./+types/create-docker-service";

export function meta() {
  return [
    metaTitle("New Docker Service")
  ] satisfies ReturnType<Route.MetaFunction>;
}

export async function clientLoader({ params }: Route.ClientLoaderArgs) {
  const queryClient = getQueryClient();
  const { id: workspaceId } = await getCurrentWorkspace(queryClient);
  const registries = await queryClient.ensureQueryData(
    sharedRegistryCredentialsQueries.list(workspaceId)
  );
  return { registries };
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
    <div
      className={cn(
        currentStep !== "FORM" &&
          "h-[70vh] flex flex-col items-center justify-center w-full"
      )}
    >
      <Link
        to={href(
          "/workspace/project/:projectSlug/:envSlug/create-service",
          params
        )}
        className={cn(
          "text-sm text-grey lg:w-1/3 md:w-1/2 w-full mx-auto mb-2",
          "flex items-center gap-0.5 hover:underline"
        )}
      >
        <ArrowLeftIcon className="size-4" />
        Create service
      </Link>

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
    </div>
  );
}

async function createService(
  projectSlug: string,
  envSlug: string,
  formData: FormData
) {
  const registry_credentials_id = formData
    .get("container_registry_credentials_id")
    ?.toString();
  const userData = {
    slug: formData.get("slug")?.toString().trim() ?? "",
    image: formData.get("image")?.toString() ?? "",
    container_registry_credentials_id: registry_credentials_id
      ? registry_credentials_id
      : undefined
  } satisfies RequestInput<
    "post",
    "/api/projects/{project_slug}/{env_slug}/create-service/docker/"
  >;

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
  const [selectedRegistry, setSelectedRegistry] = React.useState<
    string | undefined
  >(undefined);
  const formRef = React.useRef<React.ComponentRef<"form">>(null);
  const SelectTriggerRef =
    React.useRef<React.ComponentRef<typeof SelectTrigger>>(null);

  const [debouncedValue] = useDebounce(imageSearchQuery, 150);
  const { data: imageListData } = useQuery(
    dockerHubQueries.images(debouncedValue)
  );

  const loaderData = useLoaderData<typeof clientLoader>();
  const workspaceId = useCurrentWorkspace().id;
  const { data: registries } = useQuery({
    ...sharedRegistryCredentialsQueries.list(workspaceId),
    initialData: loaderData.registries
  });
  const navigate = useNavigate();

  const errors = getFormErrorsFromResponseData(actionData?.errors);

  const imageList = imageListData?.data?.images ?? [];
  const navigation = useNavigation();
  const isPending = navigation.state === "submitting";

  React.useEffect(() => {
    const key = Object.keys(errors ?? {})[0] as keyof typeof errors;

    if (key === "container_registry_credentials_id") {
      SelectTriggerRef.current?.focus();
      return;
    }

    if (key !== "image") {
      const field = formRef.current?.elements.namedItem(
        key
      ) as HTMLInputElement;
      field?.focus();
    }
  }, [errors]);

  if (actionData?.serviceSlug) {
    onSuccess(actionData.serviceSlug);
  }

  return (
    <Form
      ref={formRef}
      method="post"
      className="flex grow w-full justify-center"
    >
      <div className="card flex lg:w-1/3 md:w-1/2 w-full flex-col gap-3">
        <h1 className="text-3xl font-bold">New Docker Service</h1>

        {errors.non_field_errors && (
          <Alert variant="destructive">
            <AlertCircleIcon className="h-4 w-4" />
            <AlertTitle>Error</AlertTitle>
            <AlertDescription>{errors.non_field_errors}</AlertDescription>
          </Alert>
        )}

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
              autoFocus
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
          />
        </FieldSet>

        <div className="flex flex-col gap-3">
          <h2 className="text-lg">
            Credentials <span className="text-gray-400">(optional)</span>
          </h2>
          <p className="text-gray-400">
            If your image is on a private registry, select which one in the list
          </p>

          <FieldSet
            errors={errors.container_registry_credentials_id}
            name="container_registry_credentials_id"
            className="flex flex-col gap-1.5 flex-1 w-full"
          >
            <FieldSetLabel htmlFor="registry_credentials">
              Credentials
            </FieldSetLabel>
            <FieldSetSelect
              name="container_registry_credentials_id"
              value={selectedRegistry}
              onValueChange={(value) => {
                if (value === "add-new") {
                  navigate(href("/workspace/settings/shared-credentials/new"));
                } else {
                  setSelectedRegistry(value);
                }
              }}
            >
              <SelectTrigger
                id="registry_credentials"
                ref={SelectTriggerRef}
                className={cn(
                  "[&_[data-item]_.flex]:flex-row [&_[data-item]_.flex]:gap-1",
                  "[&_[data-item]]:items-center [&_[data-item]_:first-child]:top-0"
                )}
              >
                <SelectValue placeholder="Select a registry" />
              </SelectTrigger>
              <SelectContent>
                {registries.map((registry) => {
                  const Icon = DEFAULT_REGISTRIES[registry.registry_type].Icon;
                  return (
                    <SelectItem
                      value={registry.id}
                      className="items-start [&_[data-indicator]]:relative [&_[data-indicator]]:top-0.5"
                    >
                      <div data-item className="inline-flex items-start gap-2">
                        <Icon className="relative top-0.5" />
                        <div className="flex flex-col items-start gap-0">
                          <span>{registry.slug}</span>
                          <span className="text-grey">{registry.username}</span>
                        </div>
                      </div>
                    </SelectItem>
                  );
                })}
                <SelectItem value="add-new" className="px-2">
                  <div className="inline-flex items-start gap-2">
                    <PlusIcon className="size-4 relative top-0.5" />
                    <div className="flex flex-col items-start">
                      <span>Add new credentials</span>
                    </div>
                  </div>
                </SelectItem>
              </SelectContent>
            </FieldSetSelect>
          </FieldSet>
        </div>

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
            "Create New Service"
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
  const fetcher = useFetcher<typeof clientAction>();
  const errors = getFormErrorsFromResponseData(fetcher.data?.errors);
  const isPending = fetcher.state !== "idle";

  if (fetcher.data?.deploymentHash) {
    onSuccess(fetcher.data.deploymentHash);
  }
  return (
    <div className="flex flex-col w-full justify-center items-center">
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
              to={href(
                "/workspace/project/:projectSlug/:envSlug/services/:serviceSlug",
                {
                  projectSlug,
                  envSlug,
                  serviceSlug
                }
              )}
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
    <div className="flex  flex-col justify-center items-center w-full">
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
              to={href(
                "/workspace/project/:projectSlug/:envSlug/services/:serviceSlug/deployments/:deploymentHash/build-logs",
                {
                  projectSlug,
                  envSlug,
                  serviceSlug,
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
