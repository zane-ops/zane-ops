import {
  BanIcon,
  ClockArrowUpIcon,
  FastForwardIcon,
  HammerIcon,
  HeartPulseIcon,
  HourglassIcon,
  LoaderIcon,
  PauseIcon,
  RefreshCwOffIcon,
  RotateCcwIcon,
  Trash2Icon,
  TriangleAlertIcon,
  XIcon
} from "lucide-react";
import type { StatusBadgeColor } from "~/components/status-badge";
import type { DEPLOYMENT_STATUSES } from "~/lib/constants";
import { cn } from "~/lib/utils";
import { capitalizeText } from "~/utils";

const DEPLOYMENT_STATUS_COLOR_MAP = {
  STARTING: "blue",
  RESTARTING: "blue",
  BUILDING: "blue",
  PREPARING: "blue",
  CANCELLING: "blue",
  HEALTHY: "green",
  UNHEALTHY: "red",
  FAILED: "red",
  REMOVED: "gray",
  CANCELLED: "gray",
  QUEUED: "gray",
  SLEEPING: "yellow"
} as const satisfies Record<
  (typeof DEPLOYMENT_STATUSES)[number],
  StatusBadgeColor
>;

type DeploymentStatusBadgeProps = {
  status: keyof typeof DEPLOYMENT_STATUS_COLOR_MAP;
  className?: string;
};

export function DeploymentStatusBadge({
  status,
  className
}: DeploymentStatusBadgeProps) {
  const color = DEPLOYMENT_STATUS_COLOR_MAP[status];

  const icons = {
    HEALTHY: HeartPulseIcon,
    RESTARTING: RotateCcwIcon,
    FAILED: XIcon,
    UNHEALTHY: TriangleAlertIcon,
    CANCELLED: BanIcon,
    QUEUED: ClockArrowUpIcon,
    REMOVED: Trash2Icon,
    SLEEPING: PauseIcon,
    STARTING: FastForwardIcon,
    BUILDING: HammerIcon,
    PREPARING: HourglassIcon,
    CANCELLING: RefreshCwOffIcon
  } as const satisfies Record<typeof status, React.ComponentType<any>>;

  const Icon = icons[status];

  const isLoading = [
    "STARTING",
    "PREPARING",
    "BUILDING",
    "CANCELLING",
    "RESTARTING"
  ].includes(status);

  const isActive = ["HEALTHY", "UNHEALTHY"].includes(status);
  return (
    <div
      className={cn(
        "relative top-0.5 rounded-md bg-link/20 text-link px-2  inline-flex gap-1 items-center",
        {
          "bg-emerald-400/20 dark:bg-emerald-600/20 text-green-600  dark:text-emerald-400":
            color === "green",
          "bg-red-600/10 text-red-600 dark:text-red-400": color === "red",
          "bg-yellow-400/20 dark:bg-yellow-600/20 text-yellow-600 dark:text-yellow-400":
            color === "yellow",
          "bg-gray-600/20 dark:bg-gray-600/60 text-gray": color === "gray",
          "bg-link/20 text-link": color === "blue"
        },
        className
      )}
    >
      <div className="relative ">
        {isActive && (
          <Icon
            size={15}
            className="flex-none animate-ping absolute h-full w-full"
          />
        )}
        <Icon size={15} className="flex-none" />
      </div>
      <p>{capitalizeText(status)}</p>
      {isLoading && <LoaderIcon className="animate-spin flex-none" size={15} />}
    </div>
  );
}
