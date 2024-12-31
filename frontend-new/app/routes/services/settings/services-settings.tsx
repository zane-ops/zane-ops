import { useQuery } from "@tanstack/react-query";
import {
  CheckIcon,
  ContainerIcon,
  InfoIcon,
  LoaderIcon,
  PencilLineIcon,
  XIcon
} from "lucide-react";
import * as React from "react";
import { Link, redirect, useFetcher, useMatches } from "react-router";
import { toast } from "sonner";
import { apiClient } from "~/api/client";
import { Button, SubmitButton } from "~/components/ui/button";
import { Input } from "~/components/ui/input";
import { serviceQueries } from "~/lib/queries";
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
            {/* <ServiceImageForm />
            <ServiceImageCredentialsForm /> */}
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

  await queryClient.invalidateQueries(
    serviceQueries.single({ project_slug, service_slug: service_slug })
  );
  toast.success("Service updated successfully!", { closeButton: true });

  if (data.slug !== service_slug) {
    queryClient.setQueryData(
      serviceQueries.single({ project_slug, service_slug: data.slug }).queryKey,
      data
    );

    throw redirect(`/project/${project_slug}/services/${data.slug}/settings`);
  }
}

function ServiceSlugForm({ service_slug }: ServiceFormProps) {
  const [isEditing, setIsEditing] = React.useState(false);

  const fetcher = useFetcher<typeof clientAction>();
  const isPending = fetcher.state !== "idle";
  const errors = getFormErrorsFromResponseData(fetcher.data?.errors);

  React.useEffect(() => {
    if (fetcher.state === "idle" && !fetcher.data?.errors) {
      setIsEditing(false);
    }
  }, [fetcher.state, fetcher.data]);

  return (
    <div className="w-full max-w-4xl">
      {isEditing ? (
        <fetcher.Form
          method="post"
          className="flex flex-col md:flex-row gap-2 w-full"
        >
          <fieldset className="flex flex-col gap-1.5 flex-1">
            <label htmlFor="slug">Service slug</label>
            <Input
              id="slug"
              name="slug"
              placeholder="service slug"
              defaultValue={fetcher.data?.userData.slug ?? service_slug}
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
              onClick={() => setIsEditing(false)}
              variant="outline"
              className="bg-inherit"
              type="button"
            >
              <XIcon size={15} className="flex-none" />
              <span className="sr-only">Cancel</span>
            </Button>
          </div>
        </fetcher.Form>
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
