import type { useSpinDelay } from "spin-delay";
import { durationToMs } from "~/utils";
export const DEPLOYMENT_STATUSES = [
  "QUEUED",
  "BUILDING",
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

export const DEFAULT_QUERY_REFETCH_INTERVAL = durationToMs(5, "seconds");
export const LOGS_QUERY_REFETCH_INTERVAL = durationToMs(3, "seconds");
export const DEFAULT_LOGS_PER_PAGE = 50;
export const MAX_VISIBLE_LOG_CHARS_LIMIT = 1_000;

export const SPIN_DELAY_DEFAULT_OPTIONS: Parameters<typeof useSpinDelay>[1] = {
  delay: 150,
  minDuration: 150
};
export const METRICS_TIME_RANGES = [
  "LAST_HOUR",
  "LAST_6HOURS",
  "LAST_DAY",
  "LAST_WEEK",
  "LAST_MONTH"
] as const;
export const REALLY_BIG_NUMBER_THAT_IS_LESS_THAN_MAX_SAFE_INTEGER = 9_999_999_999;
export const STANDARD_HTTP_STATUS_CODES: { [key: number]: string } = {
  100: "Continue",
  101: "Switching Protocols",
  102: "Processing",
  103: "Early Hints",
  200: "OK",
  201: "Created",
  202: "Accepted",
  203: "Non-Authoritative Information",
  204: "No Content",
  205: "Reset Content",
  206: "Partial Content",
  207: "Multi-Status",
  208: "Already Reported",
  226: "IM Used",
  300: "Multiple Choices",
  301: "Moved Permanently",
  302: "Found",
  303: "See Other",
  304: "Not Modified",
  305: "Use Proxy",
  306: "Switch Proxy",
  307: "Temporary Redirect",
  308: "Permanent Redirect",
  400: "Bad Request",
  401: "Unauthorized",
  402: "Payment Required",
  403: "Forbidden",
  404: "Not Found",
  405: "Method Not Allowed",
  406: "Not Acceptable",
  407: "Proxy Authentication Required",
  408: "Request Timeout",
  409: "Conflict",
  410: "Gone",
  411: "Length Required",
  412: "Precondition Failed",
  413: "Payload Too Large",
  414: "URI Too Long",
  415: "Unsupported Media Type",
  416: "Range Not Satisfiable",
  417: "Expectation Failed",
  418: "I'm a teapot",
  421: "Misdirected Request",
  422: "Unprocessable Entity",
  423: "Locked",
  424: "Failed Dependency",
  425: "Too Early",
  426: "Upgrade Required",
  427: "Precondition Required",
  428: "Too Many Requests",
  429: "Request Header Fields Too Large",
  431: "Unavailable For Legal Reasons",
  451: "Unavailable For Legal Reasons",
  500: "Internal Server Error",
  501: "Not Implemented",
  502: "Bad Gateway",
  503: "Service Unavailable",
  504: "Gateway Timeout",
  505: "HTTP Version Not Supported",
  506: "Variant Also Negotiates",
  507: "Insufficient Storage",
  508: "Loop Detected",
  510: "Not Extended",
  511: "Network Authentication Required"
};
export const BUILDER_DESCRIPTION_MAP = {
  DOCKERFILE: {
    title: "Dockerfile",
    description: "Build your app using a Dockerfile"
  },
  STATIC_DIR: {
    title: "Static directory",
    description: "Deploy a simple HTML/CSS/JS website"
  },
  NIXPACKS: {
    title: "Nixpacks",
    description:
      "Automatically detect your stack and generate a Dockerfile for you"
  },
  RAILPACK: {
    title: "Railpack",
    description:
      "New and improved version of nixpacks with smaller image sizes, and faster builds"
  }
};

export const ZANE_DEPLOYMENT_HASH_HEADER = "x-zane-dpl-hash";
export const THEME_COOKIE_KEY = "__theme";
export const ZANE_UPDATE_TOAST_ID = "zaneops-update-toast";
