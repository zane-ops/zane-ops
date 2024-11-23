import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Link, createLazyFileRoute } from "@tanstack/react-router";
import {
  AlertCircle,
  ArrowRight,
  Check,
  ClockArrowUp,
  Container,
  LoaderIcon
} from "lucide-react";
import * as React from "react";
import { useDebounce } from "use-debounce";
import { type RequestInput, apiClient } from "~/api/client";
import { withAuthRedirect } from "~/components/helper/auth-redirect";
import { MetaTitle } from "~/components/meta-title";
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
import { Input } from "~/components/ui/input";
import { dockerHubQueries, projectQueries } from "~/lib/queries";
import { cn, getFormErrorsFromResponseData } from "~/lib/utils";
import { getCsrfTokenHeader } from "~/utils";

export const Route = createLazyFileRoute(
  "/_dashboard/project/$slug/create-service/docker"
)({
  component: withAuthRedirect(Docker)
});

function Docker() {
  const { slug } = Route.useParams();
  const [currentStep, setCurrentStep] = React.useState<
    "FORM" | "CREATED" | "DEPLOYED"
  >("FORM");

  const [serviceSlug, setServiceSlug] = React.useState("");
  const [deploymentHash, setDeploymentHash] = React.useState("");

  return (
    <main>
      <MetaTitle title="New docker service" />
      <Breadcrumb>
        <BreadcrumbList className="text-sm">
          <BreadcrumbItem>
            <BreadcrumbLink asChild>
              <Link to="/">Projects</Link>
            </BreadcrumbLink>
          </BreadcrumbItem>
          <BreadcrumbSeparator />
          <BreadcrumbItem>
            <BreadcrumbLink asChild>
              <Link to={`/project/${slug}`} className="capitalize">
                {slug}
              </Link>
            </BreadcrumbLink>
          </BreadcrumbItem>

          <BreadcrumbSeparator />
          <BreadcrumbItem>
            <BreadcrumbLink asChild>
              <Link to={`/project/${slug}/create-service`}>Create service</Link>
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
          slug={slug}
          onSuccess={(slug) => {
            setCurrentStep("CREATED");
            setServiceSlug(slug);
          }}
        />
      )}

      {currentStep === "CREATED" && (
        <StepServiceCreated
          slug={slug}
          onSuccess={(hash) => {
            setCurrentStep("DEPLOYED");
            setDeploymentHash(hash);
          }}
          serviceSlug={serviceSlug}
        />
      )}

      {currentStep === "DEPLOYED" && (
        <StepServiceDeployed
          slug={slug}
          serviceSlug={serviceSlug}
          deploymentHash={deploymentHash}
        />
      )}
    </main>
  );
}

type StepServiceFormProps = {
  slug: string;
  onSuccess: (slug: string) => void;
};

