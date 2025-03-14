import { apiClient } from "./api/client";

/**
 * Truncates a string to a specified maximum length, adding an ellipsis if necessary.
 *
 * @param {string} text The string to truncate.
 * @param {number} maxLength The maximum length of the truncated string.
 * @returns {string} The truncated string.
 */
export function excerpt(text: string, maxLength: number): string {
  if (!text) return ""; // Handle null or undefined input
  if (text.length <= maxLength) {
    return text;
  }
  return text.substring(0, maxLength).trimEnd() + "...";
}

/**
 * Retrieves the value of a cookie by its name.
 *
 * @param {string} name The name of the cookie to retrieve.
 * @returns {string | null} The value of the cookie, or null if the cookie is not found.
 */
export function getCookie(name: string): string | null {
  if (typeof document === "undefined") return null; // Handle server-side rendering
  const cookieString = document.cookie;
  const cookies = cookieString.split("; ");

  for (const cookie of cookies) {
    const [cookieName, cookieValue] = cookie.split("=");
    if (cookieName === name) {
      try {
        return decodeURIComponent(cookieValue); // Decode the cookie value
      } catch (e) {
        console.error("Error decoding cookie:", e);
        return null; // Handle decoding errors
      }
    }
  }

  return null;
}

/**
 * Deletes a cookie by setting its expiration date to the past.
 *
 * @param {string} name The name of the cookie to delete.
 */
export function deleteCookie(name: string): void {
  if (typeof document === "undefined") return; // Handle server-side rendering

  document.cookie = `${name}=; Max-Age=0; Path=/; Secure; SameSite=Strict`;
}

/**
 * Formats a date as a string in the format "dd Mon yyyy".
 *
 * @param {string | Date} dateInput The date to format.
 * @returns {string} The formatted date string.
 */
export function formattedDate(dateInput: string | Date): string {
  const date = new Date(dateInput);
  if (isNaN(date.getTime())) {
    return "Invalid Date"; // Handle invalid date inputs
  }
  return new Intl.DateTimeFormat("en-GB", {
    month: "short",
    day: "numeric",
    year: "numeric",
  }).format(date);
}

/**
 * Formats a date and time as a string in the format "dd Mon yyyy, HH:mm:ss".
 *
 * @param {string | Date} dateInput The date and time to format.
 * @returns {string} The formatted date and time string.
 */
export function formattedTime(dateInput: string | Date): string {
  const date = new Date(dateInput);
  if (isNaN(date.getTime())) {
    return "Invalid Date"; // Handle invalid date inputs
  }
  return new Intl.DateTimeFormat("en-GB", {
    month: "short",
    hour: "numeric",
    minute: "numeric",
    second: "numeric",
    day: "numeric",
    year: "numeric",
  }).format(date);
}

/**
 * Retrieves the CSRF token from the cookie and returns it in a header object.
 *
 * @returns {Promise<{ "X-CSRFToken": string | null }>} A promise that resolves to an object containing the CSRF token header.
 */
export async function getCsrfTokenHeader(): Promise<{ "X-CSRFToken": string | null }> {
  try {
    await apiClient.GET("/api/csrf/");
    const csrfToken = getCookie("csrftoken");
    return { "X-CSRFToken": csrfToken };
  } catch (error) {
    console.error("Failed to retrieve CSRF token:", error);
    return { "X-CSRFToken": null }; // Return null if retrieval fails
  }
}

/**
 * Formats a date into a relative time string (e.g., "2 hours ago", "1 day ago").
 *
 * @param {string | Date} dateInput The date to format.
 * @param {boolean} [short=false] Whether to use a short style (e.g., "2h ago", "1d ago").
 * @returns {string} The formatted relative time string.
 */
export function timeAgoFormatter(
  dateInput: string | Date,
  short: boolean = false
): string {
  const date = new Date(dateInput);
  if (isNaN(date.getTime())) {
    return "Invalid Date"; // Handle invalid date inputs
  }
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
    style: short ? "narrow" : "long",
  });
  const formattedValue = rtf.format(-value, unit);
  return formattedValue === "now" ? "Just now" : formattedValue;
}

/**
 * Combines relative time formatting with absolute date formatting.  If the date is within the last week,
 * it will return a relative time string (e.g., "2 days ago").  Otherwise, it returns an absolute date string
 * (e.g., "1 Jan 2024").
 *
 * @param {string | Date} dateInput The date to format.
 * @returns {string} The formatted date string.
 */
