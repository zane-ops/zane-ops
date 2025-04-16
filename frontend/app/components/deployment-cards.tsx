import {
  Ban,
  ChartNoAxesColumnIcon,
  Container,
  EllipsisVertical,
  Eye,
  GitCommitHorizontalIcon,
  GlobeIcon,
  Hash,
  LoaderIcon,
  Redo2,
  RotateCw,
  ScanTextIcon,
  ScrollText,
  Timer,
  ZapOffIcon
} from "lucide-react";
import * as React from "react";
import { useFetcher, useNavigate } from "react-router";
import { Link } from "react-router";
import { Code } from "~/components/code";
import { Button } from "~/components/ui/button";
import {
  Menubar,
  MenubarContent,
  MenubarMenu,
  MenubarTrigger
} from "~/components/ui/menubar";
import { MenubarContentItem } from "~/components/ui/menubar";
import {
  Tooltip,
  TooltipContent,
  TooltipProvider,
  TooltipTrigger
} from "~/components/ui/tooltip";
import type { DEPLOYMENT_STATUSES } from "~/lib/constants";
import type { Deployment } from "~/lib/queries";
import { cn } from "~/lib/utils";
import type { clientAction as cancelClientAction } from "~/routes/deployments/cancel-deployment";
import type { clientAction as redeployClientAction } from "~/routes/deployments/redeploy-docker-deployment";
import {
  capitalizeText,
  formatElapsedTime,
  formattedTime,
  mergeTimeAgoFormatterAndFormattedDate
} from "~/utils";

export type DockerDeploymentCardProps = {
  status: (typeof DEPLOYMENT_STATUSES)[number];
  started_at?: Date;
  finished_at?: Date;
  queued_at: Date;
  commit_message: string;
  image: string;
  hash: string;
  is_current_production?: boolean;
  redeploy_hash: string | null;
  urls?: Deployment["urls"];
};

