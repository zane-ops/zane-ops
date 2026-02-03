import { BoxIcon, BoxesIcon } from "lucide-react";
import * as React from "react";
import { Link } from "react-router";
import type { ComposeStack } from "~/api/types";
import { Ping, type PingProps } from "~/components/ping";
import type { StatusBadgeColor } from "~/components/status-badge";
import { Card, CardContent, CardHeader, CardTitle } from "~/components/ui/card";
import {
  Popover,
  PopoverContent,
  PopoverTrigger
} from "~/components/ui/popover";
import { Separator } from "~/components/ui/separator";
import type { ValueOf } from "~/lib/types";
import { cn } from "~/lib/utils";
import { getDockerImageIconURL, pluralize } from "~/utils";

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
  const total_services = Object.values(service_statuses).length;
  const healthy_services = Object.values(service_statuses).filter(
    (status) =>
      status.status === "HEALTHY" ||
      status.status === "COMPLETE" ||
      status.status === "SLEEPING"
  ).length;

  // Sort starting & unhealthy services at the top as they need attention
  const services = Object.entries(service_statuses)
    .map(([name, service]) => [name, service] as const)
    .toSorted(([, serviceA], [, serviceB]) => {
      if (serviceA.status === "STARTING" || serviceA.status === "UNHEALTHY") {
        return -1;
      }
      if (serviceB.status === "STARTING" || serviceB.status === "UNHEALTHY") {
        return 1;
      }
      return 0;
    });

  let pingColor: StatusBadgeColor;
  let pingState: PingProps["state"] = "static";

  if (total_services === 0) {
    pingColor = "gray";
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
                name={name}
                status={service.status}
                image={service.image}
                running_replicas={service.running_replicas}
                desired_replicas={service.desired_replicas}
                urls={urls[name] ?? []}
              />
            ))}
            {services.length > MAX_SERVICES_SHOWN && (
              <Link
                to={`compose-stacks/${slug}`}
                className={cn(
                  "size-10 border border-border rounded-md dark:bg-card bg-white",
                  "inline-flex items-center justify-center",
                  "relative z-10 cursor-pointer"
                )}
              >
                +{services.length - MAX_SERVICES_SHOWN}
              </Link>
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
            </p>
          )}
        </div>
      </CardContent>
    </Card>
  );
}

type ComposeStackServiceProps = Pick<
  ValueOf<ComposeStack["service_statuses"]>,
  "running_replicas" | "image" | "status" | "desired_replicas"
> & {
  name: string;
  urls: ValueOf<ComposeStack["urls"]>;
};

function ComposeStackService({
  name,
  status,
  urls,
  image
}: ComposeStackServiceProps) {
  const [imageNotFound, setImageNotFound] = React.useState(false);
  const iconSrc = getDockerImageIconURL(image);
  return (
    <div className="relative">
      <span
        tabIndex={0}
        className="absolute cursor-pointer flex size-2.5 -top-1 -right-1 z-20"
      >
        <span
          className={cn(
            "absolute inline-flex h-full w-full rounded-full  opacity-75",
            {
              "animate-ping bg-green-400":
                status === "HEALTHY" || status == "COMPLETE",
              "bg-red-400": status === "UNHEALTHY",
              "bg-yellow-400": status === "SLEEPING",
              "bg-secondary/60": status === "STARTING"
            }
          )}
        />

        <span
          className={cn(
            "relative inline-flex rounded-full size-2.5 bg-green-500",
            {
              "bg-green-500": status === "HEALTHY" || status == "COMPLETE",
              "bg-red-500": status === "UNHEALTHY",
              "bg-yellow-500": status === "SLEEPING",
              "bg-secondary": status === "STARTING"
            }
          )}
        ></span>
      </span>

      <Popover>
        <PopoverTrigger asChild>
          <button className="rounded-md relative z-10 dark:bg-card bg-white p-1 border border-border">
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
          </button>
        </PopoverTrigger>
        <PopoverContent align="center" className="w-40 text-sm">
          {name}
        </PopoverContent>
      </Popover>
    </div>
  );
}
