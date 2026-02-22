import {
  ArrowRightIcon,
  BoxIcon,
  ChartNoAxesColumnIcon,
  EllipsisVerticalIcon,
  Eye,
  GlobeIcon,
  Layers2Icon,
  LayersIcon,
  RotateCcwIcon,
  ScrollText,
  TagIcon,
  TerminalIcon
} from "lucide-react";
import * as React from "react";
import { Link, useNavigate } from "react-router";
import type { ComposeStack } from "~/api/types";
import { CopyButton } from "~/components/copy-button";
import { DeploymentStatusBadge } from "~/components/deployment-status-badge";
import { Button } from "~/components/ui/button";
import { Card } from "~/components/ui/card";
import {
  Menubar,
  MenubarContent,
  MenubarContentItem,
  MenubarMenu,
  MenubarTrigger
} from "~/components/ui/menubar";
import {
  Tooltip,
  TooltipContent,
  TooltipProvider,
  TooltipTrigger
} from "~/components/ui/tooltip";
import type { ValueOf } from "~/lib/types";
import { cn } from "~/lib/utils";
import { formatURL, getDockerImageIconURL, stripSlashIfExists } from "~/utils";

export type ComposeStackServiceCardProps = {
  service: ValueOf<ComposeStack["services"]>;
  urls: ValueOf<ComposeStack["urls"]>;
  name: string;
  className?: string;
};

