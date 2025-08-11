import { useQuery } from "@tanstack/react-query";
import {
  CableIcon,
  ContainerIcon,
  FileSlidersIcon,
  FlameIcon,
  GitBranchIcon,
  GlobeLockIcon,
  HammerIcon,
  HardDriveIcon,
  InfoIcon
} from "lucide-react";
import { Link, useFetcher, useMatches } from "react-router";
import { type RequestInput, apiClient } from "~/api/client";

import * as React from "react";
import { toast } from "sonner";
import { Code } from "~/components/code";
import { CopyButton } from "~/components/copy-button";
import { StatusBadge } from "~/components/status-badge";
import { Separator } from "~/components/ui/separator";
import {
  Tooltip,
  TooltipContent,
  TooltipProvider,
  TooltipTrigger
} from "~/components/ui/tooltip";
import {
  type Service,
  gitAppsQueries,
  projectQueries,
  resourceQueries,
  serviceQueries
} from "~/lib/queries";
import { cn } from "~/lib/utils";
import { queryClient } from "~/root";
import { ServiceAutoDeployForm } from "~/routes/services/components/service-auto-deploy-form";
import { ServiceBuilderForm } from "~/routes/services/components/service-builder-form";
import { ServiceCommandForm } from "~/routes/services/components/service-command-form";
import { ServiceConfigsForm } from "~/routes/services/components/service-configs-form";
import { ServiceDangerZoneForm } from "~/routes/services/components/service-danger-zone-form";
import {
  ServiceDeployURLForm,
  ServicePreviewDeployURLForm
} from "~/routes/services/components/service-deploy-url-form";
import { ServiceGitSourceForm } from "~/routes/services/components/service-git-source-form";
import { ServiceHealthcheckForm } from "~/routes/services/components/service-healthcheck-form";
import { ServicePortsForm } from "~/routes/services/components/service-ports-form";
import { ServiceResourceLimits } from "~/routes/services/components/service-resource-limits-form";
import { ServiceSlugForm } from "~/routes/services/components/service-slug-form";
import { ServiceSourceForm } from "~/routes/services/components/service-source-form";
import { ServiceURLsForm } from "~/routes/services/components/service-urls-form";
import { ServiceVolumesForm } from "~/routes/services/components/service-volumes-form";
import { getCsrfTokenHeader, wait } from "~/utils";
import { type Route } from "./+types/service-settings";

export async function clientLoader({}: Route.ClientLoaderArgs) {
  const gitAppList = await queryClient.ensureQueryData(gitAppsQueries.list);
  return { gitAppList };
}

