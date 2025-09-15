import { apiClient } from "./api/client";

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

export function timeAgoFormatter(
  dateInput: string | Date,
  short: boolean = false
): string {
  const date = new Date(dateInput);
  const now = new Date();
  const diffInSeconds = Math.floor((now.getTime() - date.getTime()) / 1000);

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
  const formatedValue = rtf.format(-value, unit);
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

  return timeAgoFormatter(date);
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

export function formatTimeValue(value: number) {
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
  return input.replace(/ /g, "\u00A0");
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
  stripEnd: boolean = true,
  stripStart: boolean = false
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
  let isDockerHubImage =
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