function StepServiceForm({ slug, onSuccess }: StepServiceFormProps) {
  const [isComboxOpen, setComboxOpen] = React.useState(false);
  const [imageSearchQuery, setImageSearchQuery] = React.useState("");

  const [debouncedValue] = useDebounce(imageSearchQuery, 300);
  const { data: imageListData } = useQuery(
    dockerHubQueries.images(debouncedValue)
  );

  const { mutateAsync, data } = useMutation({
    onSuccess: (data) => {
      if (data.data) {
        onSuccess(data.data.slug);
      }
    },
    mutationFn: async (
      input: RequestInput<
        "post",
        "/api/projects/{project_slug}/create-service/docker/"
      >
    ) => {
      const { error, data } = await apiClient.POST(
        "/api/projects/{project_slug}/create-service/docker/",
        {
          headers: {
            ...(await getCsrfTokenHeader())
          },
          params: {
            path: {
              project_slug: slug
            }
          },
          body: input
        }
      );

      return { error, data };
    }
  });

  const [state, formAction, isPending] = React.useActionState(
    async (prev: any, formData: FormData) => {
      const data = {
        slug: formData.get("slug")?.toString().trim() ?? "",
        image: formData.get("image")?.toString() ?? "",
        credentials: {
          password: formData.get("credentials.password")?.toString(),
          username: formData.get("credentials.username")?.toString().trim()
        }
      };
      const { error } = await mutateAsync(data);

      if (error) {
        return data;
      }
    },
    null
  );

  const errors = getFormErrorsFromResponseData(data?.error);

  const imageList = imageListData?.data?.images ?? [];

  return (
    <form
      action={formAction}
      className="flex my-10 flex-grow justify-center items-center"
    >
      <div className="card flex lg:w-[30%] md:w-[50%] w-full flex-col gap-3">
        <h1 className="text-3xl font-bold">New Docker Service</h1>

        {errors.non_field_errors && (
          <Alert variant="destructive">
            <AlertCircle className="h-4 w-4" />
            <AlertTitle>Error</AlertTitle>
            <AlertDescription>{errors.non_field_errors}</AlertDescription>
          </Alert>
        )}

        <div className="my-2 flex flex-col gap-1">
          <label htmlFor="slug">Slug</label>

          <Input
            className="p-3"
            placeholder="ex: db"
            name="slug"
            id="slug"
            type="text"
            defaultValue={state?.slug}
            aria-describedby="slug-error"
          />
          {errors.slug && (
            <span id="slug-error" className="text-red-500 text-sm">
              {errors.slug}
            </span>
          )}
        </div>

        <div className="my-2 flex flex-col gap-1">
          <label aria-hidden="true" htmlFor="image">
            Image
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
            />
            <CommandList
              className={cn({
                "!hidden":
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
                    setComboxOpen(false);
                  }}
                >
                  <Container size={15} className="flex-none relative top-1" />
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

        <div className="my-2 flex flex-col gap-1">
          <label htmlFor="credentials.username">Username for registry</label>
          <Input
            className="p-3"
            placeholder="ex: mocherif"
            type="text"
            id="credentials.username"
            name="credentials.username"
            defaultValue={state?.credentials.username}
            aria-describedby="credentials.username-error"
          />

          {errors.credentials?.username && (
            <span
              id="credentials.username-error"
              className="text-red-500 text-sm"
            >
              {errors.credentials.username}
            </span>
          )}
        </div>

        <div className="my-2 flex flex-col gap-1">
          <label htmlFor="credentials.password">Password for registry</label>
          <Input
            className="p-3"
            type="password"
            name="credentials.password"
            id="credentials.password"
            defaultValue={state?.credentials.password}
            aria-describedby="credentials.password-error"
          />
          {errors.credentials?.password && (
            <span
              id="credentials.password-error"
              className="text-red-500 text-sm"
            >
              {errors.credentials.password}
            </span>
          )}
        </div>

        <SubmitButton className="p-3 rounded-lg gap-2" isPending={isPending}>
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
    </form>
  );
}

type StepServiceCreatedProps = {
  slug: string;
  serviceSlug: string;
  onSuccess: (deploymentHash: string) => void;
};

function StepServiceCreated({
  slug,
  serviceSlug,
  onSuccess
}: StepServiceCreatedProps) {
  const queryClient = useQueryClient();
  const { isPending, mutateAsync, data } = useMutation({
    onSuccess: (data) => {
      if (data.data) {
        onSuccess(data.data.hash);
        queryClient.invalidateQueries({
          predicate(query) {
            const [prefix] = projectQueries.serviceList(slug).queryKey;
            return query.queryKey[0] === prefix && query.queryKey[1] === slug;
          }
        });
      }
    },
    mutationFn: async () => {
      const { error, data } = await apiClient.PUT(
        "/api/projects/{project_slug}/deploy-service/docker/{service_slug}/",
        {
          headers: {
            ...(await getCsrfTokenHeader())
          },
          params: {
            path: {
              project_slug: slug,
              service_slug: serviceSlug
            }
          }
        }
      );

      return { error, data };
    }
  });

  const errors = getFormErrorsFromResponseData(data?.error);

  return (
    <div className="flex  flex-col h-[70vh] justify-center items-center">
      {errors.non_field_errors && (
        <Alert variant="destructive">
          <AlertCircle className="h-4 w-4" />
          <AlertTitle>Error</AlertTitle>
          <AlertDescription>{errors.non_field_errors}</AlertDescription>
        </Alert>
      )}

      <form
        action={async () => {
          await mutateAsync();
        }}
        className="flex flex-col gap-4 lg:w-1/3 md:w-1/2 w-full"
      >
        <Alert variant="success">
          <Check className="h-5 w-5" />
          <AlertTitle className="text-lg">Success</AlertTitle>

          <AlertDescription>
            Service `<strong>{serviceSlug}</strong>` Created Successfuly
          </AlertDescription>
        </Alert>

        <div className="flex gap-3 md:flex-row flex-col items-stretch">
          <SubmitButton
            className="p-3 rounded-lg gap-2 flex-1"
            isPending={isPending}
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
              to={`/project/${slug}/services/docker/${serviceSlug}`}
              className="flex gap-2  items-center"
            >
              Go to service details <ArrowRight size={20} />
            </Link>
          </Button>
        </div>
      </form>
    </div>
  );
}

type StepServiceDeployedProps = {
  slug: string;
  serviceSlug: string;
  deploymentHash: string;
};

function StepServiceDeployed({
  slug,
  serviceSlug,
  deploymentHash
}: StepServiceDeployedProps) {
  return (
    <div className="flex  flex-col h-[70vh] justify-center items-center">
      <div className="flex flex-col gap-4 lg:w-1/3 md:w-1/2 w-full">
        <Alert variant="info">
          <ClockArrowUp className="h-5 w-5" />
          <AlertTitle className="text-lg">Queued</AlertTitle>

          <AlertDescription>
            Deployment queued for service&nbsp; `<strong>{serviceSlug}</strong>`
          </AlertDescription>
        </Alert>

        <div className="flex gap-3 md:flex-row flex-col items-stretch">
          <Button asChild className="flex-1">
            <Link
              to={`/project/${slug}/services/docker/${serviceSlug}/deployments/${deploymentHash}`}
              className="flex gap-2  items-center"
            >
              Inspect deployment <ArrowRight size={20} />
            </Link>
          </Button>
        </div>
      </div>
    </div>
  );
}
