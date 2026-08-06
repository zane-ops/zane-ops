import { type ClassValue, clsx } from "clsx";
import { type ErrorResponse, isRouteErrorResponse } from "react-router";
import { twMerge } from "tailwind-merge";
import { apiClient } from "~/api/client";
import type {
  AuthedUserResponse,
  UserRole,
  WorkspaceInvitation,
  WorkspaceMember,
  WorkspaceMembership
} from "~/api/types";
import { WORKSPACE_ROLE_MAPPING } from "~/lib/constants";
import { createDevLogger } from "~/lib/logger";
import type {
  DotNotationToObject,
  MergeUnions,
  RecursivePartial
} from "~/lib/types";

const logger = createDevLogger(import.meta.url);

export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs));
}

type ValidationErrorDetail = {
  attr: "non_field_errors" | (string & {});
  code: string;
  detail: string;
};

type ClientErrorDetail = {
  code: string;
  detail: string;
  attr: string | null;
};

export type ErrorResponseFromAPI =
  | { type: "validation_error"; errors: ValidationErrorDetail[] }
  | { type: "client_error"; errors: ClientErrorDetail[] }
  | { type: "server_error"; errors: ClientErrorDetail[] };

export function getFormErrorsFromResponseData<T extends ErrorResponseFromAPI>(
  data: T | undefined
): MergeUnions<
  T extends { type: "validation_error"; errors: ValidationErrorDetail[] }
    ? RecursivePartial<
        DotNotationToObject<T["errors"][number]["attr"], string[]>
      >
    : T extends
          | { type: "client_error"; errors: ClientErrorDetail[] }
          | { type: "server_error"; errors: ClientErrorDetail[] }
      ? { non_field_errors?: string[] }
      : never
> {
  const errors: any = {};

  if (data?.type === "validation_error") {
    for (const error of data.errors) {
      const key = error.attr;
      if (key) {
        const keys = key.split(".");
        if (keys.length === 1) {
          if (!errors[key]) {
            errors[key] = [];
          }
          errors[key].push(error.detail);
        } else {
          let prefix = keys.shift();
          let root: Record<string, any> | null = null;
          if (prefix !== undefined) {
            if (!errors[prefix]) {
              errors[prefix] = {};
            }
            root = errors[prefix];
          }
          while (prefix !== undefined && root !== null) {
            prefix = keys.shift();

            if (prefix !== undefined) {
              if (keys.length > 0) {
                if (!root[prefix]) {
                  root[prefix] = {};
                }
                root = root[prefix];
              } else {
                root[prefix] = [...(root[prefix] ?? []), error.detail];
              }
            }
          }
        }
      }
    }
  } else if (data?.type === "client_error" || data?.type === "server_error") {
    errors["non_field_errors"] = data.errors.map((e) => e.detail);
  }

  return errors as any;
}

export function notFound(message = "Not Found") {
  return new Response(message, { status: 404, statusText: message });
}

export function isNotFoundError(error: unknown): error is ErrorResponse {
  return isRouteErrorResponse(error) && error.status === 404;
}

export function formatLogTime(time: string | Date) {
  const date = new Date(time);
  const now = new Date();
  const userTimeZone = Intl.DateTimeFormat().resolvedOptions().timeZone;

  const dateFormat = new Intl.DateTimeFormat("en-GB", {
    month: "short",
    day: "numeric",
    timeZone: userTimeZone,
    year: date.getFullYear() === now.getFullYear() ? undefined : "numeric"
  })
    .format(date)
    .replaceAll(".", "");

  const hourFormat = new Intl.DateTimeFormat("en-GB", {
    hour: "numeric",
    minute: "numeric",
    second: "numeric",
    timeZone: userTimeZone
  }).format(date);

  return { dateFormat, hourFormat };
}

