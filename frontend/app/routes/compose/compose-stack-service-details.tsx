import { useQuery } from "@tanstack/react-query";
import {
  ArrowRightIcon,
  CableIcon,
  ContainerIcon,
  ExternalLinkIcon,
  EyeIcon,
  EyeOffIcon,
  FileSlidersIcon,
  GlobeIcon,
  GlobeLockIcon,
  HardDriveIcon,
  HeartPulseIcon,
  HistoryIcon,
  InfoIcon,
  KeyRoundIcon,
  MetronomeIcon,
  NetworkIcon,
  RotateCwIcon,
  TerminalIcon,
  TimerResetIcon
} from "lucide-react";
import * as React from "react";
import { Link, Navigate, href } from "react-router";
import type { ComposeStackService } from "~/api/types";
import { Code } from "~/components/code";
import { CopyButton } from "~/components/copy-button";
import { StatusBadge } from "~/components/status-badge";
import {
  Accordion,
  AccordionContent,
  AccordionItem,
  AccordionTrigger
} from "~/components/ui/accordion";
import { Button } from "~/components/ui/button";
import { CodeEditor } from "~/components/ui/code-editor";
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
import { formatElapsedTime, pluralize } from "~/utils";
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
  const serviceUrls = stack.urls[name] ?? [];

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
        <section id="details" className="flex gap-1 scroll-mt-24 max-w-4xl">
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
                    <span
                      className={cn(
                        "absolute inset-y-0 flex items-center left-3 text-sm whitespace-nowrap",
                        "w-[calc(100%-calc(var(--spacing)*4))] max-w-full min-w-0 overflow-auto pr-4"
                      )}
                    >
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

        <section id="source" className="flex gap-1 scroll-mt-24 max-w-4xl">
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
                        "absolute inset-y-0 flex items-center left-3 text-sm whitespace-nowrap",
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

        <section id="environment" className="flex gap-1 scroll-mt-24 max-w-4xl">
          <div className="w-16 hidden md:flex flex-col items-center">
            <div className="flex rounded-full size-10 flex-none items-center justify-center p-1 border-2 border-grey/50">
              <KeyRoundIcon size={15} className="flex-none text-grey" />
            </div>
            <div className="h-full border border-grey/50"></div>
          </div>

          <div className="w-full flex flex-col gap-5 pt-1 pb-8">
            <h2 className="text-lg text-grey">Environment variables</h2>
            <div className="w-full max-w-4xl">
              {service.environment.length === 0 ? (
                <div
                  className={cn(
                    "flex flex-col gap-2 items-center py-8 bg-muted/20",
                    "border-border border-dashed rounded-md border-1"
                  )}
                >
                  No variables in this service
                </div>
              ) : (
                <div className="flex flex-col gap-4">
                  <hr className="border-border" />
                  <h3 className="text-lg inline-flex gap-2 items-center">
                    <span>
                      {service.environment.length}&nbsp;
                      {pluralize("variable", service.environment.length)}
                    </span>
                    <CopyButton
                      variant="outline"
                      size="sm"
                      showLabel
                      label={(hasCopied) =>
                        hasCopied ? "Copied" : "Copy as .env"
                      }
                      value={service.environment
                        .map((env) => `${env.key}="${env.value}"`)
                        .join("\n")}
                    />
                  </h3>

                  <hr className="border-border" />

                  {service.environment.map((env) => (
                    <EnVariableRow
                      key={`env-${env.key}`}
                      name={env.key}
                      value={env.value}
                    />
                  ))}
                  <hr className="border-border" />
                </div>
              )}
            </div>
          </div>
        </section>

        <section id="networking" className="flex gap-1 scroll-mt-24 max-w-4xl">
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

            <hr className="w-full max-w-4xl border-border" />
            <div className="w-full max-w-4xl flex flex-col gap-5">
              <div className="flex flex-col gap-3">
                <h3 className="text-lg">URL Routes</h3>
                <p className="text-gray-400">
                  The domains and base path which are associated to this
                  service.
                </p>
              </div>

              {serviceUrls.length === 0 && (
                <div
                  className={cn(
                    "flex flex-col gap-2 items-center py-8 bg-muted/20",
                    "border-border border-dashed rounded-md border-1"
                  )}
                >
                  No url routes in this service
                </div>
              )}
              {serviceUrls.map((url) => (
                <div
                  key={url.domain + url.base_path}
                  className={cn(
                    "flex flex-col gap-2 items-stretch md:flex-row overflow-x-auto",
                    "relative group/url"
                  )}
                >
                  <div className="absolute top-2 right-2 inline-flex gap-1 items-center">
                    <TooltipProvider>
                      <Tooltip delayDuration={0}>
                        <TooltipTrigger asChild>
                          <Button
                            variant="ghost"
                            className={cn(
                              "px-2.5 py-0.5 opacity-0 focus-visible:opacity-100 group-hover/url:opacity-100"
                            )}
                            asChild
                          >
                            <Link to={`//${url.domain}${url.base_path}`}>
                              <ExternalLinkIcon
                                size={15}
                                className="flex-none"
                              />
                              <span className="sr-only">
                                Navigate to this url
                              </span>
                            </Link>
                          </Button>
                        </TooltipTrigger>
                        <TooltipContent>Navigate to this url</TooltipContent>
                      </Tooltip>
                      <Tooltip delayDuration={0}>
                        <TooltipTrigger asChild>
                          <CopyButton
                            label="Copy URL"
                            className={cn(
                              "px-2.5 py-0.5 focus-visible:opacity-100 opacity-0 group-hover/url:opacity-100"
                            )}
                            value={`${url.domain}${url.base_path}`}
                          />
                        </TooltipTrigger>
                        <TooltipContent>Copy url</TooltipContent>
                      </Tooltip>
                    </TooltipProvider>
                  </div>
                  <div
                    className={cn(
                      "w-full px-3 bg-muted rounded-md flex flex-col gap-2 items-start text-start flex-wrap pr-24 py-4",
                      "text-base"
                    )}
                  >
                    <p className="break-all">
                      {url.domain}
                      <span className="text-grey">{url.base_path}</span>
                      &nbsp;
                    </p>

                    {url.port && (
                      <small className="inline-flex gap-2 items-center">
                        <ArrowRightIcon
                          size={15}
                          className="text-grey flex-none"
                        />
                        <span className="text-grey">{url.port}</span>
                      </small>
                    )}
                  </div>
                </div>
              ))}
            </div>

            <hr className="w-full max-w-4xl border-border" />

            <div className="w-full max-w-4xl flex flex-col gap-5">
              <div className="flex flex-col gap-3">
                <h3 className="text-lg">Exposed ports</h3>
                <p className="text-gray-400">
                  Ports exposed to make this service reachable from outside the
                  cluster. For HTTP/HTTPS traffic, URLs are preferred over
                  exposed ports.
                </p>
              </div>
              {service.ports.length === 0 && (
                <div
                  className={cn(
                    "flex flex-col gap-2 items-center py-8 bg-muted/20",
                    "border-border border-dashed rounded-md border-1"
                  )}
                >
                  No exposed in this service
                </div>
              )}
              {service.ports.map((port) => (
                <div
                  key={`${port.published}:${port.target}/${port.protocol}`}
                  className="flex flex-col gap-2 items-center md:flex-row overflow-x-auto"
                >
                  <div
                    className={cn(
                      "w-full px-3 py-4 bg-muted rounded-md inline-flex gap-1 items-center text-start flex-wrap pr-24"
                    )}
                  >
                    <span>{port.published}</span>
                    <ArrowRightIcon size={15} className="text-grey" />
                    <span className="text-grey">{port.target}</span>
                    <Code className="ml-1">{port.protocol}</Code>
                  </div>
                </div>
              ))}
            </div>
          </div>
        </section>

        <section id="health" className="flex gap-1 scroll-mt-24 max-w-4xl">
          <div className="w-16 hidden md:flex flex-col items-center">
            <div className="flex rounded-full size-10 flex-none items-center justify-center p-1 border-2 border-grey/50">
              <HeartPulseIcon size={15} className="flex-none text-grey" />
            </div>
            <div className="h-full border border-grey/50"></div>
          </div>
          <div className="w-full flex flex-col gap-8 pt-1 pb-14">
            <h2 className="text-lg text-grey">Health checks</h2>

            {!service.healthcheck && (
              <div
                className={cn(
                  "flex flex-col gap-2 items-center py-8 bg-muted/20",
                  "border-border border-dashed rounded-md border-1"
                )}
              >
                No health check
              </div>
            )}

            {service.healthcheck && (
              <dl className="flex flex-col gap-2">
                <div className="flex flex-col items-start gap-2">
                  <dt className="flex gap-1 items-center text-grey">
                    <TerminalIcon className="size-4 flex-none" />
                    <span>Command:</span>
                  </dt>
                  <dd className="w-full">
                    <pre className="font-mono bg-muted/25 dark:bg-card p-2 rounded-md text-sm break-all w-full">
                      {service.healthcheck.command}
                    </pre>
                  </dd>
                </div>

                {service.healthcheck.interval_sec && (
                  <div className="flex items-center gap-2">
                    <dt className="flex gap-1 items-center text-grey">
                      <MetronomeIcon className="size-4 flex-none" />
                      <span>Interval:</span>
                    </dt>
                    <dd className="w-full">
                      {formatElapsedTime(
                        service.healthcheck.interval_sec,
                        "long"
                      )}
                    </dd>
                  </div>
                )}
                {service.healthcheck.retries && (
                  <div className="flex items-center gap-2 w-full">
                    <dt className="flex gap-1 items-center text-grey">
                      <RotateCwIcon className="size-4 flex-none" />
                      <span className="whitespace-nowrap">Max retries:</span>
                    </dt>
                    <dd className="w-full">{service.healthcheck.retries}</dd>
                  </div>
                )}
                {service.healthcheck.start_period && (
                  <div className="flex items-center gap-2 w-full">
                    <dt className="flex gap-1 items-center text-grey">
                      <HistoryIcon className="size-4 flex-none" />
                      <span className="whitespace-nowrap">Start period:</span>
                    </dt>
                    <dd className="w-full">
                      {formatElapsedTime(
                        service.healthcheck.start_period,
                        "long"
                      )}
                    </dd>
                  </div>
                )}
                {service.healthcheck.start_interval && (
                  <div className="flex items-center gap-2 w-full">
                    <dt className="flex gap-1 items-center text-grey">
                      <TimerResetIcon className="size-4 flex-none" />
                      <span className="whitespace-nowrap">Start interval:</span>
                    </dt>
                    <dd className="w-full">
                      {formatElapsedTime(
                        service.healthcheck.start_interval,
                        "long"
                      )}
                    </dd>
                  </div>
                )}
              </dl>
            )}
          </div>
        </section>

        <section id="volumes" className="flex gap-1 scroll-mt-24 max-w-4xl">
          <div className="w-16 hidden md:flex flex-col items-center">
            <div className="flex rounded-full size-10 flex-none items-center justify-center p-1 border-2 border-grey/50">
              <HardDriveIcon size={15} className="flex-none text-grey" />
            </div>
            <div className="h-full border border-grey/50"></div>
          </div>
          <div className="w-full flex flex-col gap-5 pt-1 pb-14">
            <h2 className="text-lg text-grey">Volumes</h2>
            {service.volumes.length === 0 ? (
              <div
                className={cn(
                  "flex flex-col gap-2 items-center py-8 bg-muted/20",
                  "border-border border-dashed rounded-md border-1"
                )}
              >
                No volumes in this service
              </div>
            ) : (
              <div className="flex flex-col gap-2">
                {service.volumes.map((v) => {
                  let prefix: string | null = null;
                  let suffix = v.source;
                  if (
                    v.type === "volume" &&
                    v.source.startsWith(stack.name + "_")
                  ) {
                    prefix = stack.name + "_";
                    suffix = v.source.substring(prefix.length);
                  }
                  return (
                    <div
                      className={cn(
                        "rounded-md p-4 flex items-start sm:items-center gap-2 bg-muted w-full"
                      )}
                      key={`v-${v.source}:${v.target}`}
                    >
                      <HardDriveIcon className="size-5 text-grey flex-none relative top-1 sm:static" />
                      <div className="inline-flex gap-1 items-center flex-wrap">
                        <span className="text-card-foreground break-all">
                          {prefix && (
                            <span className="text-grey">{prefix}</span>
                          )}
                          {suffix}
                        </span>
                        <div className="flex items-center gap-1">
                          <ArrowRightIcon size={15} className="text-grey" />
                          <span className="text-grey">{v.target}</span>
                          <Code className="text-sm ml-1">
                            {v.read_only ? "read only" : "read & write"}
                          </Code>
                        </div>
                      </div>
                    </div>
                  );
                })}
              </div>
            )}
          </div>
        </section>

        <section id="configs" className="flex gap-1 scroll-mt-24 max-w-4xl">
          <div className="w-16 hidden md:flex flex-col items-center">
            <div className="flex rounded-full size-10 flex-none items-center justify-center p-1 border-2 border-grey/50">
              <FileSlidersIcon size={15} className="flex-none text-grey" />
            </div>
          </div>
          <div className="w-full flex flex-col gap-5 pt-1 pb-14">
            <h2 className="text-lg text-grey">Configs</h2>

            {service.configs.length === 0 ? (
              <div
                className={cn(
                  "flex flex-col gap-2 items-center py-8 bg-muted/20",
                  "border-border border-dashed rounded-md border-1"
                )}
              >
                No configs in this service
              </div>
            ) : (
              <div className="flex flex-col gap-2">
                {service.configs.map((cfg) => {
                  return (
                    <ConfigItem
                      key={`c-${cfg.source}:${cfg.target}`}
                      source={cfg.source}
                      target={cfg.target}
                      content={cfg.content}
                      stackPrefix={stack.name + "_"}
                    />
                  );
                })}
              </div>
            )}
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
      <nav className="sticky top-24 flex flex-col gap-4">
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
                hash: "#environment"
              }}
            >
              Environment variables
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
              Health check
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
    <div className="flex flex-col gap-5 w-full  border-border">
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
            <div className="flex gap-x-2 gap-y-0.5 items-center flex-wrap">
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
            <div className="flex gap-x-2 gap-y-0.5 items-center  flex-wrap">
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

