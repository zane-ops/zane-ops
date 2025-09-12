import { useQuery } from "@tanstack/react-query";
import {
  AlertCircle,
  ChevronRight,
  ExternalLinkIcon,
  KeyIcon,
  LoaderIcon,
  UserIcon
} from "lucide-react";
import { Link, useFetcher, useNavigation } from "react-router";
import { toast } from "sonner";
import { apiClient } from "~/api/client";
import { Alert, AlertDescription, AlertTitle } from "~/components/ui/alert";
import { SubmitButton, buttonVariants } from "~/components/ui/button";
import {
  FieldSet,
  FieldSetInput,
  FieldSetLabel
} from "~/components/ui/fieldset";
import { Separator } from "~/components/ui/separator";
import { userQueries } from "~/lib/queries";
import { cn, getFormErrorsFromResponseData } from "~/lib/utils";
import { queryClient } from "~/root";
import { getCsrfTokenHeader, metaTitle } from "~/utils";
import type { Route } from "./+types/account-settings";

export const meta: Route.MetaFunction = () => [metaTitle("Account Settings")];

export async function clientAction({ request }: Route.ClientActionArgs) {
  const formData = await request.formData();
  const intent = formData.get("intent")?.toString();

  switch (intent) {
    case "update_profile":
      return updateProfile(formData);
    default: {
      throw new Error("Unexpected intent");
    }
  }
}

async function updateProfile(formData: FormData) {
  const profileData = {
    username: formData.get("username")!.toString(),
    first_name: formData.get("first_name")?.toString() || "",
    last_name: formData.get("last_name")?.toString() || ""
  };

  const { error: errors, data } = await apiClient.PATCH(
    "/api/auth/update-profile/",
    {
      headers: await getCsrfTokenHeader(),
      body: profileData
    }
  );

  if (errors) return { success: false, errors };

  queryClient.removeQueries(userQueries.authedUser);
  queryClient.removeQueries(userQueries.checkUserExistence);

  toast.success("Profile updated successfully");

  return {
    success: true,
    message: data.message,
    values: data.user
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
          <section id="update-profile" className="flex gap-1 scroll-mt-20">
            <div className="w-16 hidden md:flex flex-col items-center">
              <div className="flex rounded-full size-10 flex-none items-center justify-center p-1 border-2 border-grey/50">
                <UserIcon size={15} className="flex-none text-grey" />
              </div>
              <div className="h-full border border-grey/50"></div>
            </div>
            <div className="w-full flex flex-col gap-5 pt-1 pb-8">
              <div className="mb-3">
                <h1 className="text-2xl font-bold mb-2">Profile Information</h1>
                <p className="text-muted-foreground">
                  Update your username, first name, and last name. Your username
                  must be unique.
                </p>
              </div>
              <UpdateProfile />
            </div>
          </section>

          <section id="update-password" className="flex gap-1 scroll-mt-20">
            <div className="w-16 hidden md:flex flex-col items-center">
              <div className="flex rounded-full size-10 flex-none items-center justify-center p-1 border-2 border-grey/50">
                <KeyIcon size={15} className="flex-none text-grey" />
              </div>
              {/* <div className="h-full border border-grey/50"></div> */}
            </div>
            <div className="w-full pt-1 pb-8 space-y-2">
              <h1 className="text-2xl font-bold">Change Password</h1>
              <p className="text-muted-foreground">
                Update your account password. Make sure to use a strong password
              </p>
              <div>
                <Link
                  to="/settings/account/change-password"
                  className="hover:underline transition text-sm py-2 flex items-center gap-0.5 font-medium"
                >
                  <span>Change your password here</span>
                  <ChevronRight size={15} />
                </Link>
              </div>
            </div>
          </section>
        </div>
      </div>
    </section>
  );
}

function UpdateProfile() {
  const navigation = useNavigation();
  const fetcher = useFetcher<typeof clientAction>();
  const { data: userData } = useQuery(userQueries.authedUser);

  const isPending =
    navigation.state === "loading" || navigation.state === "submitting";
  const errors = getFormErrorsFromResponseData(fetcher.data?.errors);

  const user = userData?.data?.user;

  return (
    <fetcher.Form method="POST" className="space-y-6">
      {errors.non_field_errors && (
        <Alert variant="destructive">
          <AlertCircle className="h-4 w-4" />
          <AlertTitle>Error</AlertTitle>
          <AlertDescription>{errors.non_field_errors}</AlertDescription>
        </Alert>
      )}

      <div className="space-y-4">
        <FieldSet
          name="username"
          required
          errors={errors.username}
          className="space-y-2"
        >
          <FieldSetLabel className="block">Username</FieldSetLabel>
          <FieldSetInput
            placeholder="Enter your username"
            defaultValue={user?.username || ""}
          />
        </FieldSet>

        <FieldSet
          name="first_name"
          errors={errors.first_name}
          className="space-y-2"
        >
          <FieldSetLabel className="block">First Name</FieldSetLabel>
          <FieldSetInput
            placeholder="Enter your first name"
            defaultValue={user?.first_name || ""}
          />
        </FieldSet>

        <FieldSet
          name="last_name"
          errors={errors.last_name}
          className="space-y-2"
        >
          <FieldSetLabel className="block">Last Name</FieldSetLabel>
          <FieldSetInput
            placeholder="Enter your last name"
            defaultValue={user?.last_name || ""}
          />
        </FieldSet>
      </div>

      <div className="flex gap-4">
        <SubmitButton
          isPending={isPending}
          name="intent"
          value="update_profile"
          variant="secondary"
          size="sm"
        >
          {isPending ? (
            <>
              <span>Updating Profile...</span>
              <LoaderIcon className="animate-spin" size={15} />
            </>
          ) : (
            "Update Profile"
          )}
        </SubmitButton>
      </div>
    </fetcher.Form>
  );
}