export default function ServiceSettingsPage({
  params: {
    projectSlug: project_slug,
    serviceSlug: service_slug,
    envSlug: env_slug
  },
  matches: {
    "2": {
      data: { service }
    }
  }
}: Route.ComponentProps) {
  return (
    <div className="my-6 grid lg:grid-cols-12 gap-10 relative max-w-full">
      <div className="lg:col-span-10 flex flex-col max-w-full">
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
              env_slug={env_slug}
            />

            <ServiceAutoDeployForm
              service_slug={service_slug}
              project_slug={project_slug}
              env_slug={env_slug}
            />
          </div>
        </section>

        {service.type === "DOCKER_REGISTRY" && (
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
                env_slug={env_slug}
              />
            </div>
          </section>
        )}

        {service.type === "GIT_REPOSITORY" && (
          <>
            <section id="git-source" className="flex gap-1 scroll-mt-20">
              <div className="w-16 hidden md:flex flex-col items-center">
                <div className="flex rounded-full size-10 flex-none items-center justify-center p-1 border-2 border-grey/50">
                  <GitBranchIcon size={15} className="flex-none text-grey" />
                </div>
                <div className="h-full border border-grey/50"></div>
              </div>

              <div className="w-full flex flex-col gap-5 pt-1 pb-14">
                <h2 className="text-lg text-grey">Git Source</h2>
                <ServiceGitSourceForm
                  project_slug={project_slug}
                  service_slug={service_slug}
                  env_slug={env_slug}
                />
              </div>
            </section>
            <section id="builder" className="flex gap-1 scroll-mt-20">
              <div className="w-16 hidden md:flex flex-col items-center">
                <div className="flex rounded-full size-10 flex-none items-center justify-center p-1 border-2 border-grey/50">
                  <HammerIcon size={15} className="flex-none text-grey" />
                </div>
                <div className="h-full border border-grey/50"></div>
              </div>

              <div className="w-full flex flex-col gap-5 pt-1 pb-14">
                <h2 className="text-lg text-grey">Builder</h2>
                <ServiceBuilderForm
                  project_slug={project_slug}
                  service_slug={service_slug}
                  env_slug={env_slug}
                />
              </div>
            </section>
          </>
        )}

        <section id="networking" className="flex gap-1 scroll-mt-20">
          <div className="w-16 hidden md:flex flex-col items-center">
            <div className="flex rounded-full size-10 flex-none items-center justify-center p-1 border-2 border-grey/50">
              <CableIcon size={15} className="flex-none text-grey" />
            </div>
            <div className="h-full border border-grey/50"></div>
          </div>
          <div className="w-full flex flex-col gap-12 pt-1 pb-14">
            <div className="flex flex-col gap-6">
              <h2 className="text-lg text-grey">Networking</h2>
              <NetworkAliasesGroup
                project_slug={project_slug}
                service_slug={service_slug}
                env_slug={env_slug}
              />
            </div>

            <hr className="w-full max-w-4xl border-border" />
            <ServiceURLsForm
              project_slug={project_slug}
              service_slug={service_slug}
              env_slug={env_slug}
            />
            <hr className="w-full max-w-4xl border-border" />

            <ServicePortsForm
              service_slug={service_slug}
              project_slug={project_slug}
              env_slug={env_slug}
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
              env_slug={env_slug}
            />
            <ServiceHealthcheckForm
              project_slug={project_slug}
              service_slug={service_slug}
              env_slug={env_slug}
            />
            <ServiceResourceLimits
              project_slug={project_slug}
              service_slug={service_slug}
              env_slug={env_slug}
            />
            <hr className="w-full max-w-4xl border-border" />
            <ServiceDeployURLForm
              project_slug={project_slug}
              service_slug={service_slug}
              env_slug={env_slug}
            />
            {service.type === "GIT_REPOSITORY" && (
              <ServicePreviewDeployURLForm
                project_slug={project_slug}
                service_slug={service_slug}
                env_slug={env_slug}
              />
            )}
          </div>
        </section>

        <section id="volumes" className="flex gap-1 scroll-mt-20">
          <div className="w-16 hidden md:flex flex-col items-center">
            <div className="flex rounded-full size-10 flex-none items-center justify-center p-1 border-2 border-grey/50">
              <HardDriveIcon size={15} className="flex-none text-grey" />
            </div>
            <div className="h-full border border-grey/50"></div>
          </div>
          <div className="w-full flex flex-col gap-5 pt-1 pb-14">
            <h2 className="text-lg text-grey">Volumes</h2>
            <ServiceVolumesForm
              project_slug={project_slug}
              service_slug={service_slug}
              env_slug={env_slug}
            />
          </div>
        </section>

        <section id="configs" className="flex gap-1 scroll-mt-20 max-w-full">
          <div className="w-16 hidden md:flex flex-col items-center">
            <div className="flex rounded-full size-10 flex-none items-center justify-center p-1 border-2 border-grey/50">
              <FileSlidersIcon size={15} className="flex-none text-grey" />
            </div>
            <div className="h-full border border-grey/50"></div>
          </div>
          <div className="w-full flex flex-col gap-5 pt-1 pb-14">
            <h2 className="text-lg text-grey">Config files</h2>
            <ServiceConfigsForm
              project_slug={project_slug}
              service_slug={service_slug}
              env_slug={env_slug}
            />
          </div>
        </section>

        <section id="danger" className="flex gap-1 scroll-mt-20">
          <div className="w-16 hidden md:flex flex-col items-center">
            <div className="flex rounded-full size-10 flex-none items-center justify-center p-1 border-2 border-red-500">
              <FlameIcon size={15} className="flex-none text-red-500" />
            </div>
          </div>
          <div className="w-full flex flex-col gap-5 pt-1 pb-14">
            <h2 className="text-lg text-red-400">Danger Zone</h2>
            <ServiceDangerZoneForm
              project_slug={project_slug}
              service_slug={service_slug}
              env_slug={env_slug}
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
            {service.type === "DOCKER_REGISTRY" && (
              <li>
                <Link
                  to={{
                    hash: "#source"
                  }}
                >
                  Source
                </Link>
              </li>
            )}
            {service.type === "GIT_REPOSITORY" && (
              <>
                <li>
                  <Link
                    to={{
                      hash: "#git-source"
                    }}
                  >
                    Git Source
                  </Link>
                </li>
                <li>
                  <Link
                    to={{
                      hash: "#builder"
                    }}
                  >
                    Builder
                  </Link>
                </li>
              </>
            )}
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
            <li>
              <Link
                to={{
                  hash: "#configs"
                }}
              >
                Config files
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
  service_slug,
  env_slug
}: {
  project_slug: string;
  service_slug: string;
  env_slug: string;
}) {
  const { data: service } = useServiceQuery({
    project_slug,
    service_slug,
    env_slug
  });

  return (
    <div className="flex flex-col gap-5 w-full max-w-4xl border-border">
      <div className="flex flex-col gap-3">
        <h3 className="text-lg">Network aliases</h3>
        <p className="text-gray-400">
          You can reach this service using these values
        </p>
      </div>
      <div className="border border-border px-4 py-2 rounded-md flex items-center gap-4 group">
        <GlobeLockIcon
          className="text-grey flex-none hidden md:block"
          size={20}
        />

        <div className="flex flex-col gap-0.5">
          <div className="flex gap-2 items-center flex-wrap">
            <StatusBadge color="blue" pingState="hidden">
              Environment alias
            </StatusBadge>
            <div className="flex gap-2 items-center">
              <span className="text-lg break-all">{service.network_alias}</span>
              <TooltipProvider>
                <Tooltip delayDuration={0}>
                  <TooltipTrigger asChild>
                    <CopyButton
                      value={service.network_alias!.replace(
                        ".zaneops.internal",
                        ""
                      )}
                      label="Copy network alias"
                      className="!opacity-100"
                    />
                  </TooltipTrigger>
                  <TooltipContent>
                    Copy environment network alias
                  </TooltipContent>
                </Tooltip>
              </TooltipProvider>
            </div>
          </div>
          <small>
            You can also use{" "}
            <Code className=" break-all">{service.network_aliases[0]}</Code>
          </small>
          <Separator className="my-2" />
          <div className="flex gap-2 items-center flex-wrap">
            <StatusBadge color="gray" pingState="hidden">
              Global alias
            </StatusBadge>
            <div className="flex gap-2 items-center">
              <span className="text-lg break-all">
                {service.global_network_alias.replace(".zaneops.internal", "")}
              </span>

              <TooltipProvider>
                <Tooltip delayDuration={0}>
                  <TooltipTrigger asChild>
                    <CopyButton
                      value={service.global_network_alias.replace(
                        ".zaneops.internal",
                        ""
                      )}
                      label="Copy network alias"
                      className="!opacity-100"
                    />
                  </TooltipTrigger>
                  <TooltipContent>Copy global network alias</TooltipContent>
                </Tooltip>
              </TooltipProvider>
            </div>

            <small>
              You can also use{" "}
              <Code className=" break-all">{service.global_network_alias}</Code>
            </small>
          </div>
        </div>
      </div>
    </div>
  );
}

