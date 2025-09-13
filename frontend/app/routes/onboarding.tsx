import { AlertCircle, LoaderIcon } from "lucide-react";
import * as React from "react";
import { Form, redirect, useNavigation } from "react-router";
import { toast } from "sonner";
import { apiClient } from "~/api/client";
import { ThemedLogo } from "~/components/logo";
import { Alert, AlertDescription, AlertTitle } from "~/components/ui/alert";
import { SubmitButton } from "~/components/ui/button";
import { Input } from "~/components/ui/input";
import { userQueries } from "~/lib/queries";
import {
  type ErrorResponseFromAPI,
  getFormErrorsFromResponseData
} from "~/lib/utils";
import { queryClient } from "~/root";
import { getCsrfTokenHeader, metaTitle } from "~/utils";
import type { Route } from "./+types/onboarding";

export const meta: Route.MetaFunction = () => [metaTitle("Welcome to ZaneOps")];

export async function clientLoader({ request }: Route.ClientLoaderArgs) {
  const userExistQuery = await queryClient.ensureQueryData(
    userQueries.checkUserExistence
  );

  if (userExistQuery.data?.exists) {
    throw redirect("/login");
  }
  return;
}

export async function clientAction({ request }: Route.ClientActionArgs) {
  const formData = await request.formData();

  const credentials = {
    username: formData.get("username")!.toString(),
    password: formData.get("password")!.toString(),
    password_confirmation: formData.get("password_confirmation")!.toString()
  };

  if (credentials.password !== credentials.password_confirmation) {
    return {
      errors: {
        type: "validation_error",
        errors: [
          {
            attr: "password",
            detail: "Your passwords do not match",
            code: "validation_error"
          },
          {
            attr: "password_confirmation",
            detail: "Your passwords do not match",
            code: "validation_error"
          }
        ]
      } satisfies ErrorResponseFromAPI,
      userData: credentials
    };
  }

  const { error: errors, data } = await apiClient.POST(
    "/api/auth/create-initial-user/",
    {
      headers: {
        ...(await getCsrfTokenHeader())
      },
      body: credentials
    }
  );
  if (errors) {
    return {
      errors,
      userData: credentials
    };
  }

  queryClient.removeQueries(userQueries.checkUserExistence);
  queryClient.removeQueries(userQueries.authedUser);

  toast.success("Success", {
    description: data.detail,
    closeButton: true
  });

  throw redirect("/");
}

export default function InitialRegistration({
  actionData
}: Route.ComponentProps) {
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
      ) as HTMLInputElement;
      field?.focus();
    }
  }, [navigation.state, actionData]);

  return (
    <>
      <main className="h-[100vh] flex md:flex-col flex-col  justify-center items-center">
        <ThemedLogo />

        <div className="flex flex-col items-center">
          <h1 className="md:text-3xl text-4xl font-semibold">
            Welcome to ZaneOps
          </h1>
          <p className="text-sm text-grey">
            Your all-in-one platform for deploying your apps with ✨ zen ✨.
          </p>
        </div>

        <Form
          method="POST"
          ref={formRef}
          className="p-7 my-2 lg:px-32 md:px-20 md:w-[50%]  flex flex-col w-full"
        >
          <p className="my-2 text-lg text-grey">Let's setup your first user</p>
          <div className="card flex flex-col gap-3">
            {errors.non_field_errors && (
              <Alert variant="destructive">
                <AlertCircle className="h-4 w-4" />
                <AlertTitle>Error</AlertTitle>
                <AlertDescription>{errors.non_field_errors}</AlertDescription>
              </Alert>
            )}

            <div className="my-2 flex flex-col gap-1">
              <label htmlFor="username" className="">
                Username
              </label>
              <Input
                id="username"
                name="username"
                placeholder="ex: JohnDoe"
                defaultValue={actionData?.userData?.username}
                type="text"
                aria-describedby="username-error"
                aria-invalid={!!errors.username}
              />
              {errors.username && (
                <span id="username-error" className="text-red-500 text-sm">
                  {errors.username}
                </span>
              )}
            </div>

            <div className="flex flex-col gap-1">
              <label htmlFor="password">Password</label>
              <Input
                type="password"
                name="password"
                id="password"
                defaultValue={actionData?.userData?.password}
                aria-invalid={!!errors.password}
                aria-describedby="password-error"
              />
              {errors.password && (
                <span id="password-error" className="text-red-500 text-sm">
                  {errors.password}
                </span>
              )}
            </div>

            <div className="flex flex-col gap-1">
              <label htmlFor="password">Confirm your password</label>
              <Input
                type="password"
                name="password_confirmation"
                id="password_confirmation"
                defaultValue={actionData?.userData?.password_confirmation}
                aria-invalid={!!errors.password_confirmation}
                aria-describedby="password_confirmation-error"
              />
              {errors.password_confirmation && (
                <span
                  id="password_confirmation-error"
                  className="text-red-500 text-sm"
                >
                  {errors.password_confirmation}
                </span>
              )}
            </div>

            <SubmitButton
              className="lg:w-fit w-full lg:ml-auto p-3 rounded-lg gap-2"
              isPending={isPending}
            >
              {isPending ? (
                <>
                  <span>Creating...</span>
                  <LoaderIcon className="animate-spin" size={15} />
                </>
              ) : (
                "Create your first user"
              )}
            </SubmitButton>
          </div>
        </Form>
      </main>
    </>
  );
}
