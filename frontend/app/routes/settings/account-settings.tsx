import { AlertCircle, KeyIcon, LoaderIcon } from "lucide-react";
import React from "react";
import { useFetcher, useNavigation } from "react-router";
import { apiClient } from "~/api/client";
import { PasswordStrengthIndicator } from "~/components/password-strength-indicator";
import { Alert, AlertDescription, AlertTitle } from "~/components/ui/alert";
import { Button, SubmitButton } from "~/components/ui/button";
import {
  FieldSet,
  FieldSetHidableInput,
  FieldSetLabel
} from "~/components/ui/fieldset";
import { Separator } from "~/components/ui/separator";
import { userQueries } from "~/lib/queries";
import {
  type ErrorResponseFromAPI,
  getFormErrorsFromResponseData
} from "~/lib/utils";
import { queryClient } from "~/root";
import { getCsrfTokenHeader, metaTitle } from "~/utils";
import type { Route } from "./+types/account-settings";

export const meta: Route.MetaFunction = () => [metaTitle("Account Settings")];

export async function clientAction({ request }: Route.ClientActionArgs) {
  const formData = await request.formData();
  const intent = formData.get("intent")?.toString();

  switch (intent) {
    case "change_password": {
      return changePassword(formData);
    }
    default: {
      throw new Error("Unexpected intent");
    }
  }
}

async function changePassword(formData: FormData) {
  const credentials = {
    current_password: formData.get("current_password")!.toString(),
    new_password: formData.get("new_password")!.toString(),
    confirm_password: formData.get("confirm_password")!.toString()
  };

  if (credentials.new_password !== credentials.confirm_password) {
    return {
      success: false,
      errors: {
        type: "validation_error",
        errors: [
          {
            attr: "confirm_password",
            code: "validation_error",
            detail: "Your passwords do not match"
          }
        ]
      } satisfies ErrorResponseFromAPI
    };
  }

  const { error: errors, data } = await apiClient.POST(
    "/api/auth/change-password/",
    {
      headers: await getCsrfTokenHeader(),
      body: credentials
    }
  );

  if (errors) return { success: false, errors };

  queryClient.removeQueries(userQueries.authedUser);

  return {
    success: true,
    message: data.message,
    values: {
      current_password: "",
      new_password: "",
      confirm_password: ""
    }
  };
}

export default function UserSettingsPage({}: Route.ComponentProps) {
  return (
    <section className="flex flex-col gap-4">
      <div className="flex items-center gap-4">
        <h2 className="text-2xl">Profile</h2>
      </div>
      <Separator />
      <p className="text-grey">Update your profile information</p>
      <div className="grid lg:grid-cols-12 gap-10 relative">
        <div className="lg:col-span-10 flex flex-col">
          <section id="update-password" className="flex gap-1 scroll-mt-20">
            <div className="w-16 hidden md:flex flex-col items-center">
              <div className="flex rounded-full size-10 flex-none items-center justify-center p-1 border-2 border-grey/50">
                <KeyIcon size={15} className="flex-none text-grey" />
              </div>
              {/* <div className="h-full border border-grey/50"></div> */}
            </div>
            <div className="w-full flex flex-col gap-5 pt-1 pb-8">
              <div className="mb-3">
                <h1 className="text-2xl font-bold mb-2">Change Password</h1>
                <p className="text-muted-foreground">
                  Update your account password. Make sure to use a strong
                  password that you haven't used before.
                </p>
              </div>
              <ChangePassword />
            </div>
          </section>
        </div>
      </div>
    </section>
  );
}

function ChangePassword() {
  const navigation = useNavigation();
  const fetcher = useFetcher<typeof clientAction>();
  const isPending =
    navigation.state === "loading" || navigation.state === "submitting";
  const errors = getFormErrorsFromResponseData(fetcher.data?.errors);

  const formRef = React.useRef<React.ComponentRef<"form">>(null);
  const [isExpanded, setIsExpanded] = React.useState(false);
  const [newPassword, setNewPassword] = React.useState("");

  React.useEffect(() => {
    if (fetcher.state === "idle" && fetcher.data?.success) {
      formRef.current?.reset();
      setIsExpanded(false);
      setNewPassword("");
    }
  }, [fetcher.state, fetcher.data]);

  return (
    <div className="space-y-6 animate-in fade-in duration-300">
      {fetcher.data?.success && (
        <Alert className="border-green-500 bg-green-50 dark:bg-green-950">
          <AlertCircle className="h-4 w-4 text-green-600" />
          <AlertTitle className="text-green-800 dark:text-green-200">
            Success
          </AlertTitle>
          <AlertDescription className="text-green-700 dark:text-green-300">
            {fetcher.data.message}
          </AlertDescription>
        </Alert>
      )}
      {!isExpanded ? (
        <div>
          <Button onClick={() => setIsExpanded(true)}>Change Password</Button>
        </div>
      ) : (
        <fetcher.Form method="POST" ref={formRef} className="space-y-6">
          {errors.non_field_errors && (
            <Alert variant="destructive">
              <AlertCircle className="h-4 w-4" />
              <AlertTitle>Error</AlertTitle>
              <AlertDescription>{errors.non_field_errors}</AlertDescription>
            </Alert>
          )}

          <div className="space-y-4">
            <FieldSet
              name="current_password"
              required
              errors={errors.current_password}
              className="space-y-2"
              defaultValue={fetcher.data?.values?.current_password as string}
            >
              <FieldSetLabel className="block">Current Password</FieldSetLabel>
              <FieldSetHidableInput
                placeholder="Enter your current password"
                label="Current Password"
              />
            </FieldSet>
            <FieldSet
              name="new_password"
              required
              errors={errors.new_password}
              className="space-y-2"
              defaultValue={fetcher.data?.values?.new_password as string}
            >
              <FieldSetLabel className="block">New Password</FieldSetLabel>
              <FieldSetHidableInput
                placeholder="Enter your new password"
                label="New Password"
                onChange={(ev) => setNewPassword(ev.currentTarget.value)}
              />
            </FieldSet>

            <PasswordStrengthIndicator
              password={newPassword}
              className="mt-3"
            />

            <FieldSet
              name="confirm_password"
              required
              errors={errors.confirm_password}
              className="space-y-2"
              defaultValue={fetcher.data?.values?.confirm_password as string}
            >
              <FieldSetLabel className="block">
                Confirm New Password
              </FieldSetLabel>
              <FieldSetHidableInput
                placeholder="Confirm your new password"
                label="Confirm Password"
              />
            </FieldSet>
          </div>

          <div className="flex gap-4">
            <SubmitButton
              isPending={isPending}
              name="intent"
              value="change_password"
              className="flex-1"
            >
              {isPending ? (
                <>
                  <span>Changing Password...</span>
                  <LoaderIcon className="animate-spin" size={15} />
                </>
              ) : (
                "Change Password"
              )}
            </SubmitButton>
          </div>
        </fetcher.Form>
      )}
    </div>
  );
}