function ConfigItem({
  source,
  target,
  content,
  stackPrefix
}: ComposeStackService["configs"][number] & { stackPrefix: string }) {
  const [accordionValue, setAccordionValue] = React.useState("");

  let prefix: string | null = null;
  let suffix = source;
  if (source.startsWith(stackPrefix)) {
    prefix = stackPrefix;
    suffix = source.substring(stackPrefix.length);
  }

  return (
    <Accordion
      type="single"
      collapsible
      value={accordionValue}
      onValueChange={(state) => {
        setAccordionValue(state);
      }}
    >
      <AccordionItem value={`${source}`} className="border-none">
        <AccordionTrigger
          className={cn(
            "rounded-md p-4 flex items-start gap-2 bg-muted",
            "aria-expanded:rounded-b-none cursor-pointer"
          )}
        >
          <FileSlidersIcon size={20} className="text-grey relative top-1.5" />
          <div className="flex flex-col gap-2">
            <h3 className="text-lg inline-flex gap-1 items-center">
              <span>
                {prefix && <span className="text-grey">{prefix}</span>}
                {suffix}
              </span>
            </h3>
            <small className="text-card-foreground inline-flex gap-1 items-center">
              <span className="text-grey">{target}</span>
            </small>
          </div>
        </AccordionTrigger>
        <AccordionContent className="border-border border-x border-b rounded-b-md p-4 mb-4">
          <div className={cn("flex flex-col gap-4 w-full")}>
            <FieldSet name="contents" className="flex flex-col gap-1.5 flex-1">
              <FieldSetLabel className="text-muted-foreground">
                contents
              </FieldSetLabel>

              <CodeEditor
                containerClassName="w-[80dvw] sm:w-[88dvw] md:w-[82dvw] lg:w-[70dvw] xl:w-[855px]"
                path={target}
                value={content}
                readOnly
              />
            </FieldSet>
          </div>
        </AccordionContent>
      </AccordionItem>
    </Accordion>
  );
}

