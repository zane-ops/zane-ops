import {
  BoxIcon,
  BoxesIcon,
  Layers2Icon,
  LinkIcon,
  TagIcon
} from "lucide-react";
import * as React from "react";
import { Link } from "react-router";
import type { ComposeStack } from "~/api/types";
import { DeploymentStatusBadge } from "~/components/deployment-status-badge";
import { Ping, type PingProps } from "~/components/ping";
import type { StatusBadgeColor } from "~/components/status-badge";
import { Button } from "~/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "~/components/ui/card";
import {
  Popover,
  PopoverArrow,
  PopoverContent,
  PopoverTrigger
} from "~/components/ui/popover";
import { Separator } from "~/components/ui/separator";
import type { ValueOf } from "~/lib/types";
import { cn } from "~/lib/utils";
import { formatURL, getDockerImageIconURL, pluralize } from "~/utils";

export type ComposeStackCardProps = Pick<
  ComposeStack,
  "slug" | "service_statuses" | "urls"
>;

const MAX_SERVICES_SHOWN = 3;

export function ComposeStackCard({
  slug,
  service_statuses,
  urls
}: ComposeStackCardProps) {
  const services = Object.entries(service_statuses)
    .map(([name, service]) => [name, service] as const)
    .toSorted(([nameA, serviceA], [nameB, serviceB]) => {
      // Sort starting & unhealthy services at the top as they need attention
      if (serviceA.status === "STARTING" || serviceA.status === "UNHEALTHY") {
        return -1;
      }
      if (serviceB.status === "STARTING" || serviceB.status === "UNHEALTHY") {
        return 1;
      }

      // Sort services with URLs at the top
      const serviceUrlsA = urls[nameA];
      const serviceUrlsB = urls[nameB];

      if (typeof serviceUrlsA !== "undefined") {
        return -1;
      }
      if (typeof serviceUrlsB !== "undefined") {
        return 1;
      }

      return 0;
    });

  const total_services = services.length;
  const healthy_services = services.filter(
    ([, service]) =>
      service.status === "HEALTHY" ||
      service.status === "COMPLETE" ||
      service.status === "SLEEPING"
  ).length;

  const sleeping_services = services.filter(
    ([, service]) => service.status === "SLEEPING"
  ).length;

  let pingColor: StatusBadgeColor;
  let pingState: PingProps["state"] = "static";

  if (total_services === 0) {
    pingColor = "gray";
  } else if (healthy_services <= 0) {
    pingColor = "red";
  } else if (healthy_services < total_services) {
    pingColor = "yellow";
  } else {
    pingColor = "green";
    pingState = "animated";
  }

  return (
    <Card className="rounded-2xl flex group flex-col h-[220px] bg-toggle relative ring-1 ring-transparent hover:ring-primary focus-within:ring-primary transition-colors duration-300">
      <CardHeader className="p-0  pb-0  pt-4 px-6">
        <CardTitle className="flex gap-2 items-center">
          <BoxesIcon
            className={cn("flex-none", "rounded-md border border-border p-0.5")}
            size={32}
          />
          <div className="w-[calc(100%-38px)]">
            <h2 className="text-lg leading-tight">
              <Link
                to={`compose-stacks/${slug}`}
                prefetch="viewport"
                className="hover:underline after:inset-0 after:absolute"
              >
                {slug}
              </Link>
            </h2>
          </div>
        </CardTitle>
      </CardHeader>

      <Separator className="my-2" />

      <CardContent
        className="flex justify-end grow gap-0.5 flex-col text-sm text-gray-400 !pt-0 p-6 bg-size-[16px_16px]"
        style={{
          backgroundImage:
            "radial-gradient(circle, color-mix(in srgb, var(--color-gray-400) 25%, transparent) 1px, transparent 1px)"
        }}
      >
        <div className="flex-1 flex items-center justify-center pb-2">
          <div className="flex items-center gap-3  relative z-10 px-2">
            {services.slice(0, MAX_SERVICES_SHOWN).map(([name, service]) => (
              <ComposeStackService
                key={name}
                name={name}
                {...service}
                urls={urls[name] ?? []}
              />
            ))}
            {services.length > MAX_SERVICES_SHOWN && (
              <Button asChild variant="outline">
                <Link
                  to={`compose-stacks/${slug}`}
                  className={cn(
                    "size-10 inline-flex items-center justify-center",
                    "relative z-10 cursor-pointer"
                  )}
                >
                  +{services.length - MAX_SERVICES_SHOWN}
                </Link>
              </Button>
            )}
          </div>
        </div>
        <div className="bg-toggle inline-flex items-center gap-2 rounded-md self-start px-2">
          <Ping color={pingColor} state={pingState} />
          {total_services === 0 && <span>No services yet</span>}
          {total_services > 0 && (
            <p className="text-card-foreground dark:text-foreground">
              {healthy_services}/
              {`${total_services} ${pluralize("service", total_services)} healthy`}
              {sleeping_services > 0 && ` (${sleeping_services} sleeping)`}
            </p>
          )}
        </div>
      </CardContent>
    </Card>
  );
}