export function calculateDuration(
  dateBegin: Date | string,
  dateEnd: Date | string
) {
  const begin = new Date(dateBegin);
  const end = new Date(dateEnd);

  let totalSeconds = Math.floor((end.getTime() - begin.getTime()) / 1000);

  const SECONDS_IN_MINUTE = 60;
  const SECONDS_IN_HOUR = 60 * SECONDS_IN_MINUTE;
  const SECONDS_IN_DAY = 24 * SECONDS_IN_HOUR;
  const SECONDS_IN_YEAR = 365 * SECONDS_IN_DAY;

  const years = Math.floor(totalSeconds / SECONDS_IN_YEAR);
  totalSeconds -= years * SECONDS_IN_YEAR;

  const days = Math.floor(totalSeconds / SECONDS_IN_DAY);
  totalSeconds -= days * SECONDS_IN_DAY;

  const hours = Math.floor(totalSeconds / SECONDS_IN_HOUR);
  totalSeconds -= hours * SECONDS_IN_HOUR;

  const minutes = Math.floor(totalSeconds / SECONDS_IN_MINUTE);
  totalSeconds -= minutes * SECONDS_IN_MINUTE;

  const seconds = totalSeconds;

  return { years, days, hours, minutes, seconds };
}

export function excerpt(text: string, maxLength: number): string {
  if (text.length <= maxLength) {
    return text;
  }
  return text.substring(0, maxLength).trimEnd() + "...";
}

/**
 * Get the value of a cookie with the given name.
 * @example
 *      getCookie('name');
 *      // => "value"
 * @param name
 * @returns
 */
export function getCookie(name: string): string | null {
  const value = `; ${document.cookie}`;
  const parts = value.split(`; ${name}=`);
  if (parts.length === 2) {
    return parts.pop()?.split(";").shift() ?? null;
  }
  return null;
}

export function setCookie(
  name: string,
  value: string,
  days?: number,
  options: {
    path?: string;
    secure?: boolean;
    sameSite?: "Strict" | "Lax" | "None";
  } = {}
): void {
  let cookie = `${encodeURIComponent(name)}=${encodeURIComponent(value)}`;

  if (days) {
    const date = new Date();
    date.setTime(date.getTime() + days * 864e5);
    cookie += `; expires=${date.toUTCString()}`;
  }

  cookie += `; path=${options.path ?? "/"}`;

  if (options.secure) cookie += "; Secure";
  if (options.sameSite) cookie += `; SameSite=${options.sameSite}`;

  document.cookie = cookie;
}

/**
 *  Remove a cookie with the given name.
 * @param name
 */
export function deleteCookie(name: string): void {
  // Delete the cookie by setting the expiration date in the past
  document.cookie = `${name}=; expires=Thu, 01 Jan 1970 00:00:00 UTC; path=/;`;
}

export function formattedDate(dateInput: string | Date): string {
  const date = new Date(dateInput);
  const formattedDate = new Intl.DateTimeFormat("en-GB", {
    month: "short",
    day: "numeric",
    year: "numeric"
  }).format(date);

  return formattedDate;
}

export function formattedTime(dateInput: string | Date): string {
  const date = new Date(dateInput);
  const formattedDate = new Intl.DateTimeFormat("en-GB", {
    month: "short",
    hour: "numeric",
    minute: "numeric",
    second: "numeric",
    day: "numeric",
    year: "numeric"
  }).format(date);

  return formattedDate;
}

export async function getCsrfTokenHeader() {
  await apiClient.GET("/api/csrf/");
  return { "X-CSRFToken": getCookie("csrftoken") };
}

