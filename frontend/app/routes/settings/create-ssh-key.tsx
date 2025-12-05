import {
  AlertCircleIcon,
  ChevronLeftIcon,
  ChevronRightIcon,
  InfoIcon,
  LoaderIcon
} from "lucide-react";
import * as React from "react";
import { Form, Link, href, redirect, useNavigation } from "react-router";
import { type RequestInput, apiClient } from "~/api/client";
import { CopyButton } from "~/components/copy-button";
import { Alert, AlertDescription, AlertTitle } from "~/components/ui/alert";
import { Button, SubmitButton } from "~/components/ui/button";
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
import { getCsrfTokenHeader, metaTitle } from "~/utils";
import type { Route } from "./+types/create-ssh-key";

export function meta() {
  return [metaTitle("Create SSH Key")] satisfies ReturnType<Route.MetaFunction>;
}

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

  if (actionData?.data) {
    const commands = [
      "mkdir -p $HOME/.ssh",
      "touch $HOME/.ssh/authorized_keys",
      "chmod 600 $HOME/.ssh/authorized_keys",
      'echo "" >> $HOME/.ssh/authorized_keys',
      `echo '${actionData.data.public_key}' >> $HOME/.ssh/authorized_keys`
    ];
    return (
      <div className="flex flex-col gap-4">
        <h3>
          To allow login with this SSH key, please add this public key to your
          ssh folder using these commands:
        </h3>
        <div className="relative">
          <TooltipProvider>
            <Tooltip delayDuration={0}>
              <TooltipTrigger asChild>
                <CopyButton
                  value={commands.join("\n")}
                  label="Copy commands"
                  className="!opacity-100 absolute top-2 right-2 font-sans"
                />
              </TooltipTrigger>
              <TooltipContent>Copy commands</TooltipContent>
            </Tooltip>
          </TooltipProvider>

          <pre className="text-sm font-mono rounded-md bg-muted/25 dark:bg-neutral-950 p-4 overflow-x-auto px-4">
            {commands.map((cmd, index) => (
              <div key={index}>
                <span className="text-primary select-none">$</span>&nbsp;
                <span>{cmd}</span>
                &nbsp;&nbsp;
              </div>
            ))}
          </pre>
        </div>
        <div className="flex items-center gap-4 justify-end">
          <Button asChild variant="outline">
            <Link
              to={href("/settings/ssh-keys")}
              className="items-center gap-2"
            >
              <ChevronLeftIcon className="size-4 flex-none" />
              Back to ssh keys
            </Link>
          </Button>
          <Separator className="w-px h-4 rounded-md bg-grey" />
          <Button asChild>
            <Link
              to={{
                pathname: href("/settings/server-console"),
                search: `?ssh_key_slug=${actionData.data.slug}`
              }}
              className="items-center gap-2"
            >
              Use this SSH Key
              <ChevronRightIcon className="size-4 flex-none" />
            </Link>
          </Button>
        </div>
      </div>
    );
  }

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
        required
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
        <FieldSetInput autoComplete="off" autoFocus placeholder="ex: root" />
      </FieldSet>
      <FieldSet
        errors={errors.slug}
        name="slug"
        required
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

  const { error: errors, data } = await apiClient.POST("/api/shell/ssh-keys/", {
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
  return {
    data
  };
}
