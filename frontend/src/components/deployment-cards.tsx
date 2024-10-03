import { useNavigate } from "@tanstack/react-router";
import { Link } from "@tanstack/react-router";
import {
  Ban,
  Container,
  EllipsisVertical,
  Eye,
  Hash,
  LoaderIcon,
  Redo2,
  RotateCw,
  ScrollText,
  Timer
} from "lucide-react";
import * as React from "react";
import { toast } from "sonner";
import { Code } from "~/components/code";
import { Button } from "~/components/ui/button";
import {
  Menubar,
  MenubarContent,
  MenubarMenu,
  MenubarTrigger
} from "~/components/ui/menubar";
import { MenubarContentItem } from "~/components/ui/menubar";
import type { DEPLOYMENT_STATUSES } from "~/lib/constants";
import { useCancelDockerServiceDeploymentMutation } from "~/lib/hooks/use-cancel-docker-service-deployment-mutation";
import { useRedeployDockerServiceMutation } from "~/lib/hooks/use-redeploy-docker-service-mutation";
import { cn } from "~/lib/utils";
import {
  capitalizeText,
  formatElapsedTime,
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
  project_slug: string;
  service_slug: string;
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
  project_slug,
  service_slug,
  is_current_production = false
}: DockerDeploymentCardProps) {
  const now = new Date();
  const { mutateAsync: redeploy } = useRedeployDockerServiceMutation(
    project_slug,
    service_slug,
    hash
  );
  const { mutateAsync: cancel } = useCancelDockerServiceDeploymentMutation(
    project_slug,
    service_slug,
    hash
  );
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
    "PREPARING",
    "STARTING",
    "RESTARTING",
    "CANCELLING"
  ];

  const isCancellable = cancellableDeploymentsStatuses.includes(status);
  const isRedeployable =
    !is_current_production &&
    (finished_at || !runningDeploymentsStatuses.includes(status));

  return (
    <div
      className={cn(
        "flex flex-col md:flex-row items-start gap-4 md:gap-0 border group  px-3 py-4 rounded-md  bg-opacity-10 justify-between md:items-center relative",
        {
          "border-blue-600 bg-blue-600":
            status === "STARTING" ||
            status === "RESTARTING" ||
            status === "PREPARING" ||
            status === "CANCELLING",
          "border-green-600 bg-green-600": status === "HEALTHY",
          "border-red-600 bg-red-600":
            status === "UNHEALTHY" || status === "FAILED",
          "border-gray-600 bg-gray-600":
            status === "REMOVED" ||
            status === "CANCELLED" ||
            status === "QUEUED",
          "border-yellow-600 bg-yellow-600": status === "SLEEPING"
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
          <p className="text-sm text-gray-500/80 dark:text-gray-400 text-nowrap">
            {mergeTimeAgoFormatterAndFormattedDate(queued_at)}
          </p>
        </div>

        {/* Commit message & timer */}
        <div className="flex flex-col items-start gap-1">
          <h3 className="inline-flex flex-wrap gap-0.5">
            <Link
              className="after:absolute after:inset-0"
              to={`./deployments/${hash}`}
            >
              {capitalizeText(commit_message)}
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
          <div className="flex text-gray-500/80 dark:text-gray-400 gap-2.5 text-sm w-full items-start flex-wrap md:items-center">
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
          <Link to={`deployments/${hash}`}>View logs</Link>
        </Button>

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
              <MenubarContentItem
                icon={Eye}
                text="Details"
                onClick={() =>
                  navigate({
                    to: `deployments/${hash}/details`
                  })
                }
              />
              <MenubarContentItem
                icon={ScrollText}
                text="View logs"
                onClick={() =>
                  navigate({
                    to: `deployments/${hash}`
                  })
                }
              />
              {isRedeployable && (
                <MenubarContentItem
                  icon={Redo2}
                  text="Redeploy"
                  onClick={() =>
                    toast.promise(redeploy(), {
                      loading: `Queuing redeployment for #${hash}...`,
                      success: "Success",
                      error: "Error",
                      closeButton: true,
                      description(data) {
                        if (data instanceof Error) {
                          return data.message;
                        }
                        return "Redeployment queued succesfully.";
                      }
                    })
                  }
                />
              )}
              {isCancellable && (
                <MenubarContentItem
                  className="text-red-500"
                  icon={Ban}
                  text="Cancel"
                  onClick={() =>
                    toast.promise(cancel(), {
                      loading: `Requesting cancellation for deployment #${hash}...`,
                      success: "Success",
                      error: "Error",
                      closeButton: true,
                      description: (data) => {
                        if (data instanceof Error) {
                          return data.message;
                        }
                        return "Deployment cancel request sent.";
                      }
                    })
                  }
                />
              )}
            </MenubarContent>
          </MenubarMenu>
        </Menubar>
      </div>
    </div>
  );
}