export function useServiceQuery({
  project_slug,
  service_slug,
  env_slug
}: { project_slug: string; service_slug: string; env_slug: string }) {
  const {
    "2": {
      data: { service: initialData }
    }
  } = useMatches() as Route.ComponentProps["matches"];

  return useQuery({
    ...serviceQueries.single({ project_slug, service_slug, env_slug }),
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
    if (fetcher.state === "idle" && fetcher.data) {
      onSettledRef.current?.(fetcher.data);
      if (!fetcher.data.errors) {
        onSuccessRef.current?.(fetcher.data);
      }
    }
  }, [fetcher.data, fetcher.state]);

  React.useEffect(() => {
    setData(fetcher.data);
  }, [fetcher.data]);

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

  switch (intent) {
    case "update-slug": {
      return updateServiceSlug({
        project_slug: params.projectSlug,
        service_slug: params.serviceSlug,
        env_slug: params.envSlug,
        formData
      });
    }
    case "update-auto-deploy": {
      return updateServiceAutoDeployOptions({
        project_slug: params.projectSlug,
        service_slug: params.serviceSlug,
        env_slug: params.envSlug,
        formData
      });
    }
    case "request-service-change":
    case "remove-service-healthcheck":
    case "remove-service-resource-limits": {
      return requestServiceChange({
        project_slug: params.projectSlug,
        service_slug: params.serviceSlug,
        env_slug: params.envSlug,
        formData
      });
    }
    case "cancel-service-change": {
      return cancelServiceChange({
        project_slug: params.projectSlug,
        service_slug: params.serviceSlug,
        env_slug: params.envSlug,
        formData
      });
    }
    case "regenerate-deploy-token": {
      return regenerateDeployToken({
        project_slug: params.projectSlug,
        service_slug: params.serviceSlug,
        env_slug: params.envSlug
      });
    }
    default: {
      throw new Error(`Unexpected intent \`${intent}\``);
    }
  }
}

