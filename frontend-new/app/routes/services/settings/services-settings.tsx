import { useQuery } from "@tanstack/react-query";
import {
  CheckIcon,
  ContainerIcon,
  EyeIcon,
  EyeOffIcon,
  InfoIcon,
  LoaderIcon,
  PencilLineIcon,
  XIcon
} from "lucide-react";
import * as React from "react";
import {
  Link,
  redirect,
  useFetcher,
  useMatches,
  useNavigate,
  useParams
} from "react-router";
import { toast } from "sonner";
import { apiClient } from "~/api/client";
import { Button, SubmitButton } from "~/components/ui/button";
import { Input } from "~/components/ui/input";
import {
  Tooltip,
  TooltipContent,
  TooltipProvider,
  TooltipTrigger
} from "~/components/ui/tooltip";
import {
  type DockerService,
  projectQueries,
  serviceQueries
} from "~/lib/queries";
import { cn, getFormErrorsFromResponseData } from "~/lib/utils";
import { queryClient } from "~/root";
import { getCsrfTokenHeader } from "~/utils";
import { type Route } from "./+types/services-settings";

export default function ServiceSettingsPage({
  params: { projectSlug: project_slug, serviceSlug: service_slug }
}: Route.ComponentProps) {
  return (
    <div className="my-6 grid lg:grid-cols-12 gap-10 relative">
      <div className="lg:col-span-10 flex flex-col">
        <section id="details" className="flex gap-1 scroll-mt-20">
          <div className="w-16 hidden md:flex flex-col items-center">
            <div className="flex rounded-full size-10 flex-none items-center justify-center p-1 border-2 border-grey/50">
              <InfoIcon size={15} className="flex-none text-grey" />
            </div>
            <div className="h-full border border-grey/50"></div>
          </div>

          <div className="w-full flex flex-col gap-5 pt-1 pb-8">
            <h2 className="text-lg text-grey">Details</h2>
            <ServiceSlugForm
              project_slug={project_slug}
              service_slug={service_slug}
            />
          </div>
        </section>

        <section id="source" className="flex gap-1 scroll-mt-20">
          <div className="w-16 hidden md:flex flex-col items-center">
            <div className="flex rounded-full size-10 flex-none items-center justify-center p-1 border-2 border-grey/50">
              <ContainerIcon size={15} className="flex-none text-grey" />
            </div>
            <div className="h-full border border-grey/50"></div>
          </div>

          <div className="w-full flex flex-col gap-5 pt-1 pb-14">
            <h2 className="text-lg text-grey">Source</h2>
            <ServiceSourceForm
              project_slug={project_slug}
              service_slug={service_slug}
            />
          </div>
        </section>
      </div>

      <aside className="col-span-2 hidden lg:flex flex-col h-full">
        <nav className="sticky top-20">
          <ul className="flex flex-col gap-2 text-grey">
            <li>
              <Link
                to={{
                  hash: "#main"
                }}
              >
                Details
              </Link>
            </li>
            <li>
              <Link
                to={{
                  hash: "#source"
                }}
              >
                Source
              </Link>
            </li>
            <li>
              <Link
                to={{
                  hash: "#networking"
                }}
              >
                Networking
              </Link>
            </li>
            <li>
              <Link
                to={{
                  hash: "#deploy"
                }}
              >
                Deploy
              </Link>
            </li>
            <li>
              <Link
                to={{
                  hash: "#volumes"
                }}
              >
                Volumes
              </Link>
            </li>
            <li className="text-red-400">
              <Link
                to={{
                  hash: "#danger"
                }}
              >
                Danger Zone
              </Link>
            </li>
          </ul>
        </nav>
      </aside>
    </div>
  );
}
type ServiceFormProps = {
  project_slug: string;
  service_slug: string;
};

function useServiceQuery({ project_slug, service_slug }: ServiceFormProps) {
  const {
    "2": {
      data: { service: initialData }
    }
  } = useMatches() as Route.ComponentProps["matches"];

  return useQuery({
    ...serviceQueries.single({ project_slug, service_slug }),
    initialData
  });
}

export async function clientAction({
  request,
  params
}: Route.ClientActionArgs) {
  const formData = await request.formData();
  const intent = formData.get("intent")?.toString();

  switch (intent) {
    case "update-slug": {
      return updateServiceSlug({
        project_slug: params.projectSlug,
        service_slug: params.serviceSlug,
        formData
      });
    }
    case "update-field": {
      // TODO
      break;
    }
    default: {
      throw new Error("Unexpected intent");
    }
  }
}

