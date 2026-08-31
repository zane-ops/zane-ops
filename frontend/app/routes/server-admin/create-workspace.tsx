import { AlertCircleIcon, LoaderIcon } from "lucide-react";
import * as React from "react";
import { Form, href, redirect, useNavigation } from "react-router";
import { toast } from "sonner";
import { type RequestInput, apiClient } from "~/api/client";
import { Alert, AlertDescription, AlertTitle } from "~/components/ui/alert";
import { SubmitButton } from "~/components/ui/button";
import {
  FieldSet,
  FieldSetInput,
  FieldSetLabel
} from "~/components/ui/fieldset";
import { Separator } from "~/components/ui/separator";
import { ensureLicensedFeatureAvailability } from "~/lib/licensed-feature";
import { adminWorkspaceQueries, buildRegistryQueries } from "~/lib/queries";
import { getQueryClient } from "~/lib/query-client";
import {
  getCsrfTokenHeader,
  getFormErrorsFromResponseData,
  metaTitle
} from "~/lib/utils";
import type { Route } from "./+types/create-workspace";

export function meta() {
  return [metaTitle("New Workspace")] satisfies ReturnType<Route.MetaFunction>;
}

export async function clientLoader({}: Route.ClientLoaderArgs) {
  const queryClient = getQueryClient();
  await ensureLicensedFeatureAvailability(queryClient, "workspace:create");
  return;
}

export default function CreateWorkspacePage({
  actionData
}: Route.ComponentProps) {
  const navigation = useNavigation();
  const isPending =
    navigation.state === "loading" || navigation.state === "submitting";
  const errors = getFormErrorsFromResponseData(actionData?.errors);
  const formRef = React.useRef<React.ComponentRef<"form">>(null);

  React.useEffect(() => {
    const key = Object.keys(errors ?? {})[0];
    const field = formRef.current?.elements.namedItem(
      key
    ) as HTMLInputElement | null;
    field?.focus();
  }, [errors]);

  return (
    <div className="flex flex-col gap-4">
      <div className="flex items-center gap-4">
        <h2 className="text-2xl">Create new workspace</h2>
      </div>
      <Separator />

      <Form
        method="POST"
        ref={formRef}
        className="flex flex-col gap-4 items-start"
      >
        {errors.non_field_errors && (
          <Alert variant="destructive" className="w-full md:w-4/5">
            <AlertCircleIcon className="h-4 w-4" />
            <AlertTitle>Error</AlertTitle>
            <AlertDescription>{errors.non_field_errors}</AlertDescription>
          </Alert>
        )}

        <FieldSet
          errors={errors.name}
          name="name"
          required
          className="w-full md:w-4/5 flex flex-col gap-1"
        >
          <FieldSetLabel className="flex items-center gap-0.5">
            Name
          </FieldSetLabel>

          <FieldSetInput autoFocus placeholder="ex: ZaneOps" />
        </FieldSet>

        <SubmitButton isPending={isPending} className="mt-4">
          {isPending ? (
            <>
              <LoaderIcon className="animate-spin" size={15} />
              <span>Creating workspace...</span>
            </>
          ) : (
            "Create workspace"
          )}
        </SubmitButton>
      </Form>
    </div>
  );
}

export async function clientAction({ request }: Route.ClientActionArgs) {
  const queryClient = getQueryClient();
  const formData = await request.formData();

  const userData = {
    name: formData.get("name")?.toString() ?? ""
  } satisfies RequestInput<"post", "/api/workspaces/create/">;

  const { error: errors, data } = await apiClient.POST(
    "/api/workspaces/create/",
    {
      headers: {
        ...(await getCsrfTokenHeader())
      },
      body: userData
    }
  );

  if (errors) {
    return {
      errors,
      userData
    };
  }

  toast.success("Success", {
    dismissible: true,
    closeButton: true,
    description: (
      <>
        Workspace <strong className="font-medium">{data.name}</strong> created
        succesfully
      </>
    )
  });
  await queryClient.invalidateQueries({
    queryKey: adminWorkspaceQueries.list({}).queryKey.slice(0, 1)
  });
  throw redirect(href("/admin/workspaces"));
}
