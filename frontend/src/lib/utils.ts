import { type ClassValue, clsx } from "clsx";
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

type Input =
  | { type: "validation_error"; errors: ValidationErrorDetail[] }
  | { type: "client_error"; errors: ClientErrorDetail[] }
  | { type: "server_error"; errors: ClientErrorDetail[] };

export function getFormErrorsFromResponseData<T extends Input>(
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
        if (keys.length === 0) {
          if (!errors[key]) {
            errors[key] = [];
          }
          errors[key].push(error.detail);
        } else {
          const [prefix, suffix] = keys;
          if (!errors[prefix]) {
            errors[prefix] = {
              [suffix]: []
            };
          }
          errors[prefix][suffix] = {
            ...errors[prefix],
            [suffix]: [...(errors[prefix][suffix] ?? []), error.detail]
          };
        }
      }
    }
  } else if (data?.type === "client_error" || data?.type === "server_error") {
    errors["non_field_errors"] = data.errors.map((e) => e.detail);
  }

  return errors as any;
}
