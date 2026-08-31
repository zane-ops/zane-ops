import { useQuery } from "@tanstack/react-query";
import { AlertCircleIcon, LoaderIcon } from "lucide-react";
import React from "react";
import {
  Form,
  href,
  redirect,
  useActionData,
  useNavigation
} from "react-router";
import { toast } from "sonner";
import { type RequestInput, apiClient } from "~/api/client";
import { ThemedLogo } from "~/components/logo";
import { Alert, AlertDescription, AlertTitle } from "~/components/ui/alert";
import { SubmitButton } from "~/components/ui/button";
import {
  FieldSet,
  FieldSetLabel,
  FieldSetPasswordToggleInput
} from "~/components/ui/fieldset";
import { createDevLogger } from "~/lib/logger";
import { userQueries } from "~/lib/queries";
import { getQueryClient } from "~/lib/query-client";
import {
  type ErrorResponseFromAPI,
  cn,
  getCsrfTokenHeader,
  getFormErrorsFromResponseData,
  metaTitle,
  notFound
} from "~/lib/utils";
import type { Route } from "./+types/reset-password";

export function meta() {
  return [
    metaTitle("Reset your password")
  ] satisfies ReturnType<Route.MetaFunction>;
}

const logger = createDevLogger(import.meta.url);

export async function clientLoader({ params }: Route.ClientLoaderArgs) {
  const queryClient = getQueryClient();

  const [token, authedUser] = await Promise.all([
    queryClient.fetchQuery(userQueries.passwordResetToken(params.token)),
    queryClient.ensureQueryData(userQueries.authedUser)
  ]);

  // if a user is already logged in, sending them here is a mistake
  if (authedUser) {
    logger.info("redirect to `/` (already authenticated)");
    throw notFound("Invalid or expired password reset link.");
  }

  return { token };
}

export async function clientAction({
  request,
  params
}: Route.ClientActionArgs) {
  const formData = await request.formData();

  const userData = {
    new_password: formData.get("new_password")?.toString() ?? "",
    confirm_password: formData.get("confirm_password")?.toString() ?? ""
  } satisfies RequestInput<"post", "/api/auth/reset-password/{token}/">;

  if (userData.new_password !== userData.confirm_password) {
    return {
      errors: {
        type: "validation_error",
        errors: [
          {
            attr: "confirm_password",
            detail: "Passwords do not match",
            code: "validation_error"
          }
        ]
      } satisfies ErrorResponseFromAPI,
      userData
    };
  }

  const { error: errors } = await apiClient.POST(
    "/api/auth/reset-password/{token}/",
    {
      headers: {
        ...(await getCsrfTokenHeader())
      },
      params: {
        path: { token: params.token }
      },
      body: userData
    }
  );

  if (errors) {
    return { errors, userData };
  }

  getQueryClient().removeQueries(userQueries.passwordResetToken(params.token));

  toast.success("Success", {
    description: "Your password has been updated, you can now log in.",
    closeButton: true
  });

  throw redirect(href("/login"));
}

export default function ResetPasswordPage({
  loaderData,
  params
}: Route.ComponentProps) {
  useQuery({
    ...userQueries.passwordResetToken(params.token),
    initialData: loaderData.token
  });

  return (
    <main
      className={cn(
        "h-[100vh] container p-6",
        "flex flex-col justify-center items-center"
      )}
    >
      <ThemedLogo />
      <div className="flex flex-col items-center">
        <h1 className="md:text-3xl text-4xl font-semibold">
          Reset your password
        </h1>
        <p className="text-sm text-grey">
          Choose a new password for your account
        </p>
      </div>

      <ResetPasswordForm />
    </main>
  );
}

function ResetPasswordForm() {
  const actionData = useActionData<Route.ComponentProps["actionData"]>();
  const navigation = useNavigation();

  const isPending =
    navigation.state === "loading" || navigation.state === "submitting";

  const formRef = React.useRef<React.ComponentRef<"form">>(null);
  const errors = getFormErrorsFromResponseData(actionData?.errors);

  React.useEffect(() => {
    if (navigation.state === "idle" && actionData?.errors) {
      const errors = getFormErrorsFromResponseData(actionData?.errors);
      const key = Object.keys(errors ?? {})[0];
      const field = formRef.current?.elements.namedItem(
        key
      ) as HTMLInputElement | null;
      field?.focus();
    }
  }, [navigation.state, actionData]);

  return (
    <Form
      method="POST"
      ref={formRef}
      className="p-7 my-2 lg:px-32 md:px-20 md:w-2/3 xl:md:w-1/2 flex flex-col w-full gap-4"
    >
      {errors.non_field_errors && (
        <Alert variant="destructive">
          <AlertCircleIcon className="h-4 w-4" />
          <AlertTitle>Error</AlertTitle>
          <AlertDescription>{errors.non_field_errors}</AlertDescription>
        </Alert>
      )}

      <div className="flex flex-col gap-1 text-muted-foreground">
        <h3 className="font-medium text-sm">Hints for a good password</h3>
        <ul className="list-disc list-inside text-xs">
          <li>Use a mix of uppercase, lowercase, numbers, and symbols.</li>
          <li>Avoid using common passwords.</li>
          <li>Make it long and hard to guess.</li>
        </ul>
      </div>

      <FieldSet
        errors={errors.new_password}
        name="new_password"
        required
        className="flex flex-col gap-1"
      >
        <FieldSetLabel>New password</FieldSetLabel>
        <FieldSetPasswordToggleInput autoFocus />
      </FieldSet>

      <FieldSet
        errors={errors.confirm_password}
        name="confirm_password"
        required
        className="flex flex-col gap-1"
      >
        <FieldSetLabel>Confirm your new password</FieldSetLabel>
        <FieldSetPasswordToggleInput />
      </FieldSet>

      <SubmitButton
        className="lg:w-fit w-full lg:ml-auto p-3 rounded-lg gap-2"
        isPending={isPending}
      >
        {isPending ? (
          <>
            <span>Updating...</span>
            <LoaderIcon className="animate-spin" size={15} />
          </>
        ) : (
          "Reset password"
        )}
      </SubmitButton>
    </Form>
  );
}
