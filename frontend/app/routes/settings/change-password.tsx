import { AlertCircle, LoaderIcon } from "lucide-react";
import { redirect, useFetcher } from "react-router";
import { toast } from "sonner";
import { apiClient } from "~/api/client";
import { Alert, AlertDescription, AlertTitle } from "~/components/ui/alert";
import { SubmitButton } from "~/components/ui/button";
import {
  FieldSet,
  FieldSetLabel,
  FieldSetPasswordToggleInput
} from "~/components/ui/fieldset";
import { Separator } from "~/components/ui/separator";
import { userQueries } from "~/lib/queries";
import { getFormErrorsFromResponseData } from "~/lib/utils";
import { queryClient } from "~/root";
import { getCsrfTokenHeader, metaTitle } from "~/utils";
import type { Route } from "./+types/change-password";

export const meta: Route.MetaFunction = () => [metaTitle("Account Settings")];

export async function clientAction({ request }: Route.ClientActionArgs) {
  const formData = await request.formData();
  const credentials = {
    current_password: formData.get("current_password")!.toString(),
    new_password: formData.get("new_password")!.toString(),
    confirm_password: formData.get("confirm_password")!.toString()
  } satisfies RequestInput<"post", "/api/auth/change-password/">;

  const { error: errors, data } = await apiClient.POST(
    "/api/auth/change-password/",
    {
      headers: await getCsrfTokenHeader(),
      body: credentials
    }
  );

  if (errors) return { errors };

  await queryClient.invalidateQueries(userQueries.authedUser);

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

      <ChangePasswordForm />
    </section>
  );
}

function ChangePasswordForm() {
  const fetcher = useFetcher<typeof clientAction>();
  const isPending =
  const isPending = fetcher.state != "idle";
  const errors = getFormErrorsFromResponseData(fetcher.data?.errors);

  return (
    <fetcher.Form method="POST" className="flex flex-col gap-6 max-w-lg">
      {errors.non_field_errors && (
        <Alert variant="destructive">
          <AlertCircle className="h-4 w-4" />
          <AlertTitle>Error</AlertTitle>
          <AlertDescription>{errors.non_field_errors}</AlertDescription>
        </Alert>
      )}
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
      <Separator />
      <div className="space-y-1 text-muted-foreground">
        <h3 className="font-medium">Hints for a good password</h3>
        <ul className="list-disc list-inside text-xs">
          <li>Use a mix of uppercase, lowercase, numbers, and symbols.</li>
          <li>Avoid using common passwords.</li>
          <li>Make it long and hard to guess.</li>
        </ul>
      </div>
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
      <SubmitButton
        isPending={isPending}
        variant="default"
        className="self-start"
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
    </fetcher.Form>
  );
}