export function mergeTimeAgoFormatterAndFormattedDate(
  dateInput: string | Date
): string {
  const date = new Date(dateInput);
  if (isNaN(date.getTime())) {
    return "Invalid Date"; // Handle invalid date inputs
  }
  const now = new Date();
  const diffInSeconds = Math.round((now.getTime() - date.getTime()) / 1000);

  const secondsInWeek = 7 * 24 * 3600;

  if (diffInSeconds > secondsInWeek) {
    return formattedDate(date);
  }

  return timeAgoFormatter(date);
}

/**
 * Formats a duration in seconds into a human-readable string (e.g., "1h 30min 15s").
 *
 * @param {number} seconds The duration in seconds.
 * @param {"short" | "long"} [notation="short"] Whether to use short notations (e.g., "s", "min", "h") or long notations (e.g., "seconds", "minutes", "hours").
 * @returns {string} The formatted duration string.
 */
export function formatElapsedTime(
  seconds: number,
  notation: "short" | "long" = "short"
): string {
  if (typeof seconds !== "number" || isNaN(seconds) || seconds < 0) {
    return "Invalid Input"; // Handle invalid input
  }

  const secondsInMinute = 60;
  const secondsInHour = 60 * secondsInMinute;
  const secondsInDay = 24 * secondsInHour;

  const NOTATIONS = {
    SECONDS: notation === "short" ? "s" : " seconds",
    MINUTES: notation === "short" ? "min" : " minutes",
    HOURS: notation === "short" ? "h" : " hours",
    DAYS: notation === "short" ? "d" : " days",
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

/**
 * Capitalizes the first letter of a string and converts the remaining letters to lowercase.
 *
 * @param {string} text The string to capitalize.
 * @returns {string} The capitalized string.
 */
export function capitalizeText(text: string): string {
  if (!text) return ""; // Handle null or empty input
  return text.charAt(0).toUpperCase() + text.substring(1).toLowerCase();
}

/**
 * Formats a URL based on a domain and base path.
 *
 * @param {{ domain: string; base_path?: string }} options The domain and base path to use.
 * @returns {string} The formatted URL.
 */
export function formatURL({
  domain,
  base_path = "/",
}: { domain: string; base_path?: string }): string {
  if (typeof window === "undefined") {
    return domain + base_path; // handle SSR
  }
  try {
    const currentUrl = new URL(window.location.href);
    return `${currentUrl.protocol}//${domain}${base_path}`;
  } catch (error) {
    console.error("Invalid URL:", error);
    return domain + base_path;
  }
}

/**
 * Pluralizes a word based on a count.
 *
 * @param {string} word The word to pluralize.
 * @param {number} itemCount The count to use for pluralization.
 * @returns {string} The pluralized word.
 */
export function pluralize(word: string, itemCount: number): string {
  return word + (itemCount !== 1 ? "s" : "");
}

/**
 * Asynchronously waits for a specified number of milliseconds.
 *
 * @param {number} ms The number of milliseconds to wait.
 * @returns {Promise<void>} A promise that resolves after the specified time has elapsed.
 */
export function wait(ms: number): Promise<void> {
  return new Promise((resolve) => setTimeout(resolve, ms));
}

/**
 * Type guard that checks if an array contains only numbers.
 *
 * @param {any} arr The array to check.
 * @returns {arr is number[]} True if the array contains only numbers, false otherwise.
 */
export function isArrayOfNumbers(arr: any): arr is number[] {
  return Array.isArray(arr) && arr.every((item) => typeof item === "number");
}

/**
 * Type guard that checks if an array contains only dates.
 *
 * @param {any} arr The array to check.
 * @returns {arr is Date[]} True if the array contains only dates, false otherwise.
 */
export function isArrayOfDates(arr: any): arr is Date[] {
  return Array.isArray(arr) && arr.every((item) => item instanceof Date);
}

/**
 * Type guard that checks if an array contains only strings.
 *
 * @param {any} arr The array to check.
 * @returns {arr is string[]} True if the array contains only strings, false otherwise.
 */
export function isArrayOfStrings(arr: any): arr is string[] {
  return Array.isArray(arr) && arr.every((item) => typeof item === "string");
}

/**
 * Type guard that checks if an array contains only booleans.
 *
 * @param {any} arr The array to check.
 * @returns {arr is boolean[]} True if the array contains only booleans, false otherwise.
 */
export function isArrayOfBooleans(arr: any): arr is boolean[] {
  return Array.isArray(arr) && arr.every((item) => typeof item === "boolean");
}

/**
 * Checks if an object is empty (i.e., contains no non-null or non-undefined values).
 *
 * @param {Record<string, any> | undefined | null} object The object to check.
 * @returns {boolean} True if the object is empty, false otherwise.
 */
export function isEmptyObject(
  object: Record<string, any> | undefined | null
): boolean {
  if (!object) return true;

  return !Object.values(object).some(
    (value) => value !== null && typeof value !== "undefined"
  );
}

/**
 * Formats a date for a specific time zone.
 *
 * @param {Date} date The date to format.
 * @param {string} timeZone The time zone to use.
 * @returns {string} The formatted date string.
 */
export function formatDateForTimeZone(date: Date, timeZone: string): string {
  if (!(date instanceof Date) || isNaN(date.getTime())) {
    return "Invalid Date"; // Handle invalid date inputs
  }
  try {
    return new Intl.DateTimeFormat("en-GB", {
      timeZone: timeZone,
      year: "numeric",
      month: "short",
      day: "2-digit",
      hour: "2-digit",
      minute: "2-digit",
      second: "2-digit",
      fractionalSecondDigits: 3,
    }).format(date);
  } catch (error) {
    console.error("Invalid timezone:", error);
    return "Invalid Timezone";
  }
}

/**
 * Creates a meta title string with the format "title | ZaneOps".
 *
 * @param {string} title The title to use.
 * @returns {{ readonly title: string }} An object containing the meta title.
 */
export function metaTitle(title: string): { readonly title: string } {
  return { title: `${title} | ZaneOps` } as const;
}

/**
 * Formats a storage value in bytes to a human-readable string with units (e.g., "1.23 GiB").
 *
 * @param {number} value The storage value in bytes.
 * @returns {{ value: string; unit: string }} An object containing the formatted value and unit.
 */
export function formatStorageValue(value: number): { value: string; unit: string } {
  if (typeof value !== "number" || isNaN(value) || value < 0) {
    return { value: "Invalid", unit: "bytes" }; // Handle invalid input
  }
  const kb = 1024;
  const mb = 1024 * kb;
  const gb = 1024 * mb;

  if (value < kb) {
    return { value: `${value}`, unit: "bytes" };
  }
  if (value < mb) {
    return {
      value: `${(value / kb).toFixed(2)}`,
      unit: `KiB`,
    };
  }
  if (value < gb) {
    return {
      value: `${(value / mb).toFixed(2)}`,
      unit: `MiB`,
    };
  }

  return {
    value: `${(value / gb).toFixed(2)}`,
    unit: `GiB`,
  };
}

/**
 * Converts a storage value from a given unit (BYTES, KILOBYTES, MEGABYTES, GIGABYTES) to bytes.
 *
 * @param {number} value The storage value to convert.
 * @param {"BYTES" | "KILOBYTES" | "MEGABYTES" | "GIGABYTES"} [unit="BYTES"] The unit of the input value.
 * @returns {number} The storage value in bytes.
 */
export function convertValueToBytes(
  value: number,
  unit: "BYTES" | "KILOBYTES" | "MEGABYTES" | "GIGABYTES" = "BYTES"
): number {
  if (typeof value !== "number" || isNaN(value)) {
    return 0; // Handle invalid input
  }
  switch (unit) {
    case "BYTES":
      return value;
    case "KILOBYTES":
      return value * 1024;
    case "MEGABYTES":
      return value * 1024 * 1024;
    case "GIGABYTES":
      return value * 1024 * 1024 * 1024;
    default:
      return value; // Default to bytes if unit is not recognized
  }
}

/**
 * Replaces spaces with non-breaking spaces ( ).
 *
 * @param {string} input The string to replace spaces in.
 * @returns {string} The string with spaces replaced by non-breaking spaces.
 */
export function spacesToNbsp(input: string): string {
  if (!input) return ""; // Handle null or empty input
  return input.replace(/ /g, "\u00A0");
}
