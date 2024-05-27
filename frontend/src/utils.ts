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

function getMonthName(monthNumber: number) {
  const monthNames = [
    "Jan",
    "Feb",
    "Mar",
    "Apr",
    "May",
    "Jun",
    "Jul",
    "Aug",
    "Sep",
    "Oct",
    "Nov",
    "Dec",
  ];
  return monthNames[monthNumber - 1];
}

export function formatedDate(x: string) {
  const date = new Date(x);
  const year = date.getFullYear();
  const month = getMonthName(date.getMonth());
  const day = date.getDate();
  return `${month} ${day}, ${year}`;
}
