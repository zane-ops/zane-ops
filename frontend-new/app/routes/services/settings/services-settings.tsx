import { useQuery } from "@tanstack/react-query";
import {
  AlertCircleIcon,
  CableIcon,
  CheckIcon,
  ContainerIcon,
  ExternalLinkIcon,
  EyeIcon,
  EyeOffIcon,
  InfoIcon,
  LoaderIcon,
  PencilLineIcon,
  TriangleAlertIcon,
  Undo2Icon,
  XIcon
} from "lucide-react";
import * as React from "react";
import { flushSync } from "react-dom";
import { Link, useFetcher, useMatches, useNavigate } from "react-router";
import { toast } from "sonner";
import { type RequestInput, apiClient } from "~/api/client";
import { Code } from "~/components/code";
import { Alert, AlertDescription, AlertTitle } from "~/components/ui/alert";
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

        <section id="networking" className="flex gap-1 scroll-mt-20">
          <div className="w-16 hidden md:flex flex-col items-center">
            <div className="flex rounded-full size-10 flex-none items-center justify-center p-1 border-2 border-grey/50">
              <CableIcon size={15} className="flex-none text-grey" />
            </div>
            <div className="h-full border border-grey/50"></div>
          </div>
          <div className="w-full flex flex-col gap-12 pt-1 pb-14">
            <h2 className="text-lg text-grey">Networking</h2>
            <ServicePortsForm
              service_slug={service_slug}
              project_slug={project_slug}
            />
            {/* 
            <hr className="w-full max-w-4xl border-border" />
            <ServiceURLsForm className="w-full max-w-4xl" />
            <hr className="w-full max-w-4xl border-border" />
            <NetworkAliasesGroup className="w-full max-w-4xl border-border" /> */}
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
    case "request-service-change": {
      return requestServiceChange({
        project_slug: params.projectSlug,
        service_slug: params.serviceSlug,
        formData
      });
    }
    case "cancel-service-change": {
      return cancelServiceChange({
        project_slug: params.projectSlug,
        service_slug: params.serviceSlug,
        formData
      });
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

type ChangeRequestBody = RequestInput<
  "put",
  "/api/projects/{project_slug}/request-service-changes/docker/{service_slug}/"
>;
type FindByType<Union, Type> = Union extends { field: Type } ? Union : never;
type BodyOf<Type extends ChangeRequestBody["field"]> = FindByType<
  ChangeRequestBody,
  Type
>;

async function requestServiceChange({
  project_slug,
  service_slug,
  formData
}: {
  project_slug: string;
  service_slug: string;
  formData: FormData;
}) {
  const field = formData
    .get("change_field")
    ?.toString() as ChangeRequestBody["field"];
  const type = formData
    .get("change_type")
    ?.toString() as ChangeRequestBody["type"];
  const item_id = formData.get("item_id")?.toString();

  let userData = null;
  switch (field) {
    case "source": {
      userData = {
        image: formData.get("image")?.toString(),
        credentials: {
          username: formData.get("credentials.username")?.toString(),
          password: formData.get("credentials.password")?.toString()
        }
      };
      break;
    }
    default: {
      throw new Error("Unexpected field");
    }
  }

  const { error: errors, data } = await apiClient.PUT(
    "/api/projects/{project_slug}/request-service-changes/docker/{service_slug}/",
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
      body: {
        field,
        type,
        new_value: userData,
        item_id
      } as BodyOf<typeof field>
    }
  );
  if (errors) {
    return {
      errors,
      userData
    };
  }

  await Promise.all([
    queryClient.invalidateQueries({
      ...serviceQueries.single({ project_slug, service_slug: service_slug }),
      exact: true
    })
  ]);

  return {
    data
  };
}

async function cancelServiceChange({
  project_slug,
  service_slug,
  formData
}: {
  project_slug: string;
  service_slug: string;
  formData: FormData;
}) {
  const change_id = formData.get("change_id")?.toString();
  const { error: errors, data } = await apiClient.DELETE(
    "/api/projects/{project_slug}/cancel-service-changes/docker/{service_slug}/{change_id}/",
    {
      headers: {
        ...(await getCsrfTokenHeader())
      },
      params: {
        path: {
          project_slug,
          service_slug,
          change_id: change_id!
        }
      }
    }
  );

  if (errors) {
    return {
      errors
    };
  }

  await queryClient.invalidateQueries({
    ...serviceQueries.single({ project_slug, service_slug }),
    exact: true
  });
  return {
    data
  };
}