export function DockerDeploymentCard({
  status,
  started_at,
  finished_at,
  queued_at,
  commit_message,
  image,
  hash,
  redeploy_hash,
  urls = [],
  is_current_production = false
}: DockerDeploymentCardProps) {
  const now = new Date();
  const [timeElapsed, setTimeElapsed] = React.useState(
    started_at ? Math.ceil((now.getTime() - started_at.getTime()) / 1000) : 0
  );

  const navigate = useNavigate();

  React.useEffect(() => {
    if (started_at && !finished_at) {
      const timer = setInterval(() => {
        setTimeElapsed(() =>
          Math.ceil((new Date().getTime() - started_at.getTime()) / 1000)
        );
      }, 1000);

      return () => clearInterval(timer);
    }
  }, [started_at, finished_at]);

  if (!image.includes(":")) {
    image += ":latest";
  }

  // all deployments statuse that match these filters can be cancelled
  const cancellableDeploymentsStatuses: Array<typeof status> = [
    "QUEUED",
    "PREPARING",
    "STARTING",
    "RESTARTING"
  ];

  const runningDeploymentsStatuses: Array<typeof status> = [
    "QUEUED",
    "BUILDING",
    "PREPARING",
    "STARTING",
    "RESTARTING",
    "CANCELLING"
  ];

  const isCancellable = cancellableDeploymentsStatuses.includes(status);
  const isRedeployable =
    !is_current_production &&
    (finished_at || !runningDeploymentsStatuses.includes(status));
  const isPending = !finished_at && runningDeploymentsStatuses.includes(status);

  const redeployFetcher = useFetcher<typeof redeployClientAction>();
  const cancelFetcher = useFetcher<typeof cancelClientAction>();

  return (
    <div
      className={cn(
        "flex flex-col md:flex-row items-start gap-4 md:gap-0 border group  px-3 py-4 rounded-md justify-between md:items-center relative",
        {
          "border-blue-600 bg-blue-600/10":
            status === "STARTING" ||
            status === "RESTARTING" ||
            status === "BUILDING" ||
            status === "PREPARING" ||
            status === "CANCELLING",
          "border-green-600 bg-green-600/10": status === "HEALTHY",
          "border-red-600 bg-red-600/10":
            status === "UNHEALTHY" || status === "FAILED",
          "border-gray-600 bg-gray-600/10":
            status === "REMOVED" ||
            status === "CANCELLED" ||
            status === "QUEUED",
          "border-yellow-600 bg-yellow-600/10": status === "SLEEPING"
        }
      )}
    >
      <div className="flex flex-col md:flex-row gap-4 md:gap-0">
        {/* Status name */}
        <div className="w-[160px]">
          <h3 className="flex items-center gap-1 capitalize">
            <span
              className={cn("text-lg", {
                "text-blue-500":
                  status === "STARTING" ||
                  status === "RESTARTING" ||
                  status === "BUILDING" ||
                  status === "PREPARING" ||
                  status === "CANCELLING",
                "text-green-500": status === "HEALTHY",
                "text-red-500": status === "UNHEALTHY" || status === "FAILED",
                "text-gray-500 dark:text-gray-400":
                  status === "REMOVED" || status === "QUEUED",
                "text-yellow-500": status === "SLEEPING",
                "text-card-foreground rounded-md bg-gray-400/40 dark:bg-gray-500/60 px-1":
                  status === "CANCELLED"
              })}
            >
              {capitalizeText(status)}
            </span>
            {Boolean(started_at && !finished_at) && (
              <LoaderIcon className="animate-spin" size={15} />
            )}
          </h3>
          <TooltipProvider>
            <Tooltip delayDuration={0}>
              <TooltipTrigger asChild>
                <time
                  dateTime={queued_at.toISOString()}
                  className="text-sm relative z-10 text-gray-500/80 dark:text-gray-400 text-nowrap"
                >
                  {mergeTimeAgoFormatterAndFormattedDate(queued_at)}
                </time>
              </TooltipTrigger>
              <TooltipContent className="max-w-64 text-balance">
                {formattedTime(queued_at)}
              </TooltipContent>
            </Tooltip>
          </TooltipProvider>
        </div>

        {/* Commit message & timer */}
        <div className="flex flex-col items-start gap-1">
          <h3 className="inline-flex flex-wrap gap-0.5">
            <Link
              prefetch="viewport"
              to={
                isPending || status === "FAILED" || status === "CANCELLED"
                  ? `deployments/${hash}/build-logs`
                  : `deployments/${hash}`
              }
              className="whitespace-nowrap after:absolute after:inset-0 overflow-x-hidden text-ellipsis max-w-[300px] sm:max-w-[500px] lg:max-w-[600px] xl:max-w-[800px]"
            >
              {capitalizeText(commit_message.split("\n")[0])}
            </Link>
            &nbsp;
            {redeploy_hash && (
              <small>
                <Code className="whitespace-nowrap inline-flex items-center gap-1">
                  <RotateCw size={12} className="flex-none" />
                  <span>Redeploy of {redeploy_hash}</span>
                </Code>
              </small>
            )}
          </h3>
          <div className="flex relative z-10 text-gray-500/80 dark:text-gray-400 gap-2.5 text-sm w-full items-start flex-wrap md:items-center">
            <div className="gap-0.5 inline-flex items-center">
              <Timer size={15} className="flex-none" />
              {started_at && !finished_at ? (
                <span>{formatElapsedTime(timeElapsed)}</span>
              ) : started_at && finished_at ? (
                <span>
                  {formatElapsedTime(
                    Math.round(
                      (finished_at.getTime() - started_at.getTime()) / 1000
                    )
                  )}
                </span>
              ) : (
                <span>-</span>
              )}
            </div>
            <div className="gap-1 inline-flex items-center">
              <Container size={15} className="flex-none" />
              <span>{image}</span>
            </div>
            <div className="inline-flex items-center gap-0.5 right-1">
              <Hash size={15} className="flex-none" />
              <span>{hash}</span>
            </div>
          </div>
        </div>
      </div>

      {/* View logs button & triple dot */}
      <div className="flex items-center gap-2 absolute right-4 z-10 md:relative md:right-auto">
        <Button
          asChild
          variant="ghost"
          className={cn(
            "border hover:bg-inherit focus:opacity-100 hidden lg:inline-flex",
            {
              "border-blue-600":
                status === "STARTING" ||
                status === "RESTARTING" ||
                status === "BUILDING" ||
                status === "CANCELLING" ||
                status === "PREPARING",
              "border-green-600": status === "HEALTHY",
              "border-red-600": status === "UNHEALTHY" || status === "FAILED",
              "border-gray-600 md:opacity-0 group-hover:opacity-100 transition-opacity ease-in duration-150":
                status === "REMOVED" ||
                status === "CANCELLED" ||
                status === "QUEUED",
              "border-yellow-600": status === "SLEEPING"
            }
          )}
        >
          <Link
            to={
              isPending || status === "FAILED" || status === "CANCELLED"
                ? `deployments/${hash}/build-logs`
                : `deployments/${hash}`
            }
          >
            View logs
          </Link>
        </Button>

        {isRedeployable && (
          <redeployFetcher.Form
            method="post"
            action={`./deployments/${hash}/redeploy-docker`}
            id={`redeploy-${hash}-form`}
            className="hidden"
          />
        )}
        {isCancellable && (
          <cancelFetcher.Form
            method="post"
            action={`./deployments/${hash}/cancel`}
            id={`cancel-${hash}-form`}
            className="hidden"
          />
        )}

        <Menubar className="border-none h-auto w-fit">
          <MenubarMenu>
            <MenubarTrigger
              className="flex justify-center items-center gap-2"
              asChild
            >
              <Button variant="ghost" className="px-1.5 py-1 hover:bg-inherit">
                <EllipsisVertical />
              </Button>
            </MenubarTrigger>
            <MenubarContent
              side="bottom"
              align="start"
              className="border min-w-0 mx-9 border-border"
            >
              {isRedeployable && (
                <button
                  form={`redeploy-${hash}-form`}
                  className="w-full"
                  disabled={redeployFetcher.state !== "idle"}
                  onClick={(e) => {
                    e.currentTarget.form?.requestSubmit();
                  }}
                >
                  <MenubarContentItem icon={Redo2} text="Redeploy" />
                </button>
              )}
              {isCancellable && (
                <button
                  form={`cancel-${hash}-form`}
                  className="w-full"
                  onClick={(e) => {
                    e.currentTarget.form?.requestSubmit();
                  }}
                  disabled={cancelFetcher.state !== "idle"}
                >
                  <MenubarContentItem
                    className="text-red-500"
                    icon={Ban}
                    text="Cancel"
                  />
                </button>
              )}
              <MenubarContentItem
                icon={Eye}
                text="Details"
                onClick={() => navigate(`./deployments/${hash}/details`)}
              />
              <MenubarContentItem
                icon={ScrollText}
                text="View runtime logs"
                onClick={() => navigate(`./deployments/${hash}`)}
              />
              <MenubarContentItem
                icon={ScanTextIcon}
                text="View deployment logs"
                onClick={() => navigate(`./deployments/${hash}/build-logs`)}
              />
              <MenubarContentItem
                icon={ChartNoAxesColumnIcon}
                text="View metrics"
                onClick={() => navigate(`./deployments/${hash}/metrics`)}
              />

              {urls?.length > 0 && (
                <>
                  <MenubarContentItem
                    icon={GlobeIcon}
                    text="View http logs"
                    onClick={() => navigate(`./deployments/${hash}/http-logs`)}
                  />
                </>
              )}
            </MenubarContent>
          </MenubarMenu>
        </Menubar>
      </div>
    </div>
  );
}

