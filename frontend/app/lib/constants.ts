import { type useSpinDelay } from "spin-delay";
export const DEPLOYMENT_STATUSES = [
  "QUEUED",
  "CANCELLED",
  "CANCELLING",
  "FAILED",
  "PREPARING",
  "HEALTHY",
  "UNHEALTHY",
  "STARTING",
  "RESTARTING",
  "REMOVED",
  "SLEEPING"
] as const;

export const DEFAULT_QUERY_REFETCH_INTERVAL = 5 * 1000; // 5 seconds
export const DEFAULT_LOGS_PER_PAGE = 50;
export const MAX_VISIBLE_LOG_CHARS_LIMIT = 1_000;

export const SPIN_DELAY_DEFAULT_OPTIONS: Parameters<typeof useSpinDelay>[1] = {
  delay: 250,
  minDuration: 200
};
export const REALLY_BIG_NUMBER_THAT_IS_LESS_THAN_MAX_SAFE_INTEGER = 9_999_999_999;