function ServiceSlugForm({ service_slug }: ServiceFormProps) {
  const [isEditing, setIsEditing] = React.useState(false);
  const fetcher = useFetcher<typeof clientAction>();
  const isPending = fetcher.state !== "idle";
  const navigate = useNavigate();
  const [data, setData] = React.useState(fetcher.data);
  const errors = getFormErrorsFromResponseData(data?.errors);
  const inputRef = React.useRef<React.ComponentRef<"input">>(null);

  React.useEffect(() => {
    setData(fetcher.data);

    if (fetcher.state === "idle" && fetcher.data?.data?.slug) {
      navigate(`../../${fetcher.data.data.slug}/settings`, {
        replace: true,
        relative: "path"
      });
      setIsEditing(false);
    }
  }, [fetcher.state, fetcher.data]);

  return (
    <div className="w-full max-w-4xl">
      <fetcher.Form
        method="post"
        className="flex flex-col md:flex-row gap-2 w-full"
      >
        <fieldset className="flex flex-col gap-1.5 flex-1">
          <label htmlFor="slug">Service slug</label>
          <div className="relative">
            <Input
              id="slug"
              name="slug"
              ref={inputRef}
              placeholder="service slug"
              defaultValue={service_slug}
              disabled={!isEditing}
              aria-labelledby="slug-error"
              className={cn(
                "disabled:placeholder-shown:font-mono disabled:bg-muted",
                "disabled:border-transparent disabled:opacity-100"
              )}
            />

            {!isEditing && (
              <Button
                variant="outline"
                onClick={() => {
                  flushSync(() => {
                    setIsEditing(true);
                  });
                  inputRef.current?.focus();
                }}
                className={cn(
                  "absolute inset-y-0 right-0 text-sm py-0 border-0",
                  "bg-inherit inline-flex items-center gap-2 border-muted-foreground py-0.5"
                )}
              >
                <span>Edit</span>
                <PencilLineIcon size={15} />
              </Button>
            )}
          </div>

          {errors.slug && (
            <span id="slug-error" className="text-red-500 text-sm">
              {errors.slug}
            </span>
          )}
        </fieldset>

        {isEditing && (
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
                setIsEditing(false);
                setData(undefined);
              }}
              variant="outline"
              className="bg-inherit"
              type="reset"
            >
              <XIcon size={15} className="flex-none" />
              <span className="sr-only">Cancel</span>
            </Button>
          </div>
        )}
      </fetcher.Form>
    </div>
  );
}

