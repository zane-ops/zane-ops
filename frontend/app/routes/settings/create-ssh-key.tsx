import { AlertCircleIcon, InfoIcon, LoaderIcon } from "lucide-react";
import * as React from "react";
import { Form, href, redirect, useNavigation } from "react-router";
import { type RequestInput, apiClient } from "~/api/client";
import { Alert, AlertDescription, AlertTitle } from "~/components/ui/alert";
import { SubmitButton } from "~/components/ui/button";
import {
  FieldSet,
  FieldSetInput,
  FieldSetLabel
} from "~/components/ui/fieldset";
import { Separator } from "~/components/ui/separator";
import {
  Tooltip,
  TooltipContent,
  TooltipProvider,
  TooltipTrigger
} from "~/components/ui/tooltip";
import { sshKeysQueries } from "~/lib/queries";
import { getFormErrorsFromResponseData } from "~/lib/utils";
import { queryClient } from "~/root";
import { getCsrfTokenHeader } from "~/utils";
import type { Route } from "./+types/create-ssh-key";

export default function CreateSSHKeyPage({ actionData }: Route.ComponentProps) {
  return (
    <div className="flex flex-col gap-4">
      <div className="flex items-center gap-4">
        <h2 className="text-2xl">Add new SSH key</h2>
      </div>
      <Separator />
      <CreateSSHKeyForm actionData={actionData} />
    </div>
  );
}

function CreateSSHKeyForm({
  actionData
}: Pick<Route.ComponentProps, "actionData">) {
  const navigation = useNavigation();
  const errors = getFormErrorsFromResponseData(actionData?.errors);
  const formRef = React.useRef<React.ComponentRef<"form">>(null);
  const isPending = navigation.state !== "idle";

  React.useEffect(() => {
    const key = Object.keys(errors ?? {})[0];
    const field = formRef.current?.elements.namedItem(key) as HTMLInputElement;
    field?.focus();
  }, [errors]);

  return (
    <Form
      ref={formRef}
      className="flex flex-col gap-4 items-start"
      method="POST"
    >
      {errors.non_field_errors && (
        <Alert variant="destructive">
          <AlertCircleIcon className="h-4 w-4" />
          <AlertTitle>Error</AlertTitle>
          <AlertDescription>{errors.non_field_errors}</AlertDescription>
        </Alert>
      )}

      <FieldSet
        errors={errors.user}
        name="user"
        className="w-4/5 flex flex-col gap-1"
      >
        <FieldSetLabel className="flex items-center gap-0.5">
          Username
          <TooltipProvider>
            <Tooltip delayDuration={0}>
              <TooltipTrigger>
                <InfoIcon size={15} className="text-grey" />
              </TooltipTrigger>
              <TooltipContent className="max-w-64 dark:bg-card">
                User to login as to your terminal
              </TooltipContent>
            </Tooltip>
          </TooltipProvider>
        </FieldSetLabel>
        <FieldSetInput autoFocus placeholder="ex: root" />
      </FieldSet>
      <FieldSet
        errors={errors.slug}
        name="slug"
        className="w-4/5 flex flex-col gap-1"
      >
        <FieldSetLabel>Slug</FieldSetLabel>
        <FieldSetInput placeholder="ex: my-ssh-key" />
      </FieldSet>
      <SubmitButton isPending={isPending}>
        {isPending ? (
          <>
            Adding Key... <LoaderIcon size={15} className="animate-spin" />
          </>
        ) : (
          <>Add SSH Key</>
        )}
      </SubmitButton>
    </Form>
  );
}

export async function clientAction({ request }: Route.ClientActionArgs) {
  const formData = await request.formData();

  const userData = {
    slug: formData.get("slug")?.toString() ?? "",
    user: formData.get("user")?.toString() ?? ""
  } satisfies RequestInput<"post", "/api/shell/ssh-keys/">;

  const { error: errors } = await apiClient.POST("/api/shell/ssh-keys/", {
    headers: {
      ...(await getCsrfTokenHeader())
    },
    body: userData
  });

  if (errors) {
    return {
      errors,
      userData
    };
  }
  await queryClient.invalidateQueries(sshKeysQueries.list);
  throw redirect(href("/settings/ssh-keys"));
}
