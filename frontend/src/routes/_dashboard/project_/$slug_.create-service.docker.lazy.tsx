import * as Form from "@radix-ui/react-form";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { Link, createLazyFileRoute } from "@tanstack/react-router";
import {
  AlertCircle,
  ArrowRight,
  Check,
  ClockArrowUp,
  Container
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
import { Button } from "~/components/ui/button";
import {
  Command,
  CommandInput,
  CommandItem,
  CommandList
} from "~/components/ui/command";
import { Input } from "~/components/ui/input";
import { projectKeys } from "~/key-factories";
import { useSearchDockerHub } from "~/lib/hooks/use-search-docker-hub";
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
  const { data: imageListData } = useSearchDockerHub(debouncedValue);

  const { isPending, mutate, data } = useMutation({
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

  const errors = getFormErrorsFromResponseData(data?.error);

  const imageList = imageListData?.data?.images ?? [];

  return (
    <Form.Root
      action={(formData) => {
        let credentials = undefined;
        if (
          formData.get("credentials.username") ||
          formData.get("credentials.password")
        ) {
          credentials = {
            password: formData.get("credentials.password")!.toString(),
            username: formData.get("credentials.username")!.toString().trim()
          };
        }

        mutate({
          slug: formData.get("slug")?.toString().trim() ?? "",
          image: formData.get("image")?.toString() ?? "",
          credentials
        });
      }}
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

        <Form.Field className="my-2 flex flex-col gap-1" name="slug">
          <Form.Label>Slug</Form.Label>

          <Form.Control asChild>
            <Input
              className="p-3"
              placeholder="ex: db"
              name="slug"
              type="text"
            />
          </Form.Control>
          {errors.slug && (
            <Form.Message className="text-red-500 text-sm">
              {errors.slug}
            </Form.Message>
          )}
        </Form.Field>

        <Form.Field name="image" className="my-2 flex flex-col gap-1">
          <label aria-hidden="true">Image</label>
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
            <Form.Message className="text-red-500 text-sm">
              {errors.image}
            </Form.Message>
          )}
        </Form.Field>

        <div className="flex flex-col gap-3">
          <h1 className="text-lg">
            Credentials <span className="text-gray-400">(optional)</span>
          </h1>
          <p className="text-gray-400">
            If your image is on a private registry, please provide these
            information below.
          </p>
        </div>

        <Form.Field
          className="my-2 flex flex-col gap-1"
          name="credentials.username"
        >
          <Form.Label>Username for registry</Form.Label>
          <Form.Control asChild>
            <Input className="p-3" placeholder="ex: mocherif" type="text" />
          </Form.Control>
          {errors.credentials?.username && (
            <Form.Message className="text-red-500 text-sm">
              {errors.credentials.username}
            </Form.Message>
          )}
        </Form.Field>

        <Form.Field
          className="my-2 flex flex-col gap-1"
          name="credentials.password"
        >
          <Form.Label>Password for registry</Form.Label>
          <Form.Control asChild>
            <Input className="p-3" type="password" />
          </Form.Control>
          {errors.credentials?.password && (
            <Form.Message className="text-red-500 text-sm">
              {errors.credentials.password}
            </Form.Message>
          )}
        </Form.Field>

        <Form.Submit asChild>
          <Button className="p-3 rounded-lg">
            {isPending ? "Creating Service..." : " Create New Service"}
          </Button>
        </Form.Submit>
      </div>
    </Form.Root>
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
  const { isPending, mutate, data } = useMutation({
    onSuccess: (data) => {
      if (data.data) {
        onSuccess(data.data.hash);
        queryClient.invalidateQueries({
          predicate(query) {
            const [prefix] = projectKeys.detail(slug, {});
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

      <Form.Root
        action={() => mutate()}
        className="flex flex-col gap-4 lg:w-1/3 md:w-1/2 w-full"
      >
        <Alert variant="success">
          <Check className="h-5 w-5 text-green-400" />
          <AlertTitle className="text-lg">Success</AlertTitle>

          <AlertDescription>
            Service `<strong>{serviceSlug}</strong>` Created Successfuly
          </AlertDescription>
        </Alert>

        <div className="flex gap-3 md:flex-row flex-col items-stretch">
          <Button className="p-3 rounded-lg">
            {isPending ? "Deploying service..." : "Deploy Now"}
          </Button>

          <Button asChild className="flex-1" variant="outline">
            <Link
              to={`/project/${slug}/services/docker/${serviceSlug}`}
              className="flex gap-2  items-center"
            >
              Go to service details <ArrowRight size={20} />
            </Link>
          </Button>
        </div>
      </Form.Root>
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