type ComposeStackServiceProps = ValueOf<ComposeStack["service_statuses"]> & {
  name: string;
  urls: ValueOf<ComposeStack["urls"]>;
};

function ComposeStackService({
  name,
  status,
  desired_replicas,
  running_replicas,
  urls,
  image,
  mode,
  tasks
}: ComposeStackServiceProps) {
  const [imageNotFound, setImageNotFound] = React.useState(false);
  const iconSrc = getDockerImageIconURL(image);

  const total_completed = tasks.filter(
    (task) => task.status === "complete"
  ).length;
  const is_job = mode === "global-job" || mode === "replicated-job";

  let serviceImage = image;
  if (serviceImage && !serviceImage.includes(":")) {
    serviceImage += ":latest";
  }

  return (
    <div className="relative">
      {(status === "UNHEALTHY" || status === "STARTING") && (
        <span
          tabIndex={0}
          className="absolute cursor-pointer flex size-2.5 -top-1 -right-1 z-20"
        >
          <Ping color={status === "UNHEALTHY" ? "red" : "blue"} />
        </span>
      )}

      <Popover>
        <PopoverTrigger asChild>
          <Button className="relative z-10 p-1" variant="outline">
            {iconSrc && !imageNotFound ? (
              <img
                src={iconSrc}
                onError={() => setImageNotFound(true)}
                alt={`Logo for ${image}`}
                className={cn(
                  "size-8 flex-none object-center object-contain",
                  "rounded-md p-0.5",
                  "text-xs text-muted"
                )}
              />
            ) : (
              <BoxIcon
                className={cn(
                  "flex-none size-8 text-card-foreground",
                  "rounded-md p-0.5"
                )}
              />
            )}
          </Button>
        </PopoverTrigger>
        <PopoverContent
          align="center"
          className="w-60 text-sm flex flex-col gap-1.5 px-0 pt-1.5"
        >
          <PopoverArrow className="fill-popover stroke-border stroke-2" />
          <div className="px-3">
            <strong
              className={cn(
                "whitespace-nowrap overflow-x-hidden text-ellipsis",
                "text-card-foreground font-medium",
                "inline-flex justify-between gap-0.5 items-center"
              )}
            >
              <span className="relative top-0.5">{name}</span>
              <span className="ml-1 inline-block rounded-full size-0.5 bg-foreground relative top-0.5" />
              <DeploymentStatusBadge
                status={status}
                variant="outline"
                className="my-1"
              />
            </strong>
          </div>
          <Separator />

          <div className="flex flex-col gap-1 px-3">
            <div className="col-span-2 flex items-start gap-1">
              <TagIcon className="dark:text-foreground text-grey flex-none size-4 relative top-1" />
              <span className="whitespace-nowrap overflow-x-hidden text-ellipsis text-grey dark:text-foreground">
                {serviceImage}
              </span>
            </div>

            {urls.length > 0 && (
              <ul className="w-full">
                {urls.map((url) => (
                  <li
                    key={url.domain + url.base_path}
                    className="w-full flex items-center gap-1"
                  >
                    <LinkIcon className="flex-none size-4 text-link" />
                    <a
                      href={formatURL(url)}
                      target="_blank"
                      className="underline text-link text-sm inline-block w-[calc(100%_-calc(var(--spacing)_*_4))]"
                    >
                      <p className="whitespace-nowrap overflow-x-hidden text-ellipsis">
                        {formatURL(url)}
                      </p>
                    </a>
                  </li>
                ))}
              </ul>
            )}
            <div className="text-card-foreground col-span-2 flex items-start gap-1">
              <Layers2Icon className="flex-none dark:text-foreground text-grey size-4 relative top-1" />
              {is_job ? (
                <span className="text-grey dark:text-foreground">
                  {total_completed}/{desired_replicas} tasks completed
                </span>
              ) : (
                <span className="text-grey dark:text-foreground">
                  {running_replicas}/{desired_replicas} replicas running
                </span>
              )}
            </div>
          </div>
        </PopoverContent>
      </Popover>
    </div>
  );
}