export function relativeTimeFormatter(
  dateInput: string | Date,
  short = false,
  direction: "past" | "future" = "past"
): string {
  const date = new Date(dateInput);
  const now = new Date();
  const diffInSeconds = Math.abs(
    Math.floor((now.getTime() - date.getTime()) / 1000)
  );

  const secondsInMinute = 60;
  const secondsInHour = 60 * secondsInMinute;
  const secondsInDay = 24 * secondsInHour;
  const secondsInWeek = 7 * secondsInDay;
  const secondsInMonth = 30 * secondsInDay;
  const secondsInYear = 365 * secondsInDay;

  let value: number;
  let unit: Intl.RelativeTimeFormatUnit;

  if (diffInSeconds < secondsInMinute) {
    value = diffInSeconds;
    unit = "second";
  } else if (diffInSeconds < secondsInHour) {
    value = Math.floor(diffInSeconds / secondsInMinute);
    unit = "minute";
  } else if (diffInSeconds < secondsInDay) {
    value = Math.floor(diffInSeconds / secondsInHour);
    unit = "hour";
  } else if (diffInSeconds < secondsInWeek) {
    value = Math.floor(diffInSeconds / secondsInDay);
    unit = "day";
  } else if (diffInSeconds < secondsInMonth) {
    value = Math.floor(diffInSeconds / secondsInWeek);
    unit = "week";
  } else if (diffInSeconds < secondsInYear) {
    value = Math.floor(diffInSeconds / secondsInMonth);
    unit = "month";
  } else {
    value = Math.floor(diffInSeconds / secondsInYear);
    unit = "year";
  }

  const rtf = new Intl.RelativeTimeFormat("en", {
    numeric: "auto",
    style: short ? "narrow" : "long"
  });
  const formatedValue = rtf.format(
    direction === "past" ? -value : +value,
    unit
  );
  return formatedValue === "now" ? "Just now" : formatedValue;
}

export function mergeTimeAgoFormatterAndFormattedDate(
  dateInput: string | Date
): string {
  const date = new Date(dateInput);
  const now = new Date();
  const diffInSeconds = Math.round((now.getTime() - date.getTime()) / 1000);

  const secondsInWeek = 7 * 24 * 3600;

  if (diffInSeconds > secondsInWeek) {
    return formattedDate(date);
  }

  return relativeTimeFormatter(date);
}

export function formatElapsedTime(
  seconds: number,
  notation: "short" | "long" = "short"
) {
  const secondsInMinute = 60;
  const secondsInHour = 60 * secondsInMinute;
  const secondsInDay = 24 * secondsInHour;

  const NOTATIONS = {
    SECONDS: notation === "short" ? "s" : " seconds",
    MINUTES: notation === "short" ? "min" : " minutes",
    HOURS: notation === "short" ? "h" : " hours",
    DAYS: notation === "short" ? "d" : " days"
  };

  if (seconds < secondsInMinute) {
    return `${seconds}${NOTATIONS.SECONDS}`;
  }
  if (seconds < secondsInHour) {
    const secondsLeftInMinute = seconds % secondsInMinute;
    return `${Math.floor(seconds / secondsInMinute)}${NOTATIONS.MINUTES} ${secondsLeftInMinute}${NOTATIONS.SECONDS}`;
  }
  if (seconds < secondsInDay) {
    const hours = Math.floor(seconds / secondsInHour);
    const minutes = Math.floor((seconds % secondsInHour) / secondsInMinute);
    const secondsLeft = seconds % secondsInMinute;
    return `${hours}${NOTATIONS.HOURS} ${minutes}${NOTATIONS.MINUTES} ${secondsLeft}${NOTATIONS.SECONDS}`;
  }

  const days = Math.floor(seconds / secondsInDay);
  const hours = Math.floor((seconds % secondsInDay) / secondsInHour);
  const minutes = Math.floor((seconds % secondsInHour) / secondsInMinute);
  const secondsLeft = seconds % secondsInMinute;

  return `${days}${NOTATIONS.DAYS} ${hours}${NOTATIONS.HOURS} ${minutes}${NOTATIONS.MINUTES} ${secondsLeft}${NOTATIONS.SECONDS}`;
}

export function capitalizeText(text: string): string {
  return text.charAt(0).toUpperCase() + text.substring(1).toLowerCase();
}

export function formatURL({
  domain,
  base_path = "/"
}: { domain: string; base_path?: string }) {
  const currentUrl = new URL(window.location.href);
  return `${currentUrl.protocol}//${domain}${base_path}`;
}