async function updateServiceSlug({
  project_slug,
  service_slug,
  formData
}: {
  project_slug: string;
  service_slug: string;
  formData: FormData;
}) {
  const userData = {
    slug: formData.get("slug")?.toString()
  };
  await queryClient.cancelQueries({
    queryKey: serviceQueries.single({ project_slug, service_slug }).queryKey,
    exact: true
  });

  const { error: errors, data } = await apiClient.PATCH(
    "/api/projects/{project_slug}/service-details/docker/{service_slug}/",
    {
      headers: {
        ...(await getCsrfTokenHeader())
      },
      params: {
        path: {
          project_slug,
          service_slug
        }
      },
      body: userData
    }
  );

  if (errors) {
    return {
      errors,
      userData
    };
  }

  await Promise.all([
    queryClient.invalidateQueries(
      serviceQueries.single({ project_slug, service_slug: service_slug })
    ),
    queryClient.invalidateQueries(projectQueries.serviceList(project_slug))
  ]);

  if (data.slug !== service_slug) {
    queryClient.setQueryData(
      serviceQueries.single({ project_slug, service_slug: data.slug }).queryKey,
      data
    );
  }
  return {
    data
  };
}

function ServiceSlugForm({ service_slug }: ServiceFormProps) {
  const [isEditing, setIsEditing] = React.useState(false);

  return (
    <div className="w-full max-w-4xl">
      {isEditing ? (
        <ServiceSlugEditForm
          service_slug={service_slug}
          quitEditing={() => setIsEditing(false)}
        />
      ) : (
        <div className="flex flex-col gap-1.5">
          <span>Service slug</span>
          <div
            className={cn(
              "w-full rounded-md flex justify-between items-center gap-2 py-1 pl-4 pr-2",
              "bg-muted"
            )}
          >
            <span>{service_slug}</span>
            <Button
              variant="outline"
              onClick={() => {
                setIsEditing(true);
              }}
              className="bg-inherit inline-flex items-center gap-2 border-muted-foreground py-0.5"
            >
              <span>Edit</span>
              <PencilLineIcon size={15} />
            </Button>
          </div>
        </div>
      )}
    </div>
  );
}

function ServiceSlugEditForm({
  service_slug,
  quitEditing
}: { service_slug: string; quitEditing: () => void }) {
  const fetcher = useFetcher<typeof clientAction>();
  const isPending = fetcher.state !== "idle";
  const navigate = useNavigate();
  const errors = getFormErrorsFromResponseData(fetcher.data?.errors);

  React.useEffect(() => {
    if (fetcher.state === "idle" && fetcher.data?.data?.slug) {
      navigate(`../../${fetcher.data.data.slug}/settings`, {
        replace: true,
        relative: "path"
      });
      quitEditing();
    }
  }, [fetcher.state, fetcher.data]);

  return (
    <fetcher.Form
      method="post"
      className="flex flex-col md:flex-row gap-2 w-full"
    >
      <fieldset className="flex flex-col gap-1.5 flex-1">
        <label htmlFor="slug">Service slug</label>
        <Input
          id="slug"
          name="slug"
          autoFocus
          placeholder="service slug"
          defaultValue={service_slug}
          aria-labelledby="slug-error"
        />

        {errors.slug && (
          <span id="slug-error" className="text-red-500 text-sm">
            {errors.slug}
          </span>
        )}
      </fieldset>

      <div className="flex gap-2 md:relative top-8">
        <SubmitButton
          isPending={isPending}
          variant="outline"
          className="bg-inherit"
          name="intent"
          value="update-slug"
        >
          {isPending ? (
            <>
              <LoaderIcon className="animate-spin" size={15} />
              <span className="sr-only">Updating service slug...</span>
            </>
          ) : (
            <>
              <CheckIcon size={15} className="flex-none" />
              <span className="sr-only">Update service slug</span>
            </>
          )}
        </SubmitButton>
        <Button
          onClick={() => {
            quitEditing();
          }}
          variant="outline"
          className="bg-inherit"
          type="button"
        >
          <XIcon size={15} className="flex-none" />
          <span className="sr-only">Cancel</span>
        </Button>
      </div>
    </fetcher.Form>
  );
}

