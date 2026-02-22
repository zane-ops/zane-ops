import { useQuery } from "@tanstack/react-query";
import {
  CableIcon,
  ContainerIcon,
  GlobeIcon,
  GlobeLockIcon,
  InfoIcon,
  NetworkIcon
} from "lucide-react";
import { Link, Navigate, href } from "react-router";
import { Code } from "~/components/code";
import { CopyButton } from "~/components/copy-button";
import { StatusBadge } from "~/components/status-badge";
import {
  FieldSet,
  FieldSetInput,
  FieldSetLabel
} from "~/components/ui/fieldset";
import { Separator } from "~/components/ui/separator";
import {
  Tooltip,
  TooltipContent,
  TooltipProvider,
  TooltipTrigger
} from "~/components/ui/tooltip";
import { ZANEOPS_INTERNAL_DOMAIN } from "~/lib/constants";
import { composeStackQueries } from "~/lib/queries";
import { cn } from "~/lib/utils";
import type { Route } from "./+types/compose-stack-service-details";

export default function ComposeStackServiceDetailsPage({
  params,
  matches: {
    2: { loaderData }
  }
}: Route.ComponentProps) {
  const { data: stack } = useQuery({
    ...composeStackQueries.single({
      project_slug: params.projectSlug,
      stack_slug: params.composeStackSlug,
      env_slug: params.envSlug
    }),
    initialData: loaderData.stack
  });
  const serviceFound = Object.entries(stack.services).find(
    ([name]) => name === params.serviceSlug
  );

  if (!serviceFound) {
    return (
      <Navigate
        to={href(
          "/project/:projectSlug/:envSlug/compose-stacks/:composeStackSlug",
          params
        )}
      />
    );
  }
  const [name, service] = serviceFound;

  const servicePrefix = `${stack.name}_${stack.hash_prefix}_`;
  let [serviceImage, imageSha] = service.image.split("@"); // the image is in the format 'image@sha'

  if (serviceImage && !serviceImage.includes(":")) {
    serviceImage += ":latest";
  }

  const network_alias = `${stack.network_alias_prefix}-${name}.${ZANEOPS_INTERNAL_DOMAIN}`;
  const global_alias = `${stack.hash_prefix}_${name}.${ZANEOPS_INTERNAL_DOMAIN}`;

  return (
    <div className="my-6 grid lg:grid-cols-12 gap-10 relative max-w-full">
      <div className="lg:col-span-10 flex flex-col max-w-full">
        <section id="details" className="flex gap-1 scroll-mt-24">
          <div className="w-16 hidden md:flex flex-col items-center">
            <div className="flex rounded-full size-10 flex-none items-center justify-center p-1 border-2 border-grey/50">
              <InfoIcon size={15} className="flex-none text-grey" />
            </div>
            <div className="h-full border border-grey/50"></div>
          </div>

          <div className="w-full flex flex-col gap-5 pt-1 pb-8">
            <h2 className="text-lg text-grey">Details</h2>
            <div className="w-full max-w-4xl">
              <div className="flex flex-col  gap-2 w-full">
                <FieldSet name="slug" className="flex flex-col gap-1.5 flex-1">
                  <FieldSetLabel htmlFor="slug">
                    Docker Swarm Service Name
                  </FieldSetLabel>
                  <div className="relative">
                    <FieldSetInput
                      defaultValue={servicePrefix + name}
                      disabled
                      className={cn(
                        "disabled:placeholder-shown:font-mono disabled:bg-muted",
                        "disabled:border-transparent disabled:opacity-100",
                        "disabled:text-transparent disabled:select-none"
                      )}
                    />
                    <span className="absolute inset-y-0 left-3 flex items-center text-sm">
                      <span className="text-grey">
                        {servicePrefix}
                        <span className="text-card-foreground">{name}</span>
                      </span>
                      <TooltipProvider>
                        <Tooltip delayDuration={0}>
                          <TooltipTrigger asChild>
                            <CopyButton
                              value={servicePrefix + name}
                              label={servicePrefix + name}
                              className="!opacity-100 ml-1.5"
                            />
                          </TooltipTrigger>
                          <TooltipContent>Copy service name</TooltipContent>
                        </Tooltip>
                      </TooltipProvider>
                    </span>
                  </div>
                </FieldSet>

                <FieldSet name="slug" className="flex flex-col gap-1.5 flex-1">
                  <FieldSetLabel htmlFor="slug">
                    Docker Swarm Service ID
                  </FieldSetLabel>
                  <div className="relative">
                    <FieldSetInput
                      defaultValue={service.id}
                      disabled
                      className={cn(
                        "disabled:placeholder-shown:font-mono disabled:bg-muted",
                        "disabled:border-transparent disabled:opacity-100",
                        "disabled:text-transparent disabled:select-none"
                      )}
                    />

                    <span className="absolute inset-y-0 left-3 flex items-center text-sm">
                      <span>{service.id}</span>
                      <TooltipProvider>
                        <Tooltip delayDuration={0}>
                          <TooltipTrigger asChild>
                            <CopyButton
                              value={service.id}
                              label={service.id}
                              className="!opacity-100 ml-1.5"
                            />
                          </TooltipTrigger>
                          <TooltipContent>Copy service ID</TooltipContent>
                        </Tooltip>
                      </TooltipProvider>
                    </span>
                  </div>
                </FieldSet>
              </div>
            </div>
          </div>
        </section>

        <section id="source" className="flex gap-1 scroll-mt-24">
          <div className="w-16 hidden md:flex flex-col items-center">
            <div className="flex rounded-full size-10 flex-none items-center justify-center p-1 border-2 border-grey/50">
              <ContainerIcon size={15} className="flex-none text-grey" />
            </div>
            <div className="h-full border border-grey/50"></div>
          </div>

          <div className="w-full flex flex-col gap-5 pt-1 pb-8">
            <h2 className="text-lg text-grey">Source</h2>
            <div className="w-full max-w-4xl">
              <div className="flex flex-col gap-2 w-full">
                <FieldSet
                  name="slug"
                  className="flex flex-col gap-1.5 flex-1 w-full"
                >
                  <FieldSetLabel htmlFor="slug">Full Image</FieldSetLabel>
                  <div className="relative w-full max-w-full min-w-0">
                    <FieldSetInput
                      defaultValue={servicePrefix + name}
                      disabled
                      className={cn(
                        "disabled:placeholder-shown:font-mono disabled:bg-muted",
                        "disabled:border-transparent disabled:opacity-100",
                        "disabled:text-transparent disabled:select-none"
                      )}
                    />
                    <div
                      className={cn(
                        "absolute  inset-y-0 flex items-center left-3 text-sm whitespace-nowrap",
                        "w-[calc(100%-calc(var(--spacing)*4))] max-w-full min-w-0 overflow-auto pr-4"
                      )}
                    >
                      <span>
                        {serviceImage}
                        <span className="text-grey">:{imageSha}</span>
                      </span>
                    </div>
                  </div>
                </FieldSet>
              </div>
            </div>
          </div>
        </section>

        <section id="networking" className="flex gap-1 scroll-mt-24">
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
                global_alias={global_alias}
                network_alias={network_alias}
              />
            </div>

            {/* <hr className="w-full max-w-4xl border-border" />
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
            /> */}
          </div>
        </section>
      </div>
      <SideNav />
    </div>
  );
}

