import { type ClassValue, clsx } from "clsx";
import { twMerge } from "tailwind-merge";

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

export function getFormErrorsFromResponseData<
  T extends
    | {
        type: string;
        errors: ValidationErrorDetail[] | ClientErrorDetail[];
      }
    | undefined
>(
  data: T
): Record<
  T extends {
    type: "validation_error";
    errors: ValidationErrorDetail[];
  }
    ? T["errors"][number]["attr"]
    : T extends {
          type: "client_error";
          errors: ClientErrorDetail[];
        }
      ? "non_field_errors"
      : never,
  string[]
> {
  const errors: Record<string, string[]> = {};

  if (data?.type === "validation_error") {
    for (const error of data.errors) {
      const key = error.attr;
      if (key) {
        if (!errors[key]) {
          errors[key] = [];
        }
        errors[key].push(error.detail);
      }
    }
  } else if (data?.type === "client_error" || data?.type === "server_error") {
    errors["non_field_errors"] = data.errors.map((e) => e.detail);
  }

  return errors as any;
}
