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
