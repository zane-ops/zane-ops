import { apiClient } from "./api/client";

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
  const formattedDate = new Intl.DateTimeFormat("en-US", {
    month: "short",
    day: "numeric",
    year: "numeric"
  }).format(date);

  return formattedDate;
}

export async function getCsrfTokenHeader() {
  await apiClient.GET("/api/csrf/");
  return { "X-CSRFToken": getCookie("csrftoken") };
}

export function timeAgoFormatter(dateInput: string | Date): string {
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

  const rtf = new Intl.RelativeTimeFormat("en", { numeric: "auto" });
  return rtf.format(-value, unit);
}
