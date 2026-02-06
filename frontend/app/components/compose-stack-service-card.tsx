import type { hash } from "crypto";
import { url } from "inspector";
import {
  ArrowRightIcon,
  Ban,
  BoxIcon,
  ChartNoAxesColumnIcon,
  ChevronRight,
  ContainerIcon,
  EllipsisVertical,
  EllipsisVerticalIcon,
  Eye,
  GlobeIcon,
  Layers2Icon,
  LinkIcon,
  Redo2,
  ScanTextIcon,
  ScrollText,
  TagIcon,
  TerminalIcon
} from "lucide-react";
import * as React from "react";
import { Link, useNavigate } from "react-router";
import type { ComposeStack } from "~/api/types";
import { CopyButton } from "~/components/copy-button";
import { DeploymentStatusBadge } from "~/components/deployment-status-badge";
import { StatusBadge } from "~/components/status-badge";
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
  Popover,
  PopoverContent,
  PopoverTrigger
} from "~/components/ui/popover";
import {
  Tooltip,
  TooltipContent,
  TooltipProvider,
  TooltipTrigger
} from "~/components/ui/tooltip";
import type { ValueOf } from "~/lib/types";
import { cn } from "~/lib/utils";
import {
  formatURL,
  getDockerImageIconURL,
  pluralize,
  stripSlashIfExists
} from "~/utils";

export type ComposeStackServiceCardProps = {
  service: ValueOf<ComposeStack["service_statuses"]>;
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

  let serviceImage = service.image;
  if (serviceImage && !serviceImage.includes(":")) {
    serviceImage += ":latest";
  }

  const navigate = useNavigate();

  return (
    <Card
      className={cn(
        "group p-3 relative",
        "flex items-center justify-between",
        "bg-toggle",
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
      <div className="flex flex-col gap-2">
        <div className="flex items-center gap-x-0 flex-wrap">
          {iconSrc && !iconNotFound ? (
            <img
              src={iconSrc}
              onError={() => setIconNotFound(true)}
              alt={`Logo for ${serviceImage}`}
              className={cn(
                "size-4 flex-none object-center object-contain",
                "rounded-md mr-1"
              )}
            />
          ) : (
            <BoxIcon className="flex-none size-4 mr-1" />
          )}
          <h3 className="text-lg">{name}</h3>
          <span className="ml-2 inline-block rounded-full size-0.5 bg-foreground relative " />
          <DeploymentStatusBadge
            status={service.status}
            variant="outline"
            className="self-start"
          />

          {/* {urls.length > 0 && (
            <Popover>
              <PopoverTrigger asChild>
                <button>
                  <StatusBadge
                    className="relative rounded-md top-0.5 text-xs pl-3 pr-2 inline-flex items-center gap-1 cursor-pointer"
                    color="gray"
                    pingState="hidden"
                  >
                    <LinkIcon className="size-3.5 flex-none" />
                    <span>
                      {`${urls.length} ${pluralize("url", urls.length)}`}
                    </span>
                    <ChevronRight className="size-[15px] flex-none" />
                  </StatusBadge>
                </button>
              </PopoverTrigger>
              <PopoverContent
                align="start"
                side="bottom"
                className="px-4 pt-3 pb-2 max-w-[300px] md:max-w-[500px] lg:max-w-[600px] w-auto"
              >
                <ul className="w-full">
                  {urls.map((url) => (
                    <li
                      key={url.domain + url.base_path}
                      className="w-full flex items-center gap-0.5"
                    >
                      <CopyButton
                        value={url.domain + url.base_path}
                        label="Copy url"
                        size="icon"
                        className="hover:bg-transparent !opacity-100 size-4"
                      />
                      <a
                        href={formatURL(url)}
                        target="_blank"
                        className="underline text-link text-sm inline-block w-full"
                      >
                        <p className="whitespace-nowrap overflow-x-hidden text-ellipsis">
                          {stripSlashIfExists(formatURL(url))}
                        </p>
                      </a>
                      <ArrowRightIcon className="size-4 flex-none" />
                      <small className="text-card-foreground">{url.port}</small>
                    </li>
                  ))}
                </ul>
              </PopoverContent>
            </Popover>
          )} */}
        </div>
        <div className="flex gap-1 items-center">
          <TagIcon className="flex-none size-4 text-grey dark:text-foreground " />
          <span className="text-grey dark:text-foreground text-sm">
            {serviceImage}
          </span>
        </div>

        {urls.length > 0 && (
          <ul>
            {urls.map((url) => (
              <li
                key={url.domain + url.base_path}
                className="w-full flex items-center gap-1 text-grey dark:text-foreground"
              >
                <TooltipProvider>
                  <Tooltip delayDuration={0}>
                    <TooltipTrigger asChild>
                      <CopyButton
                        value={url.domain + url.base_path}
                        label="Copy url"
                        size="icon"
                        className="hover:bg-transparent !opacity-100 size-4 text-grey dark:text-foreground p-0"
                      />
                    </TooltipTrigger>
                    <TooltipContent>Copy URL</TooltipContent>
                  </Tooltip>
                </TooltipProvider>
                <a
                  href={formatURL(url)}
                  target="_blank"
                  className="underline text-link text-sm inline-block w-fit"
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

        <div className="text-grey dark:text-foreground col-span-2 flex items-center gap-1 text-sm">
          <Layers2Icon className="flex-none  text-grey dark:text-foreground size-4" />
          {is_job ? (
            <span className="text-grey dark:text-foreground">
              {total_completed}/{service.desired_replicas} tasks completed
            </span>
          ) : (
            <span className="text-grey dark:text-foreground">
              {service.running_replicas}/{service.desired_replicas} replicas
              running
            </span>
          )}
        </div>
      </div>

      {/* View logs button & triple dot */}
      <div className="flex items-center gap-1 absolute right-4 z-10 md:relative md:right-auto">
        <Button
          asChild
          variant="ghost"
          className="bg-muted !border border-card/20 dark:border-grey/20  text-sm"
          size="sm"
        >
          <Link to={`./runtime-logs`}>View logs</Link>
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
              align="start"
              className="border min-w-0 mx-9 border-border"
            >
              <MenubarContentItem
                icon={TerminalIcon}
                text="Terminal"
                onClick={() => navigate(`./terminal`)}
              />
              <MenubarContentItem
                icon={ScrollText}
                text="View runtime logs"
                onClick={() => navigate(`./runtime-logs`)}
              />
              {urls?.length > 0 && (
                <>
                  <MenubarContentItem
                    icon={GlobeIcon}
                    text="View http logs"
                    onClick={() => navigate(`./http-logs`)}
                  />
                </>
              )}
              <MenubarContentItem
                icon={ChartNoAxesColumnIcon}
                text="View metrics"
                onClick={() => navigate(`./metrics`)}
              />
            </MenubarContent>
          </MenubarMenu>
        </Menubar>
      </div>
    </Card>
  );
}
