import { useQuery } from "@tanstack/react-query";
import {
  AlertCircleIcon,
  HeartHandshake,
  LoaderIcon,
  MailCheckIcon,
  UserIcon
} from "lucide-react";
import React from "react";
import {
  Form,
  href,
  redirect,
  useActionData,
  useLoaderData,
  useNavigation
} from "react-router";
import { toast } from "sonner";
import { type RequestInput, apiClient } from "~/api/client";
import type { WorkspaceInvitationLink } from "~/api/types";
import { Header } from "~/components/header/header";
import { UserHeaderDropdown } from "~/components/header/user-header-dropdown";
import { ThemedLogo } from "~/components/logo";
import { Alert, AlertDescription, AlertTitle } from "~/components/ui/alert";
import { SubmitButton } from "~/components/ui/button";
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
  cn,
  getCsrfTokenHeader,
  getFormErrorsFromResponseData,
  getUserDisplayName,
  metaTitle,
  stringToColor
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
    if (
      url.pathname !== href("/workspace") &&
      url.pathname !== href("/login")
    ) {
      const params = new URLSearchParams([["redirect_to", url.pathname]]);

      redirectPathName = [href("/login"), "?", params.toString()].join("");
    }
    throw redirect(redirectPathName);
  }

  return { invitationLink, authedUser };
}

export default function RegisterPage({
  loaderData,
  params
}: Route.ComponentProps) {
  const { data: invitation } = useQuery({
    ...workspaceQueries.invitationLink(params.token),
    initialData: loaderData.invitationLink
  });

  return (
    <>
      {loaderData.authedUser && (
        <Header
          rigthSlot={<UserHeaderDropdown user={loaderData.authedUser} />}
        />
      )}

      <main
        className={cn(
          "grow container p-6 relative overflow-y-clip",
          " flex md:flex-col flex-col  justify-center items-center",
          loaderData.authedUser
            ? !import.meta.env.PROD
              ? "my-14"
              : "my-7"
            : "h-[100vh]"
        )}
      >
        <ThemedLogo />
        <div className="flex flex-col items-center">
          <h1 className="md:text-3xl text-4xl font-semibold">
            You've been invited!
          </h1>
          <p className="text-sm text-grey">
            {invitation.has_existing_account
              ? "Review your invitation"
              : "Create an account to accept the invitation"}
          </p>
        </div>
        {invitation.has_existing_account ? (
          <ReviewInvitationForm invitation={invitation} />
        ) : (
          <RegisterForm invitation={invitation} />
        )}
      </main>
    </>
  );
}

type InvitationFormProps = {
  invitation: WorkspaceInvitationLink;
};

type WorkspaceJoinDecision = RequestInput<
  "post",
  "/api/workspace/invitations/{token}/review/"
>["decision"];

