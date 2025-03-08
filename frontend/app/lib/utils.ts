import { type ClassValue, clsx } from "clsx";
import { type ErrorResponse, isRouteErrorResponse } from "react-router";
import { twMerge } from "tailwind-merge";
import type {
  DotNotationToObject,
  MergeUnions,
  RecursivePartial
} from "~/lib/types";

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

export function notFound(message: string = "Not Found") {
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