export function ComposeStackServiceCard({
  service,
  name,
  className,
  urls
}: ComposeStackServiceCardProps) {
  const [iconNotFound, setIconNotFound] = React.useState(false);
  const iconSrc = getDockerImageIconURL(service.image);

  const total_completed = service.tasks.filter(
    (task) => task.status === "complete"
  ).length;
  const is_job =
    service.mode === "global-job" || service.mode === "replicated-job";

  let [serviceImage] = service.image.split("@"); // the image is in the format 'image@sha', we just remove the sha

  if (serviceImage && !serviceImage.includes(":")) {
    serviceImage += ":latest";
  }

  const navigate = useNavigate();

  return (
    <Card
      className={cn(
        "group p-3 relative",
        "flex items-center justify-between w-full gap-4",
        "bg-toggle text-grey dark:text-foreground text-sm min-w-0",
        "transition-colors duration-300",
        "shadow-sm border-l-2",
        "rounded-l-none",
        {
          "border-l-green-500": service.status === "HEALTHY",
          "border-l-red-500": service.status === "UNHEALTHY",
          "border-l-yellow-500":
            service.status === "SLEEPING" || service.status === "COMPLETE",
          "border-l-secondary": service.status === "STARTING"
        },
        className
      )}
    >
      {/* Service name & status */}
      <div className="flex flex-col gap-2 w-full items-start shrink min-w-0">
        <div className="flex items-center gap-x-0 flex-wrap">
          {iconSrc && !iconNotFound ? (
            <img
              src={iconSrc}
              onError={() => setIconNotFound(true)}
              alt={`Logo for ${serviceImage}`}
              className={cn(
                "size-4 flex-none object-center object-contain",
                "rounded-sm mr-1"
              )}
            />
          ) : (
            <BoxIcon className="flex-none size-4 mr-1" />
          )}
          <h3 className="text-lg text-card-foreground break-all">
            <Link
              to={`./services/${name}`}
              className="after:absolute after:inset-0 after:z-1"
            >
              {name}
            </Link>
          </h3>
          <span className="ml-2 inline-block rounded-full size-0.5 bg-foreground relative " />
          <DeploymentStatusBadge
            status={service.status}
            variant="outline"
            className="self-start"
          />
        </div>

        {/* Service image */}
        <div className="inline-flex gap-1 items-center max-w-[calc(100%_-_2.5rem)] relative z-10">
          <TagIcon className="flex-none size-4" />
          <span className="whitespace-nowrap overflow-x-hidden text-ellipsis">
            {serviceImage}
          </span>
        </div>

        {/* URLS */}
        {urls.length > 0 && (
          <ul className="w-full max-w-[calc(100%_-_6rem)] md:max-w-[calc(100%_-_5rem)]">
            {urls.map((url) => (
              <li
                key={url.domain + url.base_path}
                className="flex items-center gap-1 w-full relative z-10"
              >
                <TooltipProvider>
                  <Tooltip delayDuration={0}>
                    <TooltipTrigger asChild>
                      <CopyButton
                        value={url.domain + url.base_path}
                        label="Copy url"
                        size="icon"
                        className="hover:bg-transparent !opacity-100 size-4 p-0"
                      />
                    </TooltipTrigger>
                    <TooltipContent>Copy URL</TooltipContent>
                  </Tooltip>
                </TooltipProvider>
                <a
                  href={formatURL(url)}
                  target="_blank"
                  className="underline text-link text-sm inline-block w-fit max-w-[calc(100%_-_1rem)]"
                >
                  <p className="whitespace-nowrap overflow-x-hidden text-ellipsis">
                    {stripSlashIfExists(`${url.domain}${url.base_path}`)}
                  </p>
                </a>

                <ArrowRightIcon className="size-4 flex-none" />
                <small className="text-card-foreground">{url.port}</small>
              </li>
            ))}
          </ul>
        )}

        <div className=" col-span-2 flex items-center gap-1 text-sm relative z-10">
          <Layers2Icon className="flex-none size-4" />
          {is_job ? (
            <span>
              {total_completed}/{service.desired_replicas} tasks completed
            </span>
          ) : (
            <span>
              {service.running_replicas}/{service.desired_replicas} replicas
              running
            </span>
          )}
        </div>
      </div>

      {/* View logs button & triple dot */}
      <div
        className={cn(
          "flex items-center gap-1",
          "md:relative md:top-auto md:right-auto",
          "absolute top-3 right-4 z-10"
        )}
      >
        <Button
          asChild
          variant="ghost"
          className={cn(
            "!border border-card/20 dark:border-grey/20",
            "bg-muted text-sm text-card-foreground hidden md:inline-flex"
          )}
          size="sm"
        >
          <Link to={`./services/${name}/runtime-logs`}>View logs</Link>
        </Button>

        <Menubar className="border-none h-auto w-fit">
          <MenubarMenu>
            <MenubarTrigger
              className="flex justify-center items-center gap-2"
              asChild
            >
              <Button variant="ghost" className="px-1.5 py-1 hover:bg-inherit">
                <EllipsisVerticalIcon className="flex-none size-4" />
              </Button>
            </MenubarTrigger>
            <MenubarContent
              side="bottom"
              align="center"
              className="border min-w-0 mx-9 border-border"
            >
              <MenubarContentItem
                icon={LayersIcon}
                text="Replicas"
                onClick={() => navigate(`./services/${name}`)}
              />
              <MenubarContentItem
                icon={ScrollText}
                text="View runtime logs"
                onClick={() => navigate(`./services/${name}/runtime-logs`)}
              />

              <MenubarContentItem
                icon={TerminalIcon}
                text="Terminal"
                onClick={() => navigate(`./services/${name}/terminal`)}
              />
              <MenubarContentItem
                icon={Eye}
                text="Details"
                onClick={() => navigate(`./services/${name}/details`)}
              />

              {urls?.length > 0 && (
                <>
                  <MenubarContentItem
                    icon={GlobeIcon}
                    text="View http logs"
                    onClick={() => navigate(`./services/${name}/http-logs`)}
                  />
                </>
              )}
              <MenubarContentItem
                icon={ChartNoAxesColumnIcon}
                text="View metrics"
                onClick={() => navigate(`./services/${name}/metrics`)}
              />

              {!is_job && (
                <MenubarContentItem
                  icon={RotateCcwIcon}
                  text="Restart service"
                  onClick={() => {
                    //...
                  }}
                />
              )}
            </MenubarContent>
          </MenubarMenu>
        </Menubar>
      </div>
    </Card>
  );
}