function ServiceSourceForm({ service_slug, project_slug }: ServiceFormProps) {
  const fetcher = useFetcher<typeof clientAction>();
  const isPending = fetcher.state !== "idle";

  const [data, setData] = React.useState(fetcher.data);
  const [isEditing, setIsEditing] = React.useState(false);
  const [isPasswordShown, setIsPasswordShown] = React.useState(false);
  const inputRef = React.useRef<React.ComponentRef<"input">>(null);

  const { data: service } = useServiceQuery({ project_slug, service_slug });

  React.useEffect(() => {
    setData(fetcher.data);
    if (fetcher.state === "idle" && fetcher.data) {
      if (!fetcher.data.errors) {
        setIsEditing(false);
        setIsPasswordShown(false);
      }
    }
  }, [fetcher.state, fetcher.data]);

  const serviceSourcheChange = service.unapplied_changes.find(
    (change) => change.field === "source"
  ) as
    | { new_value: Pick<DockerService, "image" | "credentials">; id: string }
    | undefined;

  const serviceImage = serviceSourcheChange?.new_value.image ?? service.image!;
  const imageParts = serviceImage.split(":");
  const tag = imageParts.length > 1 ? imageParts.pop() : "latest";
  const image = imageParts.join(":");

  const credentials =
    serviceSourcheChange?.new_value.credentials ?? service.credentials;

  const errors = getFormErrorsFromResponseData(data?.errors);

  React.useEffect(() => {
    if (errors.non_field_errors && errors.non_field_errors.length > 0) {
      const fullErrorMessages = errors.non_field_errors.join("\n");
      toast.error("Error", {
        description: fullErrorMessages,
        closeButton: true,
        onDismiss: () => {
          setData(undefined);
        }
      });
    }
  }, [errors]);

  return (
    <div className="w-full max-w-4xl">
      <fetcher.Form method="post" className="flex flex-col gap-4 w-full">
        <input type="hidden" name="change_field" value="source" />
        <input type="hidden" name="change_type" value="UPDATE" />
        <input
          type="hidden"
          name="change_id"
          value={serviceSourcheChange?.id}
        />
        <fieldset className="flex flex-col gap-1.5 flex-1">
          <label htmlFor="image">Source Image</label>
          <div className="relative">
            <Input
              id="image"
              name="image"
              ref={inputRef}
              disabled={!isEditing || serviceSourcheChange !== undefined}
              placeholder="image"
              defaultValue={serviceImage}
              aria-labelledby="image-error"
              data-edited={
                serviceSourcheChange !== undefined ? "true" : undefined
              }
              className={cn(
                "disabled:placeholder-shown:font-mono disabled:bg-muted data-[edited]:disabled:bg-secondary/60",
                "data-[edited]:dark:disabled:bg-secondary-foreground",
                "disabled:border-transparent disabled:opacity-100",
                "disabled:text-transparent"
              )}
            />
            {!isEditing && (
              <span className="absolute inset-y-0 left-3 flex items-center pr-2 text-sm">
                {image}
                <span className="text-grey">:{tag}</span>
              </span>
            )}
          </div>
          {errors.new_value?.image && (
            <span id="image-error" className="text-red-500 text-sm">
              {errors.new_value?.image}
            </span>
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
          <div className="flex flex-col gap-1">
            <Input
              placeholder={!isEditing ? "<empty>" : "username"}
              name="credentials.username"
              id="credentials.username"
              disabled={!isEditing || serviceSourcheChange !== undefined}
              defaultValue={credentials?.username}
              data-edited={
                serviceSourcheChange !== undefined ? "true" : undefined
              }
              className={cn(
                "disabled:placeholder-shown:font-mono disabled:bg-muted data-[edited]:disabled:bg-secondary/60",
                "data-[edited]:dark:disabled:bg-secondary-foreground",
                "disabled:border-transparent disabled:opacity-100 disabled:select-none"
              )}
              aria-labelledby="credentials.username-error"
            />
            {errors.new_value?.credentials?.username && (
              <span
                id="credentials.username-error"
                className="text-red-500 text-sm"
              >
                {errors.new_value?.credentials?.username}
              </span>
            )}
          </div>

          <label
            className="text-muted-foreground"
            htmlFor="credentials.password"
          >
            Password for registry
          </label>
          <div className="flex gap-2 items-start">
            <div className="inline-flex flex-col gap-1 flex-1">
              <Input
                placeholder={!isEditing ? "<empty>" : "*******"}
                disabled={!isEditing || serviceSourcheChange !== undefined}
                type={isPasswordShown ? "text" : "password"}
                defaultValue={credentials?.password}
                name="credentials.password"
                id="credentials.password"
                data-edited={
                  serviceSourcheChange !== undefined ? "true" : undefined
                }
                className={cn(
                  "disabled:placeholder-shown:font-mono disabled:bg-muted data-[edited]:disabled:bg-secondary/60",
                  "data-[edited]:dark:disabled:bg-secondary-foreground",
                  "disabled:border-transparent disabled:opacity-100"
                )}
                aria-labelledby="credentials.password-error"
              />
              {errors.new_value?.credentials?.password && (
                <span
                  id="credentials.username-error"
                  className="text-red-500 text-sm"
                >
                  {errors.new_value?.credentials?.password}
                </span>
              )}
            </div>

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
          {serviceSourcheChange !== undefined ? (
            <>
              <SubmitButton
                isPending={isPending}
                variant="outline"
                name="intent"
                value="cancel-service-change"
              >
                {isPending ? (
                  <>
                    <LoaderIcon className="animate-spin" size={15} />
                    <span>Reverting...</span>
                  </>
                ) : (
                  <>
                    <Undo2Icon size={15} className="flex-none" />
                    <span>Revert change</span>
                  </>
                )}
              </SubmitButton>
            </>
          ) : (
            <>
              {isEditing && (
                <SubmitButton
                  isPending={isPending}
                  variant="secondary"
                  className="self-start"
                  name="intent"
                  value="request-service-change"
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
                type="reset"
                disabled={isPending}
                onClick={() => {
                  const newIsEditing = !isEditing;
                  flushSync(() => {
                    setIsEditing(newIsEditing);
                  });
                  if (newIsEditing) {
                    inputRef.current?.focus();
                  }
                  setData(undefined);
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
            </>
          )}
        </div>
      </fetcher.Form>
    </div>
  );
}

function ServicePortsForm({ service_slug, project_slug }: ServiceFormProps) {
  return (
    <div className="w-full max-w-4xl flex flex-col gap-5">
      <div className="flex flex-col gap-3">
        <h3 className="text-lg">Exposed ports</h3>
        <p className="text-gray-400">
          This makes the service reachable externally via the ports defined
          in&nbsp;
          <Code>host port</Code>. Using&nbsp;
          <Code>80</Code>
          &nbsp;or&nbsp;
          <Code>443</Code>
          &nbsp;will create a default URL for the service.
        </p>

        <Alert variant="warning">
          <TriangleAlertIcon size={15} />
          <AlertTitle>Warning</AlertTitle>
          <AlertDescription>
            Using a host value other than 80 or 443 will disable&nbsp;
            <a href="#" className="underline inline-flex gap-1 items-center">
              zero-downtime deployments <ExternalLinkIcon size={12} />
            </a>
            .
          </AlertDescription>
        </Alert>
      </div>
    </div>
  );
}

function NewServicePortForm() {}
