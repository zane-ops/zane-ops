import { AlertCircle, LoaderIcon } from "lucide-react";
import React from "react";
import { redirect, useFetcher, useNavigation } from "react-router";
import { toast } from "sonner";
import { apiClient } from "~/api/client";
import { Alert, AlertDescription, AlertTitle } from "~/components/ui/alert";
import { Button, SubmitButton } from "~/components/ui/button";
import {
  FieldSet,
  FieldSetLabel,
  FieldSetPasswordToggleInput
} from "~/components/ui/fieldset";
import { Separator } from "~/components/ui/separator";
import { userQueries } from "~/lib/queries";
import {
  type ErrorResponseFromAPI,
  getFormErrorsFromResponseData
} from "~/lib/utils";
import { queryClient } from "~/root";
import { getCsrfTokenHeader, metaTitle } from "~/utils";
import type { Route } from "./+types/change-password";

export const meta: Route.MetaFunction = () => [metaTitle("Account Settings")];

export async function clientAction({ request }: Route.ClientActionArgs) {
  const formData = await request.formData();
  const intent = formData.get("intent")?.toString();

  switch (intent) {
    case "change_password":
      return changePassword(formData);
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

  toast.success("Password updated successfully");

  throw redirect("/settings/account");
}

export default function UserSettingsPage({}: Route.ComponentProps) {
  return (
    <section className="flex flex-col gap-4">
      <div className="flex items-center gap-4">
        <h2 className="text-2xl">Change Password</h2>
      </div>
      <Separator />

      <p className="text-gray">
        Update your account password. Make sure to use a strong password
      </p>

      <ChangePassword />
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

  return (
    <fetcher.Form
      method="POST"
      ref={formRef}
      className="space-y-6 animate-in fade-in duration-300 max-w-lg"
    >
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
        >
          <FieldSetLabel className="block">Current Password</FieldSetLabel>
          <FieldSetPasswordToggleInput
            placeholder="Enter your current password"
            label="Current Password"
          />
        </FieldSet>
        <FieldSet
          name="new_password"
          required
          errors={errors.new_password}
          className="space-y-2"
        >
          <FieldSetLabel className="block">New Password</FieldSetLabel>
          <FieldSetPasswordToggleInput
            placeholder="Enter your new password"
            label="New Password"
          />
        </FieldSet>

        <FieldSet
          name="confirm_password"
          required
          errors={errors.confirm_password}
          className="space-y-2"
        >
          <FieldSetLabel className="block">Confirm New Password</FieldSetLabel>
          <FieldSetPasswordToggleInput
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
          variant="secondary"
          size="sm"
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
  );
}