async function regenerateDeployToken({
  project_slug,
  service_slug,
  env_slug
}: {
  project_slug: string;
  service_slug: string;
  env_slug: string;
}) {
  const toastId = toast.loading("Regenerating service deploy URL...");
  const { error: errors, data } = await apiClient.PATCH(
    "/api/projects/{project_slug}/{env_slug}/service-details/{service_slug}/regenerate-deploy-token/",
    {
      headers: {
        ...(await getCsrfTokenHeader())
      },
      params: {
        path: {
          project_slug,
          service_slug,
          env_slug
        }
      }
    }
  );
  if (errors) {
    const fullErrorMessage = errors.errors.map((err) => err.detail).join(" ");

    toast.error("Failed to regenerate the deloy URL", {
      description: fullErrorMessage,
      id: toastId,
      closeButton: true
    });
    return {
      errors
    };
  }

  await queryClient.invalidateQueries({
    ...serviceQueries.single({ project_slug, service_slug, env_slug }),
    exact: true
  });

  toast.success("Done", { id: toastId, closeButton: true });
  return {
    data
  };
}

async function updateServiceSlug({
  project_slug,
  service_slug,
  env_slug,
  formData
}: {
  project_slug: string;
  service_slug: string;
  env_slug: string;
  formData: FormData;
}) {
  let userData = {
    slug: formData.get("slug")?.toString()
  } satisfies RequestInput<
    "patch",
    "/api/projects/{project_slug}/{env_slug}/service-details/{slug}/"
  >;

  await queryClient.cancelQueries({
    queryKey: serviceQueries.single({ project_slug, service_slug, env_slug })
      .queryKey,
    exact: true
  });

  const { error: errors, data } = await apiClient.PATCH(
    "/api/projects/{project_slug}/{env_slug}/service-details/{slug}/",
    {
      headers: {
        ...(await getCsrfTokenHeader())
      },
      params: {
        path: {
          project_slug,
          slug: service_slug,
          env_slug
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
      serviceQueries.single({
        project_slug,
        service_slug,
        env_slug
      })
    ),
    queryClient.invalidateQueries(
      projectQueries.serviceList(project_slug, env_slug)
    ),
    queryClient.invalidateQueries({
      predicate: (query) =>
        query.queryKey[0] === resourceQueries.search().queryKey[0]
    })
  ]);

  toast.success("Success", {
    description: "Service updated succesfully",
    closeButton: true
  });
  if (data.slug !== service_slug) {
    queryClient.setQueryData(
      serviceQueries.single({ project_slug, service_slug: data.slug, env_slug })
        .queryKey,
      data
    );
  }
  return {
    data
  };
}

async function updateServiceAutoDeployOptions({
  project_slug,
  service_slug,
  env_slug,
  formData
}: {
  project_slug: string;
  service_slug: string;
  env_slug: string;
  formData: FormData;
}) {
  let userData: RequestInput<
    "patch",
    "/api/projects/{project_slug}/{env_slug}/service-details/{slug}/"
  > = {
    auto_deploy_enabled:
      formData.get("auto_deploy_enabled")?.toString() === "on"
  } satisfies RequestInput<
    "patch",
    "/api/projects/{project_slug}/{env_slug}/service-details/{slug}/"
  >;

  if (userData.auto_deploy_enabled) {
    const watch_paths = formData.get("watch_paths")?.toString();
    userData = {
      ...userData,
      cleanup_queue_on_auto_deploy:
        formData.get("cleanup_queue_on_auto_deploy")?.toString() === "on",
      watch_paths: !watch_paths ? null : watch_paths
    };
  }

  await queryClient.cancelQueries({
    queryKey: serviceQueries.single({ project_slug, service_slug, env_slug })
      .queryKey,
    exact: true
  });

  const { error: errors, data } = await apiClient.PATCH(
    "/api/projects/{project_slug}/{env_slug}/service-details/{slug}/",
    {
      headers: {
        ...(await getCsrfTokenHeader())
      },
      params: {
        path: {
          project_slug,
          slug: service_slug,
          env_slug
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
    serviceQueries.single({
      project_slug,
      service_slug,
      env_slug
    })
  );

  toast.success("Success", {
    description: "Service  updated succesfully",
    closeButton: true
  });

  return {
    data
  };
}

type ChangeRequestBody = RequestInput<
  "put",
  "/api/projects/{project_slug}/{env_slug}/request-service-changes/{service_slug}/"
>;
type FindByType<Union, Type> = Union extends { field: Type } ? Union : never;
type BodyOf<Type extends ChangeRequestBody["field"]> = FindByType<
  ChangeRequestBody,
  Type
>;

async function requestServiceChange({
  project_slug,
  service_slug,
  env_slug,
  formData
}: {
  project_slug: string;
  service_slug: string;
  env_slug: string;
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
        image: formData.get("image")!.toString(),
        credentials: {
          username: formData.get("credentials.username")?.toString(),
          password: formData.get("credentials.password")?.toString()
        }
      } satisfies BodyOf<typeof field>["new_value"];
      break;
    }
    case "ports": {
      userData = {
        forwarded: Number(formData.get("forwarded")?.toString() ?? ""),
        host: Number((formData.get("host")?.toString() ?? "").trim())
      } satisfies BodyOf<typeof field>["new_value"];
      break;
    }
    case "urls": {
      const isRedirect = formData.get("is_redirect")?.toString() === "on";

      const domain = formData.get("domain")?.toString();
      userData = {
        domain: domain ? domain : undefined,
        base_path: formData.get("base_path")?.toString(),
        strip_prefix: formData.get("strip_prefix")?.toString() === "on",
        associated_port: isRedirect
          ? undefined
          : Number(formData.get("associated_port")?.toString().trim()),
        redirect_to: !isRedirect
          ? undefined
          : {
              url: formData.get("redirect_to_url")?.toString() ?? "",
              permanent:
                formData.get("redirect_to_permanent")?.toString() === "on"
            }
      } satisfies BodyOf<typeof field>["new_value"];
      break;
    }
    case "command": {
      const cmd = formData.get("command")?.toString().trim() ?? "";
      userData = cmd.length === 0 ? null : cmd;
      break;
    }
    case "healthcheck": {
      const removeHealthcheck =
        formData.get("intent")?.toString() === "remove-service-healthcheck";

      const type = formData.get("type")?.toString() as NonNullable<
        Service["healthcheck"]
      >["type"];

      userData = removeHealthcheck
        ? null
        : ({
            type: formData.get("type")?.toString() as NonNullable<
              Service["healthcheck"]
            >["type"],
            associated_port:
              type === "PATH"
                ? Number(formData.get("associated_port")?.toString())
                : undefined,
            value: formData.get("value")?.toString() ?? "",
            timeout_seconds: Number(
              formData.get("timeout_seconds")?.toString() || 30
            ),
            interval_seconds: Number(
              formData.get("interval_seconds")?.toString() || 30
            )
          } satisfies BodyOf<typeof field>["new_value"]);
      break;
    }
    case "resource_limits": {
      const removeLimits =
        formData.get("intent")?.toString() === "remove-service-resource-limits";
      userData = removeLimits
        ? null
        : ({
            cpus: Boolean(formData.get("cpus")?.toString().trim())
              ? Number(formData.get("cpus")?.toString())
              : undefined,
            memory: Boolean(formData.get("memory")?.toString().trim())
              ? {
                  value: Number(formData.get("memory")?.toString())
                }
              : undefined
          } satisfies BodyOf<typeof field>["new_value"]);
      break;
    }
    case "volumes": {
      const hostPath = formData.get("host_path")?.toString();
      const name = formData.get("name")?.toString();
      userData = {
        container_path: formData.get("container_path")?.toString() ?? "",
        host_path: !hostPath ? undefined : hostPath,
        mode: formData
          .get("mode")
          ?.toString() as Service["volumes"][number]["mode"],
        name: !name ? undefined : name
      } satisfies BodyOf<typeof field>["new_value"];
      break;
    }
    case "configs": {
      const name = formData.get("name")?.toString();
      userData = {
        mount_path: formData.get("mount_path")?.toString() ?? "",
        language: formData.get("language")?.toString(),
        name: !name ? undefined : name,
        contents: formData.get("contents")?.toString() ?? ""
      } satisfies BodyOf<typeof field>["new_value"];
      break;
    }
    case "git_source": {
      const app_id = formData.get("git_app_id")?.toString() ?? "";
      userData = {
        repository_url: formData.get("repository_url")?.toString() ?? "",
        branch_name: formData.get("branch_name")?.toString() ?? "",
        commit_sha: formData.get("commit_sha")?.toString() ?? "",
        git_app_id: !app_id ? null : app_id
      } satisfies BodyOf<typeof field>["new_value"];
      break;
    }
    case "builder": {
      type BuilderRequestBody = BodyOf<typeof field>["new_value"];
      const build_stage_target = formData
        .get("build_stage_target")
        ?.toString()
        .trim();
      const not_found_page = formData.get("not_found_page")?.toString().trim();
      const custom_install_command = formData
        .get("custom_install_command")
        ?.toString()
        .trim();
      const custom_build_command = formData
        .get("custom_build_command")
        ?.toString()
        .trim();
      const custom_start_command = formData
        .get("custom_start_command")
        ?.toString()
        .trim();

      userData = {
        builder: formData
          .get("builder")
          ?.toString() as BuilderRequestBody["builder"],
        dockerfile_path: formData.get("dockerfile_path")?.toString(),
        build_context_dir: formData.get("build_context_dir")?.toString(),
        build_stage_target: !build_stage_target
          ? undefined
          : build_stage_target,
        publish_directory: formData.get("publish_directory")?.toString(),
        not_found_page: !not_found_page ? undefined : not_found_page,
        index_page: formData.get("index_page")?.toString().trim(),
        is_spa: formData.get("is_spa")?.toString() === "on",
        is_static: formData.get("is_static")?.toString() === "on",
        build_directory: formData.get("build_directory")?.toString(),
        custom_install_command: !custom_install_command
          ? undefined
          : custom_install_command,
        custom_build_command: !custom_build_command
          ? undefined
          : custom_build_command,
        custom_start_command: !custom_start_command
          ? undefined
          : custom_start_command
      } satisfies BodyOf<typeof field>["new_value"];
      break;
    }
    default: {
      throw new Error(`Unexpected field \`${field}\``);
    }
  }

  let toastId: string | number | undefined;
  if (type === "DELETE") {
    toastId = toast.loading("Sending change request...");
    userData = undefined;
  }
  const { error: errors, data } = await apiClient.PUT(
    "/api/projects/{project_slug}/{env_slug}/request-service-changes/{service_slug}/",
    {
      headers: {
        ...(await getCsrfTokenHeader())
      },
      params: {
        path: {
          project_slug,
          service_slug,
          env_slug
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

  await queryClient.invalidateQueries({
    ...serviceQueries.single({
      project_slug,
      service_slug: service_slug,
      env_slug
    }),
    exact: true
  });

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
  env_slug,
  formData
}: {
  project_slug: string;
  service_slug: string;
  env_slug: string;
  formData: FormData;
}) {
  const toastId = toast.loading("Discarding service change...");
  const change_id = formData.get("change_id")?.toString();
  const { error: errors, data } = await apiClient.DELETE(
    "/api/projects/{project_slug}/{env_slug}/cancel-service-changes/{service_slug}/{change_id}/",
    {
      headers: {
        ...(await getCsrfTokenHeader())
      },
      params: {
        path: {
          project_slug,
          service_slug,
          env_slug,
          change_id: change_id!
        }
      }
    }
  );

  if (errors) {
    const fullErrorMessage = errors.errors.map((err) => err.detail).join(" ");
    toast.error("Failed to discard change", {
      id: toastId,
      closeButton: true,
      description: fullErrorMessage
    });
    return {
      errors
    };
  }

  await queryClient.invalidateQueries({
    ...serviceQueries.single({ project_slug, service_slug, env_slug }),
    exact: true
  });
  toast.success("Change discarded successfully", {
    id: toastId,
    closeButton: true
  });
  return {
    data
  };
}