/**
 * Turn an app-relative path into a shareable absolute URL on the current origin.
 *
 * ex: `getAbsoluteURL(href("/invite/:token", { token }))`
 *      -> `https://zaneops.dev/invite/gh1234`
 */
export function getLocalAbsoluteURL(path: string) {
  return new URL(path, window.location.origin).toString();
}

export function pluralize(word: string, item_count: number) {
  return word + (item_count > 1 ? "s" : "");
}

export function wait(ms: number): Promise<void> {
  // Wait for the specified amount of time
  return new Promise((resolve) => setTimeout(resolve, ms));
}

export function isArrayOfNumbers(arr: any): arr is number[] {
  if (!Array.isArray(arr)) return false;
  return arr.every((item) => typeof item === "number");
}

export function isArrayOfDates(arr: any): arr is Date[] {
  if (!Array.isArray(arr)) return false;
  return arr.every((item) => item instanceof Date);
}

export function isArrayOfStrings(arr: any): arr is string[] {
  if (!Array.isArray(arr)) return false;
  return arr.every((item) => typeof item === "string");
}

export function isArrayOfBooleans(arr: any): arr is boolean[] {
  if (!Array.isArray(arr)) return false;
  return arr.every((item) => typeof item === "boolean");
}

export function isEmptyObject(object: Record<string, any> | undefined | null) {
  if (object === null || typeof object === "undefined") return true;

  return !Object.entries(object).some(
    ([, value]) => value !== null && typeof value !== "undefined"
  );
}

export function formatDateForTimeZone(date: Date, timeZone: string) {
  return new Intl.DateTimeFormat("en-GB", {
    timeZone: timeZone,
    year: "numeric",
    month: "short",
    day: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
    second: "2-digit",
    fractionalSecondDigits: 3
  }).format(date);
}

export function metaTitle(title: string) {
  return { title: `${title} | ZaneOps` } as const;
}

export function formatStorageValue(value: number) {
  const kb = 1024;
  const mb = 1024 * kb;
  const gb = 1024 * mb;

  if (value < kb) {
    return { value: `${value}`, unit: "bytes" };
  }
  if (value < mb) {
    return {
      value: `${(value / kb).toFixed(2)}`,
      unit: `KiB`
    };
  }
  if (value < gb) {
    return {
      value: `${(value / mb).toFixed(2)}`,
      unit: `MiB`
    };
  }

  return {
    value: `${(value / gb).toFixed(2)}`,
    unit: `GiB`
  };
}

export function formatDuration(value: number) {
  const ms = 1;
  const sec = 1000 * ms;
  const min = 60 * sec;
  const hr = 60 * min;
  const day = 24 * hr;
  const week = 7 * day;

  if (value < sec) {
    return { value: value, unit: "ms" };
  }
  if (value < min) {
    return {
      value: value / sec,
      unit: "s"
    };
  }
  if (value < hr) {
    return {
      value: value / min,
      unit: "min"
    };
  }
  if (value < day) {
    return {
      value: value / hr,
      unit: "h"
    };
  }
  if (value < week) {
    return {
      value: value / day,
      unit: "d"
    };
  }
  return {
    value: value / week,
    unit: "w"
  };
}

export function convertValueToBytes(
  value: number,
  unit: "BYTES" | "KILOBYTES" | "MEGABYTES" | "GIGABYTES" = "BYTES"
): number {
  switch (unit) {
    case "BYTES":
      return value;
    case "KILOBYTES":
      return value * 1024;
    case "MEGABYTES":
      return value * 1024 * 1024;
    case "GIGABYTES":
      return value * 1024 * 1024 * 1024;
  }
}

export function spacesToNbsp(input: string) {
  return input.replace(/ /g, " ");
}

export function durationToMs(
  value: number,
  unit: "seconds" | "minutes" | "hours" | "days" | "weeks"
): number {
  const multipliers = {
    seconds: 1000,
    minutes: 60 * 1000,
    hours: 60 * 60 * 1000,
    days: 24 * 60 * 60 * 1000,
    weeks: 7 * 24 * 60 * 60 * 1000
  };
  return value * multipliers[unit];
}