export type GitDeploymentCardProps = {
  status: (typeof DEPLOYMENT_STATUSES)[number];
  started_at?: Date;
  finished_at?: Date;
  queued_at: Date;
  commit_message: string;
  commit_sha: string;
  hash: string;
  is_current_production?: boolean;
  redeploy_hash: string | null;
  urls?: Deployment["urls"];
  ignore_build_cache: boolean;
};

export function GitDeploymentCard({
  status,
  started_at,
  finished_at,
  queued_at,
  commit_message,
  commit_sha,
  hash,
  redeploy_hash,
  ignore_build_cache,
  urls = [],
  is_current_production = false
}: GitDeploymentCardProps) {
  const now = new Date();
  const [timeElapsed, setTimeElapsed] = React.useState(
    started_at ? Math.ceil((now.getTime() - started_at.getTime()) / 1000) : 0
  );

  const navigate = useNavigate();

  React.useEffect(() => {
    if (started_at && !finished_at) {
      const timer = setInterval(() => {
        setTimeElapsed(() =>
          Math.ceil((new Date().getTime() - started_at.getTime()) / 1000)
        );
      }, 1000);

      return () => clearInterval(timer);
    }
  }, [started_at, finished_at]);

  // all deployments statuse that match these filters can be cancelled
  const cancellableDeploymentsStatuses: Array<typeof status> = [
    "QUEUED",
    "BUILDING",
    "PREPARING",
    "STARTING",
    "RESTARTING"
  ];

  const runningDeploymentsStatuses: Array<typeof status> = [
    "QUEUED",
    "BUILDING",
    "PREPARING",
    "STARTING",
    "RESTARTING",
    "CANCELLING"
  ];

  const isCancellable = cancellableDeploymentsStatuses.includes(status);
  const isRedeployable =
    !is_current_production &&
    (finished_at || !runningDeploymentsStatuses.includes(status));

  const isPending = !finished_at && runningDeploymentsStatuses.includes(status);

  const redeployFetcher = useFetcher<typeof redeployClientAction>();
  const cancelFetcher = useFetcher<typeof cancelClientAction>();

  return (
    <div
      className={cn(
        "flex flex-col md:flex-row items-start gap-4 md:gap-0 border group  px-3 py-4 rounded-md justify-between md:items-center relative",
        {
          "border-blue-600 bg-blue-600/10":
            status === "STARTING" ||
            status === "RESTARTING" ||
            status === "BUILDING" ||
            status === "PREPARING" ||
            status === "CANCELLING",
          "border-green-600 bg-green-600/10": status === "HEALTHY",
          "border-red-600 bg-red-600/10":
            status === "UNHEALTHY" || status === "FAILED",
          "border-gray-600 bg-gray-600/10":
            status === "REMOVED" ||
            status === "CANCELLED" ||
            status === "QUEUED",
          "border-yellow-600 bg-yellow-600/10": status === "SLEEPING"
        }
      )}
    >
      <div className="flex flex-col md:flex-row gap-4 md:gap-0 max-w-full w-full">
        {/* Status name */}
        <div className="w-[160px]">
          <h3 className="flex items-center gap-1 capitalize">
            <span
              className={cn("text-lg", {
                "text-blue-500":
                  status === "STARTING" ||
                  status === "RESTARTING" ||
                  status === "BUILDING" ||
                  status === "PREPARING" ||
                  status === "CANCELLING",
                "text-green-500": status === "HEALTHY",
                "text-red-500": status === "UNHEALTHY" || status === "FAILED",
                "text-gray-500 dark:text-gray-400":
                  status === "REMOVED" || status === "QUEUED",
                "text-yellow-500": status === "SLEEPING",
                "text-card-foreground rounded-md bg-gray-400/40 dark:bg-gray-500/60 px-1":
                  status === "CANCELLED"
              })}
            >
              {capitalizeText(status)}
            </span>
            {Boolean(started_at && !finished_at) && (
              <LoaderIcon className="animate-spin" size={15} />
            )}
          </h3>
          <TooltipProvider>
            <Tooltip delayDuration={0}>
              <TooltipTrigger asChild>
                <time
                  dateTime={queued_at.toISOString()}
                  className="text-sm relative z-10 text-gray-500/80 dark:text-gray-400 text-nowrap"
                >
                  {mergeTimeAgoFormatterAndFormattedDate(queued_at)}
                </time>
              </TooltipTrigger>
              <TooltipContent className="max-w-64 text-balance">
                {formattedTime(queued_at)}
              </TooltipContent>
            </Tooltip>
          </TooltipProvider>
        </div>

        {/* Commit message & timer */}
        <div className="flex flex-col items-start gap-1">
          <h3 className="inline-flex flex-wrap gap-0.5">
            <Link
              prefetch="viewport"
              to={
                isPending || status === "FAILED"
                  ? `deployments/${hash}/build-logs`
                  : `deployments/${hash}`
              }
              className="whitespace-nowrap after:absolute after:inset-0 overflow-x-hidden text-ellipsis max-w-[300px] sm:max-w-[500px] lg:max-w-[600px] xl:max-w-[800px]"
            >
              {capitalizeText(commit_message.split("\n")[0])}
            </Link>
            &nbsp;
            {redeploy_hash && (
              <small>
                <Code className="whitespace-nowrap inline-flex items-center gap-1">
                  <RotateCw size={12} className="flex-none" />
                  <span>Redeploy of {redeploy_hash}</span>
                </Code>
              </small>
            )}
            {ignore_build_cache && (
              <small>
                <Code className="whitespace-nowrap inline-flex items-center gap-1">
                  <ZapOffIcon size={12} className="flex-none" />
                  <span>build cache ignored</span>
                </Code>
              </small>
            )}
          </h3>
          <div className="flex relative z-10 text-gray-500/80 dark:text-gray-400 gap-2.5 text-sm max-w-full w-full items-start flex-wrap md:items-center">
            <div className="gap-0.5 inline-flex items-center">
              <Timer size={15} className="flex-none" />
              {started_at && !finished_at ? (
                <span>{formatElapsedTime(timeElapsed)}</span>
              ) : started_at && finished_at ? (
                <span>
                  {formatElapsedTime(
                    Math.round(
                      (finished_at.getTime() - started_at.getTime()) / 1000
                    )
                  )}
                </span>
              ) : (
                <span>-</span>
              )}
            </div>
            <div className="gap-1 inline-flex items-center max-w-full">
              <GitCommitHorizontalIcon size={15} className="flex-none" />
              <p className="text-ellipsis overflow-x-hidden whitespace-nowrap">
                {commit_sha}
              </p>
            </div>
            <div className="inline-flex items-center gap-0.5 right-1">
              <Hash size={15} className="flex-none" />
              <span>{hash}</span>
            </div>
          </div>
        </div>
      </div>

      {/* View logs button & triple dot */}
      <div className="flex items-center gap-2 absolute right-4 z-10 md:relative md:right-auto">
        <Button
          asChild
          variant="ghost"
          className={cn(
            "border hover:bg-inherit focus:opacity-100 hidden lg:inline-flex",
            {
              "border-blue-600":
                status === "STARTING" ||
                status === "RESTARTING" ||
                status === "BUILDING" ||
                status === "CANCELLING" ||
                status === "PREPARING",
              "border-green-600": status === "HEALTHY",
              "border-red-600": status === "UNHEALTHY" || status === "FAILED",
              "border-gray-600 md:opacity-0 group-hover:opacity-100 transition-opacity ease-in duration-150":
                status === "REMOVED" ||
                status === "CANCELLED" ||
                status === "QUEUED",
              "border-yellow-600": status === "SLEEPING"
            }
          )}
        >
          <Link
            to={
              isPending || status === "FAILED"
                ? `deployments/${hash}/build-logs`
                : `deployments/${hash}`
            }
          >
            View logs
          </Link>
        </Button>

        {isRedeployable && (
          <redeployFetcher.Form
            method="post"
            action={`./deployments/${hash}/redeploy-git`}
            id={`redeploy-${hash}-form`}
            className="hidden"
          />
        )}
        {isCancellable && (
          <cancelFetcher.Form
            method="post"
            action={`./deployments/${hash}/cancel`}
            id={`cancel-${hash}-form`}
            className="hidden"
          />
        )}

        <Menubar className="border-none h-auto w-fit">
          <MenubarMenu>
            <MenubarTrigger
              className="flex justify-center items-center gap-2"
              asChild
            >
              <Button variant="ghost" className="px-1.5 py-1 hover:bg-inherit">
                <EllipsisVertical />
              </Button>
            </MenubarTrigger>
            <MenubarContent
              side="bottom"
              align="start"
              className="border min-w-0 mx-9 border-border"
            >
              {isRedeployable && (
                <button
                  form={`redeploy-${hash}-form`}
                  className="w-full"
                  disabled={redeployFetcher.state !== "idle"}
                  onClick={(e) => {
                    e.currentTarget.form?.requestSubmit();
                  }}
                >
                  <MenubarContentItem icon={Redo2} text="Redeploy" />
                </button>
              )}
              {isCancellable && (
                <button
                  form={`cancel-${hash}-form`}
                  className="w-full"
                  onClick={(e) => {
                    e.currentTarget.form?.requestSubmit();
                  }}
                  disabled={cancelFetcher.state !== "idle"}
                >
                  <MenubarContentItem
                    className="text-red-500"
                    icon={Ban}
                    text="Cancel"
                  />
                </button>
              )}
              <MenubarContentItem
                icon={Eye}
                text="Details"
                onClick={() => navigate(`./deployments/${hash}/details`)}
              />
              <MenubarContentItem
                icon={ScrollText}
                text="View runtime logs"
                onClick={() => navigate(`./deployments/${hash}`)}
              />
              <MenubarContentItem
                icon={ScanTextIcon}
                text="View deployment logs"
                onClick={() => navigate(`./deployments/${hash}/build-logs`)}
              />
              <MenubarContentItem
                icon={ChartNoAxesColumnIcon}
                text="View metrics"
                onClick={() => navigate(`./deployments/${hash}/metrics`)}
              />

              {urls?.length > 0 && (
                <>
                  <MenubarContentItem
                    icon={GlobeIcon}
                    text="View http logs"
                    onClick={() => navigate(`./deployments/${hash}/http-logs`)}
                  />
                </>
              )}
            </MenubarContent>
          </MenubarMenu>
        </Menubar>
      </div>
    </div>
  );
}
