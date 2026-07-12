import { useQuery } from "@tanstack/react-query";
import { LoaderIcon, MailCheckIcon } from "lucide-react";
import React from "react";
import { Form, href, redirect, useNavigation } from "react-router";
import { toast } from "sonner";
import { type RequestInput, apiClient } from "~/api/client";
import { ThemedLogo } from "~/components/logo";
import { Alert, AlertDescription, AlertTitle } from "~/components/ui/alert";
import { SubmitButton } from "~/components/ui/button";
import { Card, CardContent, CardTitle } from "~/components/ui/card";
import {
  FieldSet,
  FieldSetInput,
  FieldSetLabel,
  FieldSetPasswordToggleInput
} from "~/components/ui/fieldset";
import { WorkspaceRoleBadge } from "~/components/workspace-role-badge";
import { userQueries, workspaceQueries } from "~/lib/queries";
import { getQueryClient } from "~/lib/query-client";
import {
  type ErrorResponseFromAPI,
  getCsrfTokenHeader,
  getFormErrorsFromResponseData,
  metaTitle
} from "~/lib/utils";
import type { Route } from "./+types/workspace-invitation";

export function meta() {
  return [
    metaTitle("Workspace Invitation")
  ] satisfies ReturnType<Route.MetaFunction>;
}

export async function clientLoader({
  params,
  request
}: Route.ClientLoaderArgs) {
  const queryClient = getQueryClient();

  const [invitationLink, authedUser] = await Promise.all([
    queryClient.fetchQuery(workspaceQueries.invitationLink(params.token)),
    queryClient.ensureQueryData(userQueries.authedUser)
  ]);

  if (!authedUser && invitationLink.has_existing_account) {
    let redirectPathName = href("/login");
    const url = new URL(request.url);
    if (url.pathname !== "/" && url.pathname !== "/login") {
      const params = new URLSearchParams([["redirect_to", url.pathname]]);

      redirectPathName = [href("/login"), "?", params.toString()].join("");
    }
    throw redirect(redirectPathName);
  }

  return { invitationLink };
}

export default function RegisterPage({
  loaderData,
  params,
  actionData
}: Route.ComponentProps) {
  const { data: invitation } = useQuery({
    ...workspaceQueries.invitationLink(params.token),
    initialData: loaderData.invitationLink
  });

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
    <main className="h-[100vh] flex md:flex-col flex-col  justify-center items-center">
      <ThemedLogo />

      <div className="flex flex-col items-center">
        <h1 className="md:text-3xl text-4xl font-semibold">
          You've been invited !
        </h1>
        <p className="text-sm text-grey">
          Create an account to accept the invitation
        </p>
      </div>

      <Form
        method="POST"
        ref={formRef}
        className="p-7 my-2 lg:px-32 md:px-20 md:w-2/3 xl:md:w-1/2  flex flex-col w-full gap-4"
      >
        <input type="hidden" name="intent" value="register" />
        <Alert className="p-4" variant="info">
          <MailCheckIcon className="size-4 flex-none" />
          <AlertTitle>Welcome</AlertTitle>
          <AlertDescription className="flex items-center gap-2 text-card-foreground">
            <p>
              You've been invited to join <span className="text-grey">`</span>
              <span className="text-link">{invitation.workspace.name}</span>
              <span className="text-grey">`</span> workspace as{" "}
              {invitation.role_name === "Owner" ||
              invitation.role_name === "Admin"
                ? "an"
                : "a"}
              &nbsp;
              <WorkspaceRoleBadge
                role={invitation.role_name}
                className="inline-flex text-xs [&_svg]:size-3.5"
              />
            </p>
          </AlertDescription>
        </Alert>

        <FieldSet className="my-2 flex flex-col gap-1">
          <FieldSetLabel className="">Username</FieldSetLabel>
          <FieldSetInput
            value={invitation.username}
            type="text"
            readOnly
            disabled
            className="!opacity-100"
          />
        </FieldSet>

        <FieldSet
          errors={errors.first_name}
          name="first_name"
          className="my-2 flex flex-col gap-1"
        >
          <FieldSetLabel>
            Display Name <span className="text-grey">(optional)</span>
          </FieldSetLabel>
          <FieldSetInput
            placeholder="ex: John Doe"
            autoFocus
            defaultValue={actionData?.userData?.first_name}
            type="text"
          />
        </FieldSet>

        <div className="flex flex-col gap-1 text-muted-foreground">
          <h3 className="font-medium text-sm">Hints for a good password</h3>
          <ul className="list-disc list-inside text-xs">
            <li>Use a mix of uppercase, lowercase, numbers, and symbols.</li>
            <li>Avoid using common passwords.</li>
            <li>Make it long and hard to guess.</li>
          </ul>
        </div>

        <FieldSet
          errors={errors.password}
          name="password"
          required
          className="flex flex-col gap-1"
        >
          <FieldSetLabel>Password</FieldSetLabel>
          <FieldSetPasswordToggleInput
            defaultValue={actionData?.userData?.password}
          />
        </FieldSet>

        <FieldSet
          required
          errors={errors.password_confirmation}
          name="password_confirmation"
          className="flex flex-col gap-1"
        >
          <FieldSetLabel>Confirm your password</FieldSetLabel>
          <FieldSetPasswordToggleInput
            defaultValue={actionData?.userData?.password_confirmation}
          />
        </FieldSet>

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
            "Create your account"
          )}
        </SubmitButton>
      </Form>
    </main>
  );
}

export async function clientAction({
  request,
  params
}: Route.ClientActionArgs) {
  const formData = await request.formData();

  const intent = formData.get("intent")?.toString();
  switch (intent) {
    case "register":
      return registerToWorkspace(formData, params);
    case "accept-invitation":
      return acceptInvitationToWorkspace(formData, params);
    default: {
      throw new Error(`Unexpected intent \`${intent}\``);
    }
  }
}

async function registerToWorkspace(
  formData: FormData,
  params: Route.ClientActionArgs["params"]
) {
  const queryClient = getQueryClient();

  const firstName = formData.get("first_name")?.toString();

  const userData = {
    password: formData.get("password")?.toString() ?? "",
    password_confirmation:
      formData.get("password_confirmation")?.toString() ?? "",
    first_name: firstName?.trim() ? firstName : undefined
  } satisfies RequestInput<"post", "/api/workspace/register/{token}/"> & {
    password_confirmation: string;
  };

  if (userData.password !== userData.password_confirmation) {
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
      userData
    };
  }

  const { error: errors } = await apiClient.POST(
    "/api/workspace/register/{token}/",
    {
      headers: {
        ...(await getCsrfTokenHeader())
      },
      params: {
        path: params
      },
      body: userData
    }
  );
  if (errors) {
    return {
      errors,
      userData: userData
    };
  }

  queryClient.removeQueries(userQueries.authedUser);
  queryClient.removeQueries(workspaceQueries.invitationLink(params.token));

  toast.success("Welcome to ZaneOps", {
    description: "Your account have been created succesfully",
    closeButton: true
  });

  throw redirect(href("/"));
}

async function acceptInvitationToWorkspace(
  formData: FormData,
  params: Route.ClientActionArgs["params"]
) {}