function SideNav() {
  return (
    <aside className="col-span-2 hidden lg:flex flex-col h-full">
      <nav className="sticky top-20 flex flex-col gap-4">
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
                hash: "#health"
              }}
            >
              Health
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
              Configs
            </Link>
          </li>
        </ul>
      </nav>
    </aside>
  );
}

function NetworkAliasesGroup({
  network_alias,
  global_alias
}: {
  network_alias: string;
  global_alias: string;
}) {
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

        <div className="flex flex-col gap-0.5 w-full">
          <div className="flex gap-2 flex-col items-start">
            <div className="flex gap-2 items-center">
              <StatusBadge
                color="blue"
                pingState="hidden"
                className="inline-flex"
              >
                <NetworkIcon className="size-4 flex-none" />
                Environment alias
              </StatusBadge>
              <span className="text-lg break-all">
                {network_alias.replace(`.${ZANEOPS_INTERNAL_DOMAIN}`, "")}
              </span>
              <TooltipProvider>
                <Tooltip delayDuration={0}>
                  <TooltipTrigger asChild>
                    <CopyButton
                      value={network_alias.replace(
                        `.${ZANEOPS_INTERNAL_DOMAIN}`,
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

            <small>
              You can also use{" "}
              <Code className=" break-all">{network_alias}</Code>
            </small>
          </div>

          <Separator className="my-2" />
          <div className="flex gap-2 flex-col items-start">
            <div className="flex gap-2 items-center">
              <StatusBadge
                color="gray"
                pingState="hidden"
                className="inline-flex"
              >
                <GlobeIcon className="size-4 flex-none" />
                Global alias
              </StatusBadge>
              <div className="flex gap-2 items-center">
                <span className="text-lg break-all">
                  {global_alias.replace(`.${ZANEOPS_INTERNAL_DOMAIN}`, "")}
                </span>

                <TooltipProvider>
                  <Tooltip delayDuration={0}>
                    <TooltipTrigger asChild>
                      <CopyButton
                        value={global_alias.replace(
                          `.${ZANEOPS_INTERNAL_DOMAIN}`,
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
            </div>

            <small>
              You can also use{" "}
              <Code className=" break-all">{global_alias}</Code>
            </small>
          </div>
        </div>
      </div>
    </div>
  );
}