function ReviewInvitationForm({ invitation }: InvitationFormProps) {
  const actionData = useActionData<Route.ComponentProps["actionData"]>();
  const loaderData = useLoaderData<Route.ComponentProps["loaderData"]>();
  const navigation = useNavigation();

  const errors = getFormErrorsFromResponseData(actionData?.errors);

  const isPending =
    navigation.state === "loading" || navigation.state === "submitting";

  if (!loaderData.authedUser) return null;

  const workspaceColor = stringToColor(invitation.workspace.name);
  const [decision, setDecision] = React.useState<WorkspaceJoinDecision | null>(
    null
  );

  return (
    <div className="p-7 my-2 lg:px-32 md:px-20 md:w-2/3 xl:md:w-1/2  flex flex-col w-full gap-6">
      {errors.non_field_errors && (
        <Alert variant="destructive">
          <AlertCircleIcon className="h-4 w-4" />
          <AlertTitle>Error</AlertTitle>
          <AlertDescription>{errors.non_field_errors}</AlertDescription>
        </Alert>
      )}

      <div className="flex items-center justify-center gap-8">
        <div
          style={
            {
              "--color-light": workspaceColor.light,
              "--color-dark": workspaceColor.dark
            } as React.CSSProperties
          }
          className={cn(
            "size-16 text-2xl flex-none rounded-md flex items-center justify-center",
            "text-[var(--color-light)] dark:text-[var(--color-dark)]",
            "bg-[var(--color-light)]/10 dark:bg-[var(--color-dark)]/10",
            "border  border-[var(--color-light)]/10 dark:border-[var(--color-dark)]/10"
          )}
        >
          <span>{invitation.workspace.name.charAt(0).toUpperCase()}</span>
        </div>

        <HeartHandshake className="size-6 flex-none" />

        <div
          className={cn(
            "size-16 text-2xl flex-none rounded-md flex items-center justify-center",
            "text-card-foreground bg-grey/10 border border-grey/20"
          )}
        >
          <UserIcon className="size-4" />
        </div>
      </div>

      <p className="text-lg">
        <span className="text-link">
          {getUserDisplayName(invitation.invited_by)}
        </span>{" "}
        has invited you to join{" "}
        <span className="text-link">{invitation.workspace.name}</span> workspace
        as&nbsp;
        {invitation.role_name === "Owner" || invitation.role_name === "Admin"
          ? "an"
          : "a"}
        &nbsp;
        <WorkspaceRoleBadge
          role={invitation.role_name}
          className="inline-flex text-xs [&_svg]:size-3.5"
        />
      </p>

      <div className="flex items-center gap-2 justify-center">
        <Form
          method="POST"
          onSubmit={(ev) => {
            const fd = new FormData(ev.currentTarget);
            setDecision(
              (fd.get("decision")?.toString() as WorkspaceJoinDecision) ?? null
            );
          }}
        >
          <input type="hidden" name="intent" value="review-invitation" />
          <input type="hidden" name="decision" value="ACCEPT" />
          <SubmitButton isPending={isPending} variant="default">
            {decision === "ACCEPT" ? (
              <>
                <LoaderIcon className="animate-spin" size={15} />
                <span>Joining workspace...</span>
              </>
            ) : (
              "Accept invitation"
            )}
          </SubmitButton>
        </Form>

        <Form
          method="POST"
          onSubmit={(ev) => {
            const fd = new FormData(ev.currentTarget);
            setDecision(
              (fd.get("decision")?.toString() as WorkspaceJoinDecision) ?? null
            );
          }}
        >
          <input type="hidden" name="intent" value="review-invitation" />
          <input type="hidden" name="decision" value="DECLINE" />
          <SubmitButton isPending={isPending} variant="outline">
            {decision === "DECLINE" ? (
              <>
                <LoaderIcon className="animate-spin" size={15} />
                <span>Submiting...</span>
              </>
            ) : (
              "Decline"
            )}
          </SubmitButton>
        </Form>
      </div>
    </div>
  );
}

function RegisterForm({ invitation }: InvitationFormProps) {
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
      ) as HTMLInputElement;
      field?.focus();
    }
  }, [navigation.state, actionData]);

  return (
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

      {errors.non_field_errors && (
        <Alert variant="destructive">
          <AlertCircleIcon className="h-4 w-4" />
          <AlertTitle>Error</AlertTitle>
          <AlertDescription>{errors.non_field_errors}</AlertDescription>
        </Alert>
      )}

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
        <FieldSetInput placeholder="ex: John Doe" autoFocus type="text" />
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
        <FieldSetPasswordToggleInput />
      </FieldSet>

      <FieldSet
        required
        errors={errors.password_confirmation}
        name="password_confirmation"
        className="flex flex-col gap-1"
      >
        <FieldSetLabel>Confirm your password</FieldSetLabel>
        <FieldSetPasswordToggleInput />
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
    case "review-invitation":
      return reviewWorkspaceInvitation(formData, params);
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

  throw redirect(href("/workspace"));
}

async function reviewWorkspaceInvitation(
  formData: FormData,
  params: Route.ClientActionArgs["params"]
) {
  const queryClient = getQueryClient();
  const link = await queryClient.fetchQuery(
    workspaceQueries.invitationLink(params.token)
  );

  const userData = {
    decision: (formData.get("decision")?.toString() ??
      "") as WorkspaceJoinDecision
  } satisfies RequestInput<
    "post",
    "/api/workspace/invitations/{token}/review/"
  >;

  const { error: errors } = await apiClient.POST(
    "/api/workspace/invitations/{token}/review/",
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

  queryClient.invalidateQueries(userQueries.authedUser);
  queryClient.removeQueries(workspaceQueries.invitationLink(params.token));

  toast.info(`Success`, {
    description:
      userData.decision === "ACCEPT"
        ? `Welcome to ${link.workspace.name}`
        : "The workspace invitation has been declined",
    closeButton: true
  });

  throw redirect(href("/workspace"));
}
