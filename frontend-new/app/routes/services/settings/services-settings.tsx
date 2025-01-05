import { useQuery } from "@tanstack/react-query";
import {
  CableIcon,
  CheckIcon,
  ContainerIcon,
  CopyIcon,
  GlobeLockIcon,
  HammerIcon,
  InfoIcon
} from "lucide-react";
import { Link, useFetcher, useMatches } from "react-router";
import { type RequestInput, apiClient } from "~/api/client";

import * as React from "react";
import { toast } from "sonner";
import { Code } from "~/components/code";
import { Button } from "~/components/ui/button";
import {
  Tooltip,
  TooltipContent,
  TooltipProvider,
  TooltipTrigger
} from "~/components/ui/tooltip";
import { projectQueries, serviceQueries } from "~/lib/queries";
import { cn } from "~/lib/utils";
import { queryClient } from "~/root";
import { ServiceCommandForm } from "~/routes/services/settings/service-command-form";
import { ServiceHealthcheckForm } from "~/routes/services/settings/service-healthcheck-form";
import { ServicePortsForm } from "~/routes/services/settings/service-ports-form";
import { ServiceSlugForm } from "~/routes/services/settings/service-slug-form";
import { ServiceSourceForm } from "~/routes/services/settings/service-source-form";
import { ServiceURLsForm } from "~/routes/services/settings/service-urls-form";
import { getCsrfTokenHeader, wait } from "~/utils";
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
              service_slug={service_slug}
              project_slug={project_slug}
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
            <hr className="w-full max-w-4xl border-border" />
            <ServiceURLsForm
              project_slug={project_slug}
              service_slug={service_slug}
            />
            <hr className="w-full max-w-4xl border-border" />
            <NetworkAliasesGroup
              project_slug={project_slug}
              service_slug={service_slug}
            />
          </div>
        </section>

        <section id="deploy" className="flex gap-1 scroll-mt-20">
          <div className="w-16 hidden md:flex flex-col items-center">
            <div className="flex rounded-full size-10 flex-none items-center justify-center p-1 border-2 border-grey/50">
              <HammerIcon size={15} className="flex-none text-grey" />
            </div>
            <div className="h-full border border-grey/50"></div>
          </div>
          <div className="w-full flex flex-col gap-12 pt-1 pb-14">
            <h2 className="text-lg text-grey">Deploy</h2>
            <ServiceCommandForm
              project_slug={project_slug}
              service_slug={service_slug}
            />
            <ServiceHealthcheckForm
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

function NetworkAliasesGroup({
  project_slug,
  service_slug
}: {
  project_slug: string;
  service_slug: string;
}) {
  const { data: service } = useServiceQuery({
    project_slug,
    service_slug
  });
  const [hasCopied, startTransition] = React.useTransition();

  return (
    <div className="flex flex-col gap-5 w-full max-w-4xl border-border">
      <div className="flex flex-col gap-3">
        <h3 className="text-lg">Network alias</h3>
        <p className="text-gray-400">
          You can reach this service from within the same project using this
          value
        </p>
      </div>
      <div className="border border-border px-4 pb-4 pt-1 rounded-md flex items-center gap-4 group">
        <GlobeLockIcon
          className="text-grey flex-none hidden md:block"
          size={20}
        />
        <div className="flex flex-col gap-0.5">
          <div className="flex gap-2 items-center">
            <span className="text-lg break-all">
              {service.network_aliases[0]}
            </span>
            <TooltipProvider>
              <Tooltip delayDuration={0}>
                <TooltipTrigger asChild>
                  <Button
                    variant="ghost"
                    className={cn(
                      "px-2.5 py-0.5 focus-visible:opacity-100 group-hover:opacity-100",
                      hasCopied ? "opacity-100" : "md:opacity-0"
                    )}
                    onClick={() => {
                      navigator.clipboard
                        .writeText(service.network_aliases[0])
                        .then(() => {
                          // show pending state (which is success state), until the user has stopped clicking the button
                          startTransition(() => wait(1000));
                        });
                    }}
                  >
                    {hasCopied ? (
                      <CheckIcon size={15} className="flex-none" />
                    ) : (
                      <CopyIcon size={15} className="flex-none" />
                    )}
                    <span className="sr-only">Copy network alias</span>
                  </Button>
                </TooltipTrigger>
                <TooltipContent>Copy network alias</TooltipContent>
              </Tooltip>
            </TooltipProvider>
          </div>
          <small className="text-grey">
            You can also simply use <Code>{service.network_alias}</Code>
          </small>
        </div>
      </div>
    </div>
  );
}