function ServiceSourceForm({ service_slug, project_slug }: ServiceFormProps) {
  const fetcher = useFetcher<typeof clientAction>();
  const isPending = fetcher.state !== "idle";
  const errors = getFormErrorsFromResponseData(fetcher.data?.errors);
  const [isEditing, setIsEditing] = React.useState(false);
  const [isPasswordShown, setIsPasswordShown] = React.useState(false);

  const { data: service } = useServiceQuery({ project_slug, service_slug });

  const serviceSourcheChange = service.unapplied_changes.find(
    (change) => change.field === "source"
  ) as { new_value: Pick<DockerService, "image" | "credentials"> } | undefined;

  const serviceImage = serviceSourcheChange?.new_value.image ?? service.image!;

  const imageParts = serviceImage.split(":");

  const tag = imageParts.length > 1 ? imageParts.pop() : "latest";
  const image = imageParts.join(":");

  const credentials =
    serviceSourcheChange?.new_value.credentials ?? service.credentials;

  return (
    <div className="w-full max-w-4xl">
      {/* {non_field_errors.length > 0 && (
          <Alert variant="destructive">
            <AlertCircleIcon className="h-4 w-4" />
            <AlertTitle>Error</AlertTitle>
            <AlertDescription>{non_field_errors}</AlertDescription>
          </Alert>
        )} */}
      <fetcher.Form method="post" className="flex flex-col gap-4 w-full">
        <fieldset className="flex flex-col gap-1.5 flex-1">
          <label htmlFor="image">Source Image</label>
          {isEditing ? (
            <Input
              id="image"
              name="image"
              autoFocus
              placeholder="image"
              defaultValue={serviceImage}
              aria-labelledby="image-error"
            />
          ) : (
            <div
              className={cn(
                "w-full rounded-md flex justify-between items-center gap-2 py-2.5 pl-4 pr-2",
                serviceSourcheChange !== undefined
                  ? "dark:bg-secondary-foreground bg-secondary/60"
                  : "bg-muted"
              )}
            >
              <span>
                {image}
                <span className="text-grey">:{tag}</span>
              </span>
            </div>
          )}
        </fieldset>

        <fieldset className="w-full flex flex-col gap-2">
          <legend>Credentials</legend>
          <p className="text-gray-400">
            If your service pulls private Docker images from a registry, specify
            the information below.
          </p>

          <label
            className="text-muted-foreground"
            htmlFor="credentials.username"
          >
            Username for registry
          </label>
          <Input
            placeholder={!isEditing ? "<empty>" : "username"}
            name="credentials.username"
            id="credentials.username"
            disabled={!isEditing}
            defaultValue={credentials?.username}
            className={cn(
              "disabled:placeholder-shown:font-mono disabled:bg-muted data-[edited]:disabled:bg-secondary/60",
              "data-[edited]:dark:disabled:bg-secondary-foreground",
              "disabled:border-transparent disabled:opacity-100"
            )}
            aria-labelledby="credentials.username-error"
          />

          <label
            className="text-muted-foreground"
            htmlFor="credentials.password"
          >
            Password for registry
          </label>
          <div className="flex gap-2">
            <Input
              placeholder={!isEditing ? "<empty>" : "*******"}
              disabled={!isEditing}
              type={isPasswordShown ? "text" : "password"}
              defaultValue={credentials?.password}
              name="credentials.password"
              id="credentials.password"
              className={cn(
                "disabled:placeholder-shown:font-mono disabled:bg-muted data-[edited]:disabled:bg-secondary/60",
                "data-[edited]:dark:disabled:bg-secondary-foreground",
                "disabled:border-transparent disabled:opacity-100"
              )}
              aria-labelledby="credentials.password-error"
            />

            <TooltipProvider>
              <Tooltip delayDuration={0}>
                <TooltipTrigger asChild>
                  <Button
                    variant="outline"
                    type="button"
                    onClick={() => setIsPasswordShown(!isPasswordShown)}
                    className="p-4"
                  >
                    {isPasswordShown ? (
                      <EyeOffIcon size={15} className="flex-none" />
                    ) : (
                      <EyeIcon size={15} className="flex-none" />
                    )}
                    <span className="sr-only">
                      {isPasswordShown ? "Hide" : "Show"} password
                    </span>
                  </Button>
                </TooltipTrigger>
                <TooltipContent>
                  {isPasswordShown ? "Hide" : "Show"} password
                </TooltipContent>
              </Tooltip>
            </TooltipProvider>
          </div>
        </fieldset>
        <div className="flex gap-4">
          {isEditing && (
            <SubmitButton
              isPending={isPending}
              variant="secondary"
              className="self-start"
              name="intent"
              value="update-field"
            >
              {isPending ? (
                <>
                  <LoaderIcon className="animate-spin" size={15} />
                  <span>Updating...</span>
                </>
              ) : (
                <>
                  <CheckIcon size={15} className="flex-none" />
                  <span>Update</span>
                </>
              )}
            </SubmitButton>
          )}
          <Button
            variant="outline"
            type="button"
            onClick={() => {
              setIsEditing(!isEditing);
            }}
            className="bg-inherit inline-flex items-center gap-2 border-muted-foreground py-0.5"
          >
            {!isEditing ? (
              <>
                <span>Edit</span>
                <PencilLineIcon size={15} className="flex-none" />
              </>
            ) : (
              <>
                <XIcon size={15} className="flex-none" />
                <span>Cancel</span>
              </>
            )}
          </Button>
        </div>
      </fetcher.Form>
    </div>
  );
}