export function stripSlashIfExists(
  url: string,
  stripEnd = true,
  stripStart = false
): string {
  let finalUrl: string = url;
  if (stripEnd && url.endsWith("/")) {
    finalUrl = finalUrl.substring(0, finalUrl.length - 1);
  }
  if (stripStart && url.startsWith("/")) {
    finalUrl = finalUrl.substring(1);
  }
  return finalUrl;
}

export function getDockerImageIconURL(image: string) {
  let iconSrc: string | null = null;

  const imageWithoutTag = image.split(":")[0];
  const isDockerHubImage =
    !imageWithoutTag.startsWith("ghcr.io") && !imageWithoutTag.includes(".");

  if (imageWithoutTag.startsWith("ghcr.io")) {
    // GitHub Container Registry: use GitHub username as avatar
    const fullImage = imageWithoutTag.split("/");
    const username = fullImage[1];
    iconSrc = `https://github.com/${username}.png`;
  } else if (isDockerHubImage) {
    // use our custom API which also caches the icons both in DB & in cloudflare
    iconSrc = `https://zaneops.dev/icons/${imageWithoutTag}.png`;
  }
  // Other registries are ignored
  return iconSrc;
}

const AVAILABLE_COLORS = [
  "blue",
  "emerald",
  "violet",
  "orange",
  "pink",
  "teal",
  "amber",
  "indigo",
  "green",
  "red",
  "cyan",
  "purple",
  "lime",
  "rose",
  "sky",
  "fuchsia"
];

export function stringToColor(str: string): {
  light: string;
  dark: string;
} {
  let hash = 0;
  for (let i = 0; i < str.length; i++) {
    hash = str.charCodeAt(i) + ((hash << 5) - hash);
  }
  const color = AVAILABLE_COLORS[Math.abs(hash) % AVAILABLE_COLORS.length];
  return {
    light: `var(--color-${color}-700)`,
    dark: `var(--color-${color}-400)`
  };
}

export function getMaxDomainForStorageValue(maxValueInBytes: number) {
  const _100Kb = convertValueToBytes(100, "KILOBYTES");
  const _10Mb = convertValueToBytes(10, "MEGABYTES");
  const _100Mb = convertValueToBytes(100, "MEGABYTES");
  const _500Mb = convertValueToBytes(500, "MEGABYTES");
  const _1GB = convertValueToBytes(1, "GIGABYTES");

  return (
    maxValueInBytes +
    (maxValueInBytes > _1GB
      ? _1GB
      : maxValueInBytes > _500Mb
        ? _500Mb
        : maxValueInBytes > _100Mb
          ? _100Mb
          : maxValueInBytes > _10Mb
            ? _10Mb
            : _100Kb)
  );
}

export type UserWithMembership =
  | AuthedUserResponse
  | WorkspaceMembership
  | WorkspaceMember
  | WorkspaceInvitation;

export function hasMinRole(
  user: UserWithMembership,
  roleName: UserRole
): boolean {
  if (roleName === "ServerAdmin") {
    return (
      "user" in user &&
      "is_superuser" in user.user &&
      Boolean(user.user?.is_superuser)
    );
  }

  const membership = "membership" in user ? user.membership : user;

  const hasRole = Boolean(
    membership && membership.role >= WORKSPACE_ROLE_MAPPING[roleName].value
  );

  logger.info({
    membership,
    roleName,
    hasRole
  });

  return hasRole;
}

export function getUserDisplayName(
  user: Pick<AuthedUserResponse["user"], "first_name" | "username">
) {
  return user.first_name.trim() ? user.first_name : user.username;
}

export function isEditableTarget(target: EventTarget | null) {
  if (!(target instanceof HTMLElement)) return false;
  if (target.isContentEditable) return true;
  const tagName = target.tagName;
  return ["input", "textarea", "select"].includes(tagName.toLowerCase());
}