export function useServiceQuery({
  project_slug,
  service_slug
}: { project_slug: string; service_slug: string }) {
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

export function useFetcherWithCallbacks({
  onSettled,
  onSuccess
}: {
  onSuccess?: (data: Awaited<ReturnType<typeof clientAction>>) => void;
  onSettled?: (data: Awaited<ReturnType<typeof clientAction>>) => void;
}) {
  const fetcher = useFetcher<typeof clientAction>();
  const [data, setData] = React.useState(fetcher.data);
  const onSuccessRef = React.useRef(onSuccess);
  const onSettledRef = React.useRef(onSettled);

  React.useEffect(() => {
    onSuccessRef.current = onSuccess;
    onSettledRef.current = onSettled;
  });

  React.useEffect(() => {
    setData(fetcher.data);
    if (fetcher.state === "idle" && fetcher.data) {
      onSettledRef.current?.(fetcher.data);
      if (!fetcher.data.errors) {
        onSuccessRef.current?.(fetcher.data);
      }
    }
  }, [fetcher.data, fetcher.state]);

  return {
    fetcher,
    data,
    reset: () => setData(undefined)
  };
}

export async function clientAction({
  request,
  params
}: Route.ClientActionArgs) {
  const formData = await request.formData();
  const intent = formData.get("intent")?.toString();

  console.log({
    formData,
    intent
  });
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
      throw new Error(`Unexpected intent ${intent}`);
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
    case "ports": {
      userData = {
        forwarded: Number(formData.get("forwarded")?.toString() ?? ""),
        host: Number((formData.get("host")?.toString() ?? "").trim() || 80)
      };
      break;
    }
    case "urls":
      {
        const isRedirect = formData.get("is_redirect")?.toString() === "on";

        userData = {
          domain: formData.get("domain")?.toString() ?? "",
          base_path: formData.get("base_path")?.toString(),
          strip_prefix: formData.get("strip_prefix")?.toString() === "on",
          redirect_to: !isRedirect
            ? undefined
            : {
                url: formData.get("redirect_to_url")?.toString() ?? "",
                permanent:
                  formData.get("redirect_to_permanent")?.toString() === "on"
              }
        };
      }
      break;
    case "command":
      {
        userData = formData.get("command")?.toString().trim();
      }
      break;
    default: {
      throw new Error("Unexpected field");
    }
  }

  let toastId: string | number | undefined;
  if (type === "DELETE") {
    toastId = toast.loading("Sending change request...");
    userData = undefined;
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
    if (toastId) {
      const fullErrorMessage = errors.errors.map((err) => err.detail).join(" ");

      toast.error("Failed to send change request", {
        description: fullErrorMessage,
        id: toastId,
        closeButton: true
      });
    }
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

  if (toastId) {
    toast.success("Change request sent", { id: toastId, closeButton: true });
  }

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
  const toastId = toast.loading("Cancelling service change...");
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
    toast.error("Failed to cancel change", { id: toastId, closeButton: true });
    return {
      errors
    };
  }

  await queryClient.invalidateQueries({
    ...serviceQueries.single({ project_slug, service_slug }),
    exact: true
  });
  toast.success("Change cancelled", { id: toastId, closeButton: true });
  return {
    data
  };
}