type EnvVariableUI = {
  name: string;
  value: string;
};

function EnVariableRow({ name: key, value }: EnvVariableUI) {
  const [isEnvValueShown, setIsEnvValueShown] = React.useState(false);

  return (
    <div
      className={cn(
        "grid gap-4 items-center md:grid-cols-7 lg:grid-cols-8 grid-cols-3 group pl-4 pt-2 md:py-1"
      )}
    >
      <>
        <div
          className={cn("col-span-3 md:col-span-2 lg:col-span-3 flex flex-col")}
        >
          <span className="font-mono break-all">{key}</span>
        </div>
        <div className="col-span-2 font-mono flex items-center gap-2 md:col-span-4">
          {isEnvValueShown ? (
            <p className="whitespace-nowrap overflow-x-auto">
              {value.length > 0 ? (
                value
              ) : (
                <span className=" font-mono">{`<empty>`}</span>
              )}
            </p>
          ) : (
            <span className="relative top-1">*********</span>
          )}
          <TooltipProvider>
            <Tooltip delayDuration={0}>
              <TooltipTrigger asChild>
                <Button
                  variant="ghost"
                  onClick={() => setIsEnvValueShown(!isEnvValueShown)}
                  className="px-2.5 py-0.5 md:opacity-0 focus-visible:opacity-100 group-hover:opacity-100"
                >
                  {isEnvValueShown ? (
                    <EyeOffIcon size={15} className="flex-none" />
                  ) : (
                    <EyeIcon size={15} className="flex-none" />
                  )}
                  <span className="sr-only">
                    {isEnvValueShown ? "Hide" : "Reveal"} variable value
                  </span>
                </Button>
              </TooltipTrigger>
              <TooltipContent>
                {isEnvValueShown ? "Hide" : "Reveal"} variable value
              </TooltipContent>
            </Tooltip>

            <Tooltip delayDuration={0}>
              <TooltipTrigger asChild>
                <CopyButton label="Copy variable value" value={value} />
              </TooltipTrigger>
              <TooltipContent>Copy variable value</TooltipContent>
            </Tooltip>
          </TooltipProvider>
        </div>
      </>
    </div>
  );
}
